"""Pure in-memory smoke for direct-batch compatibility comparison."""

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

SERVICE_NAME = "AI OS Semantic Relation Compatibility Comparison Smoke"
EXPECTED_STATUSES = (
    "empty",
    "compatible_v1_shape",
    "legacy_unversioned",
    "mixed_versioning",
    "unsupported_version",
    "invalid_v1",
    "malformed_relations",
)
EXPECTED_OUTPUT_FIELDS = {
    "mode",
    "source",
    "comparison_direction",
    "comparison_semantics",
    "baseline",
    "candidate",
    "delta",
    "inventory_generation_provenance",
    "writer_validation_provenance",
    "source_identity_matching_performed",
    "target_lookup_performed",
}
EXPECTED_COUNT_FIELDS = {
    "report_count",
    "status_counts",
    "relation_count",
    "versioned_relation_count",
    "unversioned_relation_count",
    "malformed_relation_count",
    "issue_report_count",
}
EXPECTED_IMPORT_MODULES = {
    "__future__",
    "dataclasses",
    "ai_os.semantic_relation_compatibility_batch",
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
        "target": "concept:comparison-target",
        "evidence_ref": "memory:comparison-evidence",
    }
    relation.update(overrides)
    return relation


def relations_for_status(status: str, *, suffix: str) -> object:
    if status == "empty":
        return []
    if status == "compatible_v1_shape":
        return [valid_relation(target=f"concept:compatible-{suffix}")]
    if status == "legacy_unversioned":
        return [{"type": "supports", "target": f"concept:legacy-{suffix}"}]
    if status == "mixed_versioning":
        return [
            valid_relation(target=f"concept:mixed-versioned-{suffix}"),
            {"type": "supports", "target": f"concept:mixed-legacy-{suffix}"},
        ]
    if status == "unsupported_version":
        return [
            valid_relation(
                contract_version="semantic_relation.private-v2",
                target=f"concept:unsupported-{suffix}",
                evidence_ref=f"memory:unsupported-{suffix}",
            )
        ]
    if status == "invalid_v1":
        relation = valid_relation(target=f"concept:invalid-{suffix}")
        relation.pop("evidence_ref")
        return [relation]
    if status == "malformed_relations":
        return [None]
    raise AssertionError(f"unsupported fixture status: {status}")


