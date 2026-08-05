"""Focused smoke for the library-only Semantic Mesh advisory adapter."""

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


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SERVICE_NAME = "AI OS Semantic Mesh Advisory Adapter Smoke"
FORBIDDEN_PAYLOAD_KEYS = {
    "nodes",
    "relations",
    "malformed_blocks",
    "memory_block_id",
    "mesh_node_id",
    "concept_id",
    "content_ref",
    "raw_concept_core_ref",
    "evidence_refs",
    "planned_task_titles",
    "title",
    "content",
    "context",
}
ALLOWED_ADAPTER_IMPORTS = {
    "__future__",
    "ai_os.semantic_mesh",
    "collections.abc",
    "dataclasses",
    "typing",
}
REJECTED_IMPORT_PROBES = {
    "core.memory_engine",
    "execution.ledger",
    "http.client",
    "planning.policy",
    "scripts.runtime_store",
    "socket",
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


def nested_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            keys.add(str(key))
            keys.update(nested_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.update(nested_keys(item))
    return keys


def imported_modules(source: str) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def unapproved_imports(modules: set[str]) -> set[str]:
    return modules - ALLOWED_ADAPTER_IMPORTS


def run_smoke(temp_root: Path) -> dict[str, Any]:
    from ai_os.semantic_mesh import build_semantic_mesh
    from ai_os.semantic_mesh_advisory import build_semantic_mesh_advisory
    from development.scripts.smoke_semantic_mesh_library import fixture_blocks

    temp_root.mkdir(parents=True, exist_ok=True)
    marker_file = temp_root / "semantic_mesh_advisory_marker.json"
    marker_file.write_text(json.dumps({"service": SERVICE_NAME}, ensure_ascii=False), encoding="utf-8")

    project_runtime_file = PROJECT_ROOT / "GPTMemory_runtime.yaml"
    project_runtime_before = file_metadata(project_runtime_file)
    adapter_file = PROJECT_ROOT / "ai_os" / "semantic_mesh_advisory.py"

    mesh = build_semantic_mesh(fixture_blocks())
    mesh_before = copy.deepcopy(mesh.to_dict())
    plan = {
        "focus_area": "semantic_mesh",
        "plan_groups": [{"group_key": "mesh_review"}, {"group_key": "contract_review"}],
        "tasks": [{"title": "Review semantic coverage"}, {"title": "Review relation diagnostics"}],
        "recovery_requests": [{"branch_id": "main"}],
        "planned_task_titles": ["Review semantic coverage", "Review relation diagnostics"],
    }
    plan_before = copy.deepcopy(plan)

    advisory = build_semantic_mesh_advisory(mesh, plan=plan).to_dict()
    second_advisory = build_semantic_mesh_advisory(
        build_semantic_mesh(fixture_blocks()),
        plan=copy.deepcopy(plan_before),
    ).to_dict()
    empty_advisory = build_semantic_mesh_advisory(build_semantic_mesh([]), plan={}).to_dict()
    legacy_advisory = build_semantic_mesh_advisory(
        build_semantic_mesh(
            [
                {
                    "id": "legacy-only",
                    "text": "Legacy-only advisory coverage fixture.",
                    "tags": ["legacy"],
                }
            ]
        ),
        plan={"focus_area": "memory"},
    ).to_dict()
    malformed_advisory = build_semantic_mesh_advisory(
        build_semantic_mesh(
            [
                {
                    "id": "malformed-only",
                    "text": "Malformed-only advisory coverage fixture.",
                    "metadata": {"concept_core": {}},
                }
            ]
        ),
        plan={"focus_area": "semantic_mesh"},
    ).to_dict()
    strict_advisory = build_semantic_mesh_advisory(
        build_semantic_mesh([fixture_blocks()[2]]),
        plan={"focus_area": "semantic_mesh"},
    ).to_dict()
    mixed_non_strict_advisory = build_semantic_mesh_advisory(
        build_semantic_mesh(
            [
                {
                    "id": "legacy-mixed",
                    "text": "Legacy record in a non-strict mixed coverage fixture.",
                },
                {
                    "id": "malformed-mixed",
                    "text": "Malformed record in a non-strict mixed coverage fixture.",
                    "metadata": {"concept_core": {}},
                },
            ]
        ),
        plan={"focus_area": "semantic_mesh"},
    ).to_dict()

    project_runtime_after = file_metadata(project_runtime_file)
    payload_keys = nested_keys(advisory)
    signal_codes = [str(item.get("code")) for item in advisory.get("attention_signals", [])]
    empty_signal_codes = [str(item.get("code")) for item in empty_advisory.get("attention_signals", [])]
    legacy_signal_codes = [str(item.get("code")) for item in legacy_advisory.get("attention_signals", [])]
    malformed_signal_codes = [
        str(item.get("code")) for item in malformed_advisory.get("attention_signals", [])
    ]
    relation_evidence_counts = dict(advisory.get("relation_evidence_counts") or {})
    plan_summary = dict(advisory.get("plan_summary") or {})
    adapter_source = adapter_file.read_text(encoding="utf-8")
    adapter_imports = imported_modules(adapter_source)

    required_signals = {
        "malformed_concept_metadata",
        "dangling_relation_targets",
        "unknown_relation_types",
        "weak_derived_relations_present",
    }
    checks = {
        "advisory_is_deterministic": advisory == second_advisory,
        "source_mesh_not_mutated": mesh.to_dict() == mesh_before,
        "source_plan_not_mutated": plan == plan_before,
        "mode_is_advisory_only": advisory.get("mode") == "advisory_only",
        "runtime_enforcement_false": advisory.get("runtime_enforcement") is False,
        "planner_input_applied_false": advisory.get("planner_input_applied") is False,
        "dispatch_input_applied_false": advisory.get("dispatch_input_applied") is False,
        "planner_context_persistence_false": advisory.get("planner_context_persistence") is False,
        "storage_schema_mutation_false": advisory.get("storage_schema_mutation") is False,
        "public_api_behavior_mutation_false": advisory.get("public_api_behavior_mutation") is False,
        "coverage_state_mixed": advisory.get("coverage_state") == "mixed",
        "required_diagnostics_preserved": {
            "total_blocks",
            "strict_concept_blocks",
            "legacy_blocks",
            "malformed_concept_blocks",
            "relation_count",
            "dangling_relation_count",
            "weak_derived_relation_count",
            "unknown_relation_type_count",
        }.issubset(dict(advisory.get("mesh_diagnostics") or {})),
        "explicit_and_weak_relations_separated": (
            relation_evidence_counts.get("explicit_concept_core") == 3
            and int(relation_evidence_counts.get("weak_derived", 0)) >= 1
        ),
        "diagnostic_relations_counted": relation_evidence_counts.get("diagnostic") == 2,
        "required_attention_signals_present": required_signals.issubset(signal_codes),
        "plan_summary_is_aggregate_only": plan_summary == {
            "focus_area": "semantic_mesh",
            "plan_group_count": 2,
            "task_count": 2,
            "recovery_request_count": 1,
            "planned_task_title_count": 2,
        },
        "payload_excludes_sensitive_mesh_and_plan_fields": not (payload_keys & FORBIDDEN_PAYLOAD_KEYS),
        "empty_mesh_is_nonfatal": (
            empty_advisory.get("coverage_state") == "empty"
            and empty_signal_codes == ["semantic_mesh_empty"]
        ),
        "legacy_only_mesh_is_nonfatal": (
            legacy_advisory.get("coverage_state") == "legacy_only"
            and "strict_concept_coverage_absent" in legacy_signal_codes
        ),
        "malformed_only_mesh_is_nonfatal": (
            malformed_advisory.get("coverage_state") == "malformed_only"
            and "strict_concept_coverage_absent" in malformed_signal_codes
            and "malformed_concept_metadata" in malformed_signal_codes
        ),
        "strict_only_mesh_is_nonfatal": (
            strict_advisory.get("coverage_state") == "strict_only"
        ),
        "mixed_non_strict_mesh_is_nonfatal": (
            mixed_non_strict_advisory.get("coverage_state") == "mixed"
        ),
        "adapter_has_no_runtime_planner_or_network_imports": not unapproved_imports(
            adapter_imports
        ),
        "strict_import_allowlist_rejects_boundary_probes": unapproved_imports(
            REJECTED_IMPORT_PROBES
        )
        == REJECTED_IMPORT_PROBES,
        "project_runtime_file_unchanged": project_runtime_before == project_runtime_after,
        "temp_root_marker_written": marker_file.exists(),
    }

    return {
        "status": "ok" if all(checks.values()) else "failed",
        "service": SERVICE_NAME,
        "checks": checks,
        "details": {
            "coverage_state": advisory.get("coverage_state"),
            "signal_codes": signal_codes,
            "relation_evidence_counts": relation_evidence_counts,
            "plan_summary": plan_summary,
            "adapter_imports": sorted(adapter_imports),
            "unapproved_adapter_imports": sorted(unapproved_imports(adapter_imports)),
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
    temp_root = Path(tempfile.gettempdir()) / f"gptmeai_semantic_mesh_advisory_{uuid.uuid4().hex}"
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
