"""Read-only Semantic Mesh primitives for Concept Core memory records.

This module is intentionally library-only. It builds an advisory semantic index
from already-loaded memory blocks and does not read or write runtime storage,
register API routes, or enforce planner/runtime behavior.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from ai_os.concept_core import MemoryCommitValidator


ALLOWED_RELATION_TYPES = (
    "supports",
    "contradicts",
    "refines",
    "depends_on",
    "derived_from",
    "evidences",
    "related_to",
)
REQUIRED_DIAGNOSTICS = (
    "total_blocks",
    "strict_concept_blocks",
    "legacy_blocks",
    "malformed_concept_blocks",
    "relation_count",
    "dangling_relation_count",
    "weak_derived_relation_count",
    "unknown_relation_type_count",
)
STOP_WORDS = {
    "about",
    "also",
    "and",
    "from",
    "into",
    "keeps",
    "legacy",
    "memory",
    "note",
    "strict",
    "that",
    "this",
    "with",
}


@dataclass(frozen=True)
class SemanticMeshEvidenceRef:
    memory_block_id: Any
    field_path: str
    source: str
    status: str
    confidence: float
    context_keys: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_block_id": self.memory_block_id,
            "field_path": self.field_path,
            "source": self.source,
            "status": self.status,
            "confidence": self.confidence,
            "context_keys": list(self.context_keys),
        }


@dataclass(frozen=True)
class SemanticMeshNode:
    mesh_node_id: str
    concept_id: str | None
    memory_block_id: Any
    concept_type: str
    title: str
    status: str
    source: str
    confidence: float
    context: dict[str, Any]
    tags: list[str]
    created_at: str
    updated_at: str
    content_ref: dict[str, Any]
    raw_concept_core_ref: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "mesh_node_id": self.mesh_node_id,
            "concept_id": self.concept_id,
            "memory_block_id": self.memory_block_id,
            "concept_type": self.concept_type,
            "title": self.title,
            "status": self.status,
            "source": self.source,
            "confidence": self.confidence,
            "context": dict(self.context),
            "tags": list(self.tags),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "content_ref": dict(self.content_ref),
            "raw_concept_core_ref": dict(self.raw_concept_core_ref),
        }


@dataclass(frozen=True)
class SemanticMeshRelation:
    relation_id: str
    source_node_id: str
    target_node_id: str | None
    target_concept_id: str | None
    relation_type: str
    direction: str
    status: str
    confidence: float
    evidence_refs: list[SemanticMeshEvidenceRef]
    relation_source: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "relation_id": self.relation_id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "target_concept_id": self.target_concept_id,
            "relation_type": self.relation_type,
            "direction": self.direction,
            "status": self.status,
            "confidence": self.confidence,
            "evidence_refs": [item.to_dict() for item in self.evidence_refs],
            "relation_source": self.relation_source,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class SemanticMeshIndex:
    nodes: list[SemanticMeshNode]
    relations: list[SemanticMeshRelation]
    diagnostics: dict[str, int]
    malformed_blocks: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [node.to_dict() for node in self.nodes],
            "relations": [relation.to_dict() for relation in self.relations],
            "diagnostics": dict(self.diagnostics),
            "malformed_blocks": [dict(item) for item in self.malformed_blocks],
        }


def build_semantic_mesh(blocks: Iterable[dict[str, Any]]) -> SemanticMeshIndex:
    """Build an advisory Semantic Mesh index from loaded memory blocks."""

    block_list = [dict(block) for block in blocks if isinstance(block, dict)]
    nodes: list[SemanticMeshNode] = []
    explicit_relations: list[SemanticMeshRelation] = []
    malformed_blocks: list[dict[str, Any]] = []
    legacy_blocks = 0
    concept_id_to_node_id: dict[str, str] = {}
    node_payloads_by_id: dict[str, dict[str, Any]] = {}

    for block in block_list:
        memory_block_id = block.get("id")
        concept_core = _concept_core_for(block)
        if concept_core is None:
            legacy_blocks += 1
            legacy_node = _legacy_node(block)
            nodes.append(legacy_node)
            node_payloads_by_id[legacy_node.mesh_node_id] = _node_signal_payload(legacy_node, block)
            continue

        concept, errors = _validated_concept_core(concept_core)
        if concept is None:
            malformed_blocks.append(
                {
                    "memory_block_id": memory_block_id,
                    "field_path": "metadata.concept_core",
                    "errors": errors,
                }
            )
            continue

        node = _concept_node(block, concept)
        nodes.append(node)
        concept_id_to_node_id[str(node.concept_id)] = node.mesh_node_id
        node_payloads_by_id[node.mesh_node_id] = _node_signal_payload(node, block)

        explicit_relations.extend(_explicit_relations(block, concept, node))

    resolved_explicit_relations = [
        _resolve_relation_targets(relation, concept_id_to_node_id) for relation in explicit_relations
    ]
    weak_relations = _weak_derived_relations(sorted(node_payloads_by_id.values(), key=lambda item: item["mesh_node_id"]))
    all_relations = sorted(resolved_explicit_relations + weak_relations, key=lambda item: item.relation_id)

    diagnostics = {
        "total_blocks": len(block_list),
        "strict_concept_blocks": sum(1 for node in nodes if node.concept_id is not None),
        "legacy_blocks": legacy_blocks,
        "malformed_concept_blocks": len(malformed_blocks),
        "relation_count": len(all_relations),
        "dangling_relation_count": sum(
            1
            for relation in all_relations
            if "dangling_relation_target" in relation.metadata.get("diagnostics", [])
        ),
        "weak_derived_relation_count": sum(
            1 for relation in all_relations if relation.relation_source == "weak_derived"
        ),
        "unknown_relation_type_count": sum(
            1
            for relation in all_relations
            if "unknown_relation_type" in relation.metadata.get("diagnostics", [])
        ),
    }

    return SemanticMeshIndex(
        nodes=sorted(nodes, key=lambda item: item.mesh_node_id),
        relations=all_relations,
        diagnostics=diagnostics,
        malformed_blocks=malformed_blocks,
    )


def _concept_core_for(block: dict[str, Any]) -> object:
    metadata = block.get("metadata")
    if not isinstance(metadata, dict):
        return None
    return metadata.get("concept_core")


def _validated_concept_core(value: object) -> tuple[dict[str, Any] | None, list[str]]:
    if not isinstance(value, dict):
        return None, ["concept_core_not_object"]
    try:
        node = MemoryCommitValidator().validate(value)
    except ValueError as exc:
        return None, [str(exc)]
    return node.to_dict(), []


def _block_tags(block: dict[str, Any]) -> list[str]:
    tags = block.get("tags")
    if not isinstance(tags, list):
        return []
    return sorted(str(tag).strip() for tag in tags if str(tag).strip())


def _block_text(block: dict[str, Any]) -> str:
    return str(block.get("text") or "").strip()


def _text_title(text: str) -> str:
    words = str(text or "").strip().split()
    if not words:
        return "Legacy memory block"
    return " ".join(words[:8])


def _mesh_node_id(concept_id: str | None, memory_block_id: Any) -> str:
    if concept_id:
        return f"mesh-node:{concept_id}"
    return f"mesh-node:memory:{memory_block_id}"


def _legacy_node(block: dict[str, Any]) -> SemanticMeshNode:
    memory_block_id = block.get("id")
    text = _block_text(block)
    created_at = str(block.get("created_at") or "")
    return SemanticMeshNode(
        mesh_node_id=_mesh_node_id(None, memory_block_id),
        concept_id=None,
        memory_block_id=memory_block_id,
        concept_type="legacy_memory",
        title=_text_title(text),
        status="legacy",
        source="memory_block",
        confidence=0.0,
        context={},
        tags=_block_tags(block),
        created_at=created_at,
        updated_at=str(block.get("updated_at") or created_at),
        content_ref={
            "memory_block_id": memory_block_id,
            "field_path": "text",
        },
        raw_concept_core_ref={
            "memory_block_id": memory_block_id,
            "field_path": None,
            "source": "legacy_memory",
        },
    )


def _concept_node(block: dict[str, Any], concept: dict[str, Any]) -> SemanticMeshNode:
    memory_block_id = block.get("id")
    created_at = str(concept.get("created_at") or block.get("created_at") or "")
    return SemanticMeshNode(
        mesh_node_id=_mesh_node_id(str(concept.get("id")), memory_block_id),
        concept_id=str(concept.get("id")),
        memory_block_id=memory_block_id,
        concept_type=str(concept.get("type") or ""),
        title=str(concept.get("title") or ""),
        status=str(concept.get("status") or ""),
        source=str(concept.get("source") or ""),
        confidence=_safe_float(concept.get("confidence")),
        context=dict(concept.get("context") or {}),
        tags=_block_tags(block),
        created_at=created_at,
        updated_at=str(concept.get("updated_at") or block.get("updated_at") or created_at),
        content_ref={
            "memory_block_id": memory_block_id,
            "field_path": "text",
        },
        raw_concept_core_ref={
            "memory_block_id": memory_block_id,
            "field_path": "metadata.concept_core",
        },
    )


def _node_signal_payload(node: SemanticMeshNode, block: dict[str, Any]) -> dict[str, Any]:
    return {
        "mesh_node_id": node.mesh_node_id,
        "memory_block_id": node.memory_block_id,
        "text": _block_text(block),
        "tags": list(node.tags),
        "status": node.status,
        "confidence": node.confidence,
        "context_keys": sorted(node.context),
    }


def _explicit_relations(
    block: dict[str, Any],
    concept: dict[str, Any],
    node: SemanticMeshNode,
) -> list[SemanticMeshRelation]:
    relations: list[SemanticMeshRelation] = []
    raw_relations = concept.get("relations") or []
    if not isinstance(raw_relations, list):
        return relations

    for index, raw_relation in enumerate(raw_relations):
        if not isinstance(raw_relation, dict):
            continue

        relation_type = str(raw_relation.get("type") or "").strip()
        target_concept_id = str(raw_relation.get("target") or "").strip() or None
        diagnostics: list[str] = []
        if relation_type not in ALLOWED_RELATION_TYPES:
            diagnostics.append("unknown_relation_type")

        evidence_ref = SemanticMeshEvidenceRef(
            memory_block_id=block.get("id"),
            field_path=f"metadata.concept_core.relations[{index}]",
            source="explicit_concept_core",
            status=node.status,
            confidence=node.confidence,
            context_keys=tuple(sorted(node.context)),
        )
        relation_id = _relation_id(
            node.mesh_node_id,
            relation_type,
            target_concept_id or "",
            evidence_ref.field_path,
            "explicit_concept_core",
        )

        relations.append(
            SemanticMeshRelation(
                relation_id=relation_id,
                source_node_id=node.mesh_node_id,
                target_node_id=None,
                target_concept_id=target_concept_id,
                relation_type=relation_type,
                direction="outbound",
                status="diagnostic" if diagnostics else "advisory",
                confidence=node.confidence,
                evidence_refs=[evidence_ref],
                relation_source="explicit_concept_core",
                metadata={
                    "relation_index": index,
                    "diagnostics": diagnostics,
                    "raw_relation": dict(raw_relation),
                },
            )
        )

    return relations


def _resolve_relation_targets(
    relation: SemanticMeshRelation,
    concept_id_to_node_id: dict[str, str],
) -> SemanticMeshRelation:
    target_node_id = concept_id_to_node_id.get(str(relation.target_concept_id))
    diagnostics = list(relation.metadata.get("diagnostics", []))
    if relation.target_concept_id and target_node_id is None:
        diagnostics.append("dangling_relation_target")

    metadata = dict(relation.metadata)
    metadata["diagnostics"] = diagnostics
    status = "diagnostic" if diagnostics else relation.status

    return SemanticMeshRelation(
        relation_id=relation.relation_id,
        source_node_id=relation.source_node_id,
        target_node_id=target_node_id,
        target_concept_id=relation.target_concept_id,
        relation_type=relation.relation_type,
        direction=relation.direction,
        status=status,
        confidence=relation.confidence,
        evidence_refs=relation.evidence_refs,
        relation_source=relation.relation_source,
        metadata=metadata,
    )


def _weak_derived_relations(node_payloads: list[dict[str, Any]]) -> list[SemanticMeshRelation]:
    relations: list[SemanticMeshRelation] = []
    for index, left in enumerate(node_payloads):
        for right in node_payloads[index + 1 :]:
            shared_tags = sorted(set(left["tags"]) & set(right["tags"]))
            shared_words = sorted(_words(left["text"]) & _words(right["text"]))
            if not shared_tags and not shared_words:
                continue

            evidence_ref = SemanticMeshEvidenceRef(
                memory_block_id=left["memory_block_id"],
                field_path="text,tags",
                source="weak_derived",
                status="inference",
                confidence=0.25,
                context_keys=(),
            )
            relation_id = _relation_id(
                left["mesh_node_id"],
                "related_to",
                right["mesh_node_id"],
                "|".join(shared_tags + shared_words),
                "weak_derived",
            )
            relations.append(
                SemanticMeshRelation(
                    relation_id=relation_id,
                    source_node_id=left["mesh_node_id"],
                    target_node_id=right["mesh_node_id"],
                    target_concept_id=None,
                    relation_type="related_to",
                    direction="undirected",
                    status="weak_signal",
                    confidence=0.25,
                    evidence_refs=[evidence_ref],
                    relation_source="weak_derived",
                    metadata={
                        "diagnostics": [],
                        "weak_signal": {
                            "shared_tags": shared_tags,
                            "shared_words": shared_words,
                        },
                    },
                )
            )
    return relations


def _words(text: str) -> set[str]:
    words = {word.lower() for word in re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", str(text or ""))}
    return words - STOP_WORDS


def _relation_id(source: str, relation_type: str, target: str, evidence: str, relation_source: str) -> str:
    basis = "\0".join([source, relation_type, target, evidence, relation_source])
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]
    return f"mesh-rel:{digest}"


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


__all__ = [
    "ALLOWED_RELATION_TYPES",
    "REQUIRED_DIAGNOSTICS",
    "SemanticMeshEvidenceRef",
    "SemanticMeshIndex",
    "SemanticMeshNode",
    "SemanticMeshRelation",
    "build_semantic_mesh",
]
