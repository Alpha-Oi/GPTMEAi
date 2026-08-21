"""Pure in-memory smoke for direct compatibility-comparison batch inventory."""

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

SERVICE_NAME = "AI OS Semantic Relation Compatibility Comparison Batch Smoke"
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
    "aggregation_semantics",
    "comparison_direction",
    "comparison_count",
    "baseline",
    "candidate",
    "delta",
    "comparison_generation_provenance",
    "comparison_inventory_generation_provenance",
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
    "ai_os.semantic_relation_compatibility_comparison",
    "ai_os.semantic_relation_compatibility_comparison_inventory",
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
        "target": "concept:comparison-batch-target",
        "evidence_ref": "memory:comparison-batch-evidence",
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
    import ai_os.semantic_relation_compatibility_comparison_batch as batch_module
    from ai_os.semantic_relation_compatibility import COMPATIBILITY_STATUSES
    from ai_os.semantic_relation_compatibility_batch import (
        SemanticRelationCompatibilityInput,
    )
    from ai_os.semantic_relation_compatibility_comparison import (
        COMPARISON_DIRECTION,
        compare_direct_semantic_relation_compatibility_batches as compare_direct,
    )
    from ai_os.semantic_relation_compatibility_comparison_batch import (
        COMPARISON_BATCH_AGGREGATION_SEMANTICS,
        COMPARISON_BATCH_GENERATION_PROVENANCE,
        COMPARISON_BATCH_INVENTORY_MODE,
        COMPARISON_BATCH_INVENTORY_PROVENANCE,
        COMPARISON_BATCH_INVENTORY_SOURCE,
        SemanticRelationCompatibilityComparisonBatchError,
        SemanticRelationCompatibilityComparisonBatchInput,
        SemanticRelationCompatibilityComparisonBatchInventory,
        build_direct_semantic_relation_compatibility_comparison_inventory as build_batch,
    )
    from ai_os.semantic_relation_compatibility_comparison_inventory import (
        build_semantic_relation_compatibility_comparison_inventory as aggregate,
    )

    temp_root.mkdir(parents=True, exist_ok=True)
    temp_before = directory_snapshot(temp_root)
    project_runtime_file = PROJECT_ROOT / "GPTMemory_runtime.yaml"
    project_runtime_before = file_metadata(project_runtime_file)
    module_path = (
        PROJECT_ROOT
        / "ai_os"
        / "semantic_relation_compatibility_comparison_batch.py"
    )
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {"errors": {}, "inventory": {}}

    def make_input(status: str, *, suffix: str) -> SemanticRelationCompatibilityInput:
        return SemanticRelationCompatibilityInput(
            source_concept_id=f"concept:comparison-batch-source-{suffix}",
            relations=relations_for_status(status, suffix=suffix),
        )

    def make_pair(
        baseline_statuses: tuple[str, ...],
        candidate_statuses: tuple[str, ...],
        *,
        suffix: str,
    ) -> SemanticRelationCompatibilityComparisonBatchInput:
        return SemanticRelationCompatibilityComparisonBatchInput(
            baseline_inputs=[
                make_input(status, suffix=f"{suffix}-baseline-{index}")
                for index, status in enumerate(baseline_statuses)
            ],
            candidate_inputs=[
                make_input(status, suffix=f"{suffix}-candidate-{index}")
                for index, status in enumerate(candidate_statuses)
            ],
        )

    def build(comparison_inputs: object):
        with patch(
            "builtins.open",
            side_effect=AssertionError("comparison_batch_file_io_forbidden"),
        ):
            return build_batch(comparison_inputs)

    def capture_error(comparison_inputs: object) -> tuple[dict[str, object], str]:
        try:
            build(comparison_inputs)
        except SemanticRelationCompatibilityComparisonBatchError as exc:
            return exc.to_dict(), str(exc)
        raise AssertionError(
            "expected SemanticRelationCompatibilityComparisonBatchError"
        )

    comparison_inputs = [
        make_pair(
            ("empty", "legacy_unversioned"),
            ("compatible_v1_shape", "mixed_versioning"),
            suffix="forward",
        ),
        make_pair(
            ("unsupported_version", "invalid_v1"),
            ("malformed_relations", "empty"),
            suffix="issues",
        ),
    ]
    comparison_inputs_before = copy.deepcopy(comparison_inputs)
    pair_refs = tuple(comparison_inputs)
    baseline_refs = tuple(item.baseline_inputs for item in comparison_inputs)
    candidate_refs = tuple(item.candidate_inputs for item in comparison_inputs)
    baseline_item_refs = tuple(tuple(items) for items in baseline_refs)
    candidate_item_refs = tuple(tuple(items) for items in candidate_refs)
    relation_refs = tuple(
        item.relations
        for pair in comparison_inputs
        for items in (pair.baseline_inputs, pair.candidate_inputs)
        for item in items
    )

    f3d_calls: list[tuple[object, object]] = []
    generated_comparisons: list[object] = []
    f3e_calls: list[object] = []
    f3e_items: list[tuple[object, ...]] = []
    f3e_results: list[object] = []

    def tracked_compare(*, baseline_inputs: object, candidate_inputs: object):
        f3d_calls.append((baseline_inputs, candidate_inputs))
        comparison = compare_direct(
            baseline_inputs=baseline_inputs,
            candidate_inputs=candidate_inputs,
        )
        generated_comparisons.append(comparison)
        return comparison

    def tracked_aggregate(comparisons: object):
        f3e_calls.append(comparisons)
        f3e_items.append(tuple(comparisons))
        inventory = aggregate(comparisons)
        f3e_results.append(inventory)
        return inventory

    with patch.object(
        batch_module,
        "compare_direct_semantic_relation_compatibility_batches",
        side_effect=tracked_compare,
    ), patch.object(
        batch_module,
        "build_semantic_relation_compatibility_comparison_inventory",
        side_effect=tracked_aggregate,
    ):
        inventory = build(comparison_inputs)

    payload = inventory.to_dict()
    details["inventory"] = payload
    checks["output_type_and_fields_exact"] = (
        type(inventory) is SemanticRelationCompatibilityComparisonBatchInventory
        and set(payload) == EXPECTED_OUTPUT_FIELDS
        and all(set(payload[name]) == EXPECTED_COUNT_FIELDS for name in ("baseline", "candidate", "delta"))
    )
    checks["contract_markers_exact"] = (
        payload["mode"] == COMPARISON_BATCH_INVENTORY_MODE
        and payload["source"] == COMPARISON_BATCH_INVENTORY_SOURCE
        and payload["aggregation_semantics"]
        == COMPARISON_BATCH_AGGREGATION_SEMANTICS
        and payload["comparison_direction"] == COMPARISON_DIRECTION
        and payload["comparison_generation_provenance"]
        == COMPARISON_BATCH_GENERATION_PROVENANCE
        and payload["comparison_inventory_generation_provenance"]
        == COMPARISON_BATCH_INVENTORY_PROVENANCE
        and payload["writer_validation_provenance"] == "not_available"
        and payload["source_identity_matching_performed"] is False
        and payload["target_lookup_performed"] is False
    )
    checks["f3d_called_once_per_input_with_exact_batch_identities"] = (
        len(f3d_calls) == len(comparison_inputs)
        and all(
            call[0] is baseline_refs[index] and call[1] is candidate_refs[index]
            for index, call in enumerate(f3d_calls)
        )
    )
    checks["f3e_called_once_with_exact_generated_comparison_identities"] = (
        len(f3e_calls) == 1
        and type(f3e_calls[0]) is list
        and f3e_calls[0] is not comparison_inputs
        and len(f3e_items[0]) == len(generated_comparisons)
        and all(
            item is generated_comparisons[index]
            for index, item in enumerate(f3e_items[0])
        )
    )
    checks["f3e_aggregate_object_identities_preserved"] = (
        len(f3e_results) == 1
        and inventory.baseline is f3e_results[0].baseline
        and inventory.candidate is f3e_results[0].candidate
        and inventory.delta is f3e_results[0].delta
    )

    expected_comparisons = [
        compare_direct(
            baseline_inputs=item.baseline_inputs,
            candidate_inputs=item.candidate_inputs,
        )
        for item in comparison_inputs
    ]
    expected_inventory = aggregate(expected_comparisons)
    checks["aggregate_matches_direct_f3d_then_f3e"] = (
        payload["comparison_count"] == expected_inventory.comparison_count
        and payload["baseline"] == expected_inventory.baseline.to_dict()
        and payload["candidate"] == expected_inventory.candidate.to_dict()
        and payload["delta"] == expected_inventory.delta.to_dict()
    )

    taxonomy_pair = make_pair(
        EXPECTED_STATUSES,
        tuple(reversed(EXPECTED_STATUSES)),
        suffix="taxonomy",
    )
    taxonomy_payload = build([taxonomy_pair]).to_dict()
    checks["full_f3a_taxonomy_preserved"] = (
        tuple(COMPATIBILITY_STATUSES) == EXPECTED_STATUSES
        and taxonomy_payload["baseline"]["status_counts"]
        == {status: 1 for status in EXPECTED_STATUSES}
        and taxonomy_payload["candidate"]["status_counts"]
        == {status: 1 for status in EXPECTED_STATUSES}
    )

    positive_input = make_pair((), ("compatible_v1_shape",), suffix="positive")
    negative_input = make_pair(("compatible_v1_shape",), (), suffix="negative")
    zero_input = make_pair(
        ("legacy_unversioned",),
        ("legacy_unversioned",),
        suffix="zero",
    )
    positive = build([positive_input]).to_dict()["delta"]
    negative = build([negative_input]).to_dict()["delta"]
    zero = build([zero_input]).to_dict()["delta"]
    cancelling = build([positive_input, negative_input]).to_dict()["delta"]
    checks["positive_negative_zero_and_cancelling_deltas_preserved"] = (
        positive["report_count"] > 0
        and positive["relation_count"] > 0
        and negative["report_count"] < 0
        and negative["relation_count"] < 0
        and all(
            value == 0
            for field, value in zero.items()
            if field != "status_counts"
        )
        and all(value == 0 for value in zero["status_counts"].values())
        and all(
            value == 0
            for field, value in cancelling.items()
            if field != "status_counts"
        )
        and all(value == 0 for value in cancelling["status_counts"].values())
    )

    ordered = build([positive_input, zero_input, negative_input]).to_dict()
    reversed_order = build([negative_input, zero_input, positive_input]).to_dict()
    checks["aggregate_is_order_independent"] = ordered == reversed_order

    single = build([positive_input]).to_dict()
    duplicate = build([positive_input, positive_input]).to_dict()
    checks["duplicate_comparison_inputs_count_independently"] = (
        duplicate["comparison_count"] == 2 * single["comparison_count"]
        and all(
            duplicate[group][field] == 2 * single[group][field]
            for group in ("baseline", "candidate", "delta")
            for field in EXPECTED_COUNT_FIELDS - {"status_counts"}
        )
        and all(
            duplicate[group]["status_counts"][status]
            == 2 * single[group]["status_counts"][status]
            for group in ("baseline", "candidate", "delta")
            for status in EXPECTED_STATUSES
        )
    )

    empty = build([]).to_dict()
    checks["empty_outer_batch_is_deterministic_zero"] = (
        empty["comparison_count"] == 0
        and all(
            empty[group][field] == 0
            for group in ("baseline", "candidate", "delta")
            for field in EXPECTED_COUNT_FIELDS - {"status_counts"}
        )
        and all(
            empty[group]["status_counts"][status] == 0
            for group in ("baseline", "candidate", "delta")
            for status in EXPECTED_STATUSES
        )
    )

    malformed_only = SemanticRelationCompatibilityComparisonBatchInput(
        baseline_inputs=[
            SemanticRelationCompatibilityInput(
                source_concept_id="concept:malformed-only-baseline",
                relations=[None],
            )
        ],
        candidate_inputs=[
            SemanticRelationCompatibilityInput(
                source_concept_id="concept:malformed-only-candidate",
                relations=[None],
            )
        ],
    )
    malformed_payload = build([malformed_only]).to_dict()
    checks["malformed_only_fixture_is_positive"] = (
        malformed_payload["baseline"]["status_counts"]["malformed_relations"] == 1
        and malformed_payload["candidate"]["status_counts"]["malformed_relations"] == 1
        and malformed_payload["baseline"]["malformed_relation_count"] == 1
        and malformed_payload["candidate"]["malformed_relation_count"] == 1
    )

    zero_relation_malformed = SemanticRelationCompatibilityComparisonBatchInput(
        baseline_inputs=[
            SemanticRelationCompatibilityInput(
                source_concept_id="concept:zero-relation-malformed-baseline",
                relations=(),
            )
        ],
        candidate_inputs=[],
    )
    zero_relation_payload = build([zero_relation_malformed]).to_dict()
    checks["zero_relation_malformed_fixture_is_positive"] = (
        zero_relation_payload["baseline"]["status_counts"]["malformed_relations"] == 1
        and zero_relation_payload["baseline"]["relation_count"] == 0
        and zero_relation_payload["baseline"]["malformed_relation_count"] == 0
        and zero_relation_payload["baseline"]["issue_report_count"] == 1
    )

    class DerivedInput(SemanticRelationCompatibilityComparisonBatchInput):
        pass

    private_value = "private-comparison-input-value"
    error_cases = {
        "outer_not_list": (
            tuple(comparison_inputs),
            {
                "code": "compatibility_comparison_inputs_not_list",
                "comparison_index": None,
                "batch": None,
                "index": None,
                "field": "comparison_inputs",
            },
        ),
        "item_type_invalid": (
            [object()],
            {
                "code": "compatibility_comparison_input_type_invalid",
                "comparison_index": 0,
                "batch": None,
                "index": None,
                "field": None,
            },
        ),
        "derived_item_type_invalid": (
            [DerivedInput([], [])],
            {
                "code": "compatibility_comparison_input_type_invalid",
                "comparison_index": 0,
                "batch": None,
                "index": None,
                "field": None,
            },
        ),
        "nested_baseline_not_list": (
            [SemanticRelationCompatibilityComparisonBatchInput((), [])],
            {
                "code": "compatibility_inputs_not_list",
                "comparison_index": 0,
                "batch": "baseline",
                "index": None,
                "field": "inputs",
            },
        ),
        "nested_candidate_item_invalid": (
            [
                SemanticRelationCompatibilityComparisonBatchInput(
                    [],
                    [private_value],
                )
            ],
            {
                "code": "compatibility_input_type_invalid",
                "comparison_index": 0,
                "batch": "candidate",
                "index": 0,
                "field": None,
            },
        ),
    }
    captured_errors = {
        name: capture_error(value)
        for name, (value, _) in error_cases.items()
    }
    details["errors"] = {
        name: error[0] for name, error in captured_errors.items()
    }
    checks["outer_and_item_errors_exact"] = all(
        captured_errors[name][0] == expected
        for name, (_, expected) in error_cases.items()
    )
    checks["nested_f3d_error_context_preserved"] = all(
        captured_errors[name][0] == error_cases[name][1]
        for name in ("nested_baseline_not_list", "nested_candidate_item_invalid")
    )
    checks["errors_never_echo_rejected_values"] = private_value not in captured_errors[
        "nested_candidate_item_invalid"
    ][1]

    checks["comparison_inputs_are_not_mutated"] = (
        comparison_inputs == comparison_inputs_before
    )
    checks["direct_input_identities_are_preserved"] = (
        all(comparison_inputs[index] is pair_refs[index] for index in range(len(pair_refs)))
        and all(
            comparison_inputs[index].baseline_inputs is baseline_refs[index]
            and comparison_inputs[index].candidate_inputs is candidate_refs[index]
            for index in range(len(pair_refs))
        )
        and all(
            comparison_inputs[pair_index].baseline_inputs[item_index]
            is baseline_item_refs[pair_index][item_index]
            for pair_index in range(len(pair_refs))
            for item_index in range(len(baseline_item_refs[pair_index]))
        )
        and all(
            comparison_inputs[pair_index].candidate_inputs[item_index]
            is candidate_item_refs[pair_index][item_index]
            for pair_index in range(len(pair_refs))
            for item_index in range(len(candidate_item_refs[pair_index]))
        )
        and all(
            item.relations is relation_refs[index]
            for index, item in enumerate(
                item
                for pair in comparison_inputs
                for items in (pair.baseline_inputs, pair.candidate_inputs)
                for item in items
            )
        )
    )

    serialized_payload = json.dumps(payload, sort_keys=True)
    checks["output_is_aggregate_only_and_policy_free"] = (
        "concept:comparison-batch-source" not in serialized_payload
        and "memory:unsupported" not in serialized_payload
        and all(
            not hasattr(inventory, attribute)
            for attribute in ("comparison_inputs", "comparisons", "reports")
        )
        and all(
            forbidden not in serialized_payload
            for forbidden in (
                '"readiness"',
                '"migration"',
                '"improved"',
                '"regressed"',
                '"percentage"',
                '"trend"',
            )
        )
    )
    inventory_again = build(comparison_inputs)
    checks["builder_returns_fresh_container_and_aggregates"] = (
        inventory_again is not inventory
        and inventory_again.baseline is not inventory.baseline
        and inventory_again.candidate is not inventory.candidate
        and inventory_again.delta is not inventory.delta
        and inventory_again.to_dict() == payload
        and inventory_again.to_dict() is not payload
    )
    checks["module_import_allowlist_exact"] = (
        imported_modules(module_path) == EXPECTED_IMPORT_MODULES
    )

    project_runtime_after = file_metadata(project_runtime_file)
    temp_after = directory_snapshot(temp_root)
    checks["comparison_batch_creates_no_files"] = temp_before == temp_after == []
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
        f"gptmeai_semantic_relation_compatibility_comparison_batch_{uuid.uuid4().hex}"
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
