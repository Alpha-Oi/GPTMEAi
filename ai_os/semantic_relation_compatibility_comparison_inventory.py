"""Pure aggregate inventory for caller-supplied compatibility comparisons."""

from __future__ import annotations

from dataclasses import dataclass

from ai_os.semantic_relation_compatibility import COMPATIBILITY_STATUSES
from ai_os.semantic_relation_compatibility_batch import (
    SemanticRelationCompatibilityBatchInventory,
)
from ai_os.semantic_relation_compatibility_comparison import (
    COMPARISON_DIRECTION,
    SemanticRelationCompatibilityComparison,
)

COMPARISON_INVENTORY_MODE = "read_only_compatibility_comparison_inventory"
COMPARISON_INVENTORY_SOURCE = "caller_supplied_compatibility_comparisons"
COMPARISON_INVENTORY_AGGREGATION_SEMANTICS = "count_each_comparison"

_COUNT_FIELDS = (
    "report_count",
    "relation_count",
    "versioned_relation_count",
    "unversioned_relation_count",
    "malformed_relation_count",
    "issue_report_count",
)
_DELTA_FIELDS = {
    "report_count": "report_count_delta",
    "relation_count": "relation_count_delta",
    "versioned_relation_count": "versioned_relation_count_delta",
    "unversioned_relation_count": "unversioned_relation_count_delta",
    "malformed_relation_count": "malformed_relation_count_delta",
    "issue_report_count": "issue_report_count_delta",
}
_ISSUE_FREE_STATUSES = {
    "empty",
    "compatible_v1_shape",
    "legacy_unversioned",
}


class SemanticRelationCompatibilityComparisonInventoryError(ValueError):
    """Stable inventory error that never includes rejected input values."""

    def __init__(
        self,
        code: str,
        *,
        index: int | None = None,
        field: str | None = None,
    ) -> None:
        self.code = code
        self.index = index
        self.field = field
        parts = [code]
        if index is not None:
            parts.append(f"index={index}")
        if field is not None:
            parts.append(f"field={field}")
        super().__init__(";".join(parts))

    def to_dict(self) -> dict[str, str | int | None]:
        return {
            "code": self.code,
            "index": self.index,
            "field": self.field,
        }


@dataclass(frozen=True)
class SemanticRelationCompatibilityComparisonAggregateCounts:
    """Immutable aggregate counts without comparison-level references."""

    report_count: int
    status_counts: tuple[tuple[str, int], ...]
    relation_count: int
    versioned_relation_count: int
    unversioned_relation_count: int
    malformed_relation_count: int
    issue_report_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "report_count": self.report_count,
            "status_counts": dict(self.status_counts),
            "relation_count": self.relation_count,
            "versioned_relation_count": self.versioned_relation_count,
            "unversioned_relation_count": self.unversioned_relation_count,
            "malformed_relation_count": self.malformed_relation_count,
            "issue_report_count": self.issue_report_count,
        }


@dataclass(frozen=True)
class SemanticRelationCompatibilityComparisonInventory:
    """Aggregate-only inventory without individual comparison references."""

    comparison_count: int
    baseline: SemanticRelationCompatibilityComparisonAggregateCounts
    candidate: SemanticRelationCompatibilityComparisonAggregateCounts
    delta: SemanticRelationCompatibilityComparisonAggregateCounts

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": COMPARISON_INVENTORY_MODE,
            "source": COMPARISON_INVENTORY_SOURCE,
            "aggregation_semantics": (
                COMPARISON_INVENTORY_AGGREGATION_SEMANTICS
            ),
            "comparison_direction": COMPARISON_DIRECTION,
            "comparison_count": self.comparison_count,
            "baseline": self.baseline.to_dict(),
            "candidate": self.candidate.to_dict(),
            "delta": self.delta.to_dict(),
            "comparison_generation_provenance": "not_available",
            "writer_validation_provenance": "not_available",
            "source_identity_matching_performed": False,
            "target_lookup_performed": False,
        }


def build_semantic_relation_compatibility_comparison_inventory(
    comparisons: object,
) -> SemanticRelationCompatibilityComparisonInventory:
    """Validate and aggregate caller-supplied comparisons without I/O."""

    if type(comparisons) is not list:
        raise SemanticRelationCompatibilityComparisonInventoryError(
            "compatibility_comparisons_not_list",
            field="comparisons",
        )

    baseline_count_totals, baseline_status_totals = _empty_totals()
    candidate_count_totals, candidate_status_totals = _empty_totals()

    for index, comparison in enumerate(comparisons):
        _validate_comparison(comparison, index=index)
        _add_inventory_counts(
            baseline_count_totals,
            baseline_status_totals,
            comparison.baseline_inventory,
        )
        _add_inventory_counts(
            candidate_count_totals,
            candidate_status_totals,
            comparison.candidate_inventory,
        )

    baseline = _aggregate_counts(baseline_count_totals, baseline_status_totals)
    candidate = _aggregate_counts(candidate_count_totals, candidate_status_totals)
    delta = _subtract_counts(candidate, baseline)
    return SemanticRelationCompatibilityComparisonInventory(
        comparison_count=len(comparisons),
        baseline=baseline,
        candidate=candidate,
        delta=delta,
    )


