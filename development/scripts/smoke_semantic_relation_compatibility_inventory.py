"""Pure in-memory smoke for aggregate Semantic Relation compatibility inventory."""

from __future__ import annotations

import argparse
import ast
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

SERVICE_NAME = "AI OS Semantic Relation Compatibility Inventory Smoke"
EXPECTED_STATUSES = (
    "empty",
    "compatible_v1_shape",
    "legacy_unversioned",
    "mixed_versioning",
    "unsupported_version",
    "invalid_v1",
    "malformed_relations",
)
EXPECTED_INVENTORY_FIELDS = {
    "mode",
    "source",
    "report_count",
    "status_counts",
    "relation_count",
    "versioned_relation_count",
    "unversioned_relation_count",
    "malformed_relation_count",
    "issue_report_count",
    "report_generation_provenance",
    "writer_validation_provenance",
    "target_lookup_performed",
}
EXPECTED_IMPORT_MODULES = {
    "__future__",
    "dataclasses",
    "ai_os.semantic_relation_compatibility",
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
    return {"exists": True, "size": stat.st_size, "mtime": stat.st_mtime}


def directory_snapshot(path: Path) -> list[str]:
    if not path.exists():
        return []
    return sorted(str(item.relative_to(path)) for item in path.rglob("*"))


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add(node.module or "")
    return modules


def valid_relation(**overrides: object) -> dict[str, object]:
    relation: dict[str, object] = {
        "contract_version": "semantic_relation.v1",
        "type": "supports",
        "target": "concept:inventory-target",
        "evidence_ref": "memory:inventory-evidence",
    }
    relation.update(overrides)
    return relation


def run_smoke(temp_root: Path) -> dict[str, Any]:
    from ai_os.semantic_relation_compatibility import (
        COMPATIBILITY_STATUSES,
        SemanticRelationCompatibilityReport,
        classify_semantic_relation_compatibility,
    )
    from ai_os.semantic_relation_compatibility_inventory import (
        INVENTORY_MODE,
        INVENTORY_SOURCE,
        SemanticRelationCompatibilityInventory,
        SemanticRelationCompatibilityInventoryError,
        build_semantic_relation_compatibility_inventory as build_contract,
    )

    temp_root.mkdir(parents=True, exist_ok=True)
    temp_before = directory_snapshot(temp_root)
    project_runtime_file = PROJECT_ROOT / "GPTMemory_runtime.yaml"
    project_runtime_before = file_metadata(project_runtime_file)
    module_path = PROJECT_ROOT / "ai_os" / "semantic_relation_compatibility_inventory.py"
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {"inventories": {}, "errors": {}}

    def classify(relations: object):
        return classify_semantic_relation_compatibility(
            relations,
            source_concept_id="concept:inventory-source",
        )

    def build(reports: object):
        with patch("builtins.open", side_effect=AssertionError("inventory_file_io_forbidden")):
            return build_contract(reports)

    def capture_error(reports: object) -> tuple[dict[str, object], str]:
        try:
            build(reports)
        except SemanticRelationCompatibilityInventoryError as exc:
            return exc.to_dict(), str(exc)
        raise AssertionError("expected SemanticRelationCompatibilityInventoryError")

    missing_evidence = valid_relation()
    missing_evidence.pop("evidence_ref")
    reports_by_status = {
        "empty": classify([]),
        "compatible_v1_shape": classify([valid_relation()]),
        "legacy_unversioned": classify(
            [{"type": "supports", "target": "concept:legacy-target"}]
        ),
        "mixed_versioning": classify(
            [valid_relation(), {"type": "supports", "target": "concept:legacy-target"}]
        ),
        "unsupported_version": classify(
            [
                valid_relation(
                    contract_version="semantic_relation.private-v2",
                    target="concept:private-target",
                    evidence_ref="memory:private-evidence",
                )
            ]
        ),
        "invalid_v1": classify([missing_evidence]),
        "malformed_relations": classify([None]),
    }
    reports = [reports_by_status[status] for status in EXPECTED_STATUSES]
    reports_before = [report.to_dict() for report in reports]

    inventory = build(reports)
    payload = inventory.to_dict()
    inventory_again = build(list(reversed(reports)))
    payload_again = inventory_again.to_dict()
    details["inventories"]["all_statuses"] = payload

    expected_status_counts = {status: 1 for status in EXPECTED_STATUSES}
    expected_relation_count = sum(report.relation_count for report in reports)
    expected_versioned_count = sum(report.versioned_relation_count for report in reports)
    expected_unversioned_count = sum(report.unversioned_relation_count for report in reports)
    expected_malformed_count = sum(report.malformed_relation_count for report in reports)
    expected_issue_count = sum(report.issue_code is not None for report in reports)

    checks["f3a_status_taxonomy_reused_exactly"] = tuple(COMPATIBILITY_STATUSES) == EXPECTED_STATUSES
    checks["inventory_type_stable"] = isinstance(
        inventory,
        SemanticRelationCompatibilityInventory,
    )
    checks["inventory_shape_exact"] = set(payload) == EXPECTED_INVENTORY_FIELDS
    checks["inventory_mode_and_source_exact"] = (
        payload["mode"] == INVENTORY_MODE == "read_only_compatibility_inventory"
        and payload["source"]
        == INVENTORY_SOURCE
        == "caller_supplied_compatibility_reports"
    )
    checks["all_statuses_aggregated_once"] = (
        payload["report_count"] == len(EXPECTED_STATUSES)
        and payload["status_counts"] == expected_status_counts
        and tuple(payload["status_counts"]) == EXPECTED_STATUSES
    )
    checks["relation_counts_aggregated_exactly"] = (
        payload["relation_count"] == expected_relation_count
        and payload["versioned_relation_count"] == expected_versioned_count
        and payload["unversioned_relation_count"] == expected_unversioned_count
        and payload["malformed_relation_count"] == expected_malformed_count
        and payload["issue_report_count"] == expected_issue_count
    )
    checks["positive_malformed_count_aggregated"] = (
        expected_malformed_count > 0
        and payload["malformed_relation_count"] == expected_malformed_count
    )
    checks["inventory_is_order_independent"] = payload == payload_again
    checks["inventory_does_not_mutate_reports"] = reports_before == [
        report.to_dict() for report in reports
    ]
    checks["inventory_returns_fresh_objects"] = (
        inventory is not inventory_again
        and payload is not payload_again
        and payload["status_counts"] is not payload_again["status_counts"]
    )
    checks["inventory_does_not_claim_writer_provenance"] = (
        payload["writer_validation_provenance"] == "not_available"
    )
    checks["inventory_does_not_claim_report_generation_provenance"] = (
        payload["report_generation_provenance"] == "not_available"
    )
    checks["inventory_never_performs_target_lookup"] = payload["target_lookup_performed"] is False

    empty_payload = build([]).to_dict()
    details["inventories"]["empty"] = empty_payload
    checks["empty_inventory_is_deterministic"] = (
        empty_payload["report_count"] == 0
        and empty_payload["status_counts"] == {status: 0 for status in EXPECTED_STATUSES}
        and empty_payload["relation_count"] == 0
        and empty_payload["issue_report_count"] == 0
    )

    not_list_error = capture_error(None)
    wrong_type_error = capture_error(["private-report-value"])
    invalid_status_error = capture_error(
        [
            SemanticRelationCompatibilityReport(
                status="private-status-value",
                relation_count=0,
                versioned_relation_count=0,
                unversioned_relation_count=0,
                malformed_relation_count=0,
            )
        ]
    )
    negative_count_error = capture_error(
        [
            SemanticRelationCompatibilityReport(
                status="compatible_v1_shape",
                relation_count=-1,
                versioned_relation_count=0,
                unversioned_relation_count=0,
                malformed_relation_count=0,
            )
        ]
    )
    count_mismatch_error = capture_error(
        [
            SemanticRelationCompatibilityReport(
                status="compatible_v1_shape",
                relation_count=1,
                versioned_relation_count=0,
                unversioned_relation_count=0,
                malformed_relation_count=0,
            )
        ]
    )
    status_count_mismatch_error = capture_error(
        [
            SemanticRelationCompatibilityReport(
                status="empty",
                relation_count=1,
                versioned_relation_count=1,
                unversioned_relation_count=0,
                malformed_relation_count=0,
            )
        ]
    )
    issue_missing_error = capture_error(
        [
            SemanticRelationCompatibilityReport(
                status="invalid_v1",
                relation_count=1,
                versioned_relation_count=1,
                unversioned_relation_count=0,
                malformed_relation_count=0,
            )
        ]
    )
    issue_unexpected_error = capture_error(
        [
            SemanticRelationCompatibilityReport(
                status="compatible_v1_shape",
                relation_count=1,
                versioned_relation_count=1,
                unversioned_relation_count=0,
                malformed_relation_count=0,
                issue_code="private-issue-value",
            )
        ]
    )
    details["errors"] = {
        "not_list": not_list_error[0],
        "wrong_type": wrong_type_error[0],
        "invalid_status": invalid_status_error[0],
        "negative_count": negative_count_error[0],
        "count_mismatch": count_mismatch_error[0],
        "status_count_mismatch": status_count_mismatch_error[0],
        "issue_missing": issue_missing_error[0],
        "issue_unexpected": issue_unexpected_error[0],
    }

    checks["non_list_reports_rejected_safely"] = not_list_error[0] == {
        "code": "compatibility_reports_not_list",
        "index": None,
        "field": "reports",
    }
    checks["wrong_report_type_rejected_safely"] = wrong_type_error[0] == {
        "code": "compatibility_report_type_invalid",
        "index": 0,
        "field": None,
    }
    checks["invalid_status_rejected_safely"] = invalid_status_error[0] == {
        "code": "compatibility_report_status_invalid",
        "index": 0,
        "field": "status",
    }
    checks["invalid_counts_rejected_safely"] = (
        negative_count_error[0]
        == {
            "code": "compatibility_report_count_invalid",
            "index": 0,
            "field": "relation_count",
        }
        and count_mismatch_error[0]
        == {
            "code": "compatibility_report_count_mismatch",
            "index": 0,
            "field": "relation_count",
        }
        and status_count_mismatch_error[0]
        == {
            "code": "compatibility_report_status_count_mismatch",
            "index": 0,
            "field": "status",
        }
    )
    checks["issue_invariants_rejected_safely"] = (
        issue_missing_error[0]
        == {
            "code": "compatibility_report_issue_missing",
            "index": 0,
            "field": "issue_code",
        }
        and issue_unexpected_error[0]
        == {
            "code": "compatibility_report_issue_unexpected",
            "index": 0,
            "field": "issue_code",
        }
    )

    serialized_output = json.dumps(
        {"payload": payload, "errors": details["errors"]},
        ensure_ascii=False,
        sort_keys=True,
    )
    error_text = " ".join(
        item[1]
        for item in (
            not_list_error,
            wrong_type_error,
            invalid_status_error,
            negative_count_error,
            count_mismatch_error,
            status_count_mismatch_error,
            issue_missing_error,
            issue_unexpected_error,
        )
    )
    checks["output_contains_no_report_or_relation_payloads"] = all(
        private_value not in serialized_output and private_value not in error_text
        for private_value in (
            "private-report-value",
            "private-status-value",
            "private-issue-value",
            "semantic_relation.private-v2",
            "concept:private-target",
            "memory:private-evidence",
        )
    )
    checks["module_import_allowlist_exact"] = (
        imported_modules(module_path) == EXPECTED_IMPORT_MODULES
    )

    project_runtime_after = file_metadata(project_runtime_file)
    temp_after = directory_snapshot(temp_root)
    checks["inventory_creates_no_files"] = temp_before == temp_after == []
    checks["project_runtime_file_unchanged"] = project_runtime_before == project_runtime_after
    details["project_runtime_before"] = project_runtime_before
    details["project_runtime_after"] = project_runtime_after
    details["module_imports"] = sorted(imported_modules(module_path))

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
    temp_root = Path(tempfile.gettempdir()) / (
        f"gptmeai_semantic_relation_compatibility_inventory_{uuid.uuid4().hex}"
    )
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
