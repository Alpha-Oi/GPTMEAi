"""Pure validation for authored Semantic Relation contract payloads."""

from __future__ import annotations

RELATION_CONTRACT_VERSION = "semantic_relation.v1"
ALLOWED_RELATION_TYPES = (
    "supports",
    "contradicts",
    "refines",
    "depends_on",
    "derived_from",
    "evidences",
    "related_to",
)
REQUIRED_RELATION_FIELDS = frozenset(
    {
        "contract_version",
        "type",
        "target",
        "evidence_ref",
    }
)
MAX_RELATIONS_PER_NODE = 64
MAX_TARGET_LENGTH = 256
MAX_EVIDENCE_REF_LENGTH = 512


class SemanticRelationContractError(ValueError):
    """Stable validation error without exposing rejected payload values."""

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


def _is_canonical_string(value: object, *, max_length: int) -> bool:
    return (
        type(value) is str
        and bool(value)
        and value == value.strip()
        and len(value) <= max_length
    )


def validate_semantic_relation_list(
    relations: object,
    *,
    source_concept_id: object,
    contract_version: str = RELATION_CONTRACT_VERSION,
) -> list[dict[str, str]]:
    """Validate and copy authored relations without I/O, lookup, or mutation."""

    if type(contract_version) is not str or contract_version != RELATION_CONTRACT_VERSION:
        raise SemanticRelationContractError(
            "unsupported_contract_version",
            field="contract_version",
        )
    if not _is_canonical_string(source_concept_id, max_length=MAX_TARGET_LENGTH):
        raise SemanticRelationContractError(
            "invalid_source_concept_id",
            field="source_concept_id",
        )
    if type(relations) is not list:
        raise SemanticRelationContractError("relations_not_list", field="relations")
    if len(relations) > MAX_RELATIONS_PER_NODE:
        raise SemanticRelationContractError("relation_limit_exceeded", field="relations")

    validated: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for index, relation in enumerate(relations):
        if type(relation) is not dict:
            raise SemanticRelationContractError("relation_not_object", index=index)

        fields = set(relation)
        if not REQUIRED_RELATION_FIELDS.issubset(fields):
            raise SemanticRelationContractError("relation_missing_fields", index=index)
        if fields != REQUIRED_RELATION_FIELDS:
            raise SemanticRelationContractError("relation_unknown_fields", index=index)

        item_version = relation["contract_version"]
        relation_type = relation["type"]
        target = relation["target"]
        evidence_ref = relation["evidence_ref"]

        if type(item_version) is not str or item_version != contract_version:
            raise SemanticRelationContractError(
                "relation_contract_version_mismatch",
                index=index,
                field="contract_version",
            )
        if type(relation_type) is not str or relation_type not in ALLOWED_RELATION_TYPES:
            raise SemanticRelationContractError(
                "relation_type_not_allowed",
                index=index,
                field="type",
            )
        if not _is_canonical_string(target, max_length=MAX_TARGET_LENGTH):
            raise SemanticRelationContractError(
                "relation_target_invalid",
                index=index,
                field="target",
            )
        if not _is_canonical_string(evidence_ref, max_length=MAX_EVIDENCE_REF_LENGTH):
            raise SemanticRelationContractError(
                "relation_evidence_ref_invalid",
                index=index,
                field="evidence_ref",
            )
        if target == source_concept_id:
            raise SemanticRelationContractError(
                "relation_self_reference",
                index=index,
                field="target",
            )

        identity = (relation_type, target, evidence_ref)
        if identity in seen:
            raise SemanticRelationContractError("relation_duplicate", index=index)
        seen.add(identity)

        validated.append(
            {
                "contract_version": item_version,
                "type": relation_type,
                "target": target,
                "evidence_ref": evidence_ref,
            }
        )

    return validated


__all__ = [
    "ALLOWED_RELATION_TYPES",
    "MAX_EVIDENCE_REF_LENGTH",
    "MAX_RELATIONS_PER_NODE",
    "MAX_TARGET_LENGTH",
    "RELATION_CONTRACT_VERSION",
    "REQUIRED_RELATION_FIELDS",
    "SemanticRelationContractError",
    "validate_semantic_relation_list",
]
