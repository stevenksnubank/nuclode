"""Native REPL loop engine — root LM writes Python, executes it, iterates.

This is the core of the nuclode engine. It implements the RLM-inspired loop:
1. Root LM (Opus + thinking) receives context and writes Python code
2. Code executes in a sandboxed namespace with custom tools available
3. Results feed back to the root LM
4. Root LM writes more code based on results
5. Loop continues until FINAL() is called or max iterations reached
"""

from __future__ import annotations

import io
import logging
import os
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from typing import Any, Callable

from knowledge.engine.config import EngineConfig
from knowledge.engine.cost_tracker import CostTracker, GuardrailStatus
from knowledge.engine.gate import GateDecision, route_task

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EngineResult:
    """Result from an engine run.

    Attributes:
        status: "completed", "budget_exceeded", "max_iterations", or "error".
        iterations: Number of REPL loop iterations executed.
        gate_decision: The routing decision that determined the execution path.
        cost_summary: Final cost summary from the run.
        output: Final output from the REPL loop (from FINAL() call).
        error: Error message if status is "error".
    """

    status: str
    iterations: int
    gate_decision: GateDecision
    cost_summary: dict
    output: Any = None
    error: str | None = None


class _FinalSignal(Exception):
    """Raised by FINAL() to break out of the REPL loop."""

    def __init__(self, result: Any = None) -> None:
        self.result = result
        super().__init__("FINAL() called")


