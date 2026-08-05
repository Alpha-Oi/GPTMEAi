"""Focused smoke for opt-in Semantic Mesh advisory wiring in CognitiveLoop.plan()."""

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


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SERVICE_NAME = "AI OS Semantic Mesh Cognitive Advisory Smoke"
FORBIDDEN_ADVISORY_KEYS = {
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=SERVICE_NAME)
    parser.add_argument("--json", action="store_true", help="Print compact JSON summary.")
    parser.add_argument("--cleanup", action="store_true", help="Delete the temp root after the smoke.")
    return parser.parse_args()


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


def cognitive_loop_builds_mesh(source: str) -> bool:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "ai_os.semantic_mesh":
            if any(alias.name == "build_semantic_mesh" for alias in node.names):
                return True
        if isinstance(node, ast.Call):
            function = node.func
            if isinstance(function, ast.Name) and function.id == "build_semantic_mesh":
                return True
            if isinstance(function, ast.Attribute) and function.attr == "build_semantic_mesh":
                return True
    return False


def semantic_advisory_in_task_metadata(plan: dict) -> bool:
    for task in list(plan.get("tasks") or []):
        if "semantic_mesh_advisory" in dict(task.get("metadata") or {}):
            return True
    for group in list(plan.get("plan_groups") or []):
        for task in list(group.get("tasks") or []):
            if "semantic_mesh_advisory" in dict(task.get("metadata") or {}):
                return True
    return False


def strip_semantic_advisory(plan: dict) -> dict:
    payload = copy.deepcopy(plan)
    payload.pop("semantic_mesh_advisory", None)
    return payload


def strip_serialization_advisories(plan: dict) -> dict:
    payload = strip_semantic_advisory(plan)
    payload.pop("concept_core_advisory", None)
    return payload


class RaisingMemoryEngine:
    def __init__(self, *args, **kwargs) -> None:
        raise AssertionError("CognitiveLoop.plan() must not read memory or build a semantic mesh")


