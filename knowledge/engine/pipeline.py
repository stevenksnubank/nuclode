"""Deterministic analysis pipeline: chunk → fan-out → validate → reduce.

No REPL loop. No Opus. The engine orchestrates everything programmatically.
Sub-LMs return schema-conforming JSON. Reduce is mechanical.
"""

from __future__ import annotations

import logging
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

from knowledge.engine.chunking import FlowGroup
from knowledge.engine.config import EngineConfig
from knowledge.engine.cost_tracker import CostTracker, GuardrailStatus
from knowledge.engine.schema import ValidationError, validate_flow_analysis

logger = logging.getLogger(__name__)

# Sonnet's context is 200K tokens. ~4 chars/token, leave headroom for prompt template.
_MAX_SOURCE_CHARS_PER_GROUP = 500_000  # ~125K tokens, safe margin under 200K


@dataclass(frozen=True)
class PipelineResult:
    """Result from the deterministic pipeline.

    Attributes:
        status: "completed", "completed_with_errors", or "budget_exceeded".
        analyses: List of validated JSON dicts, one per successful flow group.
        validation_errors: List of (group_name, error_message) for failed groups.
        cost_summary: Final cost summary dict.
        groups_total: Total flow groups processed.
        groups_succeeded: Flow groups that produced valid analyses.
    """

    status: str
    analyses: list[dict]
    validation_errors: list[tuple[str, str]]
    cost_summary: dict
    groups_total: int
    groups_succeeded: int


def _split_oversized_groups(
    groups: list[FlowGroup],
    source_by_namespace: dict[str, str],
) -> list[FlowGroup]:
    """Split groups whose source code exceeds the context window budget.

    Groups under the limit pass through unchanged. Oversized groups get
    split into roughly equal sub-groups by namespace count.
    """
    result: list[FlowGroup] = []
    for group in groups:
        total_chars = sum(
            len(source_by_namespace.get(ns.name, ""))
            for ns in group.namespaces
        )
        if total_chars <= _MAX_SOURCE_CHARS_PER_GROUP:
            result.append(group)
            continue

        # Split into sub-groups that fit
        num_splits = math.ceil(total_chars / _MAX_SOURCE_CHARS_PER_GROUP)
        chunk_size = math.ceil(len(group.namespaces) / num_splits)
        sorted_ns = sorted(group.namespaces, key=lambda n: n.name)

        for i in range(0, len(sorted_ns), chunk_size):
            chunk = sorted_ns[i : i + chunk_size]
            chunk_names = {ns.name for ns in chunk}

            # Recompute internal deps for this chunk
            internal_deps: dict[str, list[str]] = {}
            for ns in chunk:
                deps_in_chunk = [
                    d for d in group.internal_deps.get(ns.name, [])
                    if d in chunk_names
                ]
                if deps_in_chunk:
                    internal_deps[ns.name] = deps_in_chunk

            required_by = set()
            for deps in internal_deps.values():
                required_by.update(deps)

            sub_group = FlowGroup(
                name=f"{group.name}-part{i // chunk_size + 1}",
                namespaces=chunk,
                entry_points=sorted(n for n in chunk_names if n not in required_by),
                exit_points=sorted(n for n in chunk_names if n not in internal_deps),
                internal_deps=internal_deps,
            )
            result.append(sub_group)
            logger.info(
                "Split %s: part %d with %d namespaces (%d chars)",
                group.name, i // chunk_size + 1, len(chunk),
                sum(len(source_by_namespace.get(ns.name, "")) for ns in chunk),
            )

    return result


