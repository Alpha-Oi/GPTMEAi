"""Temp-state smoke for Concept Core advisory downstream consumers."""

from __future__ import annotations

import argparse
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke-test CognitiveLoop.plan() Concept Core advisory consumer serialization."
    )
    parser.add_argument("--json", action="store_true", help="Print compact JSON output.")
    parser.add_argument("--cleanup", action="store_true", help="Remove the temp root after the smoke.")
    return parser.parse_args()


def file_metadata(path: Path) -> dict:
    if not path.exists():
        return {"exists": False}
    stat = path.stat()
    return {
        "exists": True,
        "size": stat.st_size,
        "mtime": stat.st_mtime,
    }


def project_runtime_state_metadata() -> dict:
    paths = [
        PROJECT_ROOT / "GPTMemory_runtime.yaml",
        PROJECT_ROOT / "storage" / "cognitive_loop_state.json",
        PROJECT_ROOT / "storage" / "agent_runtime.json",
        PROJECT_ROOT / "storage" / "planner_runtime.json",
        PROJECT_ROOT / "storage" / "execution_runtime.json",
        PROJECT_ROOT / "storage" / "operation_ledger.json",
        PROJECT_ROOT / "storage" / "snapshot_lineage.json",
    ]
    return {str(path): file_metadata(path) for path in paths}


