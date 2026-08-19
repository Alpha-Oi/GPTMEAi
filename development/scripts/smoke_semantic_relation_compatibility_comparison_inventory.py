"""Pure in-memory smoke for aggregate compatibility-comparison inventory."""

from __future__ import annotations

import argparse
import ast
import copy
import json
import shutil
import sys
import tempfile
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SERVICE_NAME = "AI OS Semantic Relation Compatibility Comparison Inventory Smoke"
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
    "ai_os.semantic_relation_compatibility",
    "ai_os.semantic_relation_compatibility_batch",
    "ai_os.semantic_relation_compatibility_comparison",
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
        "target": "concept:comparison-inventory-target",
        "evidence_ref": "memory:comparison-inventory-evidence",
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


def add_count_payloads(payloads: list[dict[str, object]]) -> dict[str, object]:
    totals: dict[str, object] = {
        field: 0 for field in EXPECTED_COUNT_FIELDS - {"status_counts"}
    }
    totals["status_counts"] = {status: 0 for status in EXPECTED_STATUSES}
    for payload in payloads:
        for field in EXPECTED_COUNT_FIELDS - {"status_counts"}:
            totals[field] += payload[field]
        for status in EXPECTED_STATUSES:
            totals["status_counts"][status] += payload["status_counts"][status]
    return totals


