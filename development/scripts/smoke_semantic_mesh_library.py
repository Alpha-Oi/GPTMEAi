"""Library-only smoke for the read-only Semantic Mesh model."""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SERVICE_NAME = "AI OS Semantic Mesh Library Smoke"
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


def fixture_blocks() -> list[dict[str, Any]]:
    return [
        {
            "id": 1,
            "text": "Legacy mesh signal note for weak derived coverage.",
            "tags": ["mesh-signal", "legacy"],
            "created_at": "2026-05-02T00:00:00+00:00",
        },
        {
            "id": 2,
            "text": "Strict alpha concept supports beta concept.",
            "tags": ["mesh-signal", "concept-core"],
            "created_at": "2026-05-02T00:01:00+00:00",
            "metadata": {
                "concept_core": {
                    "id": "concept:alpha",
                    "type": "decision",
                    "title": "Alpha concept",
                    "content": "Strict alpha concept supports beta concept.",
                    "status": "confirmed",
                    "source": "smoke_semantic_mesh_library",
                    "confidence": 0.91,
                    "context": {"stage": "C", "role": "source"},
                    "relations": [
                        {
                            "type": "supports",
                            "target": "concept:beta",
                            "evidence_ref": "memory:2",
                        }
                    ],
                    "created_at": "2026-05-02T00:01:00+00:00",
                    "updated_at": "2026-05-02T00:01:00+00:00",
                }
            },
        },
        {
            "id": 3,
            "text": "Strict beta concept is the explicit target.",
            "tags": ["concept-target"],
            "created_at": "2026-05-02T00:02:00+00:00",
            "metadata": {
                "concept_core": {
                    "id": "concept:beta",
                    "type": "fact",
                    "title": "Beta concept",
                    "content": "Strict beta concept is the explicit target.",
                    "status": "confirmed",
                    "source": "smoke_semantic_mesh_library",
                    "confidence": 0.89,
                    "context": {"stage": "C", "role": "target"},
                    "relations": [],
                    "created_at": "2026-05-02T00:02:00+00:00",
                    "updated_at": "2026-05-02T00:02:00+00:00",
                }
            },
        },
        {
            "id": 4,
            "text": "Dangling strict concept reports missing target.",
            "tags": ["dangling"],
            "created_at": "2026-05-02T00:03:00+00:00",
            "metadata": {
                "concept_core": {
                    "id": "concept:dangling",
                    "type": "risk",
                    "title": "Dangling concept",
                    "content": "Dangling strict concept reports missing target.",
                    "status": "hypothesis",
                    "source": "smoke_semantic_mesh_library",
                    "confidence": 0.61,
                    "context": {"stage": "C", "role": "dangling"},
                    "relations": [{"type": "depends_on", "target": "concept:missing"}],
                }
            },
        },
        {
            "id": 5,
            "text": "Unknown relation type stays diagnostic only.",
            "tags": ["unknown-relation"],
            "created_at": "2026-05-02T00:04:00+00:00",
            "metadata": {
                "concept_core": {
                    "id": "concept:unknown",
                    "type": "note",
                    "title": "Unknown relation concept",
                    "content": "Unknown relation type stays diagnostic only.",
                    "status": "unknown",
                    "source": "smoke_semantic_mesh_library",
                    "confidence": 0.52,
                    "context": {"stage": "C", "role": "unknown_relation"},
                    "relations": [{"type": "blocks", "target": "concept:beta"}],
                }
            },
        },
        {
            "id": 6,
            "text": "Malformed strict concept is reported, not repaired.",
            "tags": ["malformed"],
            "created_at": "2026-05-02T00:05:00+00:00",
            "metadata": {"concept_core": {"id": "concept:broken", "confidence": 2, "relations": "bad"}},
        },
    ]


