"""Temp-state smoke for exact opt-in Semantic Relation writer validation."""

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

SERVICE_NAME = "AI OS Semantic Relation Writer Smoke"
CONTRACT_VERSION = "semantic_relation.v1"


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


def concept_payload(**overrides: object) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": "concept:writer-source",
        "type": "decision",
        "title": "Semantic Relation writer source",
        "content": "Validate authored relations before the memory write.",
        "status": "confirmed",
        "source": "smoke_semantic_relation_writer",
        "confidence": 0.93,
        "context": {"stage": "F2A", "mode": "direct-library"},
        "relations": [
            {
                "contract_version": CONTRACT_VERSION,
                "type": "supports",
                "target": "concept:writer-target",
                "evidence_ref": "memory:writer-evidence",
            }
        ],
    }
    payload.update(overrides)
    return payload


def rejection_code_without_write(
    engine: object,
    payload: dict[str, Any],
    *,
    relation_contract_version: object,
) -> tuple[str | None, bool]:
    from ai_os.semantic_relation_contract import SemanticRelationContractError

    before = engine.count()
    try:
        engine.add_concept_node(
            payload,
            relation_contract_version=relation_contract_version,
        )
    except SemanticRelationContractError as exc:
        return exc.code, engine.count() == before
    return None, False


def run_smoke(temp_root: Path) -> dict[str, Any]:
    from ai_os.concept_core import MemoryCommitValidator
    from ai_os.semantic_mesh import build_semantic_mesh
    from ai_os.semantic_relation_contract import SemanticRelationContractError
    from core.memory_engine import MemoryEngine
    import scripts.runtime_store as runtime_store

    temp_root.mkdir(parents=True, exist_ok=True)
    temp_runtime_file = temp_root / "GPTMemory_runtime.json"
    project_runtime_file = PROJECT_ROOT / "GPTMemory_runtime.yaml"
    project_runtime_before = file_metadata(project_runtime_file)
    previous_runtime_file = runtime_store.RUNTIME_FILE
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {
        "temp_runtime_file": str(temp_runtime_file),
        "project_runtime_file": str(project_runtime_file),
    }

    try:
        runtime_store.RUNTIME_FILE = temp_runtime_file
        engine = MemoryEngine()

        legacy_block = engine.add("plain text")
        checks["legacy_add_unchanged"] = legacy_block.get("text") == "plain text"

        permissive_payload = concept_payload(
            id="concept:legacy-permissive",
            relations=[{"type": "supports", "target": "concept:legacy-target"}],
        )
        permissive_block = engine.add_concept_node(permissive_payload)
        permissive_relations = permissive_block["metadata"]["concept_core"]["relations"]
        checks["default_writer_remains_permissive"] = permissive_relations == permissive_payload["relations"]

        strict_payload = concept_payload()
        strict_payload_before = copy.deepcopy(strict_payload)
        direct_node = MemoryCommitValidator().validate(
            strict_payload,
            relation_contract_version=CONTRACT_VERSION,
        )
        direct_relations = direct_node.to_dict()["relations"]
        checks["validator_opt_in_accepts_exact_contract"] = direct_relations == strict_payload["relations"]
        checks["validator_returns_fresh_relations"] = direct_relations is not strict_payload["relations"]
        checks["validator_does_not_mutate_input"] = strict_payload == strict_payload_before

        strict_block = engine.add_concept_node(
            strict_payload,
            tags=["semantic-relation"],
            importance=8,
            relation_contract_version=CONTRACT_VERSION,
        )
        stored_relations = strict_block["metadata"]["concept_core"]["relations"]
        checks["engine_opt_in_stores_canonical_relations"] = stored_relations == strict_payload["relations"]
        checks["engine_does_not_mutate_input"] = strict_payload == strict_payload_before

        missing_relations_payload = concept_payload(id="concept:no-relations")
        missing_relations_payload.pop("relations")
        missing_relations_block = engine.add_concept_node(
            missing_relations_payload,
            relation_contract_version=CONTRACT_VERSION,
        )
        checks["missing_relations_key_defaults_to_empty_list"] = (
            missing_relations_block["metadata"]["concept_core"]["relations"] == []
        )

        invalid_cases: dict[str, tuple[dict[str, Any], object, str]] = {
            "explicit_none": (concept_payload(relations=None), CONTRACT_VERSION, "relations_not_list"),
            "non_list": (concept_payload(relations={}), CONTRACT_VERSION, "relations_not_list"),
            "missing_evidence": (
                concept_payload(
                    relations=[
                        {
                            "contract_version": CONTRACT_VERSION,
                            "type": "supports",
                            "target": "concept:writer-target",
                        }
                    ]
                ),
                CONTRACT_VERSION,
                "relation_missing_fields",
            ),
            "unknown_type": (
                concept_payload(relations=[{**strict_payload["relations"][0], "type": "blocks"}]),
                CONTRACT_VERSION,
                "relation_type_not_allowed",
            ),
            "duplicate": (
                concept_payload(relations=[strict_payload["relations"][0], strict_payload["relations"][0]]),
                CONTRACT_VERSION,
                "relation_duplicate",
            ),
            "self_reference": (
                concept_payload(relations=[{**strict_payload["relations"][0], "target": "concept:writer-source"}]),
                CONTRACT_VERSION,
                "relation_self_reference",
            ),
            "unknown_field": (
                concept_payload(relations=[{**strict_payload["relations"][0], "relation_id": "generated:no"}]),
                CONTRACT_VERSION,
                "relation_unknown_fields",
            ),
            "unsupported_version": (
                concept_payload(),
                "semantic_relation.v2",
                "unsupported_contract_version",
            ),
            "non_string_version": (
                concept_payload(),
                True,
                "unsupported_contract_version",
            ),
            "non_canonical_source_id": (
                concept_payload(id=" concept:writer-source "),
                CONTRACT_VERSION,
                "invalid_source_concept_id",
            ),
        }
        rejection_codes: dict[str, str | None] = {}
        rejection_writes: dict[str, bool] = {}
        for name, (payload, version, expected_code) in invalid_cases.items():
            code, no_write = rejection_code_without_write(
                engine,
                payload,
                relation_contract_version=version,
            )
            rejection_codes[name] = code
            rejection_writes[name] = no_write
            checks[f"rejects_{name}_with_typed_code"] = code == expected_code
            checks[f"rejects_{name}_without_write"] = no_write

        validator_rejected_none = False
        try:
            MemoryCommitValidator().validate(
                concept_payload(relations=None),
                relation_contract_version=CONTRACT_VERSION,
            )
        except SemanticRelationContractError as exc:
            validator_rejected_none = exc.code == "relations_not_list"
        checks["validator_preserves_typed_error"] = validator_rejected_none

        mesh_payload = build_semantic_mesh([strict_block]).to_dict()
        explicit_relations = [
            relation
            for relation in mesh_payload["relations"]
            if relation["relation_source"] == "explicit_concept_core"
        ]
        checks["semantic_mesh_reads_written_relation"] = len(explicit_relations) == 1
        if explicit_relations:
            mesh_relation = explicit_relations[0]
            checks["semantic_mesh_relation_identity_preserved"] = (
                mesh_relation["relation_type"] == "supports"
                and mesh_relation["target_concept_id"] == "concept:writer-target"
            )
            checks["authored_evidence_ref_remains_raw_metadata"] = (
                mesh_relation["metadata"]["raw_relation"]["evidence_ref"]
                == "memory:writer-evidence"
            )
            checks["generated_evidence_ref_semantics_unchanged"] = (
                mesh_relation["evidence_refs"][0]["source"] == "explicit_concept_core"
            )
        else:
            checks["semantic_mesh_relation_identity_preserved"] = False
            checks["authored_evidence_ref_remains_raw_metadata"] = False
            checks["generated_evidence_ref_semantics_unchanged"] = False

        checks["invalid_opt_in_payloads_did_not_add_blocks"] = engine.count() == 4
        checks["temp_runtime_file_used"] = temp_runtime_file.exists()
        details["rejection_codes"] = rejection_codes
        details["rejection_writes"] = rejection_writes
        details["stored_relations"] = stored_relations
    finally:
        runtime_store.RUNTIME_FILE = previous_runtime_file

    project_runtime_after = file_metadata(project_runtime_file)
    checks["project_runtime_file_unchanged"] = project_runtime_before == project_runtime_after
    details["project_runtime_before"] = project_runtime_before
    details["project_runtime_after"] = project_runtime_after

    return {
        "status": "ok" if all(checks.values()) else "failed",
        "service": SERVICE_NAME,
        "checks": checks,
        "details": details,
    }