def run_smoke(temp_root: Path) -> dict[str, Any]:
    import ai_os.semantic_relation_compatibility_comparison_inventory as inventory_module
    from ai_os.semantic_relation_compatibility import COMPATIBILITY_STATUSES
    from ai_os.semantic_relation_compatibility_batch import (
        SemanticRelationCompatibilityBatchInventory,
        SemanticRelationCompatibilityInput,
    )
    from ai_os.semantic_relation_compatibility_comparison import (
        COMPARISON_DIRECTION,
        COMPARISON_INVENTORY_GENERATION_PROVENANCE,
        SemanticRelationCompatibilityComparison,
        compare_direct_semantic_relation_compatibility_batches,
    )
    from ai_os.semantic_relation_compatibility_comparison_inventory import (
        COMPARISON_INVENTORY_AGGREGATION_SEMANTICS,
        COMPARISON_INVENTORY_MODE,
        COMPARISON_INVENTORY_SOURCE,
        SemanticRelationCompatibilityComparisonAggregateCounts,
        SemanticRelationCompatibilityComparisonInventory,
        SemanticRelationCompatibilityComparisonInventoryError,
        build_semantic_relation_compatibility_comparison_inventory as build_inventory,
    )

    temp_root.mkdir(parents=True, exist_ok=True)
    temp_before = directory_snapshot(temp_root)
    project_runtime_file = PROJECT_ROOT / "GPTMemory_runtime.yaml"
    project_runtime_before = file_metadata(project_runtime_file)
    module_path = (
        PROJECT_ROOT
        / "ai_os"
        / "semantic_relation_compatibility_comparison_inventory.py"
    )
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {"inventories": {}, "errors": []}

    def make_input(status: str, *, suffix: str) -> SemanticRelationCompatibilityInput:
        return SemanticRelationCompatibilityInput(
            source_concept_id=f"concept:comparison-inventory-source-{suffix}",
            relations=relations_for_status(status, suffix=suffix),
        )

    def compare(
        baseline_statuses: tuple[str, ...],
        candidate_statuses: tuple[str, ...],
        *,
        suffix: str,
    ) -> SemanticRelationCompatibilityComparison:
        baseline_inputs = [
            make_input(status, suffix=f"{suffix}-baseline-{index}")
            for index, status in enumerate(baseline_statuses)
        ]
        candidate_inputs = [
            make_input(status, suffix=f"{suffix}-candidate-{index}")
            for index, status in enumerate(candidate_statuses)
        ]
        return compare_direct_semantic_relation_compatibility_batches(
            baseline_inputs=baseline_inputs,
            candidate_inputs=candidate_inputs,
        )

    def build(comparisons: object):
        with patch(
            "builtins.open",
            side_effect=AssertionError("comparison_inventory_file_io_forbidden"),
        ):
            return build_inventory(comparisons)

    def capture_error(comparisons: object) -> tuple[dict[str, object], str]:
        try:
            build(comparisons)
        except SemanticRelationCompatibilityComparisonInventoryError as exc:
            return exc.to_dict(), str(exc)
        raise AssertionError(
            "expected SemanticRelationCompatibilityComparisonInventoryError"
        )

    def forged_zero_delta_comparison(
        *,
        status: str,
        relation_count: int,
        versioned_relation_count: int,
        unversioned_relation_count: int,
        malformed_relation_count: int,
    ) -> SemanticRelationCompatibilityComparison:
        inventory = SemanticRelationCompatibilityBatchInventory(
            report_count=1,
            status_counts=tuple(
                (expected_status, int(expected_status == status))
                for expected_status in EXPECTED_STATUSES
            ),
            relation_count=relation_count,
            versioned_relation_count=versioned_relation_count,
            unversioned_relation_count=unversioned_relation_count,
            malformed_relation_count=malformed_relation_count,
            issue_report_count=int(
                status not in {"empty", "compatible_v1_shape", "legacy_unversioned"}
            ),
        )
        return SemanticRelationCompatibilityComparison(
            baseline_inventory=inventory,
            candidate_inventory=inventory,
            report_count_delta=0,
            status_count_deltas=tuple(
                (expected_status, 0) for expected_status in EXPECTED_STATUSES
            ),
            relation_count_delta=0,
            versioned_relation_count_delta=0,
            unversioned_relation_count_delta=0,
            malformed_relation_count_delta=0,
            issue_report_count_delta=0,
        )

    baseline_statuses = (
        "empty",
        "compatible_v1_shape",
        "legacy_unversioned",
        "mixed_versioning",
        "unsupported_version",
        "invalid_v1",
        "malformed_relations",
    )
    candidate_statuses = (
        "compatible_v1_shape",
        "compatible_v1_shape",
        "legacy_unversioned",
        "mixed_versioning",
        "mixed_versioning",
        "invalid_v1",
        "malformed_relations",
    )
    forward = compare(baseline_statuses, candidate_statuses, suffix="forward")
    reverse = compare(candidate_statuses, baseline_statuses, suffix="reverse")
    same = compare(baseline_statuses, baseline_statuses, suffix="same")
    comparisons = [forward, reverse, same]
    comparisons_before = copy.deepcopy(comparisons)
    comparison_refs = list(comparisons)

    inventory = build(comparisons)
    payload = inventory.to_dict()
    details["inventories"]["cancelling"] = payload
    comparison_payloads = [comparison.to_dict() for comparison in comparisons]
    expected_baseline = add_count_payloads(
        [comparison_payload["baseline"] for comparison_payload in comparison_payloads]
    )
    expected_candidate = add_count_payloads(
        [comparison_payload["candidate"] for comparison_payload in comparison_payloads]
    )
    expected_delta = add_count_payloads(
        [comparison_payload["delta"] for comparison_payload in comparison_payloads]
    )

    checks["f3a_status_taxonomy_reused_exactly"] = (
        tuple(COMPATIBILITY_STATUSES) == EXPECTED_STATUSES
    )
    checks["inventory_type_stable"] = isinstance(
        inventory,
        SemanticRelationCompatibilityComparisonInventory,
    ) and all(
        isinstance(
            aggregate,
            SemanticRelationCompatibilityComparisonAggregateCounts,
        )
        for aggregate in (inventory.baseline, inventory.candidate, inventory.delta)
    )
    checks["inventory_shape_exact"] = set(payload) == EXPECTED_OUTPUT_FIELDS
    checks["aggregate_shapes_exact"] = (
        set(payload["baseline"])
        == set(payload["candidate"])
        == set(payload["delta"])
        == EXPECTED_COUNT_FIELDS
    )
    checks["mode_source_semantics_direction_exact"] = (
        payload["mode"]
        == COMPARISON_INVENTORY_MODE
        == "read_only_compatibility_comparison_inventory"
        and payload["source"]
        == COMPARISON_INVENTORY_SOURCE
        == "caller_supplied_compatibility_comparisons"
        and payload["aggregation_semantics"]
        == COMPARISON_INVENTORY_AGGREGATION_SEMANTICS
        == "count_each_comparison"
        and payload["comparison_direction"]
        == COMPARISON_DIRECTION
        == "candidate_minus_baseline"
    )
    checks["all_comparison_aggregates_sum_exactly"] = (
        payload["comparison_count"] == len(comparisons)
        and payload["baseline"] == expected_baseline
        and payload["candidate"] == expected_candidate
        and payload["delta"] == expected_delta
    )
    checks["aggregate_delta_is_candidate_minus_baseline"] = (
        all(
            payload["delta"][field]
            == payload["candidate"][field] - payload["baseline"][field]
            for field in EXPECTED_COUNT_FIELDS - {"status_counts"}
        )
        and all(
            payload["delta"]["status_counts"][status]
            == payload["candidate"]["status_counts"][status]
            - payload["baseline"]["status_counts"][status]
            for status in EXPECTED_STATUSES
        )
    )
    checks["positive_negative_zero_comparisons_cancel_without_interpretation"] = (
        any(value > 0 for _, value in forward.status_count_deltas)
        and any(value < 0 for _, value in reverse.status_count_deltas)
        and all(value == 0 for _, value in same.status_count_deltas)
        and all(
            payload["delta"][field] == 0
            for field in EXPECTED_COUNT_FIELDS - {"status_counts"}
        )
        and all(
            value == 0 for value in payload["delta"]["status_counts"].values()
        )
    )

    reordered_payload = build(list(reversed(comparisons))).to_dict()
    checks["inventory_is_order_independent"] = reordered_payload == payload

    duplicate_payload = build([forward, forward]).to_dict()
    details["inventories"]["duplicates"] = duplicate_payload
    forward_payload = forward.to_dict()
    checks["duplicates_are_counted_independently"] = (
        duplicate_payload["comparison_count"] == 2
        and duplicate_payload["baseline"]
        == add_count_payloads([forward_payload["baseline"], forward_payload["baseline"]])
        and duplicate_payload["candidate"]
        == add_count_payloads([forward_payload["candidate"], forward_payload["candidate"]])
        and duplicate_payload["delta"]
        == add_count_payloads([forward_payload["delta"], forward_payload["delta"]])
        and duplicate_payload["source_identity_matching_performed"] is False
    )

    empty_payload = build([]).to_dict()
    details["inventories"]["empty"] = empty_payload
    checks["empty_inventory_is_deterministic"] = (
        empty_payload["comparison_count"] == 0
        and empty_payload["baseline"] == empty_payload["candidate"]
        and empty_payload["baseline"] == empty_payload["delta"]
        and empty_payload["baseline"]["status_counts"]
        == {status: 0 for status in EXPECTED_STATUSES}
        and all(
            empty_payload["baseline"][field] == 0
            for field in EXPECTED_COUNT_FIELDS - {"status_counts"}
        )
    )

    malformed_only = compare((), ("malformed_relations",), suffix="malformed-only")
    malformed_only_payload = build([malformed_only]).to_dict()
    details["inventories"]["malformed_only"] = malformed_only_payload
    checks["positive_malformed_only_fixture"] = (
        malformed_only_payload["delta"]["status_counts"]["malformed_relations"]
        == 1
        and malformed_only_payload["delta"]["malformed_relation_count"] == 1
        and malformed_only_payload["delta"]["issue_report_count"] == 1
    )

    zero_relation_malformed = compare_direct_semantic_relation_compatibility_batches(
        baseline_inputs=[],
        candidate_inputs=[
            SemanticRelationCompatibilityInput(
                source_concept_id="concept:zero-relation-malformed-source",
                relations=("not", "a", "list"),
            )
        ],
    )
    zero_relation_malformed_payload = build([zero_relation_malformed]).to_dict()
    checks["positive_zero_relation_malformed_fixture"] = (
        zero_relation_malformed_payload["delta"]["status_counts"][
            "malformed_relations"
        ]
        == 1
        and zero_relation_malformed_payload["delta"]["relation_count"] == 0
        and zero_relation_malformed_payload["delta"]["versioned_relation_count"] == 0
        and zero_relation_malformed_payload["delta"]["unversioned_relation_count"] == 0
        and zero_relation_malformed_payload["delta"]["malformed_relation_count"] == 0
        and zero_relation_malformed_payload["delta"]["issue_report_count"] == 1
    )

    feasibility_cases = [
        (
            [
                forged_zero_delta_comparison(
                    status="empty",
                    relation_count=1,
                    versioned_relation_count=1,
                    unversioned_relation_count=0,
                    malformed_relation_count=0,
                )
            ],
            {
                "code": "compatibility_comparison_count_mismatch",
                "index": 0,
                "field": "baseline_versioned_relation_count",
            },
        ),
        (
            [
                forged_zero_delta_comparison(
                    status="empty",
                    relation_count=1,
                    versioned_relation_count=0,
                    unversioned_relation_count=1,
                    malformed_relation_count=0,
                )
            ],
            {
                "code": "compatibility_comparison_count_mismatch",
                "index": 0,
                "field": "baseline_unversioned_relation_count",
            },
        ),
        (
            [
                forged_zero_delta_comparison(
                    status="compatible_v1_shape",
                    relation_count=2,
                    versioned_relation_count=1,
                    unversioned_relation_count=0,
                    malformed_relation_count=1,
                )
            ],
            {
                "code": "compatibility_comparison_count_mismatch",
                "index": 0,
                "field": "baseline_malformed_relation_count",
            },
        ),
        (
            [
                forged_zero_delta_comparison(
                    status="malformed_relations",
                    relation_count=1,
                    versioned_relation_count=1,
                    unversioned_relation_count=0,
                    malformed_relation_count=0,
                )
            ],
            {
                "code": "compatibility_comparison_count_mismatch",
                "index": 0,
                "field": "baseline_versioned_relation_count",
            },
        ),
    ]

    private_value = "private-comparison-inventory-value"
    malformed_cases = [
        (
            (private_value,),
            {
                "code": "compatibility_comparisons_not_list",
                "index": None,
                "field": "comparisons",
            },
        ),
        (
            [private_value],
            {
                "code": "compatibility_comparison_type_invalid",
                "index": 0,
                "field": None,
            },
        ),
        (
            [replace(forward, baseline_inventory=private_value)],
            {
                "code": "compatibility_comparison_inventory_type_invalid",
                "index": 0,
                "field": "baseline_inventory",
            },
        ),
        (
            [replace(forward, candidate_inventory=private_value)],
            {
                "code": "compatibility_comparison_inventory_type_invalid",
                "index": 0,
                "field": "candidate_inventory",
            },
        ),
        (
            [
                replace(
                    forward,
                    baseline_inventory=replace(
                        forward.baseline_inventory,
                        report_count=True,
                    ),
                )
            ],
            {
                "code": "compatibility_comparison_count_invalid",
                "index": 0,
                "field": "baseline_report_count",
            },
        ),
        (
            [
                replace(
                    forward,
                    baseline_inventory=replace(
                        forward.baseline_inventory,
                        status_counts=tuple(reversed(forward.baseline_inventory.status_counts)),
                    ),
                )
            ],
            {
                "code": "compatibility_comparison_status_taxonomy_invalid",
                "index": 0,
                "field": "baseline_status_counts",
            },
        ),
        (
            [
                replace(
                    forward,
                    baseline_inventory=replace(
                        forward.baseline_inventory,
                        status_counts=list(forward.baseline_inventory.status_counts),
                    ),
                )
            ],
            {
                "code": "compatibility_comparison_status_counts_invalid",
                "index": 0,
                "field": "baseline_status_counts",
            },
        ),
        (
            [
                replace(
                    forward,
                    baseline_inventory=replace(
                        forward.baseline_inventory,
                        status_counts=(
                            (EXPECTED_STATUSES[0], forward.baseline_inventory.status_counts[0][1] + 1),
                            *forward.baseline_inventory.status_counts[1:],
                        ),
                    ),
                )
            ],
            {
                "code": "compatibility_comparison_count_mismatch",
                "index": 0,
                "field": "baseline_report_count",
            },
        ),
        (
            [
                replace(
                    forward,
                    baseline_inventory=replace(
                        forward.baseline_inventory,
                        relation_count=forward.baseline_inventory.relation_count + 1,
                    ),
                )
            ],
            {
                "code": "compatibility_comparison_count_mismatch",
                "index": 0,
                "field": "baseline_relation_count",
            },
        ),
        (
            [
                replace(
                    forward,
                    baseline_inventory=replace(
                        forward.baseline_inventory,
                        issue_report_count=0,
                    ),
                )
            ],
            {
                "code": "compatibility_comparison_count_mismatch",
                "index": 0,
                "field": "baseline_issue_report_count",
            },
        ),
        (
            [
                replace(
                    forward,
                    baseline_inventory=replace(
                        forward.baseline_inventory,
                        versioned_relation_count=0,
                        unversioned_relation_count=(
                            forward.baseline_inventory.relation_count
                            - forward.baseline_inventory.malformed_relation_count
                        ),
                    ),
                )
            ],
            {
                "code": "compatibility_comparison_count_mismatch",
                "index": 0,
                "field": "baseline_versioned_relation_count",
            },
        ),
        (
            [
                replace(
                    forward,
                    baseline_inventory=replace(
                        forward.baseline_inventory,
                        versioned_relation_count=(
                            forward.baseline_inventory.relation_count
                            - forward.baseline_inventory.malformed_relation_count
                        ),
                        unversioned_relation_count=0,
                    ),
                )
            ],
            {
                "code": "compatibility_comparison_count_mismatch",
                "index": 0,
                "field": "baseline_unversioned_relation_count",
            },
        ),
        (
            [
                replace(
                    forward,
                    status_count_deltas=tuple(reversed(forward.status_count_deltas)),
                )
            ],
            {
                "code": "compatibility_comparison_status_taxonomy_invalid",
                "index": 0,
                "field": "status_count_deltas",
            },
        ),
        (
            [
                replace(
                    forward,
                    status_count_deltas=(
                        (EXPECTED_STATUSES[0], True),
                        *forward.status_count_deltas[1:],
                    ),
                )
            ],
            {
                "code": "compatibility_comparison_count_invalid",
                "index": 0,
                "field": "status_count_deltas",
            },
        ),
        (
            [
                replace(
                    forward,
                    status_count_deltas=(
                        (EXPECTED_STATUSES[0], forward.status_count_deltas[0][1] + 1),
                        *forward.status_count_deltas[1:],
                    ),
                )
            ],
            {
                "code": "compatibility_comparison_delta_mismatch",
                "index": 0,
                "field": "status_count_deltas",
            },
        ),
        (
            [replace(forward, report_count_delta=True)],
            {
                "code": "compatibility_comparison_delta_invalid",
                "index": 0,
                "field": "report_count_delta",
            },
        ),
        (
            [replace(forward, relation_count_delta=forward.relation_count_delta + 1)],
            {
                "code": "compatibility_comparison_delta_mismatch",
                "index": 0,
                "field": "relation_count_delta",
            },
        ),
    ]
    captured_feasibility_errors = [
        capture_error(case) for case, _ in feasibility_cases
    ]
    captured_errors = [capture_error(case) for case, _ in malformed_cases]
    details["errors"] = [
        error[0]
        for error in (*captured_feasibility_errors, *captured_errors)
    ]
    checks["status_to_count_feasibility_rejected_exactly"] = all(
        captured_feasibility_errors[index][0] == expected
        for index, (_, expected) in enumerate(feasibility_cases)
    )
    checks["malformed_public_objects_rejected_exactly"] = all(
        captured_errors[index][0] == expected
        for index, (_, expected) in enumerate(malformed_cases)
    )
    checks["inventory_errors_never_echo_rejected_values"] = all(
        private_value not in error_text
        for _, error_text in captured_errors
    )

    checks["inventory_does_not_mutate_inputs"] = comparisons == comparisons_before
    checks["direct_list_and_item_identities_preserved"] = (
        all(comparisons[index] is comparison_refs[index] for index in range(len(comparisons)))
        and all(
            comparisons[index].baseline_inventory
            is comparison_refs[index].baseline_inventory
            and comparisons[index].candidate_inventory
            is comparison_refs[index].candidate_inventory
            for index in range(len(comparisons))
        )
    )
    checks["output_retains_no_comparison_or_inventory_references"] = all(
        inventory.baseline is not comparison.baseline_inventory
        and inventory.baseline is not comparison.candidate_inventory
        and inventory.candidate is not comparison.baseline_inventory
        and inventory.candidate is not comparison.candidate_inventory
        and inventory.delta is not comparison.baseline_inventory
        and inventory.delta is not comparison.candidate_inventory
        for comparison in comparisons
    )

    serialized_payload = json.dumps(payload, sort_keys=True)
    checks["output_is_aggregate_only_and_policy_free"] = (
        "concept:comparison-inventory-source" not in serialized_payload
        and "concept:unsupported" not in serialized_payload
        and "memory:unsupported" not in serialized_payload
        and COMPARISON_INVENTORY_GENERATION_PROVENANCE not in serialized_payload
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
    checks["provenance_and_safety_markers_exact"] = (
        payload["comparison_generation_provenance"] == "not_available"
        and payload["writer_validation_provenance"] == "not_available"
        and payload["source_identity_matching_performed"] is False
        and payload["target_lookup_performed"] is False
    )
    checks["aggregation_does_not_regenerate_comparisons"] = (
        not hasattr(
            inventory_module,
            "compare_direct_semantic_relation_compatibility_batches",
        )
    )
    inventory_again = build(comparisons)
    checks["inventory_returns_fresh_objects"] = (
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
    checks["comparison_inventory_creates_no_files"] = temp_before == temp_after == []
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
        f"gptmeai_semantic_relation_compatibility_comparison_inventory_{uuid.uuid4().hex}"
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