def run_smoke(temp_root: Path) -> dict[str, Any]:
    from ai_os.semantic_mesh import ALLOWED_RELATION_TYPES, build_semantic_mesh

    temp_root.mkdir(parents=True, exist_ok=True)
    marker_file = temp_root / "semantic_mesh_library_marker.json"
    marker_file.write_text(json.dumps({"service": SERVICE_NAME}, ensure_ascii=False), encoding="utf-8")

    project_runtime_file = PROJECT_ROOT / "GPTMemory_runtime.yaml"
    project_runtime_before = file_metadata(project_runtime_file)

    blocks = fixture_blocks()
    original_blocks = copy.deepcopy(blocks)
    mesh = build_semantic_mesh(blocks)
    second_mesh = build_semantic_mesh(fixture_blocks())
    payload = mesh.to_dict()
    second_payload = second_mesh.to_dict()

    diagnostics = dict(payload["diagnostics"])
    nodes = list(payload["nodes"])
    relations = list(payload["relations"])
    explicit_relations = [
        relation for relation in relations if relation["relation_source"] == "explicit_concept_core"
    ]
    weak_relations = [relation for relation in relations if relation["relation_source"] == "weak_derived"]

    project_runtime_after = file_metadata(project_runtime_file)
    relation_ids = [relation["relation_id"] for relation in relations]
    second_relation_ids = [relation["relation_id"] for relation in second_payload["relations"]]

    checks = {
        "allowed_relation_types_exported": {
            "supports",
            "contradicts",
            "refines",
            "depends_on",
            "derived_from",
            "evidences",
            "related_to",
        }.issubset(set(ALLOWED_RELATION_TYPES)),
        "required_diagnostics_present": REQUIRED_DIAGNOSTICS.issubset(diagnostics),
        "strict_concept_nodes_indexed": diagnostics["strict_concept_blocks"] == 4,
        "legacy_blocks_counted": diagnostics["legacy_blocks"] == 1,
        "malformed_concept_reported_not_fatal": diagnostics["malformed_concept_blocks"] == 1,
        "explicit_relations_counted": len(explicit_relations) == 3,
        "dangling_relation_reported_not_fatal": diagnostics["dangling_relation_count"] == 1,
        "unknown_relation_type_reported_not_fatal": diagnostics["unknown_relation_type_count"] == 1,
        "weak_derived_relations_labeled": diagnostics["weak_derived_relation_count"] >= 1
        and all(relation.get("metadata", {}).get("weak_signal") for relation in weak_relations),
        "every_node_points_to_original_memory_block": bool(nodes)
        and all(node.get("memory_block_id") is not None for node in nodes),
        "every_node_has_content_and_raw_refs": bool(nodes)
        and all(node.get("content_ref") for node in nodes)
        and all(node.get("raw_concept_core_ref") is not None for node in nodes),
        "every_relation_has_evidence_refs": bool(relations)
        and all(relation.get("evidence_refs") for relation in relations),
        "relation_ids_are_deterministic": relation_ids == second_relation_ids,
        "source_blocks_not_mutated": blocks == original_blocks,
        "project_runtime_file_unchanged": project_runtime_before == project_runtime_after,
        "temp_root_marker_written": marker_file.exists(),
    }

    return {
        "status": "ok" if all(checks.values()) else "failed",
        "service": SERVICE_NAME,
        "checks": checks,
        "diagnostics": diagnostics,
        "details": {
            "node_count": len(nodes),
            "relation_count": len(relations),
            "relation_ids": relation_ids,
            "weak_relation_ids": [relation["relation_id"] for relation in weak_relations],
            "project_runtime_file": str(project_runtime_file),
            "project_runtime_before": project_runtime_before,
            "project_runtime_after": project_runtime_after,
            "temp_root": str(temp_root),
        },
    }


def cleanup_temp_root(temp_root: Path) -> tuple[bool, str | None]:
    if not temp_root.exists():
        return True, None
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
    temp_root = Path(tempfile.gettempdir()) / f"gptmeai_semantic_mesh_library_{uuid.uuid4().hex}"
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