def run_smoke(temp_root: Path) -> dict[str, Any]:
    import ai_os.semantic_relation_compatibility_comparison as comparison_module
    from ai_os.semantic_relation_compatibility import COMPATIBILITY_STATUSES
    from ai_os.semantic_relation_compatibility_batch import (
        SemanticRelationCompatibilityBatchInventory,
        SemanticRelationCompatibilityInput,
        build_direct_semantic_relation_compatibility_inventory,
    )
    from ai_os.semantic_relation_compatibility_comparison import (
        COMPARISON_DIRECTION,
        COMPARISON_INVENTORY_GENERATION_PROVENANCE,
        COMPARISON_MODE,
        COMPARISON_SEMANTICS,
        COMPARISON_SOURCE,
        SemanticRelationCompatibilityComparison,
        SemanticRelationCompatibilityComparisonError,
        compare_direct_semantic_relation_compatibility_batches as compare_contract,
    )

    temp_root.mkdir(parents=True, exist_ok=True)
    temp_before = directory_snapshot(temp_root)
    project_runtime_file = PROJECT_ROOT / "GPTMemory_runtime.yaml"
    project_runtime_before = file_metadata(project_runtime_file)
    module_path = (
        PROJECT_ROOT / "ai_os" / "semantic_relation_compatibility_comparison.py"
    )
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {"comparisons": {}, "errors": {}}

    def make_input(status: str, *, suffix: str):
        return SemanticRelationCompatibilityInput(
            source_concept_id=f"concept:comparison-source-{suffix}",
            relations=relations_for_status(status, suffix=suffix),
        )

    def compare(baseline_inputs: object, candidate_inputs: object):
        with patch(
            "builtins.open",
            side_effect=AssertionError("comparison_file_io_forbidden"),
        ):
            return compare_contract(
                baseline_inputs=baseline_inputs,
                candidate_inputs=candidate_inputs,
            )

    def capture_error(
        baseline_inputs: object,
        candidate_inputs: object,
    ) -> tuple[dict[str, object], str]:
        try:
            compare(baseline_inputs, candidate_inputs)
        except SemanticRelationCompatibilityComparisonError as exc:
            return exc.to_dict(), str(exc)
        raise AssertionError("expected SemanticRelationCompatibilityComparisonError")

    baseline_statuses = (
        "empty",
        "compatible_v1_shape",
        "legacy_unversioned",
        "legacy_unversioned",
        "mixed_versioning",
        "unsupported_version",
        "invalid_v1",
        "malformed_relations",
        "malformed_relations",
    )
    candidate_statuses = (
        "empty",
        "compatible_v1_shape",
        "compatible_v1_shape",
        "legacy_unversioned",
        "mixed_versioning",
        "mixed_versioning",
        "invalid_v1",
        "malformed_relations",
    )
    baseline_inputs = [
        make_input(status, suffix=f"baseline-{index}")
        for index, status in enumerate(baseline_statuses)
    ]
    candidate_inputs = [
        make_input(status, suffix=f"candidate-{index}")
        for index, status in enumerate(candidate_statuses)
    ]
    baseline_before = copy.deepcopy(baseline_inputs)
    candidate_before = copy.deepcopy(candidate_inputs)
    baseline_input_refs = list(baseline_inputs)
    candidate_input_refs = list(candidate_inputs)
    baseline_relation_refs = [item.relations for item in baseline_inputs]
    candidate_relation_refs = [item.relations for item in candidate_inputs]
    baseline_relation_item_refs = [list(item.relations) for item in baseline_inputs]
    candidate_relation_item_refs = [list(item.relations) for item in candidate_inputs]

    built_inventories: list[SemanticRelationCompatibilityBatchInventory] = []

    def record_inventory(inputs: object) -> SemanticRelationCompatibilityBatchInventory:
        inventory = build_direct_semantic_relation_compatibility_inventory(inputs)
        built_inventories.append(inventory)
        return inventory

    with patch.object(
        comparison_module,
        "build_direct_semantic_relation_compatibility_inventory",
        side_effect=record_inventory,
    ) as build_spy:
        comparison = compare(baseline_inputs, candidate_inputs)

    payload = comparison.to_dict()
    details["comparisons"]["mixed_deltas"] = payload
    expected_status_deltas = {
        "empty": 0,
        "compatible_v1_shape": 1,
        "legacy_unversioned": -1,
        "mixed_versioning": 1,
        "unsupported_version": -1,
        "invalid_v1": 0,
        "malformed_relations": -1,
    }

    checks["f3a_status_taxonomy_reused_exactly"] = (
        tuple(COMPATIBILITY_STATUSES) == EXPECTED_STATUSES
    )
    checks["comparison_type_stable"] = isinstance(
        comparison,
        SemanticRelationCompatibilityComparison,
    )
    checks["comparison_shape_exact"] = set(payload) == EXPECTED_OUTPUT_FIELDS
    checks["aggregate_shapes_exact"] = (
        set(payload["baseline"])
        == set(payload["candidate"])
        == set(payload["delta"])
        == EXPECTED_COUNT_FIELDS
    )
    checks["mode_source_direction_semantics_exact"] = (
        payload["mode"]
        == COMPARISON_MODE
        == "read_only_direct_compatibility_comparison"
        and payload["source"]
        == COMPARISON_SOURCE
        == "caller_supplied_relation_input_batches"
        and payload["comparison_direction"]
        == COMPARISON_DIRECTION
        == "candidate_minus_baseline"
        and payload["comparison_semantics"]
        == COMPARISON_SEMANTICS
        == "descriptive_counts_only"
    )
    checks["exact_two_f3c_calls_with_direct_batch_identity"] = (
        build_spy.call_count == 2
        and build_spy.call_args_list[0].args[0] is baseline_inputs
        and build_spy.call_args_list[1].args[0] is candidate_inputs
    )
    checks["comparison_retains_exact_f3c_inventories"] = (
        len(built_inventories) == 2
        and comparison.baseline_inventory is built_inventories[0]
        and comparison.candidate_inventory is built_inventories[1]
    )
    checks["all_status_delta_signs_covered"] = (
        payload["delta"]["status_counts"] == expected_status_deltas
        and tuple(payload["delta"]["status_counts"]) == EXPECTED_STATUSES
        and any(value > 0 for value in expected_status_deltas.values())
        and any(value < 0 for value in expected_status_deltas.values())
        and any(value == 0 for value in expected_status_deltas.values())
    )
    checks["all_aggregate_deltas_are_candidate_minus_baseline"] = all(
        payload["delta"][field]
        == payload["candidate"][field] - payload["baseline"][field]
        for field in EXPECTED_COUNT_FIELDS - {"status_counts"}
    )
    checks["status_deltas_are_candidate_minus_baseline"] = all(
        payload["delta"]["status_counts"][status]
        == payload["candidate"]["status_counts"][status]
        - payload["baseline"]["status_counts"][status]
        for status in EXPECTED_STATUSES
    )

    swapped_payload = compare(candidate_inputs, baseline_inputs).to_dict()
    details["comparisons"]["swapped"] = swapped_payload
    checks["swap_is_antisymmetric"] = (
        swapped_payload["baseline"] == payload["candidate"]
        and swapped_payload["candidate"] == payload["baseline"]
        and all(
            swapped_payload["delta"][field] == -payload["delta"][field]
            for field in EXPECTED_COUNT_FIELDS - {"status_counts"}
        )
        and all(
            swapped_payload["delta"]["status_counts"][status]
            == -payload["delta"]["status_counts"][status]
            for status in EXPECTED_STATUSES
        )
    )

    same_payload = compare(baseline_inputs, baseline_inputs).to_dict()
    details["comparisons"]["same"] = same_payload
    checks["same_batch_has_zero_deltas"] = (
        all(
            same_payload["delta"][field] == 0
            for field in EXPECTED_COUNT_FIELDS - {"status_counts"}
        )
        and all(
            value == 0 for value in same_payload["delta"]["status_counts"].values()
        )
    )

    empty_payload = compare([], []).to_dict()
    details["comparisons"]["empty"] = empty_payload
    checks["empty_batches_are_deterministic"] = (
        empty_payload["baseline"] == empty_payload["candidate"]
        and empty_payload["baseline"]["report_count"] == 0
        and empty_payload["baseline"]["status_counts"]
        == {status: 0 for status in EXPECTED_STATUSES}
        and all(
            empty_payload["delta"][field] == 0
            for field in EXPECTED_COUNT_FIELDS - {"status_counts"}
        )
    )

    malformed_only_payload = compare(
        [],
        [make_input("malformed_relations", suffix="malformed-only")],
    ).to_dict()
    details["comparisons"]["malformed_only"] = malformed_only_payload
    checks["positive_malformed_only_delta"] = (
        malformed_only_payload["delta"]["status_counts"]["malformed_relations"]
        == 1
        and malformed_only_payload["delta"]["malformed_relation_count"] == 1
        and malformed_only_payload["delta"]["issue_report_count"] == 1
    )

    duplicate_input = make_input("compatible_v1_shape", suffix="duplicate")
    duplicate_payload = compare(
        [duplicate_input],
        [duplicate_input, duplicate_input],
    ).to_dict()
    details["comparisons"]["duplicates"] = duplicate_payload
    checks["duplicates_are_counted_without_alignment"] = (
        duplicate_payload["delta"]["report_count"] == 1
        and duplicate_payload["delta"]["status_counts"]["compatible_v1_shape"]
        == 1
        and duplicate_payload["delta"]["relation_count"] == 1
        and duplicate_payload["source_identity_matching_performed"] is False
    )

    private_value = "private-comparison-input-value"
    baseline_error = capture_error((private_value,), [])
    candidate_error = capture_error([], [private_value])
    details["errors"] = {
        "baseline": baseline_error[0],
        "candidate": candidate_error[0],
    }
    checks["baseline_error_context_exact"] = baseline_error[0] == {
        "code": "compatibility_inputs_not_list",
        "batch": "baseline",
        "index": None,
        "field": "inputs",
    }
    checks["candidate_error_context_exact"] = candidate_error[0] == {
        "code": "compatibility_input_type_invalid",
        "batch": "candidate",
        "index": 0,
        "field": None,
    }
    checks["comparison_errors_never_echo_rejected_values"] = all(
        private_value not in error_text
        for error_text in (baseline_error[1], candidate_error[1])
    )

    checks["comparison_does_not_mutate_inputs"] = (
        baseline_inputs == baseline_before and candidate_inputs == candidate_before
    )
    checks["direct_input_and_relation_identities_preserved"] = (
        all(
            baseline_inputs[index] is baseline_input_refs[index]
            and baseline_inputs[index].relations is baseline_relation_refs[index]
            and all(
                relation is baseline_relation_item_refs[index][relation_index]
                for relation_index, relation in enumerate(
                    baseline_inputs[index].relations
                )
            )
            for index in range(len(baseline_inputs))
        )
        and all(
            candidate_inputs[index] is candidate_input_refs[index]
            and candidate_inputs[index].relations is candidate_relation_refs[index]
            and all(
                relation is candidate_relation_item_refs[index][relation_index]
                for relation_index, relation in enumerate(
                    candidate_inputs[index].relations
                )
            )
            for index in range(len(candidate_inputs))
        )
    )

    detached_relations = [valid_relation(target="concept:detached-target")]
    detached_comparison = compare(
        [],
        [
            SemanticRelationCompatibilityInput(
                source_concept_id="concept:detached-source",
                relations=detached_relations,
            )
        ],
    )
    detached_payload_before = detached_comparison.to_dict()
    detached_relations[0]["target"] = "concept:mutated-after-comparison"
    checks["output_retains_no_relation_references"] = (
        detached_comparison.to_dict() == detached_payload_before
    )

    serialized_payload = json.dumps(payload, sort_keys=True)
    checks["output_is_aggregate_only_and_policy_free"] = (
        "concept:comparison-source" not in serialized_payload
        and "concept:unsupported" not in serialized_payload
        and "memory:unsupported" not in serialized_payload
        and all(
            forbidden not in serialized_payload
            for forbidden in (
                '"readiness"',
                '"migration"',
                '"improved"',
                '"regressed"',
                '"percentage"',
            )
        )
    )
    checks["provenance_and_safety_markers_exact"] = (
        payload["inventory_generation_provenance"]
        == COMPARISON_INVENTORY_GENERATION_PROVENANCE
        == "direct_f3c_batch_builder_for_both_batches"
        and payload["writer_validation_provenance"] == "not_available"
        and payload["source_identity_matching_performed"] is False
        and payload["target_lookup_performed"] is False
    )
    comparison_again = compare(baseline_inputs, candidate_inputs)
    checks["comparison_returns_fresh_objects"] = (
        comparison_again is not comparison
        and comparison_again.baseline_inventory is not comparison.baseline_inventory
        and comparison_again.candidate_inventory is not comparison.candidate_inventory
        and comparison_again.to_dict() == payload
        and comparison_again.to_dict() is not payload
    )
    checks["module_import_allowlist_exact"] = (
        imported_modules(module_path) == EXPECTED_IMPORT_MODULES
    )

    project_runtime_after = file_metadata(project_runtime_file)
    temp_after = directory_snapshot(temp_root)
    checks["comparison_creates_no_files"] = temp_before == temp_after == []
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
        f"gptmeai_semantic_relation_compatibility_comparison_{uuid.uuid4().hex}"
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