def cleanup_temp_root(temp_root: Path) -> tuple[bool, str | None]:
    if not temp_root.exists():
        return True, None
    try:
        shutil.rmtree(temp_root, ignore_errors=False)
    except OSError as exc:
        return (not temp_root.exists(), str(exc))
    return (not temp_root.exists(), None)


def apply_cleanup_outcome(
    result: dict[str, Any],
    *,
    cleanup_requested: bool,
    cleanup_succeeded: bool | None,
    temp_root_exists: bool,
    cleanup_error: str | None,
) -> int:
    result["cleanup_requested"] = cleanup_requested
    result["cleanup_succeeded"] = cleanup_succeeded
    result["temp_root_exists_after_cleanup"] = temp_root_exists
    if cleanup_error:
        result["cleanup_error"] = cleanup_error

    cleanup_failed = cleanup_requested and (
        cleanup_succeeded is not True or temp_root_exists
    )
    if cleanup_failed and result.get("status") == "ok":
        result["status"] = "failed"
    return 0 if result.get("status") == "ok" and not cleanup_failed else 1


def print_result(result: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
        return
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


def main() -> int:
    args = parse_args()
    temp_root = Path(tempfile.gettempdir()) / f"gptmeai_semantic_relation_writer_{uuid.uuid4().hex}"
    result: dict[str, Any] = {
        "status": "error",
        "service": SERVICE_NAME,
        "temp_root": str(temp_root),
    }
    cleanup_succeeded = None
    cleanup_error = None
    try:
        result = run_smoke(temp_root)
    except Exception as exc:
        result = {
            "status": "error",
            "service": SERVICE_NAME,
            "temp_root": str(temp_root),
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    finally:
        if args.cleanup:
            cleanup_succeeded, cleanup_error = cleanup_temp_root(temp_root)

    exit_code = apply_cleanup_outcome(
        result,
        cleanup_requested=bool(args.cleanup),
        cleanup_succeeded=cleanup_succeeded,
        temp_root_exists=temp_root.exists(),
        cleanup_error=cleanup_error,
    )
    print_result(result, as_json=bool(args.json))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
