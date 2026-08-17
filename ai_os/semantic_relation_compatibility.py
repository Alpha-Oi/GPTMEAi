"""Pure compatibility classification for already stored Semantic Relations."""

from __future__ import annotations

from dataclasses import dataclass

from ai_os.semantic_relation_contract import (
    RELATION_CONTRACT_VERSION,
    SemanticRelationContractError,
    validate_semantic_relation_list,
)

COMPATIBILITY_STATUSES = (
    "empty",
    "compatible_v1_shape",
    "legacy_unversioned",
    "mixed_versioning",
    "unsupported_version",
    "invalid_v1",
    "malformed_relations",
)


@dataclass(frozen=True)
class SemanticRelationCompatibilityReport:
    """Aggregate compatibility result without stored-writer provenance claims."""

    status: str
    relation_count: int
    versioned_relation_count: int
    unversioned_relation_count: int
    malformed_relation_count: int
    issue_code: str | None = None
    issue_index: int | None = None
    issue_field: str | None = None

    def to_dict(self) -> dict[str, object]:
        issue = None
        if self.issue_code is not None:
            issue = {
                "code": self.issue_code,
                "index": self.issue_index,
                "field": self.issue_field,
            }
        return {
            "status": self.status,
            "relation_count": self.relation_count,
            "versioned_relation_count": self.versioned_relation_count,
            "unversioned_relation_count": self.unversioned_relation_count,
            "malformed_relation_count": self.malformed_relation_count,
            "issue": issue,
            "writer_validation_provenance": "not_available",
            "target_lookup_performed": False,
        }


def classify_semantic_relation_compatibility(
    relations: object,
    *,
    source_concept_id: object,
) -> SemanticRelationCompatibilityReport:
    """Classify stored relation shape without lookup, I/O, or input mutation."""

    if type(relations) is not list:
        return SemanticRelationCompatibilityReport(
            status="malformed_relations",
            relation_count=0,
            versioned_relation_count=0,
            unversioned_relation_count=0,
            malformed_relation_count=0,
            issue_code="relations_not_list",
            issue_field="relations",
        )

    relation_count = len(relations)
    versioned_relation_count = 0
    unversioned_relation_count = 0
    malformed_relation_count = 0
    first_malformed_index = None

    for index, relation in enumerate(relations):
        if type(relation) is not dict:
            malformed_relation_count += 1
            if first_malformed_index is None:
                first_malformed_index = index
            continue
        if "contract_version" in relation:
            versioned_relation_count += 1
        else:
            unversioned_relation_count += 1

    counts = {
        "relation_count": relation_count,
        "versioned_relation_count": versioned_relation_count,
        "unversioned_relation_count": unversioned_relation_count,
        "malformed_relation_count": malformed_relation_count,
    }

    if malformed_relation_count:
        return SemanticRelationCompatibilityReport(
            status="malformed_relations",
            issue_code="relation_not_object",
            issue_index=first_malformed_index,
            **counts,
        )
    if relation_count == 0:
        return SemanticRelationCompatibilityReport(status="empty", **counts)
    if versioned_relation_count == 0:
        return SemanticRelationCompatibilityReport(status="legacy_unversioned", **counts)
    if unversioned_relation_count:
        first_unversioned_index = next(
            index
            for index, relation in enumerate(relations)
            if "contract_version" not in relation
        )
        return SemanticRelationCompatibilityReport(
            status="mixed_versioning",
            issue_code="mixed_relation_versioning",
            issue_index=first_unversioned_index,
            issue_field="contract_version",
            **counts,
        )

    for index, relation in enumerate(relations):
        item_version = relation["contract_version"]
        if type(item_version) is not str or item_version != RELATION_CONTRACT_VERSION:
            return SemanticRelationCompatibilityReport(
                status="unsupported_version",
                issue_code="unsupported_contract_version",
                issue_index=index,
                issue_field="contract_version",
                **counts,
            )

    try:
        validate_semantic_relation_list(
            relations,
            source_concept_id=source_concept_id,
            contract_version=RELATION_CONTRACT_VERSION,
        )
    except SemanticRelationContractError as exc:
        return SemanticRelationCompatibilityReport(
            status="invalid_v1",
            issue_code=exc.code,
            issue_index=exc.index,
            issue_field=exc.field,
            **counts,
        )

    return SemanticRelationCompatibilityReport(
        status="compatible_v1_shape",
        **counts,
    )


__all__ = [
    "COMPATIBILITY_STATUSES",
    "SemanticRelationCompatibilityReport",
    "classify_semantic_relation_compatibility",
]
