"""Pure in-memory smoke for the versioned Semantic Relation contract."""

from __future__ import annotations

import argparse
import ast
import copy
import json
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SERVICE_NAME = "AI OS Semantic Relation Contract Smoke"
EXPECTED_RELATION_TYPES = {
    "supports",
    "contradicts",
    "refines",
    "depends_on",
    "derived_from",
    "evidences",
    "related_to",
}
EXPECTED_FIELDS = {
    "contract_version",
    "type",
    "target",
    "evidence_ref",
}


class _VersionEqualitySpoof:
    def __eq__(self, other: object) -> bool:
        return True

    def __ne__(self, other: object) -> bool:
        return False


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


def directory_snapshot(path: Path) -> list[str]:
    if not path.exists():
        return []
    return sorted(str(item.relative_to(path)) for item in path.rglob("*"))


def valid_relation(**overrides: object) -> dict[str, object]:
    relation: dict[str, object] = {
        "contract_version": "semantic_relation.v1",
        "type": "supports",
        "target": "concept:beta",
        "evidence_ref": "memory:source-alpha",
    }
    relation.update(overrides)
    return relation


def error_code(call: Callable[[], object], error_type: type[Exception]) -> str | None:
    try:
        call()
    except error_type as exc:
        return getattr(exc, "code", None)
    return None


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add((node.module or "").split(".", 1)[0])
    return modules


