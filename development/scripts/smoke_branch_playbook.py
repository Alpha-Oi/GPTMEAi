"""Isolated smoke test for branch stabilization playbook reuse."""

from __future__ import annotations

import argparse
import gc
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TMP_DIR = ROOT / "development" / "tmp"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import ai_os.agent_runtime as agent_runtime_module
import ai_os.cognitive_loop as cognitive_loop_module
import execution.runtime as execution_runtime_module
import planning.runtime as planning_runtime_module
import scripts.runtime_store as runtime_store_module
from ai_os.agent_runtime import AgentRuntime
from ai_os.cognitive_loop import CognitiveLoop, build_task_metadata
from ai_os.stabilization_playbook import build_stabilization_playbooks
from core.memory_engine import MemoryEngine
from execution.ledger import OperationLedger
from execution.runtime import ExecutionRuntime
from execution.snapshots import SnapshotLineageRegistry
from planning.runtime import PlannerRuntime


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")


def utc_now(offset_seconds: int = 0) -> str:
    return (datetime.now(UTC) + timedelta(seconds=offset_seconds)).isoformat()


def make_temp_paths(tag: str) -> dict[str, Path]:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    suffix = utc_stamp()
    return {
        "runtime": TMP_DIR / f"runtime_store_{tag}_{suffix}.json",
        "agent": TMP_DIR / f"agent_runtime_{tag}_{suffix}.json",
        "execution": TMP_DIR / f"execution_runtime_{tag}_{suffix}.json",
        "ledger": TMP_DIR / f"operation_ledger_{tag}_{suffix}.json",
        "planner": TMP_DIR / f"planner_runtime_{tag}_{suffix}.json",
        "snapshots": TMP_DIR / f"snapshot_lineage_{tag}_{suffix}.json",
        "cognitive": TMP_DIR / f"cognitive_loop_{tag}_{suffix}.json",
    }


def cleanup_paths(paths: dict[str, Path]) -> list[str]:
    remaining: list[str] = []
    gc.collect()
    for path in paths.values():
        try:
            if path.exists():
                path.unlink()
        except OSError:
            remaining.append(str(path))
    return remaining


def register_default_agents(runtime: AgentRuntime) -> dict[str, dict]:
    return {
        "development_manager": runtime.register_agent(
            "Development Manager",
            "manager",
            capabilities=["planning", "coordination", "recovery"],
        ),
        "research_agent": runtime.register_agent(
            "Research Agent",
            "worker",
            capabilities=["analysis", "retrieval", "summarization"],
        ),
        "coding_agent": runtime.register_agent(
            "Coding Agent",
            "worker",
            capabilities=["runtime", "integration", "delivery"],
        ),
        "memory_agent": runtime.register_agent(
            "Memory Agent",
            "worker",
            capabilities=["memory-ingestion", "graph-build", "vector-memory"],
        ),
    }


def branch_stabilization_task_specs(branch_id: str) -> list[dict]:
    return [
        {
            "step_key": "branch_stabilization_coordination",
            "title": f"Coordinate branch stabilization for {branch_id}",
            "preferred_role": "manager",
            "metadata": build_task_metadata(
                owner_hint="Development Manager",
                timeout_seconds=180,
                max_retries=0,
                rollback_on_error=True,
                compensation_action="record_branch_stabilization_coordination",
                compensation_description="Preserve only the branch stabilization coordination trace if the plan cannot continue.",
            ) | {"branch_id": branch_id},
        },
        {
            "step_key": "review_branch_pressure_controls",
            "depends_on": ["branch_stabilization_coordination"],
            "title": f"Review branch pressure controls for {branch_id}",
            "preferred_role": "worker",
            "metadata": build_task_metadata(
                owner_hint="Research Agent",
                timeout_seconds=180,
                max_retries=0,
                rollback_on_error=True,
                compensation_action="record_branch_pressure_review",
                compensation_description="Preserve the branch pressure review trace if the analysis cannot complete safely.",
            ) | {"branch_id": branch_id},
        },
        {
            "step_key": "stabilize_branch_dispatch_policy",
            "depends_on": ["review_branch_pressure_controls"],
            "title": f"Stabilize branch dispatch policy for {branch_id}",
            "preferred_role": "worker",
            "metadata": build_task_metadata(
                owner_hint="Coding Agent",
                timeout_seconds=240,
                max_retries=0,
                rollback_on_error=True,
                compensation_action="record_branch_dispatch_stabilization",
                compensation_description="Keep only the dispatch stabilization trace if the branch policy cannot be tightened safely.",
            ) | {"branch_id": branch_id},
        },
    ]


