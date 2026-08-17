"""Pure in-memory smoke for stored Semantic Relation compatibility classification."""

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
from typing import Any
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SERVICE_NAME = "AI OS Semantic Relation Compatibility Smoke"
EXPECTED_STATUSES = (
    "empty",
    "compatible_v1_shape",
    "legacy_unversioned",
    "mixed_versioning",
    "unsupported_version",
    "invalid_v1",
    "malformed_relations",
)
EXPECTED_REPORT_FIELDS = {
    "status",
    "relation_count",
    "versioned_relation_count",
    "unversioned_relation_count",
    "malformed_relation_count",
    "issue",
    "writer_validation_provenance",
    "target_lookup_performed",
}
EXPECTED_IMPORT_ROOTS = {"__future__", "dataclasses", "ai_os"}


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


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add((node.module or "").split(".", 1)[0])
    return modules


def valid_relation(**overrides: object) -> dict[str, object]:
    relation: dict[str, object] = {
        "contract_version": "semantic_relation.v1",
        "type": "supports",
        "target": "concept:compatibility-target",
        "evidence_ref": "memory:compatibility-evidence",
    }
    relation.update(overrides)
    return relation


def run_smoke(temp_root: Path) -> dict[str, Any]:
    from ai_os.semantic_relation_compatibility import (
        COMPATIBILITY_STATUSES,
        SemanticRelationCompatibilityReport,
        classify_semantic_relation_compatibility as classify_contract,
    )

    temp_root.mkdir(parents=True, exist_ok=True)
    temp_before = directory_snapshot(temp_root)
    project_runtime_file = PROJECT_ROOT / "GPTMemory_runtime.yaml"
    project_runtime_before = file_metadata(project_runtime_file)
    module_path = PROJECT_ROOT / "ai_os" / "semantic_relation_compatibility.py"
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {"reports": {}}

    def classify(relations: object, *, source_concept_id: object = "concept:compatibility-source"):
        with patch("builtins.open", side_effect=AssertionError("classifier_file_io_forbidden")):
            return classify_contract(relations, source_concept_id=source_concept_id)

    source_relations = [valid_relation()]
    source_before = copy.deepcopy(source_relations)
    compatible_report = classify(source_relations)
    compatible_payload = compatible_report.to_dict()
    compatible_again = classify(source_relations)
    details["reports"]["compatible_v1_shape"] = compatible_payload

    checks["status_taxonomy_exact"] = COMPATIBILITY_STATUSES == EXPECTED_STATUSES
    checks["report_type_stable"] = isinstance(compatible_report, SemanticRelationCompatibilityReport)
    checks["report_shape_exact"] = set(compatible_payload) == EXPECTED_REPORT_FIELDS
    checks["compatible_v1_shape_classified"] = (
        compatible_payload["status"] == "compatible_v1_shape"
        and compatible_payload["relation_count"] == 1
        and compatible_payload["versioned_relation_count"] == 1
        and compatible_payload["unversioned_relation_count"] == 0
        and compatible_payload["malformed_relation_count"] == 0
        and compatible_payload["issue"] is None
    )
    checks["compatible_shape_does_not_claim_writer_provenance"] = (
        compatible_payload["writer_validation_provenance"] == "not_available"
    )
    checks["target_lookup_never_performed"] = compatible_payload["target_lookup_performed"] is False
    checks["classifier_does_not_mutate_input"] = source_relations == source_before
    checks["classifier_returns_fresh_reports"] = (
        compatible_report is not compatible_again
        and compatible_payload is not compatible_again.to_dict()
    )

    empty_payload = classify([]).to_dict()
    details["reports"]["empty"] = empty_payload
    checks["empty_list_is_neutral"] = (
        empty_payload["status"] == "empty"
        and empty_payload["relation_count"] == 0
        and empty_payload["issue"] is None
    )

    legacy_relations = [{"type": "supports", "target": "concept:legacy-target"}]
    legacy_payload = classify(legacy_relations).to_dict()
    details["reports"]["legacy_unversioned"] = legacy_payload
    checks["legacy_unversioned_is_not_strictly_validated"] = (
        legacy_payload["status"] == "legacy_unversioned"
        and legacy_payload["versioned_relation_count"] == 0
        and legacy_payload["unversioned_relation_count"] == 1
        and legacy_payload["issue"] is None
    )

    mixed_relations = [valid_relation(), {"type": "supports", "target": "concept:legacy"}]
    mixed_payload = classify(mixed_relations).to_dict()
    details["reports"]["mixed_versioning"] = mixed_payload
    checks["mixed_versioning_is_diagnostic_only"] = (
        mixed_payload["status"] == "mixed_versioning"
        and mixed_payload["versioned_relation_count"] == 1
        and mixed_payload["unversioned_relation_count"] == 1
        and mixed_payload["issue"]
        == {"code": "mixed_relation_versioning", "index": 1, "field": "contract_version"}
    )

    unsupported_relations = [
        valid_relation(
            contract_version="semantic_relation.private-v2",
            target="concept:private-target",
            evidence_ref="memory:private-evidence",
        )
    ]
    unsupported_payload = classify(unsupported_relations).to_dict()
    details["reports"]["unsupported_version"] = unsupported_payload
    checks["unsupported_version_is_safe_diagnostic"] = (
        unsupported_payload["status"] == "unsupported_version"
        and unsupported_payload["issue"]
        == {"code": "unsupported_contract_version", "index": 0, "field": "contract_version"}
    )

    spoof_payload = classify([valid_relation(contract_version=_VersionEqualitySpoof())]).to_dict()
    null_payload = classify([valid_relation(contract_version=None)]).to_dict()
    checks["non_string_versions_are_unsupported"] = (
        spoof_payload["status"] == "unsupported_version"
        and null_payload["status"] == "unsupported_version"
    )

    missing_evidence = valid_relation()
    missing_evidence.pop("evidence_ref")
    invalid_payload = classify([missing_evidence]).to_dict()
    details["reports"]["invalid_v1"] = invalid_payload
    checks["declared_v1_reuses_f1_error_contract"] = (
        invalid_payload["status"] == "invalid_v1"
        and invalid_payload["issue"]
        == {"code": "relation_missing_fields", "index": 0, "field": None}
    )

    duplicate_payload = classify([valid_relation(), valid_relation()]).to_dict()
    self_reference_payload = classify(
        [valid_relation(target="concept:compatibility-source")]
    ).to_dict()
    checks["list_level_v1_rules_are_preserved"] = (
        duplicate_payload["status"] == "invalid_v1"
        and duplicate_payload["issue"]
        == {"code": "relation_duplicate", "index": 1, "field": None}
        and self_reference_payload["status"] == "invalid_v1"
        and self_reference_payload["issue"]
        == {"code": "relation_self_reference", "index": 0, "field": "target"}
    )

    too_many_relations = [
        valid_relation(target=f"concept:target-{index}", evidence_ref=f"memory:evidence-{index}")
        for index in range(65)
    ]
    limit_payload = classify(too_many_relations).to_dict()
    checks["relation_limit_reuses_f1_contract"] = (
        limit_payload["status"] == "invalid_v1"
        and limit_payload["issue"]
        == {"code": "relation_limit_exceeded", "index": None, "field": "relations"}
    )

    not_list_payload = classify(None).to_dict()
    malformed_item_payload = classify([valid_relation(), "private-non-object"]).to_dict()
    details["reports"]["malformed_relations"] = not_list_payload
    checks["non_list_relations_are_safe_diagnostic"] = (
        not_list_payload["status"] == "malformed_relations"
        and not_list_payload["relation_count"] == 0
        and not_list_payload["issue"]
        == {"code": "relations_not_list", "index": None, "field": "relations"}
    )
    checks["non_object_items_are_safe_diagnostic"] = (
        malformed_item_payload["status"] == "malformed_relations"
        and malformed_item_payload["relation_count"] == 2
        and malformed_item_payload["malformed_relation_count"] == 1
        and malformed_item_payload["issue"]
        == {"code": "relation_not_object", "index": 1, "field": None}
    )

    diagnostic_text = json.dumps(details["reports"], ensure_ascii=False, sort_keys=True)
    checks["diagnostics_do_not_echo_rejected_values"] = all(
        private_value not in diagnostic_text
        for private_value in (
            "semantic_relation.private-v2",
            "concept:private-target",
            "memory:private-evidence",
            "private-non-object",
        )
    )
    checks["module_import_allowlist_exact"] = imported_modules(module_path) == EXPECTED_IMPORT_ROOTS

    project_runtime_after = file_metadata(project_runtime_file)
    temp_after = directory_snapshot(temp_root)
    checks["classifier_creates_no_files"] = temp_before == temp_after == []
    checks["project_runtime_file_unchanged"] = project_runtime_before == project_runtime_after
    details["project_runtime_before"] = project_runtime_before
    details["project_runtime_after"] = project_runtime_after
    details["module_import_roots"] = sorted(imported_modules(module_path))

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
    temp_root = Path(tempfile.gettempdir()) / f"gptmeai_semantic_relation_compatibility_{uuid.uuid4().hex}"
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
    result["temp_root"] = str(temp_root)
    print_result(result, as_json=bool(args.json))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