def direct_call_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def run_smoke(temp_root: Path) -> dict[str, Any]:
    from ai_os.semantic_mesh import ALLOWED_RELATION_TYPES as MESH_RELATION_TYPES
    from ai_os.semantic_relation_contract import (
        ALLOWED_RELATION_TYPES,
        MAX_RELATIONS_PER_NODE,
        RELATION_CONTRACT_VERSION,
        SemanticRelationContractError,
        validate_semantic_relation_list as contract_validate,
    )

    def validate_semantic_relation_list(
        relations: object,
        *,
        source_concept_id: object,
        contract_version: object = RELATION_CONTRACT_VERSION,
    ) -> list[dict[str, str]]:
        with patch(
            "builtins.open",
            side_effect=AssertionError("validator_file_io_forbidden"),
        ):
            return contract_validate(
                relations,
                source_concept_id=source_concept_id,
                contract_version=contract_version,
            )

    temp_root.mkdir(parents=True, exist_ok=True)
    temp_before = directory_snapshot(temp_root)
    project_runtime_file = PROJECT_ROOT / "GPTMemory_runtime.yaml"
    project_runtime_before = file_metadata(project_runtime_file)
    contract_path = PROJECT_ROOT / "ai_os" / "semantic_relation_contract.py"

    source_relations = [valid_relation()]
    original_relations = copy.deepcopy(source_relations)
    validated = validate_semantic_relation_list(
        source_relations,
        source_concept_id="concept:alpha",
    )
    validated_again = validate_semantic_relation_list(
        source_relations,
        source_concept_id="concept:alpha",
    )
    allowed_relations = [
        valid_relation(
            type=relation_type,
            target=f"concept:target-{index}",
            evidence_ref=f"memory:evidence-{index}",
        )
        for index, relation_type in enumerate(sorted(EXPECTED_RELATION_TYPES))
    ]
    allowed_result = validate_semantic_relation_list(
        allowed_relations,
        source_concept_id="concept:alpha",
    )
    dangling_result = validate_semantic_relation_list(
        [valid_relation(target="concept:not-yet-present")],
        source_concept_id="concept:alpha",
    )
    empty_result = validate_semantic_relation_list([], source_concept_id="concept:alpha")

    error_cases: dict[str, tuple[str, Callable[[], object]]] = {
        "unsupported_contract_version": (
            "unsupported_contract_version",
            lambda: validate_semantic_relation_list(
                [],
                source_concept_id="concept:alpha",
                contract_version="semantic_relation.v2",
            ),
        ),
        "non_string_contract_version": (
            "unsupported_contract_version",
            lambda: validate_semantic_relation_list(
                [],
                source_concept_id="concept:alpha",
                contract_version=_VersionEqualitySpoof(),
            ),
        ),
        "invalid_source_concept_id": (
            "invalid_source_concept_id",
            lambda: validate_semantic_relation_list([], source_concept_id=" concept:alpha "),
        ),
        "relations_not_list": (
            "relations_not_list",
            lambda: validate_semantic_relation_list({}, source_concept_id="concept:alpha"),
        ),
        "relation_limit_exceeded": (
            "relation_limit_exceeded",
            lambda: validate_semantic_relation_list(
                [
                    valid_relation(
                        target=f"concept:target-{index}",
                        evidence_ref=f"memory:evidence-{index}",
                    )
                    for index in range(MAX_RELATIONS_PER_NODE + 1)
                ],
                source_concept_id="concept:alpha",
            ),
        ),
        "relation_not_object": (
            "relation_not_object",
            lambda: validate_semantic_relation_list(["supports"], source_concept_id="concept:alpha"),
        ),
        "relation_missing_fields": (
            "relation_missing_fields",
            lambda: validate_semantic_relation_list(
                [{"contract_version": RELATION_CONTRACT_VERSION}],
                source_concept_id="concept:alpha",
            ),
        ),
        "relation_unknown_fields": (
            "relation_unknown_fields",
            lambda: validate_semantic_relation_list(
                [valid_relation(relation_id="generated:not-authored")],
                source_concept_id="concept:alpha",
            ),
        ),
        "relation_contract_version_mismatch": (
            "relation_contract_version_mismatch",
            lambda: validate_semantic_relation_list(
                [valid_relation(contract_version="semantic_relation.v2")],
                source_concept_id="concept:alpha",
            ),
        ),
        "relation_non_string_contract_version": (
            "relation_contract_version_mismatch",
            lambda: validate_semantic_relation_list(
                [valid_relation(contract_version=_VersionEqualitySpoof())],
                source_concept_id="concept:alpha",
            ),
        ),
        "relation_type_not_allowed": (
            "relation_type_not_allowed",
            lambda: validate_semantic_relation_list(
                [valid_relation(type="blocks")],
                source_concept_id="concept:alpha",
            ),
        ),
        "relation_target_invalid": (
            "relation_target_invalid",
            lambda: validate_semantic_relation_list(
                [valid_relation(target=" concept:beta ")],
                source_concept_id="concept:alpha",
            ),
        ),
        "relation_evidence_ref_invalid": (
            "relation_evidence_ref_invalid",
            lambda: validate_semantic_relation_list(
                [valid_relation(evidence_ref="")],
                source_concept_id="concept:alpha",
            ),
        ),
        "relation_self_reference": (
            "relation_self_reference",
            lambda: validate_semantic_relation_list(
                [valid_relation(target="concept:alpha")],
                source_concept_id="concept:alpha",
            ),
        ),
        "relation_duplicate": (
            "relation_duplicate",
            lambda: validate_semantic_relation_list(
                [valid_relation(), valid_relation()],
                source_concept_id="concept:alpha",
            ),
        ),
    }
    rejection_checks = {
        name: error_code(call, SemanticRelationContractError) == expected_code
        for name, (expected_code, call) in error_cases.items()
    }

    invalid_string_cases = {
        "target_non_string": [valid_relation(target=7)],
        "target_empty": [valid_relation(target="")],
        "target_too_long": [valid_relation(target="x" * 257)],
        "evidence_non_string": [valid_relation(evidence_ref=7)],
        "evidence_whitespace": [valid_relation(evidence_ref=" memory:alpha ")],
        "evidence_too_long": [valid_relation(evidence_ref="x" * 513)],
    }
    invalid_string_checks = {
        name: error_code(
            lambda relations=relations: validate_semantic_relation_list(
                relations,
                source_concept_id="concept:alpha",
            ),
            SemanticRelationContractError,
        )
        == ("relation_target_invalid" if name.startswith("target_") else "relation_evidence_ref_invalid")
        for name, relations in invalid_string_cases.items()
    }

    io_guard_probe_passed = False
    try:
        with patch(
            "builtins.open",
            side_effect=AssertionError("validator_file_io_forbidden"),
        ):
            open(temp_root / "io_guard_probe.txt", "w", encoding="utf-8")
    except AssertionError:
        io_guard_probe_passed = True

    cleanup_probe_result: dict[str, Any] = {"status": "ok"}
    cleanup_probe_exit_code = apply_cleanup_outcome(
        cleanup_probe_result,
        cleanup_requested=True,
        cleanup_succeeded=False,
        temp_root_exists=True,
        cleanup_error="forced_cleanup_failure",
    )

    project_runtime_after = file_metadata(project_runtime_file)
    temp_after = directory_snapshot(temp_root)
    forbidden_validator_calls = {"open", "__import__"} & direct_call_names(contract_path)
    checks = {
        "contract_version_exact": RELATION_CONTRACT_VERSION == "semantic_relation.v1",
        "allowed_types_exact": set(ALLOWED_RELATION_TYPES) == EXPECTED_RELATION_TYPES,
        "allowed_types_synced_with_semantic_mesh": set(ALLOWED_RELATION_TYPES)
        == set(MESH_RELATION_TYPES),
        "all_allowed_types_accepted": len(allowed_result) == len(EXPECTED_RELATION_TYPES),
        "canonical_output_exact_fields": list(validated[0])
        == ["contract_version", "type", "target", "evidence_ref"]
        and set(validated[0]) == EXPECTED_FIELDS,
        "deterministic_output": validated == validated_again,
        "input_not_mutated": source_relations == original_relations,
        "output_is_fresh_copy": validated is not source_relations
        and validated[0] is not source_relations[0],
        "empty_list_accepted": empty_result == [],
        "dangling_target_accepted_without_lookup": dangling_result[0]["target"]
        == "concept:not-yet-present",
        "all_required_rejections_are_typed": all(rejection_checks.values()),
        "canonical_string_boundaries_enforced": all(invalid_string_checks.values()),
        "validator_import_allowlist_exact": imported_modules(contract_path) == {"__future__"},
        "validator_builtin_open_guard_active": io_guard_probe_passed,
        "validator_forbidden_builtin_calls_absent": not forbidden_validator_calls,
        "project_runtime_file_unchanged": project_runtime_before == project_runtime_after,
        "temp_root_remained_empty": temp_before == temp_after == [],
        "cleanup_failure_sets_failed_status_and_exit_one": cleanup_probe_result["status"]
        == "failed"
        and cleanup_probe_exit_code == 1,
    }
    checks.update({f"rejects_{name}": passed for name, passed in rejection_checks.items()})
    checks.update({f"rejects_{name}": passed for name, passed in invalid_string_checks.items()})

    return {
        "status": "ok" if all(checks.values()) else "failed",
        "service": SERVICE_NAME,
        "checks": checks,
        "details": {
            "contract_version": RELATION_CONTRACT_VERSION,
            "allowed_relation_types": sorted(ALLOWED_RELATION_TYPES),
            "max_relations_per_node": MAX_RELATIONS_PER_NODE,
            "project_runtime_file": str(project_runtime_file),
            "project_runtime_before": project_runtime_before,
            "project_runtime_after": project_runtime_after,
            "forbidden_validator_calls": sorted(forbidden_validator_calls),
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
    temp_root = Path(tempfile.gettempdir()) / f"gptmeai_semantic_relation_contract_{uuid.uuid4().hex}"
    result: dict[str, Any] = {
        "status": "error",
        "service": SERVICE_NAME,
        "temp_root": str(temp_root),
    }

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
        cleanup_succeeded = None
        cleanup_error = None
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