class PipelineRunner:
    """Deterministic pipeline: dispatch sub-LMs per flow group, validate, collect."""

    def __init__(self, config: EngineConfig) -> None:
        self._config = config
        self._cost_tracker = CostTracker(config.guardrails)
        self._client = self._create_client()

    @staticmethod
    def _create_client() -> Any:
        """Create an Anthropic client with retry and timeout config."""
        import os

        import anthropic
        import httpx

        return anthropic.Anthropic(
            api_key=os.environ.get("LITELLM_API_KEY", os.environ.get("ANTHROPIC_API_KEY", "")),
            base_url=os.environ.get("LITELLM_BASE_URL", "https://ist-prod-litellm.nullmplatform.com"),
            max_retries=5,
            timeout=httpx.Timeout(300.0, connect=10.0),
        )

    def run(
        self,
        groups: list[FlowGroup],
        source_by_namespace: dict[str, str],
        mode: str = "structure",
        max_workers: int = 8,
    ) -> PipelineResult:
        """Run the deterministic pipeline over all flow groups.

        Args:
            groups: Flow groups from partition_flow_groups().
            source_by_namespace: Map of namespace name/path → source code.
            mode: "structure" or "security".
            max_workers: Max concurrent sub-LM calls.

        Returns:
            PipelineResult with validated analyses and any errors.
        """
        if not groups:
            return PipelineResult(
                status="completed", analyses=[], validation_errors=[],
                cost_summary=self._cost_tracker.summary().__dict__,
                groups_total=0, groups_succeeded=0,
            )

        # Split oversized groups that would exceed the context window
        dispatch_groups = _split_oversized_groups(groups, source_by_namespace)

        logger.info(
            "Pipeline: %d flow groups (%d after splitting), mode=%s, workers=%d",
            len(groups), len(dispatch_groups), mode, min(max_workers, len(dispatch_groups)),
        )

        # Lazy import to avoid circular dependency
        from knowledge.recipes.codebase_analysis.prompts import build_flow_group_prompt

        analyses: list[dict] = []
        validation_errors: list[tuple[str, str]] = []

        # Fan-out: parallel sub-LM calls
        def _analyze_group(group: FlowGroup) -> tuple[str, str]:
            prompt = build_flow_group_prompt(group, source_by_namespace, mode)
            raw = self._call_sub_lm_for_group(prompt)
            return group.name, raw

        results_by_group: dict[str, str] = {}

        with ThreadPoolExecutor(max_workers=min(max_workers, len(dispatch_groups))) as pool:
            futures = {pool.submit(_analyze_group, g): g.name for g in dispatch_groups}
            for future in as_completed(futures):
                if self._cost_tracker.check_guardrails() == GuardrailStatus.EXCEEDED:
                    logger.warning("Budget exceeded, cancelling remaining groups")
                    for f in futures:
                        f.cancel()
                    return PipelineResult(
                        status="budget_exceeded", analyses=analyses,
                        validation_errors=validation_errors,
                        cost_summary=self._cost_tracker.summary().__dict__,
                        groups_total=len(dispatch_groups), groups_succeeded=len(analyses),
                    )
                group_name = futures[future]
                try:
                    name, raw = future.result()
                    results_by_group[name] = raw
                except Exception as exc:
                    logger.error("API error for %s: %s", group_name, exc)
                    validation_errors.append((group_name, f"API error: {exc}"))

        # Validate + retry once on failure
        for group in dispatch_groups:
            raw = results_by_group.get(group.name, "")
            if not raw:
                continue  # already recorded as API error
            try:
                validated = validate_flow_analysis(raw)
                analyses.append(validated)
                logger.info("Validated: %s (%d namespaces)", group.name, len(validated.get("namespaces", [])))
            except ValidationError as exc:
                logger.warning("Validation failed for %s: %s — retrying", group.name, exc)
                try:
                    retry_prompt = build_flow_group_prompt(group, source_by_namespace, mode)
                    retry_prompt += f"\n\nPrevious attempt failed validation: {exc}\nFix the JSON and try again."
                    retry_raw = self._call_sub_lm_for_group(retry_prompt)
                    validated = validate_flow_analysis(retry_raw)
                    analyses.append(validated)
                    logger.info("Retry succeeded: %s", group.name)
                except (ValidationError, Exception) as retry_exc:
                    logger.error("Retry failed for %s: %s", group.name, retry_exc)
                    validation_errors.append((group.name, str(retry_exc)))

        status = "completed" if not validation_errors else "completed_with_errors"
        logger.info(
            "Pipeline done: %d/%d groups succeeded, cost=$%.4f",
            len(analyses), len(dispatch_groups), self._cost_tracker.estimated_cost_usd,
        )

        return PipelineResult(
            status=status,
            analyses=analyses,
            validation_errors=validation_errors,
            cost_summary=self._cost_tracker.summary().__dict__,
            groups_total=len(dispatch_groups),
            groups_succeeded=len(analyses),
        )

    def _call_sub_lm_for_group(self, prompt: str) -> str:
        """Call sub-LM (Sonnet) for a flow group analysis."""
        model = self._config.sub_lm_high_model
        response = self._client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        self._cost_tracker.record(model, input_tokens, output_tokens)
        logger.info(
            "Sub-LM response: %d in / %d out tokens (cost: $%.4f)",
            input_tokens, output_tokens, self._cost_tracker.estimated_cost_usd,
        )
        for block in response.content:
            if block.type == "text":
                return block.text
        return ""