class EngineRunner:
    """Native REPL loop engine runner.

    Implements the core loop where the root LM writes Python code that
    gets executed with access to sub-LM calls and custom tools.
    """

    def __init__(self, config: EngineConfig) -> None:
        self._config = config
        self._cost_tracker = CostTracker(config.guardrails)
        self._client = self._create_client()

    @staticmethod
    def _create_client() -> Any:
        """Create an Anthropic client with retry and timeout settings for LiteLLM proxy."""
        try:
            import anthropic
            import httpx
        except ImportError as exc:
            raise RuntimeError(
                "anthropic package required. Install with: pip install anthropic"
            ) from exc

        return anthropic.Anthropic(
            api_key=os.environ.get("LITELLM_API_KEY", os.environ.get("ANTHROPIC_API_KEY", "")),
            base_url=os.environ.get("LITELLM_BASE_URL", "https://ist-prod-litellm.nullmplatform.com"),
            max_retries=5,
            timeout=httpx.Timeout(300.0, connect=10.0),
        )

    def run(
        self,
        context: str | dict,
        custom_tools: dict[str, dict] | None = None,
        system_prompt: str = "",
        structure_summary: dict | None = None,
    ) -> EngineResult:
        """Run the engine on the given context.

        Decides between direct LM call and REPL loop based on the
        two-stage decision gate.

        Args:
            context: Input context (string or dict).
            custom_tools: Recipe-specific tools for the REPL namespace.
            system_prompt: System prompt for the root LM.
            structure_summary: Structural metadata for the decision gate.

        Returns:
            EngineResult with status, iterations, and output.
        """
        gate = route_task(
            context,
            structure_summary=structure_summary,
            threshold=self._config.threshold_tokens,
        )

        logger.info(
            "Gate decision: %s (tokens=%d, stage=%s) — %s",
            "fan-out" if gate.fan_out else "direct",
            gate.token_count,
            gate.stage,
            gate.reason,
        )

        # When custom tools are provided, always use the REPL loop —
        # the direct path can't execute code, so tools would be unused.
        if custom_tools:
            logger.info("Custom tools provided — overriding gate to REPL loop")
            return self._run_repl_loop(context, custom_tools, system_prompt, gate)

        if not gate.fan_out:
            return self._run_direct(context, system_prompt, gate)

        return self._run_repl_loop(context, custom_tools or {}, system_prompt, gate)

    def _run_direct(
        self,
        context: str | dict,
        system_prompt: str,
        gate: GateDecision,
    ) -> EngineResult:
        """Below-threshold path: single Opus + thinking call.

        Args:
            context: Input context.
            system_prompt: System prompt.
            gate: The gate decision that led here.

        Returns:
            EngineResult from the direct call.
        """
        logger.info("Direct path: calling root LM (%s)", self._config.root_model)
        try:
            result = self._call_root_lm(system_prompt, str(context))
            return EngineResult(
                status="completed",
                iterations=1,
                gate_decision=gate,
                cost_summary=self._cost_tracker.summary().__dict__,
                output=result,
            )
        except Exception as exc:
            logger.error("Direct LM call failed: %s", exc, exc_info=True)
            return EngineResult(
                status="error",
                iterations=1,
                gate_decision=gate,
                cost_summary=self._cost_tracker.summary().__dict__,
                error=str(exc),
            )

    def _run_repl_loop(
        self,
        context: str | dict,
        custom_tools: dict[str, dict],
        system_prompt: str,
        gate: GateDecision,
    ) -> EngineResult:
        """REPL loop path: root LM writes Python, executes, iterates.

        Args:
            context: Input context.
            custom_tools: Recipe tools available in the REPL namespace.
            system_prompt: System prompt for the root LM.
            gate: The gate decision.

        Returns:
            EngineResult from the loop.
        """
        # Build the execution namespace with tools
        namespace = self._build_namespace(custom_tools)
        # Make context available as a variable in the REPL namespace
        namespace["context"] = context
        # Shared results store — persists across iterations so the LM can
        # accumulate data without needing to re-derive it from stdout.
        namespace["_results"] = {}
        tool_names = [k for k in namespace if k not in ("print", "context", "_results")]
        logger.info(
            "REPL loop: max_iterations=%d, tools=%s",
            self._config.root_max_iterations,
            tool_names,
        )

        conversation: list[dict[str, str]] = []
        iterations = 0
        final_output = None

        for iteration in range(self._config.root_max_iterations):
            iterations = iteration + 1

            # Check guardrails
            status = self._cost_tracker.check_guardrails()
            if status == GuardrailStatus.EXCEEDED:
                logger.warning("Budget exceeded at iteration %d", iterations)
                return EngineResult(
                    status="budget_exceeded",
                    iterations=iterations,
                    gate_decision=gate,
                    cost_summary=self._cost_tracker.summary().__dict__,
                )
            if status == GuardrailStatus.WARNING:
                logger.warning(
                    "Approaching budget limit: $%.2f",
                    self._cost_tracker.estimated_cost_usd,
                )

            # Build messages for root LM
            if iteration == 0:
                user_content = (
                    f"Context:\n{context}\n\n"
                    "Write Python code to analyze this context using the available tools. "
                    "All variables you create persist across iterations in the namespace. "
                    "Use print() only for brief status messages. "
                    "Call FINAL() when complete."
                )
            else:
                # Subsequent iterations: send namespace snapshot + stdout.
                # All data stays in memory — Opus writes code to access it.
                raw_output = conversation[-1].get("output", "No output from previous code.")

                # Symbolic namespace snapshot: lossless view of all user variables
                snapshot = _snapshot_namespace(namespace, _BUILTIN_NAMES)

                # Stdout is just status — cap it modestly
                max_stdout = 2000
                if len(raw_output) > max_stdout:
                    raw_output = raw_output[:max_stdout] + "\n[...stdout truncated]"

                user_content = (
                    f"Execution result:\n{raw_output}\n\n"
                    f"Namespace state (all variables accessible in your code):\n{snapshot}\n\n"
                    "Continue from where you left off. All data persists in the namespace — "
                    "access it directly in code. Call FINAL() when complete."
                )

            # Call root LM
            logger.info(
                "[iter %d/%d] Calling root LM (%s) — cost so far: $%.4f",
                iterations,
                self._config.root_max_iterations,
                self._config.root_model,
                self._cost_tracker.estimated_cost_usd,
            )
            try:
                code = self._call_root_lm(system_prompt, user_content)
            except Exception as exc:
                logger.error("Root LM call failed at iteration %d: %s", iterations, exc)
                return EngineResult(
                    status="error",
                    iterations=iterations,
                    gate_decision=gate,
                    cost_summary=self._cost_tracker.summary().__dict__,
                    error=f"Root LM call failed: {exc}",
                )

            # Execute the code in the sandboxed namespace
            code_preview = code[:120].replace("\n", "\\n")
            logger.info("[iter %d/%d] Executing code: %s...", iterations, self._config.root_max_iterations, code_preview)
            try:
                output = self._execute_code(code, namespace)
                output_preview = output[:200].replace("\n", "\\n") if output else "(no output)"
                logger.info("[iter %d/%d] Execution output: %s", iterations, self._config.root_max_iterations, output_preview)
                conversation.append({"code": code, "output": output})
            except _FinalSignal as final:
                final_output = final.result
                logger.info(
                    "[iter %d/%d] FINAL() called — completing (total cost: $%.4f)",
                    iterations,
                    self._config.root_max_iterations,
                    self._cost_tracker.estimated_cost_usd,
                )
                return EngineResult(
                    status="completed",
                    iterations=iterations,
                    gate_decision=gate,
                    cost_summary=self._cost_tracker.summary().__dict__,
                    output=final_output,
                )
            except Exception as exc:
                error_msg = f"Code execution error: {traceback.format_exc()}"
                conversation.append({"code": code, "output": error_msg})
                logger.warning("[iter %d/%d] Code execution error: %s", iterations, self._config.root_max_iterations, exc)

        return EngineResult(
            status="max_iterations",
            iterations=iterations,
            gate_decision=gate,
            cost_summary=self._cost_tracker.summary().__dict__,
        )

    def _build_namespace(self, custom_tools: dict[str, dict]) -> dict[str, Any]:
        """Build the execution namespace with tools available to the root LM's code.

        Includes: llm_query, llm_query_batched, FINAL, print,
        plus any recipe-specific custom tools.
        """
        final_result_holder: list[Any] = []

        def final_fn(result: Any = None) -> None:
            raise _FinalSignal(result)

        def llm_query(prompt: str, tier: str = "high") -> str:
            return self._call_sub_lm(prompt, tier)

        def llm_query_batched(prompts: list[str], tier: str = "high") -> list[str]:
            return self._call_sub_lm_batched(prompts, tier)

        namespace: dict[str, Any] = {
            "llm_query": llm_query,
            "llm_query_batched": llm_query_batched,
            "FINAL": final_fn,
            "print": print,
        }

        # Add recipe custom tools
        for tool_name, tool_def in custom_tools.items():
            if "tool" in tool_def and callable(tool_def["tool"]):
                namespace[tool_name] = tool_def["tool"]

        return namespace

    def _execute_code(self, code: str, namespace: dict[str, Any]) -> str:
        """Execute Python code in a sandboxed namespace.

        Captures stdout and returns it as the execution output.

        Args:
            code: Python code string to execute.
            namespace: Execution namespace with available tools.

        Returns:
            Captured stdout output.

        Raises:
            _FinalSignal: If FINAL() is called in the code.
        """
        # Strip markdown code fences if present (LLMs often wrap code in ```)
        code = _strip_code_fences(code)

        stdout_capture = io.StringIO()
        with redirect_stdout(stdout_capture):
            exec(code, namespace)  # noqa: S102 — intentional exec in sandboxed namespace

        return stdout_capture.getvalue()

    def _call_root_lm(self, system_prompt: str, user_content: str) -> str:
        """Call the root LM (Opus + extended thinking).

        Args:
            system_prompt: System prompt.
            user_content: User message content.

        Returns:
            LM response text.
        """
        # Build messages
        messages = [{"role": "user", "content": user_content}]

        # Call with extended thinking if configured
        kwargs: dict[str, Any] = {
            "model": self._config.root_model,
            "max_tokens": 16384,
            "system": system_prompt,
            "messages": messages,
        }

        if self._config.root_extended_thinking:
            kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": 10000,
            }

        response = self._client.messages.create(**kwargs)

        # Track costs
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        self._cost_tracker.record(self._config.root_model, input_tokens, output_tokens)
        logger.info(
            "Root LM response: %d in / %d out tokens (running cost: $%.4f)",
            input_tokens,
            output_tokens,
            self._cost_tracker.estimated_cost_usd,
        )

        # Extract text content
        for block in response.content:
            if block.type == "text":
                return block.text

        return ""

    def _call_sub_lm(self, prompt: str, tier: str = "high") -> str:
        """Call a sub-LM (Sonnet or Haiku based on tier).

        Args:
            prompt: The prompt to send.
            tier: "high" for Sonnet, "low" for Haiku.

        Returns:
            Sub-LM response text.
        """
        model = (
            self._config.sub_lm_high_model
            if tier == "high"
            else self._config.sub_lm_low_model
        )

        logger.info("Sub-LM call: model=%s tier=%s", model, tier)
        response = self._client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        self._cost_tracker.record(model, input_tokens, output_tokens)
        logger.info(
            "Sub-LM response: %d in / %d out tokens (running cost: $%.4f)",
            input_tokens,
            output_tokens,
            self._cost_tracker.estimated_cost_usd,
        )

        for block in response.content:
            if block.type == "text":
                return block.text

        return ""

    def _call_sub_lm_batched(
        self, prompts: list[str], tier: str = "high", max_workers: int = 8
    ) -> list[str]:
        """Call sub-LMs in parallel using a thread pool.

        Args:
            prompts: List of prompts to send.
            tier: "high" for Sonnet, "low" for Haiku.
            max_workers: Max concurrent API calls (default 8).

        Returns:
            List of response texts, one per prompt (order preserved).
        """
        if not prompts:
            return []

        logger.info(
            "Batched sub-LM: %d prompts, tier=%s, workers=%d",
            len(prompts),
            tier,
            min(max_workers, len(prompts)),
        )

        results: list[str | None] = [None] * len(prompts)

        def _call_one(idx: int, prompt: str) -> tuple[int, str]:
            return idx, self._call_sub_lm(prompt, tier)

        with ThreadPoolExecutor(max_workers=min(max_workers, len(prompts))) as pool:
            futures = {
                pool.submit(_call_one, i, p): i for i, p in enumerate(prompts)
            }
            for future in as_completed(futures):
                # Check guardrails after each completion
                if self._cost_tracker.check_guardrails() == GuardrailStatus.EXCEEDED:
                    logger.warning("Budget exceeded during batched calls, cancelling remaining")
                    for f in futures:
                        f.cancel()
                    break
                idx, text = future.result()
                results[idx] = text

        return [r if r is not None else "" for r in results]


