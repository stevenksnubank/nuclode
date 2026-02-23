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
import traceback
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from typing import Any, Callable

from engine.config import EngineConfig
from engine.cost_tracker import CostTracker, GuardrailStatus
from engine.gate import GateDecision, route_task

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
                    "Call FINAL() when complete."
                )
            else:
                # Subsequent iterations get the execution output
                user_content = conversation[-1].get("output", "No output from previous code.")

            # Call root LM
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
            try:
                output = self._execute_code(code, namespace)
                conversation.append({"code": code, "output": output})
            except _FinalSignal as final:
                final_output = final.result
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
                logger.warning("Code execution error at iteration %d: %s", iterations, exc)

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
        try:
            import anthropic
        except ImportError as exc:
            raise RuntimeError(
                "anthropic package required. Install with: pip install anthropic"
            ) from exc

        client = anthropic.Anthropic()

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

        response = client.messages.create(**kwargs)

        # Track costs
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        self._cost_tracker.record(self._config.root_model, input_tokens, output_tokens)

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

        try:
            import anthropic
        except ImportError as exc:
            raise RuntimeError(
                "anthropic package required. Install with: pip install anthropic"
            ) from exc

        client = anthropic.Anthropic()
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        self._cost_tracker.record(model, input_tokens, output_tokens)

        for block in response.content:
            if block.type == "text":
                return block.text

        return ""

    def _call_sub_lm_batched(self, prompts: list[str], tier: str = "high") -> list[str]:
        """Call sub-LMs in sequence (batched conceptually, sequential for now).

        Future optimization: use asyncio or threading for true parallelism.

        Args:
            prompts: List of prompts to send.
            tier: "high" for Sonnet, "low" for Haiku.

        Returns:
            List of response texts, one per prompt.
        """
        results: list[str] = []
        for prompt in prompts:
            # Check guardrails between calls
            if self._cost_tracker.check_guardrails() == GuardrailStatus.EXCEEDED:
                logger.warning("Budget exceeded during batched calls, stopping early")
                break
            results.append(self._call_sub_lm(prompt, tier))
        return results


def _strip_code_fences(code: str) -> str:
    """Strip markdown code fences from LLM-generated code.

    Handles: ```python ... ```, ``` ... ```, and plain code.
    """
    lines = code.strip().splitlines()
    if not lines:
        return code

    # Check if first line is a code fence
    if lines[0].strip().startswith("```"):
        lines = lines[1:]
    # Check if last line is a closing fence
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]

    return "\n".join(lines)
