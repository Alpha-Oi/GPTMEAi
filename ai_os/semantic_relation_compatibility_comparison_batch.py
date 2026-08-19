"""Pure direct-batch composition for semantic relation compatibility comparisons."""

from __future__ import annotations

from dataclasses import dataclass

from ai_os.semantic_relation_compatibility_comparison import (
    COMPARISON_DIRECTION,
    SemanticRelationCompatibilityComparisonError,
    compare_direct_semantic_relation_compatibility_batches,
)
from ai_os.semantic_relation_compatibility_comparison_inventory import (
    SemanticRelationCompatibilityComparisonAggregateCounts,
    build_semantic_relation_compatibility_comparison_inventory,
)


COMPARISON_BATCH_INVENTORY_MODE = (
    "read_only_direct_compatibility_comparison_inventory"
)
COMPARISON_BATCH_INVENTORY_SOURCE = (
    "caller_supplied_relation_input_batch_comparisons"
)
COMPARISON_BATCH_AGGREGATION_SEMANTICS = "count_each_comparison_input"
COMPARISON_BATCH_GENERATION_PROVENANCE = "direct_f3d_comparison_for_each_input"
COMPARISON_BATCH_INVENTORY_PROVENANCE = (
    "direct_f3e_comparison_inventory_builder"
)


@dataclass(frozen=True)
class SemanticRelationCompatibilityComparisonBatchInput:
    """One explicit caller-supplied baseline/candidate batch pair."""

    baseline_inputs: object
    candidate_inputs: object


class SemanticRelationCompatibilityComparisonBatchError(ValueError):
    """Stable safe error for invalid direct comparison-batch input."""

    def __init__(
        self,
        code: str,
        *,
        comparison_index: int | None = None,
        batch: str | None = None,
        index: int | None = None,
        field: str | None = None,
    ) -> None:
        self.code = code
        self.comparison_index = comparison_index
        self.batch = batch
        self.index = index
        self.field = field

        parts = [code]
        if comparison_index is not None:
            parts.append(f"comparison_index={comparison_index}")
        if batch is not None:
            parts.append(f"batch={batch}")
        if index is not None:
            parts.append(f"index={index}")
        if field is not None:
            parts.append(f"field={field}")
        super().__init__("; ".join(parts))

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "comparison_index": self.comparison_index,
            "batch": self.batch,
            "index": self.index,
            "field": self.field,
        }


@dataclass(frozen=True)
class SemanticRelationCompatibilityComparisonBatchInventory:
    """Aggregate-only inventory for explicit direct comparison inputs."""

    comparison_count: int
    baseline: SemanticRelationCompatibilityComparisonAggregateCounts
    candidate: SemanticRelationCompatibilityComparisonAggregateCounts
    delta: SemanticRelationCompatibilityComparisonAggregateCounts

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": COMPARISON_BATCH_INVENTORY_MODE,
            "source": COMPARISON_BATCH_INVENTORY_SOURCE,
            "aggregation_semantics": COMPARISON_BATCH_AGGREGATION_SEMANTICS,
            "comparison_direction": COMPARISON_DIRECTION,
            "comparison_count": self.comparison_count,
            "baseline": self.baseline.to_dict(),
            "candidate": self.candidate.to_dict(),
            "delta": self.delta.to_dict(),
            "comparison_generation_provenance": (
                COMPARISON_BATCH_GENERATION_PROVENANCE
            ),
            "comparison_inventory_generation_provenance": (
                COMPARISON_BATCH_INVENTORY_PROVENANCE
            ),
            "writer_validation_provenance": "not_available",
            "source_identity_matching_performed": False,
            "target_lookup_performed": False,
        }


def build_direct_semantic_relation_compatibility_comparison_inventory(
    comparison_inputs: object,
) -> SemanticRelationCompatibilityComparisonBatchInventory:
    """Compose F3D comparisons and one F3E aggregate for explicit input pairs."""

    if type(comparison_inputs) is not list:
        raise SemanticRelationCompatibilityComparisonBatchError(
            "compatibility_comparison_inputs_not_list",
            field="comparison_inputs",
        )

    comparisons = []
    for comparison_index, comparison_input in enumerate(comparison_inputs):
        if type(comparison_input) is not SemanticRelationCompatibilityComparisonBatchInput:
            raise SemanticRelationCompatibilityComparisonBatchError(
                "compatibility_comparison_input_type_invalid",
                comparison_index=comparison_index,
            )

        try:
            comparison = compare_direct_semantic_relation_compatibility_batches(
                baseline_inputs=comparison_input.baseline_inputs,
                candidate_inputs=comparison_input.candidate_inputs,
            )
        except SemanticRelationCompatibilityComparisonError as exc:
            raise SemanticRelationCompatibilityComparisonBatchError(
                exc.code,
                comparison_index=comparison_index,
                batch=exc.batch,
                index=exc.index,
                field=exc.field,
            ) from None
        comparisons.append(comparison)

    inventory = build_semantic_relation_compatibility_comparison_inventory(comparisons)
    return SemanticRelationCompatibilityComparisonBatchInventory(
        comparison_count=inventory.comparison_count,
        baseline=inventory.baseline,
        candidate=inventory.candidate,
        delta=inventory.delta,
    )


__all__ = [
    "COMPARISON_BATCH_AGGREGATION_SEMANTICS",
    "COMPARISON_BATCH_GENERATION_PROVENANCE",
    "COMPARISON_BATCH_INVENTORY_MODE",
    "COMPARISON_BATCH_INVENTORY_PROVENANCE",
    "COMPARISON_BATCH_INVENTORY_SOURCE",
    "SemanticRelationCompatibilityComparisonBatchError",
    "SemanticRelationCompatibilityComparisonBatchInput",
    "SemanticRelationCompatibilityComparisonBatchInventory",
    "build_direct_semantic_relation_compatibility_comparison_inventory",
]
