"""Read-only fixture smoke for the Semantic Mesh inventory contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SERVICE_NAME = "AI OS Semantic Mesh Inventory Smoke"

ALLOWED_RELATION_TYPES = {
    "supports",
    "contradicts",
    "refines",
    "depends_on",
    "derived_from",
    "evidences",
    "related_to",
}
REQUIRED_CONCEPT_CORE_FIELDS = {
    "id",
    "type",
    "title",
    "content",
    "status",
    "source",
    "confidence",
    "context",
}
REQUIRED_DIAGNOSTICS = {
    "total_blocks",
    "strict_concept_blocks",
    "legacy_blocks",
    "malformed_concept_blocks",
    "relation_count",
    "dangling_relation_count",
    "weak_derived_relation_count",
    "unknown_relation_type_count",
}
STOP_WORDS = {
    "about",
    "and",
    "from",
    "into",
    "legacy",
    "memory",
    "strict",
    "that",
    "this",
    "with",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=SERVICE_NAME)
    parser.add_argument("--json", action="store_true", help="Print compact JSON summary.")
    parser.add_argument("--cleanup", action="store_true", help="Delete the temp root after the smoke.")
    return parser.parse_args()


def file_metadata(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"exists": False}
    stat = path.stat()
    return {
        "exists": True,
        "size": stat.st_size,
        "mtime": stat.st_mtime,
    }


def runtime_marker_path() -> Path:
    return PROJECT_ROOT / "GPTMemory_runtime.yaml"


def relation_id(source: str, relation_type: str, target: str, evidence_ref: str) -> str:
    basis = "\0".join([source, relation_type, target, evidence_ref])
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]
    return f"mesh-rel:{digest}"


def block_id(block: dict[str, Any]) -> str:
    return str(block.get("id") or "")


def tags_for(block: dict[str, Any]) -> list[str]:
    tags = block.get("tags")
    if not isinstance(tags, list):
        return []
    return sorted(str(tag) for tag in tags if str(tag).strip())


def words_for(text: object) -> set[str]:
    if not isinstance(text, str):
        return set()
    words = {word.lower() for word in re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", text)}
    return words - STOP_WORDS


def concept_core_for(block: dict[str, Any]) -> object:
    metadata = block.get("metadata")
    if not isinstance(metadata, dict):
        return None
    return metadata.get("concept_core")


def validate_concept_core(value: object) -> tuple[bool, list[str]]:
    if not isinstance(value, dict):
        return False, ["concept_core_not_object"]

    errors: list[str] = []
    missing = sorted(REQUIRED_CONCEPT_CORE_FIELDS - set(value))
    if missing:
        errors.append("missing_fields:" + ",".join(missing))

    confidence = value.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= confidence <= 1:
        errors.append("invalid_confidence")

    if not isinstance(value.get("context"), dict):
        errors.append("invalid_context")

    relations = value.get("relations", [])
    if not isinstance(relations, list):
        errors.append("invalid_relations")
    else:
        for index, relation in enumerate(relations):
            if not isinstance(relation, dict):
                errors.append(f"invalid_relation:{index}")
                continue
            if not relation.get("type") or not relation.get("target"):
                errors.append(f"incomplete_relation:{index}")

    return not errors, errors


def fixture_blocks() -> list[dict[str, Any]]:
    return [
        {
            "id": "block:legacy-overview",
            "text": "Legacy overview keeps mesh-signal inventory context visible.",
            "tags": ["mesh-signal", "legacy-overview"],
            "metadata": {"source": "semantic_mesh_inventory_fixture"},
        },
        {
            "id": "block:legacy-workflow",
            "text": "Workflow note preserves ordinary runtime notes.",
            "tags": ["workflow-note"],
            "metadata": {"source": "semantic_mesh_inventory_fixture"},
        },
        {
            "id": "block:concept-alpha",
            "text": "Alpha concept validates mesh-signal inventory behavior.",
            "tags": ["mesh-signal", "concept-core"],
            "metadata": {
                "concept_core": {
                    "id": "concept:alpha",
                    "type": "decision",
                    "title": "Alpha inventory concept",
                    "content": "Alpha concept validates Semantic Mesh inventory behavior.",
                    "status": "confirmed",
                    "source": "smoke_semantic_mesh_inventory",
                    "confidence": 0.91,
                    "context": {"stage": "B", "purpose": "inventory"},
                    "relations": [
                        {
                            "type": "supports",
                            "target": "concept:beta",
                            "evidence_ref": "block:concept-alpha",
                        }
                    ],
                }
            },
        },
        {
            "id": "block:concept-beta",
            "text": "Beta concept is a stable relation target.",
            "tags": ["concept-target"],
            "metadata": {
                "concept_core": {
                    "id": "concept:beta",
                    "type": "fact",
                    "title": "Beta target concept",
                    "content": "Beta concept is a stable relation target.",
                    "status": "confirmed",
                    "source": "smoke_semantic_mesh_inventory",
                    "confidence": 0.88,
                    "context": {"stage": "B", "purpose": "target"},
                    "relations": [],
                }
            },
        },
        {
            "id": "block:concept-dangling",
            "text": "Dangling concept references a target that is not present.",
            "tags": ["dangling-relation"],
            "metadata": {
                "concept_core": {
                    "id": "concept:dangling",
                    "type": "risk",
                    "title": "Dangling relation concept",
                    "content": "Dangling concept references a target that is not present.",
                    "status": "draft",
                    "source": "smoke_semantic_mesh_inventory",
                    "confidence": 0.72,
                    "context": {"stage": "B", "purpose": "dangling-diagnostic"},
                    "relations": [
                        {
                            "type": "depends_on",
                            "target": "concept:missing",
                            "evidence_ref": "block:concept-dangling",
                        }
                    ],
                }
            },
        },
        {
            "id": "block:concept-unknown",
            "text": "Unknown relation type is reported without failing inventory.",
            "tags": ["unknown-relation"],
            "metadata": {
                "concept_core": {
                    "id": "concept:unknown",
                    "type": "note",
                    "title": "Unknown relation type concept",
                    "content": "Unknown relation type is reported without failing inventory.",
                    "status": "draft",
                    "source": "smoke_semantic_mesh_inventory",
                    "confidence": 0.63,
                    "context": {"stage": "B", "purpose": "unknown-relation-diagnostic"},
                    "relations": [
                        {
                            "type": "blocks",
                            "target": "concept:beta",
                            "evidence_ref": "block:concept-unknown",
                        }
                    ],
                }
            },
        },
        {
            "id": "block:concept-malformed",
            "text": "Malformed concept metadata is diagnostic-only.",
            "tags": ["malformed-concept"],
            "metadata": {
                "concept_core": {
                    "id": "concept:malformed",
                    "type": "fact",
                    "title": "Malformed concept",
                    "content": "Malformed concept metadata is diagnostic-only.",
                    "confidence": 1.2,
                    "relations": "not-a-list",
                }
            },
        },
    ]


def explicit_relations_for(block: dict[str, Any], concept_core: dict[str, Any]) -> list[dict[str, Any]]:
    relations: list[dict[str, Any]] = []
    source = str(concept_core["id"])
    source_block = block_id(block)
    for index, relation in enumerate(concept_core.get("relations") or []):
        relation_type = str(relation.get("type"))
        target = str(relation.get("target"))
        evidence_ref = str(relation.get("evidence_ref") or source_block)
        diagnostics: list[str] = []
        if relation_type not in ALLOWED_RELATION_TYPES:
            diagnostics.append("unknown_relation_type")
        relations.append(
            {
                "id": relation_id(source, relation_type, target, evidence_ref),
                "source": source,
                "target": target,
                "type": relation_type,
                "strength": "explicit",
                "evidence_ref": evidence_ref,
                "memory_block_ref": source_block,
                "relation_index": index,
                "diagnostics": diagnostics,
            }
        )
    return relations


def weak_relation_for(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any] | None:
    shared_tags = sorted(set(left["tags"]) & set(right["tags"]))
    shared_words = sorted(words_for(left["text"]) & words_for(right["text"]))
    if not shared_tags and not shared_words:
        return None

    source = str(left["id"])
    target = str(right["id"])
    evidence_ref = "weak-derived:" + "|".join(
        [
            str(left["memory_block_ref"]),
            str(right["memory_block_ref"]),
            ",".join(shared_tags),
            ",".join(shared_words),
        ]
    )
    return {
        "id": relation_id(source, "related_to", target, evidence_ref),
        "source": source,
        "target": target,
        "type": "related_to",
        "strength": "weak_derived",
        "evidence_ref": evidence_ref,
        "memory_block_ref": str(left["memory_block_ref"]),
        "diagnostics": [],
        "weak_signal": {
            "shared_tags": shared_tags,
            "shared_words": shared_words,
        },
    }


def inventory_blocks(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
    malformed: list[dict[str, Any]] = []
    legacy_blocks = 0

    for block in blocks:
        concept_core = concept_core_for(block)
        if concept_core is None:
            legacy_blocks += 1
            nodes.append(
                {
                    "id": block_id(block),
                    "kind": "legacy_memory",
                    "memory_block_ref": block_id(block),
                    "text": block.get("text", ""),
                    "tags": tags_for(block),
                }
            )
            continue

        valid, errors = validate_concept_core(concept_core)
        if not valid:
            malformed.append({"memory_block_ref": block_id(block), "errors": errors})
            continue

        concept = dict(concept_core)
        nodes.append(
            {
                "id": str(concept["id"]),
                "kind": "strict_concept",
                "memory_block_ref": block_id(block),
                "text": block.get("text", ""),
                "tags": tags_for(block),
                "status": concept.get("status"),
                "source": concept.get("source"),
                "confidence": concept.get("confidence"),
                "context": concept.get("context"),
            }
        )
        relations.extend(explicit_relations_for(block, concept))

    target_ids = {str(node["id"]) for node in nodes}
    for relation in relations:
        if relation["target"] not in target_ids:
            relation["diagnostics"].append("dangling_relation_target")

    sorted_nodes = sorted(nodes, key=lambda item: str(item["id"]))
    existing_pairs = {(relation["source"], relation["target"]) for relation in relations}
    for index, left in enumerate(sorted_nodes):
        for right in sorted_nodes[index + 1 :]:
            weak_relation = weak_relation_for(left, right)
            if weak_relation is None:
                continue
            pair = (weak_relation["source"], weak_relation["target"])
            if pair in existing_pairs:
                continue
            relations.append(weak_relation)
            existing_pairs.add(pair)

    diagnostics = {
        "total_blocks": len(blocks),
        "strict_concept_blocks": sum(1 for node in nodes if node["kind"] == "strict_concept"),
        "legacy_blocks": legacy_blocks,
        "malformed_concept_blocks": len(malformed),
        "relation_count": len(relations),
        "dangling_relation_count": sum(
            1 for relation in relations if "dangling_relation_target" in relation["diagnostics"]
        ),
        "weak_derived_relation_count": sum(1 for relation in relations if relation["strength"] == "weak_derived"),
        "unknown_relation_type_count": sum(
            1 for relation in relations if "unknown_relation_type" in relation["diagnostics"]
        ),
        "explicit_relation_count": sum(1 for relation in relations if relation["strength"] == "explicit"),
        "known_explicit_relation_count": sum(
            1
            for relation in relations
            if relation["strength"] == "explicit" and "unknown_relation_type" not in relation["diagnostics"]
        ),
    }

    return {
        "nodes": nodes,
        "relations": sorted(relations, key=lambda item: str(item["id"])),
        "malformed_blocks": malformed,
        "diagnostics": diagnostics,
    }


def run_smoke(temp_root: Path) -> dict[str, Any]:
    temp_root.mkdir(parents=True, exist_ok=True)
    marker_file = temp_root / "semantic_mesh_inventory_marker.json"
    marker_file.write_text(
        json.dumps({"service": SERVICE_NAME, "writes": "temp-root-only"}, ensure_ascii=False),
        encoding="utf-8",
    )

    project_runtime_file = runtime_marker_path()
    project_runtime_before = file_metadata(project_runtime_file)

    blocks = fixture_blocks()
    inventory = inventory_blocks(blocks)
    second_inventory = inventory_blocks(fixture_blocks())

    diagnostics = dict(inventory["diagnostics"])
    relations = list(inventory["relations"])
    nodes = list(inventory["nodes"])
    weak_relations = [relation for relation in relations if relation["strength"] == "weak_derived"]

    project_runtime_after = file_metadata(project_runtime_file)

    checks = {
        "required_diagnostics_present": REQUIRED_DIAGNOSTICS.issubset(diagnostics),
        "fixture_total_blocks_counted": diagnostics["total_blocks"] == 7,
        "strict_concept_blocks_indexed": diagnostics["strict_concept_blocks"] == 4,
        "legacy_blocks_counted_not_promoted": diagnostics["legacy_blocks"] == 2
        and all(node["kind"] != "strict_concept" for node in nodes if str(node["id"]).startswith("block:legacy")),
        "malformed_concept_blocks_reported_not_fatal": diagnostics["malformed_concept_blocks"] == 1,
        "explicit_relations_counted": diagnostics["explicit_relation_count"] == 3,
        "dangling_relation_reported_not_fatal": diagnostics["dangling_relation_count"] == 1,
        "unknown_relation_type_reported_not_fatal": diagnostics["unknown_relation_type_count"] == 1,
        "weak_derived_relations_labeled": diagnostics["weak_derived_relation_count"] >= 1
        and all(relation.get("weak_signal") for relation in weak_relations),
        "every_node_has_memory_block_ref": bool(nodes) and all(node.get("memory_block_ref") for node in nodes),
        "every_relation_has_evidence_ref_where_possible": bool(relations)
        and all(relation.get("evidence_ref") for relation in relations),
        "deterministic_relation_ids": [relation["id"] for relation in relations]
        == [relation["id"] for relation in second_inventory["relations"]],
        "project_runtime_file_unchanged": project_runtime_before == project_runtime_after,
        "temp_root_marker_written": marker_file.exists(),
    }

    return {
        "status": "ok" if all(checks.values()) else "failed",
        "service": SERVICE_NAME,
        "checks": checks,
        "diagnostics": diagnostics,
        "details": {
            "allowed_relation_types": sorted(ALLOWED_RELATION_TYPES),
            "malformed_blocks": inventory["malformed_blocks"],
            "node_count": len(nodes),
            "relation_ids": [relation["id"] for relation in relations],
            "weak_relation_ids": [relation["id"] for relation in weak_relations],
            "project_runtime_file": str(project_runtime_file),
            "project_runtime_before": project_runtime_before,
            "project_runtime_after": project_runtime_after,
            "temp_root": str(temp_root),
        },
    }


def cleanup_temp_root(temp_root: Path) -> tuple[bool, str | None]:
    try:
        shutil.rmtree(temp_root, ignore_errors=False)
    except OSError as exc:
        return (not temp_root.exists(), str(exc))
    return (not temp_root.exists(), None)


def print_result(result: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
        return
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


def main() -> int:
    args = parse_args()
    temp_root = Path(tempfile.gettempdir()) / f"gptmeai_semantic_mesh_inventory_{uuid.uuid4().hex}"
    result: dict[str, Any] = {
        "status": "error",
        "service": SERVICE_NAME,
        "temp_root": str(temp_root),
    }

    try:
        result = run_smoke(temp_root)
        exit_code = 0 if result["status"] == "ok" else 1
    except Exception as exc:
        result = {
            "status": "error",
            "service": SERVICE_NAME,
            "temp_root": str(temp_root),
            "error": str(exc),
        }
        exit_code = 1
    finally:
        cleanup_succeeded = None
        cleanup_error = None
        if args.cleanup:
            cleanup_succeeded, cleanup_error = cleanup_temp_root(temp_root)
        result["cleanup_requested"] = bool(args.cleanup)
        result["cleanup_succeeded"] = cleanup_succeeded
        result["temp_root_exists_after_cleanup"] = temp_root.exists()
        if cleanup_error:
            result["cleanup_error"] = cleanup_error

    print_result(result, as_json=bool(args.json))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