def ensure_temp_layout(temp_root: Path) -> None:
    for relative in [
        "storage/snapshots",
        "dashboard",
        "memory/chats",
        "memory/parsed",
        "memory/knowledge",
        "memory/embeddings",
    ]:
        (temp_root / relative).mkdir(parents=True, exist_ok=True)
    (temp_root / "dashboard" / "index.html").write_text(
        "<html><body>temp dashboard</body></html>",
        encoding="utf-8",
    )
    (temp_root / "GPTMemory_runtime.yaml").write_text(
        json.dumps(
            {
                "memory_blocks": [
                    {
                        "id": 1,
                        "text": "Temp smoke memory for Concept Core advisory consumer coverage.",
                        "importance": 5,
                        "tags": ["runtime", "smoke"],
                        "created_at": "2026-04-30T00:00:00+00:00",
                    }
                ],
                "last_updated": "2026-04-30T00:00:00+00:00",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def strip_advisory(plan: dict) -> dict:
    payload = copy.deepcopy(plan)
    payload.pop("concept_core_advisory", None)
    return payload


def advisory_in_task_metadata(plan: dict) -> bool:
    for task in list(plan.get("tasks") or []):
        if "concept_core_advisory" in dict(task.get("metadata") or {}):
            return True
    for group in list(plan.get("plan_groups") or []):
        for task in list(group.get("tasks") or []):
            if "concept_core_advisory" in dict(task.get("metadata") or {}):
                return True
    return False


class RecordingPlanner:
    def __init__(self) -> None:
        self.created_plans: list[dict] = []
        self.recovery_requests: list[dict] = []
        self.execute_calls: list[str] = []

    def branch_health_snapshot(self, *, limit: int = 10) -> dict:
        return {
            "status": "ok",
            "service": "Recording Planner",
            "branch_counts": {},
            "branches": [],
            "playbook_counts": {},
            "playbooks": [],
            "limit": limit,
        }

    def status_snapshot(self, *, limit: int = 5, plan_id: str | None = None) -> dict:
        return {
            "status": "ok",
            "service": "Recording Planner",
            "state_file": "temp-recording-planner",
            "plan_counts": {
                "total": len(self.created_plans) + len(self.recovery_requests),
                "active": len(self.created_plans) + len(self.recovery_requests),
            },
            "plan_kind_counts": {
                "operational": len(self.created_plans),
                "recovery": len(self.recovery_requests),
            },
            "step_counts": {
                "total": 0,
                "queued": 0,
                "in_progress": 0,
                "completed": 0,
                "blocked": 0,
                "failed": 0,
            },
            "active_focus": [],
            "plans": [],
            "limit": limit,
            "plan_id": plan_id,
        }

    def create_or_refresh_plan(self, **kwargs) -> dict:
        self.created_plans.append(copy.deepcopy(kwargs))
        return {
            "id": f"recorded-plan-{len(self.created_plans)}",
            "plan_kind": kwargs.get("plan_kind", "operational"),
            "steps": [],
        }

    def create_recovery_plan_from_replay(self, **kwargs) -> dict:
        self.recovery_requests.append(copy.deepcopy(kwargs))
        return {
            "id": f"recorded-recovery-{len(self.recovery_requests)}",
            "plan_kind": "recovery",
            "steps": [],
        }

    def execute_ready_steps(self, *, plan_id: str | None = None) -> dict:
        self.execute_calls.append(str(plan_id or ""))
        return {"queued_count": 0, "queued_steps": []}


def planner_calls_ignore_advisory(planner: RecordingPlanner) -> bool:
    for call in planner.created_plans:
        if "concept_core_advisory" in dict(call.get("context") or {}):
            return False
        for task in list(call.get("task_specs") or []):
            if "concept_core_advisory" in dict(task.get("metadata") or {}):
                return False
    for call in planner.recovery_requests:
        if "concept_core_advisory" in call:
            return False
    return True


def planner_call_signature(planner: RecordingPlanner) -> dict:
    return {
        "created_plans": copy.deepcopy(planner.created_plans),
        "recovery_requests": copy.deepcopy(planner.recovery_requests),
        "execute_call_count": len(planner.execute_calls),
    }


def compare_plan_shape(plan: dict, stripped_plan: dict) -> bool:
    return (
        set(plan.keys()) == set(stripped_plan.keys()) | {"concept_core_advisory"}
        and len(plan.get("tasks") or []) == len(stripped_plan.get("tasks") or [])
        and len(plan.get("plan_groups") or []) == len(stripped_plan.get("plan_groups") or [])
        and len(plan.get("recovery_requests") or []) == len(stripped_plan.get("recovery_requests") or [])
        and list(plan.get("planned_task_titles") or []) == list(stripped_plan.get("planned_task_titles") or [])
    )


def compare_serialized_plan_shape(serialized_plan: dict, direct_plan: dict) -> bool:
    stripped_plan = strip_advisory(direct_plan)
    return (
        set(serialized_plan.keys()) == set(stripped_plan.keys())
        and len(serialized_plan.get("tasks") or []) == len(stripped_plan.get("tasks") or [])
        and len(serialized_plan.get("plan_groups") or []) == len(stripped_plan.get("plan_groups") or [])
        and len(serialized_plan.get("recovery_requests") or []) == len(stripped_plan.get("recovery_requests") or [])
        and list(serialized_plan.get("planned_task_titles") or [])
        == list(stripped_plan.get("planned_task_titles") or [])
    )


def run_smoke(temp_root: Path) -> dict:
    import ai_os.config as config

    project_state_before = project_runtime_state_metadata()
    ensure_temp_layout(temp_root)

    previous_project_root = config.PROJECT_ROOT
    previous_env_file = config.ENV_FILE
    config.PROJECT_ROOT = temp_root
    config.ENV_FILE = temp_root / ".env"

    checks: dict[str, bool] = {}
    details: dict[str, object] = {
        "temp_root": str(temp_root),
        "project_root": str(PROJECT_ROOT),
    }

    try:
        import scripts.runtime_store as runtime_store

        previous_runtime_file = runtime_store.RUNTIME_FILE
        runtime_store.RUNTIME_FILE = temp_root / "GPTMemory_runtime.yaml"

        try:
            import ai_os.cognitive_loop as cognitive_loop_module
            from ai_os.agent_runtime import AgentRuntime
            from ai_os.cognitive_loop import CognitiveLoop

            previous_planner = cognitive_loop_module.PLANNER_RUNTIME
            try:
                direct_runtime = AgentRuntime(state_path=temp_root / "storage" / "agent_runtime_direct.json")
                direct_loop = CognitiveLoop(
                    runtime=direct_runtime,
                    state_path=temp_root / "storage" / "cognitive_loop_direct.json",
                )

                perception = direct_loop.perceive()
                reasoning = direct_loop.reason(perception)
                plan = direct_loop.plan(perception, reasoning)
                stripped_plan = strip_advisory(plan)
                advisory = dict(plan.get("concept_core_advisory") or {})

                planner_with_advisory = RecordingPlanner()
                cognitive_loop_module.PLANNER_RUNTIME = planner_with_advisory
                action_with_advisory = direct_loop.act(copy.deepcopy(plan))

                stripped_runtime = AgentRuntime(state_path=temp_root / "storage" / "agent_runtime_stripped.json")
                stripped_loop = CognitiveLoop(
                    runtime=stripped_runtime,
                    state_path=temp_root / "storage" / "cognitive_loop_stripped.json",
                )
                planner_without_advisory = RecordingPlanner()
                cognitive_loop_module.PLANNER_RUNTIME = planner_without_advisory
                action_without_advisory = stripped_loop.act(copy.deepcopy(stripped_plan))

                details["direct_plan"] = {
                    "keys": sorted(plan.keys()),
                    "stripped_keys": sorted(stripped_plan.keys()),
                    "task_count": len(plan.get("tasks") or []),
                    "plan_group_count": len(plan.get("plan_groups") or []),
                    "recovery_request_count": len(plan.get("recovery_requests") or []),
                    "advisory_mode": advisory.get("mode"),
                    "runtime_enforcement": advisory.get("runtime_enforcement"),
                }
                details["act_with_advisory"] = {
                    "registered_count": action_with_advisory.get("registered_count"),
                    "queued_count": action_with_advisory.get("queued_count"),
                    "planner_signature": planner_call_signature(planner_with_advisory),
                }
                details["act_without_advisory"] = {
                    "registered_count": action_without_advisory.get("registered_count"),
                    "queued_count": action_without_advisory.get("queued_count"),
                    "planner_signature": planner_call_signature(planner_without_advisory),
                }

                checks["plan_output_contains_top_level_concept_core_advisory"] = bool(advisory)
                checks["advisory_is_top_level_only_for_tasks"] = not advisory_in_task_metadata(plan)
                checks["task_counts_plan_groups_recovery_requests_unchanged_except_advisory"] = compare_plan_shape(
                    plan,
                    stripped_plan,
                )
                checks["act_ignores_concept_core_advisory"] = (
                    action_with_advisory.get("registered_count") == action_without_advisory.get("registered_count")
                    and action_with_advisory.get("queued_count") == action_without_advisory.get("queued_count")
                    and planner_call_signature(planner_with_advisory)
                    == planner_call_signature(planner_without_advisory)
                )
                checks["planner_calls_do_not_receive_concept_core_advisory"] = planner_calls_ignore_advisory(
                    planner_with_advisory
                )
                checks["planner_call_count_matches_plan_groups_and_recovery_requests"] = (
                    len(planner_with_advisory.created_plans) == len(plan.get("plan_groups") or [])
                    and len(planner_with_advisory.recovery_requests) == len(plan.get("recovery_requests") or [])
                )

                cycle_runtime = AgentRuntime(state_path=temp_root / "storage" / "agent_runtime_cycle.json")
                cycle_loop = CognitiveLoop(
                    runtime=cycle_runtime,
                    state_path=temp_root / "storage" / "cognitive_loop_cycle.json",
                )
                cycle_planner = RecordingPlanner()
                cognitive_loop_module.PLANNER_RUNTIME = cycle_planner
                run_result = cycle_loop.run_cycle(trigger="smoke")
                status_snapshot = cycle_loop.status_snapshot()
                state_text = cycle_loop.state_path.read_text(encoding="utf-8")
                state_payload = json.loads(state_text)

                last_cycle = dict(status_snapshot.get("last_cycle") or {})
                last_plan = dict(last_cycle.get("plan") or {})
                run_last_cycle = dict(run_result.get("last_cycle") or {})
                run_last_plan = dict(run_last_cycle.get("plan") or {})
                persisted_last_cycle = dict(state_payload.get("last_cycle") or {})
                persisted_last_plan = dict(persisted_last_cycle.get("plan") or {})

                status_exposes_advisory = "concept_core_advisory" in last_plan
                run_exposes_advisory = "concept_core_advisory" in run_last_plan
                persisted_advisory = "concept_core_advisory" in persisted_last_plan

                details["serialization_behavior"] = {
                    "status_snapshot_has_last_cycle": bool(last_cycle),
                    "last_cycle_plan_keys": sorted(last_plan.keys()),
                    "run_result_plan_keys": sorted(run_last_plan.keys()),
                    "persisted_plan_keys": sorted(persisted_last_plan.keys()),
                    "status_snapshot_exposes_advisory": status_exposes_advisory,
                    "cognitive_run_shaped_output_exposes_advisory": run_exposes_advisory,
                    "state_file_persists_advisory": persisted_advisory,
                    "cycle_state_path": str(cycle_loop.state_path),
                }
                details["cycle_planner_signature"] = planner_call_signature(cycle_planner)

                checks["status_snapshot_exposes_last_cycle"] = bool(last_cycle)
                checks["persisted_last_cycle_plan_filters_concept_core_advisory"] = not persisted_advisory
                checks["status_snapshot_last_cycle_plan_filters_concept_core_advisory"] = not status_exposes_advisory
                checks["run_cycle_returned_last_cycle_plan_filters_concept_core_advisory"] = not run_exposes_advisory
                checks["serialized_plan_task_shape_matches_direct_plan"] = (
                    compare_serialized_plan_shape(last_plan, plan)
                    and compare_serialized_plan_shape(run_last_plan, plan)
                    and compare_serialized_plan_shape(persisted_last_plan, plan)
                )
                checks["cycle_planner_calls_do_not_receive_concept_core_advisory"] = planner_calls_ignore_advisory(
                    cycle_planner
                )
            finally:
                cognitive_loop_module.PLANNER_RUNTIME = previous_planner
        finally:
            runtime_store.RUNTIME_FILE = previous_runtime_file
    finally:
        config.PROJECT_ROOT = previous_project_root
        config.ENV_FILE = previous_env_file

    project_state_after = project_runtime_state_metadata()
    checks["project_runtime_state_untouched"] = project_state_before == project_state_after
    details["project_runtime_state_before"] = project_state_before
    details["project_runtime_state_after"] = project_state_after

    return {
        "status": "ok" if all(checks.values()) else "failed",
        "service": "AI OS Concept Core Advisory Consumer Smoke",
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
    temp_root = Path(tempfile.gettempdir()) / f"gptmeai_concept_core_advisory_consumers_{uuid.uuid4().hex}"
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