def _validate_comparison(comparison: object, *, index: int) -> None:
    if type(comparison) is not SemanticRelationCompatibilityComparison:
        raise SemanticRelationCompatibilityComparisonInventoryError(
            "compatibility_comparison_type_invalid",
            index=index,
        )

    _validate_inventory(
        comparison.baseline_inventory,
        index=index,
        field_prefix="baseline",
    )
    _validate_inventory(
        comparison.candidate_inventory,
        index=index,
        field_prefix="candidate",
    )
    _validate_deltas(comparison, index=index)


def _validate_inventory(
    inventory: object,
    *,
    index: int,
    field_prefix: str,
) -> None:
    if type(inventory) is not SemanticRelationCompatibilityBatchInventory:
        raise SemanticRelationCompatibilityComparisonInventoryError(
            "compatibility_comparison_inventory_type_invalid",
            index=index,
            field=f"{field_prefix}_inventory",
        )

    for field in _COUNT_FIELDS:
        value = getattr(inventory, field)
        if type(value) is not int or value < 0:
            raise SemanticRelationCompatibilityComparisonInventoryError(
                "compatibility_comparison_count_invalid",
                index=index,
                field=f"{field_prefix}_{field}",
            )

    status_total = _validate_status_counts(
        inventory.status_counts,
        index=index,
        field=f"{field_prefix}_status_counts",
        allow_signed=False,
    )
    if status_total != inventory.report_count:
        raise SemanticRelationCompatibilityComparisonInventoryError(
            "compatibility_comparison_count_mismatch",
            index=index,
            field=f"{field_prefix}_report_count",
        )

    classified_count = (
        inventory.versioned_relation_count
        + inventory.unversioned_relation_count
        + inventory.malformed_relation_count
    )
    if inventory.relation_count != classified_count:
        raise SemanticRelationCompatibilityComparisonInventoryError(
            "compatibility_comparison_count_mismatch",
            index=index,
            field=f"{field_prefix}_relation_count",
        )
    if inventory.issue_report_count > inventory.report_count:
        raise SemanticRelationCompatibilityComparisonInventoryError(
            "compatibility_comparison_count_mismatch",
            index=index,
            field=f"{field_prefix}_issue_report_count",
        )

    status_values = dict(inventory.status_counts)
    expected_issue_report_count = sum(
        count
        for status, count in inventory.status_counts
        if status not in _ISSUE_FREE_STATUSES
    )
    if inventory.issue_report_count != expected_issue_report_count:
        raise SemanticRelationCompatibilityComparisonInventoryError(
            "compatibility_comparison_count_mismatch",
            index=index,
            field=f"{field_prefix}_issue_report_count",
        )

    minimum_versioned_count = (
        status_values["compatible_v1_shape"]
        + status_values["mixed_versioning"]
        + status_values["unsupported_version"]
        + status_values["invalid_v1"]
    )
    if inventory.versioned_relation_count < minimum_versioned_count:
        raise SemanticRelationCompatibilityComparisonInventoryError(
            "compatibility_comparison_count_mismatch",
            index=index,
            field=f"{field_prefix}_versioned_relation_count",
        )

    minimum_unversioned_count = (
        status_values["legacy_unversioned"]
        + status_values["mixed_versioning"]
    )
    if inventory.unversioned_relation_count < minimum_unversioned_count:
        raise SemanticRelationCompatibilityComparisonInventoryError(
            "compatibility_comparison_count_mismatch",
            index=index,
            field=f"{field_prefix}_unversioned_relation_count",
        )