# Names injected by the engine — excluded from namespace snapshots.
_BUILTIN_NAMES = frozenset({
    "llm_query", "llm_query_batched", "FINAL", "print",
    "context", "_results", "__builtins__",
})


def _symbol_repr(value: Any, max_sample: int = 120) -> str:
    """Produce a compact symbolic representation of a value.

    Shows type, shape/length, and a sample — enough for the LM to write
    code against it without needing the full data in the prompt.
    """
    if isinstance(value, str):
        if len(value) <= max_sample:
            return f"str({len(value)} chars) = {value!r}"
        return f"str({len(value)} chars) = {value[:max_sample]!r}..."
    if isinstance(value, list):
        if not value:
            return "list(0 items) = []"
        sample = _symbol_repr(value[0], max_sample=80)
        return f"list({len(value)} items) — [0]: {sample}"
    if isinstance(value, dict):
        if not value:
            return "dict(0 keys) = {{}}"
        keys = list(value.keys())[:8]
        keys_str = ", ".join(repr(k) for k in keys)
        suffix = ", ..." if len(value) > 8 else ""
        return f"dict({len(value)} keys) — keys: [{keys_str}{suffix}]"
    if isinstance(value, (int, float, bool)):
        return f"{type(value).__name__} = {value!r}"
    if callable(value):
        return f"callable({getattr(value, '__name__', '?')})"
    # Fallback
    r = repr(value)
    if len(r) > max_sample:
        return f"{type(value).__name__}({len(r)} chars repr)"
    return f"{type(value).__name__} = {r}"


