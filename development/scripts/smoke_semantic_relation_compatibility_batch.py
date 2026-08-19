"""Pure in-memory smoke for direct-input Semantic Relation compatibility inventory."""

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

SERVICE_NAME = "AI OS Semantic Relation Compatibility Batch Smoke"
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
    "ai_os.semantic_relation_compatibility_inventory",
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
        "target": "concept:batch-target",
        "evidence_ref": "memory:batch-evidence",
    }
    relation.update(overrides)
    return relation


def run_smoke(temp_root: Path) -> dict[str, Any]:
    import ai_os.semantic_relation_compatibility_batch as batch_module
    from ai_os.semantic_relation_compatibility import (
        COMPATIBILITY_STATUSES,
        SemanticRelationCompatibilityReport,
        classify_semantic_relation_compatibility,
    )
    from ai_os.semantic_relation_compatibility_batch import (
        BATCH_INVENTORY_MODE,
        BATCH_INVENTORY_SOURCE,
        BATCH_REPORT_GENERATION_PROVENANCE,
        SemanticRelationCompatibilityBatchError,
        SemanticRelationCompatibilityBatchInventory,
        SemanticRelationCompatibilityInput,
        build_direct_semantic_relation_compatibility_inventory as build_contract,
    )
    from ai_os.semantic_relation_compatibility_inventory import (
        build_semantic_relation_compatibility_inventory,
    )

    temp_root.mkdir(parents=True, exist_ok=True)
    temp_before = directory_snapshot(temp_root)
    project_runtime_file = PROJECT_ROOT / "GPTMemory_runtime.yaml"
    project_runtime_before = file_metadata(project_runtime_file)
    module_path = PROJECT_ROOT / "ai_os" / "semantic_relation_compatibility_batch.py"
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {"inventories": {}, "errors": {}}

    def build(inputs: object):
        with patch("builtins.open", side_effect=AssertionError("batch_file_io_forbidden")):
            return build_contract(inputs)

    def capture_error(inputs: object) -> tuple[dict[str, object], str]:
        try:
            build(inputs)
        except SemanticRelationCompatibilityBatchError as exc:
            return exc.to_dict(), str(exc)
        raise AssertionError("expected SemanticRelationCompatibilityBatchError")

    missing_evidence = valid_relation()
    missing_evidence.pop("evidence_ref")
    relations_by_status: dict[str, object] = {
        "empty": [],
        "compatible_v1_shape": [valid_relation()],
        "legacy_unversioned": [
            {"type": "supports", "target": "concept:legacy-target"}
        ],
        "mixed_versioning": [
            valid_relation(),
            {"type": "supports", "target": "concept:legacy-target"},
        ],
        "unsupported_version": [
            valid_relation(
                contract_version="semantic_relation.private-v2",
                target="concept:private-target",
                evidence_ref="memory:private-evidence",
            )
        ],
        "invalid_v1": [missing_evidence],
        "malformed_relations": [None],
    }
    inputs = [
        SemanticRelationCompatibilityInput(
            source_concept_id=f"concept:batch-source-{index}",
            relations=relations_by_status[status],
        )
        for index, status in enumerate(EXPECTED_STATUSES)
    ]
    inputs_before = copy.deepcopy(inputs)
    input_refs = list(inputs)
    relation_list_refs = [item.relations for item in inputs]
    relation_item_refs = [
        list(item.relations) if type(item.relations) is list else []
        for item in inputs
    ]

    with (
        patch.object(
            batch_module,
            "classify_semantic_relation_compatibility",
            wraps=classify_semantic_relation_compatibility,
        ) as classify_spy,
        patch.object(
            batch_module,
            "build_semantic_relation_compatibility_inventory",
            wraps=build_semantic_relation_compatibility_inventory,
        ) as aggregate_spy,
    ):
        inventory = build(inputs)

    payload = inventory.to_dict()
    payload_again = build(list(reversed(inputs))).to_dict()
    details["inventories"]["all_statuses"] = payload

    direct_reports = [
        classify_semantic_relation_compatibility(
            item.relations,
            source_concept_id=item.source_concept_id,
        )
        for item in inputs
    ]
    f3b_inventory = build_semantic_relation_compatibility_inventory(direct_reports)
    f3b_payload = f3b_inventory.to_dict()

    checks["f3a_status_taxonomy_reused_exactly"] = (
        tuple(COMPATIBILITY_STATUSES) == EXPECTED_STATUSES
    )
    checks["batch_inventory_type_stable"] = isinstance(
        inventory,
        SemanticRelationCompatibilityBatchInventory,
    )
    checks["batch_inventory_shape_exact"] = set(payload) == EXPECTED_INVENTORY_FIELDS
    checks["batch_mode_source_and_provenance_exact"] = (
        payload["mode"]
        == BATCH_INVENTORY_MODE
        == "read_only_direct_compatibility_inventory"
        and payload["source"]
        == BATCH_INVENTORY_SOURCE
        == "caller_supplied_relation_inputs"
        and payload["report_generation_provenance"]
        == BATCH_REPORT_GENERATION_PROVENANCE
        == "direct_f3a_classifier"
    )
    checks["direct_f3a_call_path_exact"] = (
        classify_spy.call_count == len(inputs)
        and all(
            call.args[0] is inputs[index].relations
            and call.kwargs["source_concept_id"] is inputs[index].source_concept_id
            for index, call in enumerate(classify_spy.call_args_list)
        )
    )
    generated_reports = aggregate_spy.call_args.args[0]
    checks["direct_f3b_call_path_exact"] = (
        aggregate_spy.call_count == 1
        and type(generated_reports) is list
        and len(generated_reports) == len(inputs)
        and all(type(report) is SemanticRelationCompatibilityReport for report in generated_reports)
    )
    checks["all_statuses_aggregated_once"] = (
        payload["report_count"] == len(EXPECTED_STATUSES)
        and payload["status_counts"] == {status: 1 for status in EXPECTED_STATUSES}
        and tuple(payload["status_counts"]) == EXPECTED_STATUSES
    )
    checks["f3b_aggregate_values_reused_exactly"] = all(
        payload[field] == f3b_payload[field]
        for field in (
            "report_count",
            "status_counts",
            "relation_count",
            "versioned_relation_count",
            "unversioned_relation_count",
            "malformed_relation_count",
            "issue_report_count",
        )
    )
    checks["batch_inventory_is_order_independent"] = payload == payload_again
    checks["batch_does_not_mutate_inputs"] = inputs == inputs_before
    checks["direct_input_and_relation_identities_preserved"] = (
        all(inputs[index] is input_refs[index] for index in range(len(inputs)))
        and all(
            inputs[index].relations is relation_list_refs[index]
            for index in range(len(inputs))
        )
        and all(
            all(
                inputs[input_index].relations[item_index]
                is relation_item_refs[input_index][item_index]
                for item_index in range(len(relation_item_refs[input_index]))
            )
            for input_index in range(len(inputs))
        )
    )

    malformed_only = build(
        [
            SemanticRelationCompatibilityInput(
                source_concept_id="concept:malformed-only",
                relations=[None],
            )
        ]
    ).to_dict()
    details["inventories"]["malformed_only"] = malformed_only
    checks["positive_malformed_only_fixture"] = (
        malformed_only["report_count"] == 1
        and malformed_only["status_counts"]["malformed_relations"] == 1
        and malformed_only["malformed_relation_count"] == 1
        and malformed_only["issue_report_count"] == 1
    )

    duplicate_input = SemanticRelationCompatibilityInput(
        source_concept_id="concept:duplicate-source",
        relations=[valid_relation(target="concept:duplicate-target")],
    )
    duplicate_payload = build([duplicate_input, duplicate_input]).to_dict()
    details["inventories"]["duplicates"] = duplicate_payload
    checks["duplicates_are_counted_independently"] = (
        duplicate_payload["report_count"] == 2
        and duplicate_payload["status_counts"]["compatible_v1_shape"] == 2
        and duplicate_payload["relation_count"] == 2
    )

    empty_payload = build([]).to_dict()
    details["inventories"]["empty"] = empty_payload
    checks["empty_batch_is_deterministic"] = (
        empty_payload["report_count"] == 0
        and empty_payload["status_counts"] == {
            status: 0 for status in EXPECTED_STATUSES
        }
        and empty_payload["relation_count"] == 0
        and empty_payload["issue_report_count"] == 0
    )

    malformed_envelope = build(
        [
            SemanticRelationCompatibilityInput(
                source_concept_id="concept:malformed-envelope",
                relations=None,
            )
        ]
    ).to_dict()
    checks["relation_shape_errors_remain_f3a_statuses"] = (
        malformed_envelope["status_counts"]["malformed_relations"] == 1
        and malformed_envelope["issue_report_count"] == 1
    )

    class DerivedInput(SemanticRelationCompatibilityInput):
        pass

    private_value = "private-batch-input-value"
    not_list_error = capture_error((private_value,))
    wrong_type_error = capture_error([private_value])
    derived_type_error = capture_error(
        [DerivedInput(source_concept_id="concept:derived", relations=[])]
    )
    details["errors"] = {
        "not_list": not_list_error[0],
        "wrong_type": wrong_type_error[0],
        "derived_type": derived_type_error[0],
    }
    checks["outer_batch_requires_exact_list"] = not_list_error[0] == {
        "code": "compatibility_inputs_not_list",
        "index": None,
        "field": "inputs",
    }
    checks["batch_items_require_exact_input_type"] = (
        wrong_type_error[0]
        == {
            "code": "compatibility_input_type_invalid",
            "index": 0,
            "field": None,
        }
        and derived_type_error[0] == wrong_type_error[0]
    )
    checks["batch_errors_never_echo_rejected_values"] = all(
        private_value not in error_text
        for error_text in (not_list_error[1], wrong_type_error[1], derived_type_error[1])
    )

    detached_relations = [valid_relation(target="concept:detached-target")]
    detached_inventory = build(
        [
            SemanticRelationCompatibilityInput(
                source_concept_id="concept:detached-source",
                relations=detached_relations,
            )
        ]
    )
    detached_payload_before = detached_inventory.to_dict()
    detached_relations[0]["target"] = "concept:mutated-after-build"
    checks["output_retains_no_relation_references"] = (
        detached_inventory.to_dict() == detached_payload_before
    )

    serialized_payload = json.dumps(payload, sort_keys=True)
    checks["output_is_aggregate_only"] = (
        "concept:batch-source" not in serialized_payload
        and "concept:private-target" not in serialized_payload
        and "memory:private-evidence" not in serialized_payload
        and not {
            "inputs",
            "reports",
            "source_concept_id",
            "relations",
            "targets",
            "evidence_refs",
            "readiness",
            "migration",
        }.intersection(payload)
    )
    checks["writer_provenance_remains_unavailable"] = (
        payload["writer_validation_provenance"] == "not_available"
    )
    checks["target_lookup_never_performed"] = payload["target_lookup_performed"] is False
    checks["batch_returns_fresh_objects"] = (
        inventory is not build(inputs)
        and payload is not inventory.to_dict()
        and payload["status_counts"] is not inventory.to_dict()["status_counts"]
    )
    checks["module_import_allowlist_exact"] = (
        imported_modules(module_path) == EXPECTED_IMPORT_MODULES
    )

    project_runtime_after = file_metadata(project_runtime_file)
    temp_after = directory_snapshot(temp_root)
    checks["batch_creates_no_files"] = temp_before == temp_after == []
    checks["project_runtime_file_unchanged"] = (
        project_runtime_before == project_runtime_after
    )
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
        f"gptmeai_semantic_relation_compatibility_batch_{uuid.uuid4().hex}"
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
