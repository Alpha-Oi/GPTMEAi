"""Temp-state smoke for cognitive-loop Concept Core decision advisory."""

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
    parser = argparse.ArgumentParser(description="Smoke-test Concept Core cognitive-loop decision advisory.")
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
        json.dumps({"memory_blocks": [], "last_updated": None}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def base_perception() -> dict:
    return {
        "timestamp": "2026-04-29T00:00:00+00:00",
        "memory_count": 3,
        "recent_memory": [],
        "top_tags": [{"tag": "runtime", "count": 2}],
        "agent_counts": {"total": 0, "managers": 0, "workers": 0},
        "task_counts": {"queued": 0, "in_progress": 0},
        "stabilization_memory": {"count": 0, "branch_counts": [], "recent": []},
        "stabilization_playbooks": {"playbook_counts": {"reuse_ready": 0}, "branches": []},
        "planner_branch_health": {"counts": {}, "branches": [], "playbook_counts": {}, "playbooks": []},
        "pipeline": {
            "counts": {},
            "available": {"index": True, "parsed": True, "knowledge": True, "vectors": True},
        },
        "execution": {
            "failed_count": 0,
            "pending_compensation_count": 0,
            "available_compensation_count": 0,
            "recent_failures": [],
            "pending_compensations": [],
            "repeated_attempts": [],
        },
        "operation_ledger": {
            "repeated_failures": [],
            "hot_branches": [],
            "non_main_branch_count": 0,
            "max_branch_depth": 0,
        },
        "snapshot_lineage": {
            "snapshot_counts": {
                "total": 1,
                "branch_count": 1,
                "non_main_branch_count": 0,
            }
        },
    }


def base_reasoning() -> dict:
    return {
        "observations": ["execution queue is idle"],
        "focus_tags": ["runtime"],
        "primary_focus": "runtime",
        "missing_artifacts": [],
        "queue_idle": True,
        "execution_attention": False,
        "recent_failures": [],
        "pending_compensations": [],
        "repeated_attempts": [],
        "repeated_failures": [],
        "hot_branches": [],
        "non_main_branch_count": 0,
        "snapshot_branch_count": 1,
        "snapshot_coverage_branches": [],
        "pressure_branches": [],
        "planner_branch_counts": {},
        "stabilization_memory_count": 0,
        "stabilization_memory_branches": [],
        "stabilization_playbook_counts": {"reuse_ready": 0},
    }


def strip_advisory(plan: dict) -> dict:
    payload = copy.deepcopy(plan)
    payload.pop("concept_core_advisory", None)
    return payload


def advisory_task_metadata_absent(plan: dict) -> bool:
    for task in list(plan.get("tasks") or []):
        metadata = dict(task.get("metadata") or {})
        if "concept_core_advisory" in metadata:
            return False
    for group in list(plan.get("plan_groups") or []):
        for task in list(group.get("tasks") or []):
            metadata = dict(task.get("metadata") or {})
            if "concept_core_advisory" in metadata:
                return False
    return True


class RecordingPlanner:
    def __init__(self) -> None:
        self.created_plans: list[dict] = []
        self.recovery_requests: list[dict] = []
        self.execute_calls: list[str] = []

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


def run_smoke(temp_root: Path) -> dict:
    import ai_os.config as config

    project_runtime_file = PROJECT_ROOT / "GPTMemory_runtime.yaml"
    project_runtime_before = file_metadata(project_runtime_file)
    ensure_temp_layout(temp_root)

    previous_project_root = config.PROJECT_ROOT
    previous_env_file = config.ENV_FILE
    config.PROJECT_ROOT = temp_root
    config.ENV_FILE = temp_root / ".env"

    checks: dict[str, bool] = {}
    details: dict[str, object] = {
        "temp_root": str(temp_root),
        "project_runtime_file": str(project_runtime_file),
    }

    try:
        import scripts.runtime_store as runtime_store

        runtime_store.RUNTIME_FILE = temp_root / "GPTMemory_runtime.yaml"

        import ai_os.cognitive_loop as cognitive_loop_module
        from ai_os.agent_runtime import AgentRuntime
        from ai_os.cognitive_loop import CognitiveLoop

        runtime = AgentRuntime(state_path=temp_root / "storage" / "agent_runtime_smoke.json")
        loop = CognitiveLoop(
            runtime=runtime,
            state_path=temp_root / "storage" / "cognitive_loop_smoke_state.json",
        )

        perception = base_perception()
        reasoning = base_reasoning()
        plan = loop.plan(perception, reasoning)
        advisory = dict(plan.get("concept_core_advisory") or {})
        decision = dict(advisory.get("decision") or {})
        evidence_counts = dict(advisory.get("evidence_status_counts") or {})
        red_button = dict(advisory.get("red_button") or {})
        action_summary = dict(advisory.get("planned_action_summary") or {})
        stripped_plan = strip_advisory(plan)

        details["normal_plan"] = {
            "keys": sorted(plan.keys()),
            "stripped_keys": sorted(stripped_plan.keys()),
            "task_count": len(plan.get("tasks") or []),
            "plan_group_count": len(plan.get("plan_groups") or []),
            "recovery_request_count": len(plan.get("recovery_requests") or []),
        }
        details["normal_advisory"] = advisory

        checks["concept_core_advisory_present_on_plan_output"] = bool(advisory)
        checks["advisory_mode_is_advisory_only"] = advisory.get("mode") == "advisory_only"
        checks["runtime_enforcement_false"] = advisory.get("runtime_enforcement") is False
        checks["runtime_blocking_applied_false"] = red_button.get("runtime_blocking_applied") is False
        checks["decision_payload_present_and_serializable"] = bool(decision) and isinstance(
            json.loads(json.dumps(decision)),
            dict,
        )
        checks["evidence_status_counts_contains_confirmed_and_inference"] = (
            "confirmed" in evidence_counts and "inference" in evidence_counts
        )
        checks["planned_action_summary_contains_required_fields"] = all(
            key in action_summary
            for key in ["plan_group_count", "task_count", "recovery_request_count", "planned_task_titles"]
        )
        checks["planned_action_summary_matches_plan"] = (
            action_summary.get("plan_group_count") == len(plan.get("plan_groups") or [])
            and action_summary.get("task_count") == len(plan.get("tasks") or [])
            and action_summary.get("recovery_request_count") == len(plan.get("recovery_requests") or [])
            and action_summary.get("planned_task_titles") == list(plan.get("planned_task_titles") or [])
        )

        red_plan = copy.deepcopy(stripped_plan)
        red_plan["tasks"] = list(red_plan.get("tasks") or []) + [
            {
                "step_key": "dangerous_advisory_probe",
                "title": "Destroy production storage and remove rollback",
                "preferred_role": "worker",
                "metadata": {},
            }
        ]
        red_plan["planned_task_titles"] = list(red_plan.get("planned_task_titles") or []) + [
            "Destroy production storage and remove rollback"
        ]
        helper = getattr(loop, "_build_concept_core_plan_advisory", None)
        red_advisory = helper(perception, reasoning, red_plan) if callable(helper) else {}
        red_red_button = dict(red_advisory.get("red_button") or {})
        details["red_button_advisory"] = red_advisory
        checks["synthetic_red_button_detected"] = red_red_button.get("detected") is True
        checks["synthetic_red_button_would_block_if_enforced"] = red_advisory.get("would_block_if_enforced") is True
        checks["synthetic_red_button_runtime_enforcement_false"] = red_advisory.get("runtime_enforcement") is False
        checks["synthetic_red_button_runtime_blocking_applied_false"] = (
            red_red_button.get("runtime_blocking_applied") is False
        )

        checks["normal_plan_task_titles_count_groups_recovery_unchanged_except_advisory"] = (
            set(plan.keys()) == set(stripped_plan.keys()) | {"concept_core_advisory"}
            and len(plan.get("tasks") or []) == len(stripped_plan.get("tasks") or [])
            and len(plan.get("plan_groups") or []) == len(stripped_plan.get("plan_groups") or [])
            and len(plan.get("recovery_requests") or []) == len(stripped_plan.get("recovery_requests") or [])
            and list(plan.get("planned_task_titles") or []) == list(stripped_plan.get("planned_task_titles") or [])
        )
        checks["concept_core_advisory_not_attached_to_task_metadata"] = advisory_task_metadata_absent(plan)

        previous_planner = cognitive_loop_module.PLANNER_RUNTIME
        recording_planner = RecordingPlanner()
        cognitive_loop_module.PLANNER_RUNTIME = recording_planner
        try:
            action = loop.act(plan)
        finally:
            cognitive_loop_module.PLANNER_RUNTIME = previous_planner
        details["act_probe"] = {
            "registered_count": action.get("registered_count"),
            "queued_count": action.get("queued_count"),
            "created_plan_count": len(recording_planner.created_plans),
            "execute_call_count": len(recording_planner.execute_calls),
        }
        checks["planner_dispatch_behavior_not_changed_by_advisory"] = (
            len(recording_planner.created_plans) == len(plan.get("plan_groups") or [])
            and planner_calls_ignore_advisory(recording_planner)
        )
        checks["act_behavior_ignores_advisory"] = action.get("queued_count") == 0 and planner_calls_ignore_advisory(
            recording_planner
        )
    finally:
        config.PROJECT_ROOT = previous_project_root
        config.ENV_FILE = previous_env_file

    project_runtime_after = file_metadata(project_runtime_file)
    checks["project_runtime_file_unchanged_before_after"] = project_runtime_before == project_runtime_after
    details["project_runtime_before"] = project_runtime_before
    details["project_runtime_after"] = project_runtime_after

    return {
        "status": "ok" if all(checks.values()) else "failed",
        "service": "AI OS Concept Core Decision Advisory Smoke",
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
    temp_root = Path(tempfile.gettempdir()) / f"gptmeai_concept_core_decision_advisory_{uuid.uuid4().hex}"
    cleanup_succeeded = False
    cleanup_error = None
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
    print_result(result, as_json=args.json)
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