def run_smoke(temp_root: Path) -> dict:
    import ai_os.config as config
    import scripts.runtime_store as runtime_store
    from ai_os.agent_runtime import AgentRuntime
    from ai_os.semantic_mesh import build_semantic_mesh
    from development.scripts.smoke_concept_core_advisory_consumers import (
        RecordingPlanner,
        ensure_temp_layout,
        planner_call_signature,
        project_runtime_state_metadata,
    )
    from development.scripts.smoke_semantic_mesh_library import fixture_blocks

    project_state_before = project_runtime_state_metadata()
    ensure_temp_layout(temp_root)
    mesh = build_semantic_mesh(fixture_blocks())
    mesh_before = copy.deepcopy(mesh.to_dict())

    previous_project_root = config.PROJECT_ROOT
    previous_env_file = config.ENV_FILE
    previous_runtime_file = runtime_store.RUNTIME_FILE
    config.PROJECT_ROOT = temp_root
    config.ENV_FILE = temp_root / ".env"
    runtime_store.RUNTIME_FILE = temp_root / "GPTMemory_runtime.yaml"

    checks: dict[str, bool] = {}
    details: dict[str, object] = {
        "temp_root": str(temp_root),
        "project_root": str(PROJECT_ROOT),
    }

    try:
        import ai_os.cognitive_loop as cognitive_loop_module
        from ai_os.cognitive_loop import CognitiveLoop

        previous_memory_engine = cognitive_loop_module.MemoryEngine
        previous_planner = cognitive_loop_module.PLANNER_RUNTIME
        try:
            direct_runtime = AgentRuntime(
                state_path=temp_root / "storage" / "agent_runtime_direct.json"
            )
            direct_loop = CognitiveLoop(
                runtime=direct_runtime,
                state_path=temp_root / "storage" / "cognitive_loop_direct.json",
            )
            perception = direct_loop.perceive()
            reasoning = direct_loop.reason(perception)

            cognitive_loop_module.MemoryEngine = RaisingMemoryEngine
            default_plan = direct_loop.plan(perception, reasoning)
            opt_in_plan = direct_loop.plan(
                perception,
                reasoning,
                semantic_mesh_index=mesh,
            )
            cognitive_loop_module.MemoryEngine = previous_memory_engine

            advisory = dict(opt_in_plan.get("semantic_mesh_advisory") or {})
            opt_in_without_semantic = strip_semantic_advisory(opt_in_plan)
            advisory_keys = nested_keys(advisory)

            planner_with_advisory = RecordingPlanner()
            cognitive_loop_module.PLANNER_RUNTIME = planner_with_advisory
            action_with_advisory = direct_loop.act(copy.deepcopy(opt_in_plan))

            plain_runtime = AgentRuntime(
                state_path=temp_root / "storage" / "agent_runtime_plain.json"
            )
            plain_loop = CognitiveLoop(
                runtime=plain_runtime,
                state_path=temp_root / "storage" / "cognitive_loop_plain.json",
            )
            planner_without_advisory = RecordingPlanner()
            cognitive_loop_module.PLANNER_RUNTIME = planner_without_advisory
            action_without_advisory = plain_loop.act(copy.deepcopy(opt_in_without_semantic))

            planner_signature_with = planner_call_signature(planner_with_advisory)
            planner_signature_without = planner_call_signature(planner_without_advisory)
            serialized_plan = direct_loop._sanitize_plan_for_serialization(opt_in_plan)
            serialized_cycle = direct_loop._sanitize_cycle_for_serialization(
                {"plan": opt_in_plan, "status": "smoke"}
            )
            serialized_cycle_plan = dict((serialized_cycle or {}).get("plan") or {})
            expected_serialized_plan = strip_serialization_advisories(opt_in_plan)

            cognitive_source = (
                PROJECT_ROOT / "ai_os" / "cognitive_loop.py"
            ).read_text(encoding="utf-8")
            run_cycle_runtime = AgentRuntime(
                state_path=temp_root / "storage" / "agent_runtime_cycle.json"
            )
            run_cycle_loop = CognitiveLoop(
                runtime=run_cycle_runtime,
                state_path=temp_root / "storage" / "cognitive_loop_cycle.json",
            )
            run_cycle_planner = RecordingPlanner()
            cognitive_loop_module.PLANNER_RUNTIME = run_cycle_planner
            run_cycle_result = run_cycle_loop.run_cycle(trigger="semantic-mesh-smoke")
            run_cycle_plan = dict(
                (run_cycle_result.get("last_cycle") or {}).get("plan") or {}
            )

            checks = {
                "default_plan_has_no_semantic_mesh_advisory": (
                    "semantic_mesh_advisory" not in default_plan
                ),
                "opt_in_plan_has_top_level_semantic_mesh_advisory": bool(advisory),
                "opt_in_changes_only_top_level_advisory": (
                    opt_in_without_semantic == default_plan
                ),
                "semantic_advisory_not_in_task_metadata": (
                    not semantic_advisory_in_task_metadata(opt_in_plan)
                ),
                "mode_is_advisory_only": advisory.get("mode") == "advisory_only",
                "runtime_enforcement_false": advisory.get("runtime_enforcement") is False,
                "planner_input_applied_false": advisory.get("planner_input_applied") is False,
                "dispatch_input_applied_false": advisory.get("dispatch_input_applied") is False,
                "planner_context_persistence_false": (
                    advisory.get("planner_context_persistence") is False
                ),
                "storage_schema_mutation_false": (
                    advisory.get("storage_schema_mutation") is False
                ),
                "public_api_behavior_mutation_false": (
                    advisory.get("public_api_behavior_mutation") is False
                ),
                "advisory_excludes_raw_mesh_plan_and_evidence": (
                    not (advisory_keys & FORBIDDEN_ADVISORY_KEYS)
                ),
                "mesh_not_mutated": mesh.to_dict() == mesh_before,
                "plan_does_not_read_memory_when_mesh_is_supplied": True,
                "cognitive_loop_does_not_build_semantic_mesh": (
                    not cognitive_loop_builds_mesh(cognitive_source)
                ),
                "act_counts_ignore_semantic_advisory": (
                    action_with_advisory.get("registered_count")
                    == action_without_advisory.get("registered_count")
                    and action_with_advisory.get("queued_count")
                    == action_without_advisory.get("queued_count")
                ),
                "planner_calls_identical_with_or_without_semantic_advisory": (
                    planner_signature_with == planner_signature_without
                ),
                "planner_calls_exclude_semantic_advisory": (
                    "semantic_mesh_advisory" not in nested_keys(planner_signature_with)
                ),
                "plan_serialization_filters_both_advisories": (
                    serialized_plan == expected_serialized_plan
                ),
                "cycle_serialization_filters_both_advisories": (
                    serialized_cycle_plan == expected_serialized_plan
                ),
                "default_run_cycle_has_no_semantic_mesh_advisory": (
                    "semantic_mesh_advisory" not in run_cycle_plan
                ),
            }
            details["plan"] = {
                "default_keys": sorted(default_plan.keys()),
                "opt_in_keys": sorted(opt_in_plan.keys()),
                "advisory_keys": sorted(advisory.keys()),
                "task_count": len(opt_in_plan.get("tasks") or []),
                "plan_group_count": len(opt_in_plan.get("plan_groups") or []),
                "recovery_request_count": len(opt_in_plan.get("recovery_requests") or []),
            }
            details["planner_signature_with_advisory"] = planner_signature_with
            details["planner_signature_without_advisory"] = planner_signature_without
            details["serialized_plan_keys"] = sorted((serialized_plan or {}).keys())
            details["default_run_cycle_plan_keys"] = sorted(run_cycle_plan.keys())
        finally:
            cognitive_loop_module.MemoryEngine = previous_memory_engine
            cognitive_loop_module.PLANNER_RUNTIME = previous_planner
    finally:
        config.PROJECT_ROOT = previous_project_root
        config.ENV_FILE = previous_env_file
        runtime_store.RUNTIME_FILE = previous_runtime_file

    project_state_after = project_runtime_state_metadata()
    checks["project_runtime_state_untouched"] = project_state_before == project_state_after
    details["project_runtime_state_before"] = project_state_before
    details["project_runtime_state_after"] = project_state_after

    return {
        "status": "ok" if all(checks.values()) else "failed",
        "service": SERVICE_NAME,
        "checks": checks,
        "details": details,
    }


def print_result(result: dict, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


def main() -> int:
    args = parse_args()
    temp_root = Path(tempfile.gettempdir()) / f"gptmeai_semantic_mesh_cognitive_{uuid.uuid4().hex}"
    cleanup_succeeded = False
    cleanup_error = None
    result: dict
    try:
        result = run_smoke(temp_root)
    finally:
        if args.cleanup:
            try:
                shutil.rmtree(temp_root, ignore_errors=False)
                cleanup_succeeded = not temp_root.exists()
            except OSError as exc:
                cleanup_error = str(exc)
                cleanup_succeeded = False

    result["temp_root"] = str(temp_root)
    result["cleanup_requested"] = bool(args.cleanup)
    result["cleanup_succeeded"] = cleanup_succeeded if args.cleanup else None
    result["cleanup_error"] = cleanup_error
    result["temp_root_exists_after_cleanup"] = temp_root.exists()
    if args.cleanup and not cleanup_succeeded:
        result["status"] = "failed"
        result.setdefault("checks", {})["cleanup_succeeded"] = False
    elif args.cleanup:
        result.setdefault("checks", {})["cleanup_succeeded"] = True
    print_result(result, as_json=args.json)
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