def _snapshot_namespace(
    namespace: dict[str, Any],
    builtin_names: frozenset[str],
) -> str:
    """Produce a symbolic snapshot of all user-created variables in the namespace.

    This is the lossless-compact representation: shows what exists, its shape,
    and a sample value — all actual data stays in memory for code access.
    """
    lines: list[str] = []
    for name, value in sorted(namespace.items()):
        if name in builtin_names or name.startswith("__"):
            continue
        # Skip tool functions (already listed in the tools prompt)
        if callable(value) and not isinstance(value, (list, dict, str)):
            continue
        lines.append(f"  {name}: {_symbol_repr(value)}")

    if not lines:
        return "  (no user variables yet)"
    return "\n".join(lines)


def _strip_code_fences(code: str) -> str:
    """Extract Python code from LLM responses that may contain markdown fences.

    Handles:
    - ```python ... ``` (with or without surrounding text/explanation)
    - ``` ... ``` (plain fenced block)
    - Multiple code blocks (extracts all, joins them)
    - Plain code with no fences
    """
    import re

    # Find all fenced code blocks (```python ... ``` or ``` ... ```)
    pattern = r"```(?:python)?\s*\n(.*?)```"
    blocks = re.findall(pattern, code, re.DOTALL)

    if blocks:
        return "\n\n".join(block.strip() for block in blocks)

    # Fallback: simple fence stripping (entire response is one block)
    lines = code.strip().splitlines()
    if not lines:
        return code

    if lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]

    return "\n".join(lines)