def complete_plan_chain(
    planner: PlannerRuntime,
    runtime: AgentRuntime,
    *,
    plan_id: str,
) -> dict:
    initial_queue = planner.execute_ready_steps(plan_id=plan_id)
    initial_dispatch = runtime.dispatch_ready_tasks(plan_id=plan_id, limit=3)
    queued_sequence = [
        step.get("step_key")
        for step in (initial_queue.get("queued_steps") or [])
        if step.get("step_key")
    ]
    assignment_sequence = [
        assignment.get("agent_name")
        for assignment in (initial_dispatch.get("assignments") or [])
        if assignment.get("agent_name")
    ]

    dispatch = dict(initial_dispatch)
    while int(dispatch.get("dispatch_count", 0) or 0) > 0:
        assignments = list(dispatch.get("assignments") or [])
        if not assignments:
            break

        assignment = dict(assignments[0])
        completed_task = runtime.complete_task(
            str(assignment.get("agent_id")),
            int(assignment.get("task_id")),
            result=f"{assignment.get('title') or assignment.get('task_id')} completed",
            success=True,
        )
        advance = planner.advance_from_task(
            completed_task,
            auto_dispatch=True,
            auto_compensate=True,
            dispatch_limit=3,
        )
        queue_payload = dict(
            advance.get("queue")
            or advance.get("execution")
            or {}
        )
        dispatch = dict(advance.get("dispatch") or {})
        if not dispatch:
            dispatch = runtime.dispatch_ready_tasks(plan_id=plan_id, limit=3)
        queued_sequence.extend(
            step.get("step_key")
            for step in (queue_payload.get("queued_steps") or [])
            if step.get("step_key")
        )
        assignment_sequence.extend(
            assignment_item.get("agent_name")
            for assignment_item in (dispatch.get("assignments") or [])
            if assignment_item.get("agent_name")
        )

    plan_snapshot = planner.status_snapshot(plan_id=plan_id)
    plan_payload = dict((plan_snapshot.get("plans") or [{}])[0])
    if plan_payload.get("status") != "completed":
        raise AssertionError(f"expected completed plan, got {plan_payload.get('status')}")

    return {
        "queued_sequence": queued_sequence,
        "assignment_sequence": assignment_sequence,
        "plan": plan_payload,
    }


