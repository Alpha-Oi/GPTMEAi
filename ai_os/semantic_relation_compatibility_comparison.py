"""Pure aggregate comparison for two direct Semantic Relation input batches."""

from __future__ import annotations

from dataclasses import dataclass

from ai_os.semantic_relation_compatibility_batch import (
    SemanticRelationCompatibilityBatchError,
    SemanticRelationCompatibilityBatchInventory,
    build_direct_semantic_relation_compatibility_inventory,
)

COMPARISON_MODE = "read_only_direct_compatibility_comparison"
COMPARISON_SOURCE = "caller_supplied_relation_input_batches"
COMPARISON_DIRECTION = "candidate_minus_baseline"
COMPARISON_SEMANTICS = "descriptive_counts_only"
COMPARISON_INVENTORY_GENERATION_PROVENANCE = (
    "direct_f3c_batch_builder_for_both_batches"
)

_COUNT_FIELDS = (
    "report_count",
    "relation_count",
    "versioned_relation_count",
    "unversioned_relation_count",
    "malformed_relation_count",
    "issue_report_count",
)


class SemanticRelationCompatibilityComparisonError(ValueError):
    """Stable comparison error that never includes rejected input values."""

    def __init__(
        self,
        code: str,
        *,
        batch: str,
        index: int | None = None,
        field: str | None = None,
    ) -> None:
        self.code = code
        self.batch = batch
        self.index = index
        self.field = field
        parts = [code, f"batch={batch}"]
        if index is not None:
            parts.append(f"index={index}")
        if field is not None:
            parts.append(f"field={field}")
        super().__init__(";".join(parts))

    def to_dict(self) -> dict[str, str | int | None]:
        return {
            "code": self.code,
            "batch": self.batch,
            "index": self.index,
            "field": self.field,
        }


@dataclass(frozen=True)
class SemanticRelationCompatibilityComparison:
    """Aggregate-only candidate-minus-baseline comparison."""

    baseline_inventory: SemanticRelationCompatibilityBatchInventory
    candidate_inventory: SemanticRelationCompatibilityBatchInventory
    report_count_delta: int
    status_count_deltas: tuple[tuple[str, int], ...]
    relation_count_delta: int
    versioned_relation_count_delta: int
    unversioned_relation_count_delta: int
    malformed_relation_count_delta: int
    issue_report_count_delta: int

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": COMPARISON_MODE,
            "source": COMPARISON_SOURCE,
            "comparison_direction": COMPARISON_DIRECTION,
            "comparison_semantics": COMPARISON_SEMANTICS,
            "baseline": _inventory_counts(self.baseline_inventory),
            "candidate": _inventory_counts(self.candidate_inventory),
            "delta": {
                "report_count": self.report_count_delta,
                "status_counts": dict(self.status_count_deltas),
                "relation_count": self.relation_count_delta,
                "versioned_relation_count": self.versioned_relation_count_delta,
                "unversioned_relation_count": self.unversioned_relation_count_delta,
                "malformed_relation_count": self.malformed_relation_count_delta,
                "issue_report_count": self.issue_report_count_delta,
            },
            "inventory_generation_provenance": (
                COMPARISON_INVENTORY_GENERATION_PROVENANCE
            ),
            "writer_validation_provenance": "not_available",
            "source_identity_matching_performed": False,
            "target_lookup_performed": False,
        }


def compare_direct_semantic_relation_compatibility_batches(
    *,
    baseline_inputs: object,
    candidate_inputs: object,
) -> SemanticRelationCompatibilityComparison:
    """Compare two caller-supplied batches without alignment or interpretation."""

    baseline_inventory = _build_inventory(
        baseline_inputs,
        batch="baseline",
    )
    candidate_inventory = _build_inventory(
        candidate_inputs,
        batch="candidate",
    )

    baseline_statuses = tuple(status for status, _ in baseline_inventory.status_counts)
    candidate_statuses = tuple(status for status, _ in candidate_inventory.status_counts)
    if candidate_statuses != baseline_statuses:
        raise SemanticRelationCompatibilityComparisonError(
            "compatibility_status_taxonomy_mismatch",
            batch="candidate",
            field="status_counts",
        )

    candidate_status_counts = dict(candidate_inventory.status_counts)
    status_count_deltas = tuple(
        (status, candidate_status_counts[status] - count)
        for status, count in baseline_inventory.status_counts
    )
    count_deltas = {
        field: getattr(candidate_inventory, field) - getattr(baseline_inventory, field)
        for field in _COUNT_FIELDS
    }

    return SemanticRelationCompatibilityComparison(
        baseline_inventory=baseline_inventory,
        candidate_inventory=candidate_inventory,
        report_count_delta=count_deltas["report_count"],
        status_count_deltas=status_count_deltas,
        relation_count_delta=count_deltas["relation_count"],
        versioned_relation_count_delta=count_deltas["versioned_relation_count"],
        unversioned_relation_count_delta=count_deltas["unversioned_relation_count"],
        malformed_relation_count_delta=count_deltas["malformed_relation_count"],
        issue_report_count_delta=count_deltas["issue_report_count"],
    )


def _build_inventory(
    inputs: object,
    *,
    batch: str,
) -> SemanticRelationCompatibilityBatchInventory:
    try:
        return build_direct_semantic_relation_compatibility_inventory(inputs)
    except SemanticRelationCompatibilityBatchError as exc:
        raise SemanticRelationCompatibilityComparisonError(
            exc.code,
            batch=batch,
            index=exc.index,
            field=exc.field,
        ) from None


def _inventory_counts(
    inventory: SemanticRelationCompatibilityBatchInventory,
) -> dict[str, object]:
    return {
        "report_count": inventory.report_count,
        "status_counts": dict(inventory.status_counts),
        "relation_count": inventory.relation_count,
        "versioned_relation_count": inventory.versioned_relation_count,
        "unversioned_relation_count": inventory.unversioned_relation_count,
        "malformed_relation_count": inventory.malformed_relation_count,
        "issue_report_count": inventory.issue_report_count,
    }


__all__ = [
    "COMPARISON_DIRECTION",
    "COMPARISON_INVENTORY_GENERATION_PROVENANCE",
    "COMPARISON_MODE",
    "COMPARISON_SEMANTICS",
    "COMPARISON_SOURCE",
    "SemanticRelationCompatibilityComparison",
    "SemanticRelationCompatibilityComparisonError",
    "compare_direct_semantic_relation_compatibility_batches",
]