def _validate_deltas(
    comparison: SemanticRelationCompatibilityComparison,
    *,
    index: int,
) -> None:
    baseline_status_counts = dict(comparison.baseline_inventory.status_counts)
    candidate_status_counts = dict(comparison.candidate_inventory.status_counts)
    _validate_status_counts(
        comparison.status_count_deltas,
        index=index,
        field="status_count_deltas",
        allow_signed=True,
    )
    for status, delta in comparison.status_count_deltas:
        expected = candidate_status_counts[status] - baseline_status_counts[status]
        if delta != expected:
            raise SemanticRelationCompatibilityComparisonInventoryError(
                "compatibility_comparison_delta_mismatch",
                index=index,
                field="status_count_deltas",
            )

    for count_field, delta_field in _DELTA_FIELDS.items():
        delta = getattr(comparison, delta_field)
        if type(delta) is not int:
            raise SemanticRelationCompatibilityComparisonInventoryError(
                "compatibility_comparison_delta_invalid",
                index=index,
                field=delta_field,
            )
        expected = (
            getattr(comparison.candidate_inventory, count_field)
            - getattr(comparison.baseline_inventory, count_field)
        )
        if delta != expected:
            raise SemanticRelationCompatibilityComparisonInventoryError(
                "compatibility_comparison_delta_mismatch",
                index=index,
                field=delta_field,
            )


def _validate_status_counts(
    status_counts: object,
    *,
    index: int,
    field: str,
    allow_signed: bool,
) -> int:
    if type(status_counts) is not tuple or len(status_counts) != len(
        COMPATIBILITY_STATUSES
    ):
        raise SemanticRelationCompatibilityComparisonInventoryError(
            "compatibility_comparison_status_counts_invalid",
            index=index,
            field=field,
        )

    total = 0
    for status_index, entry in enumerate(status_counts):
        if type(entry) is not tuple or len(entry) != 2:
            raise SemanticRelationCompatibilityComparisonInventoryError(
                "compatibility_comparison_status_counts_invalid",
                index=index,
                field=field,
            )
        status, value = entry
        if type(status) is not str or status != COMPATIBILITY_STATUSES[status_index]:
            raise SemanticRelationCompatibilityComparisonInventoryError(
                "compatibility_comparison_status_taxonomy_invalid",
                index=index,
                field=field,
            )
        if type(value) is not int or (not allow_signed and value < 0):
            raise SemanticRelationCompatibilityComparisonInventoryError(
                "compatibility_comparison_count_invalid",
                index=index,
                field=field,
            )
        total += value
    return total


def _empty_totals() -> tuple[dict[str, int], dict[str, int]]:
    return (
        {field: 0 for field in _COUNT_FIELDS},
        {status: 0 for status in COMPATIBILITY_STATUSES},
    )


def _add_inventory_counts(
    count_totals: dict[str, int],
    status_totals: dict[str, int],
    inventory: SemanticRelationCompatibilityBatchInventory,
) -> None:
    for field in _COUNT_FIELDS:
        count_totals[field] += getattr(inventory, field)
    for status, count in inventory.status_counts:
        status_totals[status] += count


def _aggregate_counts(
    count_totals: dict[str, int],
    status_totals: dict[str, int],
) -> SemanticRelationCompatibilityComparisonAggregateCounts:
    return SemanticRelationCompatibilityComparisonAggregateCounts(
        report_count=count_totals["report_count"],
        status_counts=tuple(
            (status, status_totals[status])
            for status in COMPATIBILITY_STATUSES
        ),
        relation_count=count_totals["relation_count"],
        versioned_relation_count=count_totals["versioned_relation_count"],
        unversioned_relation_count=count_totals["unversioned_relation_count"],
        malformed_relation_count=count_totals["malformed_relation_count"],
        issue_report_count=count_totals["issue_report_count"],
    )


def _subtract_counts(
    candidate: SemanticRelationCompatibilityComparisonAggregateCounts,
    baseline: SemanticRelationCompatibilityComparisonAggregateCounts,
) -> SemanticRelationCompatibilityComparisonAggregateCounts:
    baseline_status_counts = dict(baseline.status_counts)
    return SemanticRelationCompatibilityComparisonAggregateCounts(
        report_count=candidate.report_count - baseline.report_count,
        status_counts=tuple(
            (status, count - baseline_status_counts[status])
            for status, count in candidate.status_counts
        ),
        relation_count=candidate.relation_count - baseline.relation_count,
        versioned_relation_count=(
            candidate.versioned_relation_count - baseline.versioned_relation_count
        ),
        unversioned_relation_count=(
            candidate.unversioned_relation_count - baseline.unversioned_relation_count
        ),
        malformed_relation_count=(
            candidate.malformed_relation_count - baseline.malformed_relation_count
        ),
        issue_report_count=(
            candidate.issue_report_count - baseline.issue_report_count
        ),
    )


__all__ = [
    "COMPARISON_INVENTORY_AGGREGATION_SEMANTICS",
    "COMPARISON_INVENTORY_MODE",
    "COMPARISON_INVENTORY_SOURCE",
    "SemanticRelationCompatibilityComparisonAggregateCounts",
    "SemanticRelationCompatibilityComparisonInventory",
    "SemanticRelationCompatibilityComparisonInventoryError",
    "build_semantic_relation_compatibility_comparison_inventory",
]
