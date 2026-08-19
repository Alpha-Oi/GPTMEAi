"""Pure aggregate inventory for caller-supplied compatibility reports."""

from __future__ import annotations

from dataclasses import dataclass

from ai_os.semantic_relation_compatibility import (
    COMPATIBILITY_STATUSES,
    SemanticRelationCompatibilityReport,
)

INVENTORY_MODE = "read_only_compatibility_inventory"
INVENTORY_SOURCE = "caller_supplied_compatibility_reports"

_COUNT_FIELDS = (
    "relation_count",
    "versioned_relation_count",
    "unversioned_relation_count",
    "malformed_relation_count",
)
_ISSUE_FREE_STATUSES = {
    "empty",
    "compatible_v1_shape",
    "legacy_unversioned",
}
_ISSUE_REQUIRED_STATUSES = set(COMPATIBILITY_STATUSES) - _ISSUE_FREE_STATUSES


class SemanticRelationCompatibilityInventoryError(ValueError):
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
class SemanticRelationCompatibilityInventory:
    """Immutable aggregate state without source identifiers or relation payloads."""

    report_count: int
    status_counts: tuple[tuple[str, int], ...]
    relation_count: int
    versioned_relation_count: int
    unversioned_relation_count: int
    malformed_relation_count: int
    issue_report_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": INVENTORY_MODE,
            "source": INVENTORY_SOURCE,
            "report_count": self.report_count,
            "status_counts": dict(self.status_counts),
            "relation_count": self.relation_count,
            "versioned_relation_count": self.versioned_relation_count,
            "unversioned_relation_count": self.unversioned_relation_count,
            "malformed_relation_count": self.malformed_relation_count,
            "issue_report_count": self.issue_report_count,
            "report_generation_provenance": "not_available",
            "writer_validation_provenance": "not_available",
            "target_lookup_performed": False,
        }


def build_semantic_relation_compatibility_inventory(
    reports: object,
) -> SemanticRelationCompatibilityInventory:
    """Aggregate well-formed caller-supplied reports without I/O or mutation."""

    if type(reports) is not list:
        raise SemanticRelationCompatibilityInventoryError(
            "compatibility_reports_not_list",
            field="reports",
        )

    status_counts = {status: 0 for status in COMPATIBILITY_STATUSES}
    totals = {field: 0 for field in _COUNT_FIELDS}
    issue_report_count = 0

    for index, report in enumerate(reports):
        _validate_report(report, index=index)
        status_counts[report.status] += 1
        for field in _COUNT_FIELDS:
            totals[field] += getattr(report, field)
        if report.issue_code is not None:
            issue_report_count += 1

    return SemanticRelationCompatibilityInventory(
        report_count=len(reports),
        status_counts=tuple(
            (status, status_counts[status])
            for status in COMPATIBILITY_STATUSES
        ),
        relation_count=totals["relation_count"],
        versioned_relation_count=totals["versioned_relation_count"],
        unversioned_relation_count=totals["unversioned_relation_count"],
        malformed_relation_count=totals["malformed_relation_count"],
        issue_report_count=issue_report_count,
    )


def _validate_report(report: object, *, index: int) -> None:
    if type(report) is not SemanticRelationCompatibilityReport:
        raise SemanticRelationCompatibilityInventoryError(
            "compatibility_report_type_invalid",
            index=index,
        )
    if type(report.status) is not str or report.status not in COMPATIBILITY_STATUSES:
        raise SemanticRelationCompatibilityInventoryError(
            "compatibility_report_status_invalid",
            index=index,
            field="status",
        )

    for field in _COUNT_FIELDS:
        value = getattr(report, field)
        if type(value) is not int or value < 0:
            raise SemanticRelationCompatibilityInventoryError(
                "compatibility_report_count_invalid",
                index=index,
                field=field,
            )

    classified_count = (
        report.versioned_relation_count
        + report.unversioned_relation_count
        + report.malformed_relation_count
    )
    if report.relation_count != classified_count:
        raise SemanticRelationCompatibilityInventoryError(
            "compatibility_report_count_mismatch",
            index=index,
            field="relation_count",
        )
    if not _status_counts_are_consistent(report):
        raise SemanticRelationCompatibilityInventoryError(
            "compatibility_report_status_count_mismatch",
            index=index,
            field="status",
        )

    if report.issue_code is not None and (
        type(report.issue_code) is not str or not report.issue_code
    ):
        raise SemanticRelationCompatibilityInventoryError(
            "compatibility_report_issue_invalid",
            index=index,
            field="issue_code",
        )
    if report.issue_index is not None and (
        type(report.issue_index) is not int or report.issue_index < 0
    ):
        raise SemanticRelationCompatibilityInventoryError(
            "compatibility_report_issue_invalid",
            index=index,
            field="issue_index",
        )
    if report.issue_field is not None and (
        type(report.issue_field) is not str or not report.issue_field
    ):
        raise SemanticRelationCompatibilityInventoryError(
            "compatibility_report_issue_invalid",
            index=index,
            field="issue_field",
        )

    if report.status in _ISSUE_REQUIRED_STATUSES and report.issue_code is None:
        raise SemanticRelationCompatibilityInventoryError(
            "compatibility_report_issue_missing",
            index=index,
            field="issue_code",
        )
    if report.status in _ISSUE_FREE_STATUSES and any(
        value is not None
        for value in (report.issue_code, report.issue_index, report.issue_field)
    ):
        raise SemanticRelationCompatibilityInventoryError(
            "compatibility_report_issue_unexpected",
            index=index,
            field="issue_code",
        )


def _status_counts_are_consistent(
    report: SemanticRelationCompatibilityReport,
) -> bool:
    if report.status == "empty":
        return report.relation_count == 0
    if report.status in {"compatible_v1_shape", "unsupported_version", "invalid_v1"}:
        return (
            report.relation_count > 0
            and report.versioned_relation_count == report.relation_count
            and report.unversioned_relation_count == 0
            and report.malformed_relation_count == 0
        )
    if report.status == "legacy_unversioned":
        return (
            report.relation_count > 0
            and report.versioned_relation_count == 0
            and report.unversioned_relation_count == report.relation_count
            and report.malformed_relation_count == 0
        )
    if report.status == "mixed_versioning":
        return (
            report.versioned_relation_count > 0
            and report.unversioned_relation_count > 0
            and report.malformed_relation_count == 0
        )
    if report.status == "malformed_relations":
        return report.relation_count == 0 or report.malformed_relation_count > 0
    return False


__all__ = [
    "INVENTORY_MODE",
    "INVENTORY_SOURCE",
    "SemanticRelationCompatibilityInventory",
    "SemanticRelationCompatibilityInventoryError",
    "build_semantic_relation_compatibility_inventory",
]