def seed_branch_health_history(planner: PlannerRuntime, branch_id: str) -> None:
    observations = [
        planner._branch_health_observation_from_source(
            branch_id=branch_id,
            plan_id="history_obs_01",
            plan_status="completed",
            current_phase="validation",
            branch_health={
                "status": "observe",
                "recommendation": "heightened_monitoring",
                "quality_score": 82,
                "confidence_score": 86,
                "planner_gate": {"mode": "guarded", "recommended_action": "heightened_monitoring"},
            },
            timestamp=utc_now(-180),
        ),
        planner._branch_health_observation_from_source(
            branch_id=branch_id,
            plan_id="history_obs_02",
            plan_status="completed",
            current_phase="validation",
            branch_health={
                "status": "observe",
                "recommendation": "heightened_monitoring",
                "quality_score": 60,
                "confidence_score": 66,
                "planner_gate": {"mode": "restricted", "recommended_action": "stabilize_branch_pressure"},
            },
            timestamp=utc_now(-120),
        ),
        planner._branch_health_observation_from_source(
            branch_id=branch_id,
            plan_id="history_obs_03",
            plan_status="completed",
            current_phase="validation",
            branch_health={
                "status": "observe",
                "recommendation": "heightened_monitoring",
                "quality_score": 54,
                "confidence_score": 60,
                "planner_gate": {"mode": "restricted", "recommended_action": "stabilize_branch_pressure"},
            },
            timestamp=utc_now(-60),
        ),
    ]
    planner._branch_health_history[branch_id] = [item for item in observations if item is not None]
    planner._save_state()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run isolated branch stabilization playbook smoke test.")
    parser.add_argument("--tag", default="branch_playbook", help="Temp-file prefix tag.")
    parser.add_argument("--cleanup", action="store_true", help="Attempt to delete temp state files after the run.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON summary.")
    args = parser.parse_args()

    temp_paths = make_temp_paths(args.tag)
    previous_runtime_file = runtime_store_module.RUNTIME_FILE
    previous_agent_execution_runtime = agent_runtime_module.EXECUTION_RUNTIME
    previous_execution_runtime = execution_runtime_module.EXECUTION_RUNTIME
    previous_snapshot_lineage = planning_runtime_module.SNAPSHOT_LINEAGE
    previous_cognitive_planner = cognitive_loop_module.PLANNER_RUNTIME
    previous_cognitive_execution = cognitive_loop_module.EXECUTION_RUNTIME
    previous_cognitive_ledger = cognitive_loop_module.OPERATION_LEDGER
    previous_cognitive_snapshots = cognitive_loop_module.SNAPSHOT_LINEAGE

    result: dict[str, object] = {
        "status": "error",
        "service": "AI OS Branch Stabilization Playbook Smoke Test",
        "temp_files": {key: str(path) for key, path in temp_paths.items()},
    }

    try:
        runtime_store_module.RUNTIME_FILE = temp_paths["runtime"]
        temp_paths["runtime"].write_text(
            json.dumps({"memory_blocks": [], "last_updated": None}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        ledger = OperationLedger(temp_paths["ledger"])
        snapshot_lineage = SnapshotLineageRegistry(temp_paths["snapshots"], ledger=ledger)
        execution_runtime = ExecutionRuntime(temp_paths["execution"], ledger=ledger)

        agent_runtime_module.EXECUTION_RUNTIME = execution_runtime
        execution_runtime_module.EXECUTION_RUNTIME = execution_runtime
        planning_runtime_module.SNAPSHOT_LINEAGE = snapshot_lineage

        agent_runtime = AgentRuntime(temp_paths["agent"])
        planner = PlannerRuntime(temp_paths["planner"], runtime=agent_runtime)
        cognitive_loop_module.PLANNER_RUNTIME = planner
        cognitive_loop_module.EXECUTION_RUNTIME = execution_runtime
        cognitive_loop_module.OPERATION_LEDGER = ledger
        cognitive_loop_module.SNAPSHOT_LINEAGE = snapshot_lineage
        cognitive_loop = CognitiveLoop(runtime=agent_runtime, state_path=temp_paths["cognitive"])

        agents = register_default_agents(agent_runtime)
        for agent in agents.values():
            agent_runtime.heartbeat(str(agent["id"]), "idle")

        branch_id = "branch/playbook-reuse"
        completed_plans: list[dict] = []
        recorded_learning: list[dict] = []

        for index in range(1, 3):
            plan = planner.create_or_refresh_plan(
                title=f"Branch stabilization cycle {index} for {branch_id}",
                source="smoke_branch_playbook",
                plan_kind="branch_stabilization",
                focus_area="branch_pressure_stabilization",
                branch_id=branch_id,
                max_parallel_steps=1,
                task_specs=branch_stabilization_task_specs(branch_id),
            )
            completed = complete_plan_chain(planner, agent_runtime, plan_id=str(plan["id"]))
            completed_plans.append(completed)
            planner_snapshot = planner.status_snapshot(limit=20)
            recorded_learning.append(cognitive_loop._persist_branch_stabilization_learning(planner_snapshot))

        memory_items = MemoryEngine().get_all()
        playbooks = build_stabilization_playbooks(memory_items, limit=10)
        branch_playbook = next(
            (dict(item) for item in playbooks.get("branches", []) if item.get("branch_id") == branch_id),
            {},
        )
        if not branch_playbook:
            raise AssertionError("expected branch playbook for completed stabilization history")
        if branch_playbook.get("support_level") not in {"usable", "strong"}:
            raise AssertionError(f"expected reusable support level, got {branch_playbook.get('support_level')}")
        if not bool(branch_playbook.get("reuse_ready")):
            raise AssertionError("expected playbook reuse_ready after repeated successful stabilization plans")
        if len(branch_playbook.get("recommended_actions", []) or []) < 2:
            raise AssertionError("expected multiple recommended actions in stabilization playbook")

        seed_branch_health_history(planner, branch_id)
        branch_snapshot = planner.branch_health_snapshot(limit=10)
        branch_summary = next(
            (dict(item) for item in branch_snapshot.get("branches", []) if item.get("branch_id") == branch_id),
            {},
        )
        if not branch_summary:
            raise AssertionError("expected branch health summary for playbook branch")
        if str((branch_summary.get("planner_gate") or {}).get("recommended_action", "")).strip() != "apply_stabilization_playbook":
            raise AssertionError("expected planner gate to recommend applying stabilization playbook")
        if not bool((branch_summary.get("stabilization_playbook") or {}).get("reuse_ready")):
            raise AssertionError("expected branch health summary to carry reusable stabilization playbook")

        perception = cognitive_loop.perceive()
        reasoning = cognitive_loop.reason(perception)
        plan = cognitive_loop.plan(perception, reasoning)
        action = cognitive_loop.act(plan)
        learning = cognitive_loop.learn(perception, reasoning, action)

        pressure_branch = next(
            (dict(item) for item in reasoning.get("pressure_branches", []) if item.get("branch_id") == branch_id),
            {},
        )
        if not pressure_branch:
            raise AssertionError("expected pressure-aware reasoning entry for playbook branch")
        if not bool(pressure_branch.get("stabilization_playbook_ready")):
            raise AssertionError("expected reasoning to mark stabilization playbook as ready")

        branch_plan_group = next(
            (
                dict(group)
                for group in plan.get("plan_groups", [])
                if group.get("plan_kind") == "branch_stabilization" and group.get("branch_id") == branch_id
            ),
            {},
        )
        if not branch_plan_group:
            raise AssertionError("expected branch_stabilization plan group from cognitive plan")
        task_keys = [str(task.get("step_key") or "") for task in branch_plan_group.get("tasks", [])]
        if "review_branch_stabilization_playbook" not in task_keys:
            raise AssertionError("expected review_branch_stabilization_playbook in cognitive plan")
        if "apply_branch_stabilization_playbook" not in task_keys:
            raise AssertionError("expected apply_branch_stabilization_playbook in cognitive plan")
        if "review_prior_branch_stabilization_memory" in task_keys:
            raise AssertionError("did not expect fallback memory review when reusable playbook exists")

        acted_plan = next(
            (
                dict(item)
                for item in action.get("planner_plans", [])
                if item.get("plan_kind") == "branch_stabilization" and item.get("branch_id") == branch_id
            ),
            {},
        )
        if not acted_plan:
            raise AssertionError("expected planner action to create branch_stabilization plan")
        acted_step_keys = [str(step.get("key") or "") for step in acted_plan.get("steps", [])]
        if "review_branch_stabilization_playbook" not in acted_step_keys or "apply_branch_stabilization_playbook" not in acted_step_keys:
            raise AssertionError("expected acted plan to preserve playbook review/apply steps")
        if int(learning.get("stabilization_feedback", {}).get("playbook_counts", {}).get("reuse_ready", 0) or 0) < 1:
            raise AssertionError("expected learning feedback to report at least one reusable playbook")

        result = {
            "status": "ok",
            "service": "AI OS Branch Stabilization Playbook Smoke Test",
            "branch_id": branch_id,
            "completed_plan_ids": [item.get("plan", {}).get("id") for item in completed_plans],
            "completed_plan_statuses": [item.get("plan", {}).get("status") for item in completed_plans],
            "recorded_learning": recorded_learning,
            "playbook_counts": playbooks.get("playbook_counts", {}),
            "branch_playbook": branch_playbook,
            "branch_summary": branch_summary,
            "pressure_branch": pressure_branch,
            "planned_task_keys": task_keys,
            "acted_plan_id": acted_plan.get("id"),
            "acted_step_keys": acted_step_keys,
            "planner_execution": action.get("planner_execution", {}),
            "learning_feedback": learning.get("stabilization_feedback", {}),
            "temp_files": {key: str(path) for key, path in temp_paths.items()},
        }
    except Exception as exc:
        result = {
            **result,
            "status": "error",
            "error": str(exc),
        }
    finally:
        runtime_store_module.RUNTIME_FILE = previous_runtime_file
        agent_runtime_module.EXECUTION_RUNTIME = previous_agent_execution_runtime
        execution_runtime_module.EXECUTION_RUNTIME = previous_execution_runtime
        planning_runtime_module.SNAPSHOT_LINEAGE = previous_snapshot_lineage
        cognitive_loop_module.PLANNER_RUNTIME = previous_cognitive_planner
        cognitive_loop_module.EXECUTION_RUNTIME = previous_cognitive_execution
        cognitive_loop_module.OPERATION_LEDGER = previous_cognitive_ledger
        cognitive_loop_module.SNAPSHOT_LINEAGE = previous_cognitive_snapshots

    if args.cleanup:
        result["cleanup"] = {"remaining_files": cleanup_paths(temp_paths)}

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{result['service']}: {result['status']}")
        if result["status"] == "ok":
            print(f"branch_id={result['branch_id']}")
            print(f"playbook_support={result['branch_playbook'].get('support_level')}")
            print(f"planned_task_keys={', '.join(result['planned_task_keys'])}")
        cleanup_info = result.get("cleanup") or {}
        remaining = cleanup_info.get("remaining_files") or []
        if remaining:
            print("cleanup_remaining=" + ", ".join(remaining))

    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
