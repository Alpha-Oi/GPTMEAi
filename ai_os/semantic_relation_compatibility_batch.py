"""Pure direct-input batch inventory for Semantic Relation compatibility."""

from __future__ import annotations

from dataclasses import dataclass

from ai_os.semantic_relation_compatibility import (
    classify_semantic_relation_compatibility,
)
from ai_os.semantic_relation_compatibility_inventory import (
    build_semantic_relation_compatibility_inventory,
)

BATCH_INVENTORY_MODE = "read_only_direct_compatibility_inventory"
BATCH_INVENTORY_SOURCE = "caller_supplied_relation_inputs"
BATCH_REPORT_GENERATION_PROVENANCE = "direct_f3a_classifier"


class SemanticRelationCompatibilityBatchError(ValueError):
    """Stable batch error that never includes rejected input values."""

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
class SemanticRelationCompatibilityInput:
    """Caller-supplied in-memory source ID and relation payload."""

    source_concept_id: object
    relations: object


@dataclass(frozen=True)
class SemanticRelationCompatibilityBatchInventory:
    """Aggregate-only inventory created through the direct F3A call path."""

    report_count: int
    status_counts: tuple[tuple[str, int], ...]
    relation_count: int
    versioned_relation_count: int
    unversioned_relation_count: int
    malformed_relation_count: int
    issue_report_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": BATCH_INVENTORY_MODE,
            "source": BATCH_INVENTORY_SOURCE,
            "report_count": self.report_count,
            "status_counts": dict(self.status_counts),
            "relation_count": self.relation_count,
            "versioned_relation_count": self.versioned_relation_count,
            "unversioned_relation_count": self.unversioned_relation_count,
            "malformed_relation_count": self.malformed_relation_count,
            "issue_report_count": self.issue_report_count,
            "report_generation_provenance": BATCH_REPORT_GENERATION_PROVENANCE,
            "writer_validation_provenance": "not_available",
            "target_lookup_performed": False,
        }


def build_direct_semantic_relation_compatibility_inventory(
    inputs: object,
) -> SemanticRelationCompatibilityBatchInventory:
    """Classify direct inputs with F3A and aggregate them with F3B."""

    if type(inputs) is not list:
        raise SemanticRelationCompatibilityBatchError(
            "compatibility_inputs_not_list",
            field="inputs",
        )

    reports = []
    for index, item in enumerate(inputs):
        if type(item) is not SemanticRelationCompatibilityInput:
            raise SemanticRelationCompatibilityBatchError(
                "compatibility_input_type_invalid",
                index=index,
            )
        reports.append(
            classify_semantic_relation_compatibility(
                item.relations,
                source_concept_id=item.source_concept_id,
            )
        )

    inventory = build_semantic_relation_compatibility_inventory(reports)
    return SemanticRelationCompatibilityBatchInventory(
        report_count=inventory.report_count,
        status_counts=inventory.status_counts,
        relation_count=inventory.relation_count,
        versioned_relation_count=inventory.versioned_relation_count,
        unversioned_relation_count=inventory.unversioned_relation_count,
        malformed_relation_count=inventory.malformed_relation_count,
        issue_report_count=inventory.issue_report_count,
    )


__all__ = [
    "BATCH_INVENTORY_MODE",
    "BATCH_INVENTORY_SOURCE",
    "BATCH_REPORT_GENERATION_PROVENANCE",
    "SemanticRelationCompatibilityBatchError",
    "SemanticRelationCompatibilityBatchInventory",
    "SemanticRelationCompatibilityInput",
    "build_direct_semantic_relation_compatibility_inventory",
]
