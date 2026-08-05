"""Isolated smoke test for replay-aware recovery workflow execution."""

from __future__ import annotations

import argparse
import gc
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TMP_DIR = ROOT / "development" / "tmp"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import ai_os.agent_runtime as agent_runtime_module
import execution.runtime as execution_runtime_module
import planning.runtime as planning_runtime_module
from ai_os.agent_runtime import AgentRuntime
from execution.ledger import OperationLedger
from execution.runtime import ExecutionRuntime
from execution.snapshots import SnapshotLineageRegistry
from planning.runtime import PlannerRuntime


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")


def make_temp_paths(tag: str) -> dict[str, Path]:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    suffix = utc_stamp()
    return {
        "agent": TMP_DIR / f"agent_runtime_{tag}_{suffix}.json",
        "execution": TMP_DIR / f"execution_runtime_{tag}_{suffix}.json",
        "ledger": TMP_DIR / f"operation_ledger_{tag}_{suffix}.json",
        "planner": TMP_DIR / f"planner_runtime_{tag}_{suffix}.json",
        "snapshots": TMP_DIR / f"snapshot_lineage_{tag}_{suffix}.json",
        "anchor_snapshot": TMP_DIR / f"snapshot_anchor_{tag}_{suffix}.json",
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
    registered = {
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
    return registered


def queue_and_complete_task(
    runtime: AgentRuntime,
    *,
    title: str,
    branch_id: str,
    agent_id: str,
    metadata: dict | None = None,
    result: str = "completed",
) -> dict:
    task = runtime.queue_task(
        title=title,
        preferred_role="worker",
        metadata=metadata or {"source": "smoke_recovery_workflow"},
        branch_id=branch_id,
    )
    runtime.claim_task(agent_id, int(task["id"]))
    return runtime.complete_task(agent_id, int(task["id"]), result=result, success=True)


def find_task_id_by_step_key(plan_payload: dict, step_key: str) -> int:
    for step in plan_payload.get("steps", []):
        if step.get("key") == step_key and step.get("task_id") is not None:
            return int(step["task_id"])
    raise AssertionError(f"task_id not found for step key: {step_key}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run isolated recovery workflow smoke test.")
    parser.add_argument("--tag", default="recovery_workflow", help="Temp-file prefix tag.")
    parser.add_argument("--cleanup", action="store_true", help="Attempt to delete temp state files after the run.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON summary.")
    args = parser.parse_args()

    temp_paths = make_temp_paths(args.tag)
    previous_execution_runtime = agent_runtime_module.EXECUTION_RUNTIME
    previous_planning_execution_runtime = execution_runtime_module.EXECUTION_RUNTIME
    previous_snapshot_lineage = planning_runtime_module.SNAPSHOT_LINEAGE

    result: dict[str, object] = {
        "status": "error",
        "service": "AI OS Recovery Workflow Smoke Test",
        "temp_files": {key: str(path) for key, path in temp_paths.items()},
    }

    try:
        ledger = OperationLedger(temp_paths["ledger"])
        snapshot_lineage = SnapshotLineageRegistry(temp_paths["snapshots"], ledger=ledger)
        execution_runtime = ExecutionRuntime(temp_paths["execution"], ledger=ledger)

        agent_runtime_module.EXECUTION_RUNTIME = execution_runtime
        execution_runtime_module.EXECUTION_RUNTIME = execution_runtime
        planning_runtime_module.SNAPSHOT_LINEAGE = snapshot_lineage

        agent_runtime = AgentRuntime(temp_paths["agent"])
        planner = PlannerRuntime(temp_paths["planner"], runtime=agent_runtime)
        agents = register_default_agents(agent_runtime)

        branch_id = "recovery/test-branch"

        anchor_task = queue_and_complete_task(
            agent_runtime,
            title="Anchor memory baseline for recovery branch",
            branch_id=branch_id,
            agent_id=agents["memory_agent"]["id"],
            result="anchor baseline committed",
        )
        temp_paths["anchor_snapshot"].write_text(
            json.dumps(
                {
                    "branch_id": branch_id,
                    "memory_count": 128,
                    "graph_nodes": 32,
                    "graph_relations_total": 64,
                    "label": "Recovery smoke anchor",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        anchor_snapshot = snapshot_lineage.register_snapshot(
            temp_paths["anchor_snapshot"],
            {
                "branch_id": branch_id,
                "memory_count": 128,
                "graph_nodes": 32,
                "graph_relations_total": 64,
                "label": "Recovery smoke anchor",
            },
            branch_id=branch_id,
            source_operation_id=anchor_task.get("operation_id"),
            label="Recovery smoke anchor",
        )

        queue_and_complete_task(
            agent_runtime,
            title="Update memory graph for recovery branch",
            branch_id=branch_id,
            agent_id=agents["memory_agent"]["id"],
            result="memory graph replay candidate",
        )
        queue_and_complete_task(
            agent_runtime,
            title="Inspect lineage drift for recovery branch",
            branch_id=branch_id,
            agent_id=agents["research_agent"]["id"],
            result="lineage review replay candidate",
        )
        queue_and_complete_task(
            agent_runtime,
            title="Patch runtime handoff for recovery branch",
            branch_id=branch_id,
            agent_id=agents["coding_agent"]["id"],
            result="runtime recovery replay candidate",
        )

        preview = planner.preview_recovery_plan_from_replay(
            snapshot_id=str(anchor_snapshot["snapshot_id"]),
            branch_id=branch_id,
            max_parallel_steps=1,
            max_replay_steps=2,
        )
        if preview.get("service") != "AI OS Recovery Plan Preview":
            raise AssertionError("unexpected recovery preview service name")
        if int(preview.get("planned_replay_step_count", 0) or 0) != 2:
            raise AssertionError("preview did not limit replay steps to 2")

        plan = planner.create_recovery_plan_from_replay(
            snapshot_id=str(anchor_snapshot["snapshot_id"]),
            branch_id=branch_id,
            max_parallel_steps=1,
            max_replay_steps=2,
        )
        if plan.get("plan_kind") != "recovery":
            raise AssertionError("expected recovery plan kind")

        workflow = dict(plan.get("recovery_workflow") or {})
        if workflow.get("workflow_key") != f"recovery:{branch_id}:{anchor_snapshot['snapshot_id']}":
            raise AssertionError("unexpected recovery workflow key")

        step_meta = {
            step.get("key"): dict(step.get("metadata") or {})
            for step in plan.get("steps", [])
        }
        if step_meta["coordinate_snapshot_recovery"].get("execution_mode") != "simulate":
            raise AssertionError("coordination step must use simulate mode")
        if step_meta["review_recovery_anchor"].get("recovery_phase") != "anchor_review":
            raise AssertionError("anchor review phase metadata missing")
        if step_meta["replay_step_01"].get("recovery_phase") != "replay_execution":
            raise AssertionError("replay step phase metadata missing")
        if step_meta["validate_recovered_branch"].get("execution_mode") != "commit":
            raise AssertionError("validation step must use commit mode")

        workflows_before_dispatch = planner.recovery_workflows_snapshot(limit=10, active_only=True)
        if not workflows_before_dispatch.get("workflows"):
            raise AssertionError("expected active recovery workflow snapshot")

        advance_one = planner.advance_recovery_workflow(plan_id=str(plan["id"]), auto_dispatch=True, dispatch_limit=3)
        if int((advance_one.get("queue") or {}).get("queued_count", 0) or 0) != 1:
            raise AssertionError("expected exactly one queued coordination step")
        first_step_key = (advance_one.get("queue") or {}).get("queued_steps", [{}])[0].get("step_key")
        if first_step_key != "coordinate_snapshot_recovery":
            raise AssertionError("expected coordination step to queue first")

        assignment_one = ((advance_one.get("dispatch") or {}).get("assignments") or [None])[0]
        if not assignment_one:
            raise AssertionError("expected manager assignment for coordination step")
        if assignment_one.get("agent_name") != "Development Manager":
            raise AssertionError("coordination step was not assigned to Development Manager")
        task_id_one = int(assignment_one["task_id"])
        agent_runtime.complete_task(agents["development_manager"]["id"], task_id_one, result="recovery coordinated", success=True)

        advance_two = planner.advance_recovery_workflow(plan_id=str(plan["id"]), auto_dispatch=True, dispatch_limit=3)
        if int((advance_two.get("queue") or {}).get("queued_count", 0) or 0) != 1:
            raise AssertionError("expected exactly one queued anchor review step")
        if (advance_two.get("queue") or {}).get("queued_steps", [{}])[0].get("step_key") != "review_recovery_anchor":
            raise AssertionError("expected anchor review to queue second")

        assignment_two = ((advance_two.get("dispatch") or {}).get("assignments") or [None])[0]
        if not assignment_two:
            raise AssertionError("expected worker assignment for anchor review step")
        task_id_two = int(assignment_two["task_id"])
        agent_runtime.complete_task(agents["research_agent"]["id"], task_id_two, result="anchor reviewed", success=True)

        advance_three = planner.advance_recovery_workflow(plan_id=str(plan["id"]), auto_dispatch=True, dispatch_limit=3)
        if int((advance_three.get("queue") or {}).get("queued_count", 0) or 0) != 1:
            raise AssertionError("expected exactly one queued replay step")
        if (advance_three.get("queue") or {}).get("queued_steps", [{}])[0].get("step_key") != "replay_step_01":
            raise AssertionError("expected first replay step to queue third")

        assignment_three = ((advance_three.get("dispatch") or {}).get("assignments") or [None])[0]
        if not assignment_three:
            raise AssertionError("expected worker assignment for first replay step")
        task_id_three = int(assignment_three["task_id"])
        if task_id_three != find_task_id_by_step_key(planner.status_snapshot(plan_id=str(plan["id"]))["plans"][0], "replay_step_01"):
            raise AssertionError("planner task mapping drifted for replay_step_01")

        failed_replay = agent_runtime.complete_task(
            agents["memory_agent"]["id"],
            task_id_three,
            result="forced replay failure for compensation smoke",
            success=False,
        )
        if failed_replay.get("compensation_status") != "pending":
            raise AssertionError("expected pending compensation after forced replay failure")

        advance_four = planner.advance_recovery_workflow(
            plan_id=str(plan["id"]),
            auto_dispatch=True,
            auto_compensate=True,
            compensation_reason="smoke recovery compensation",
            dispatch_limit=3,
        )
        if int((advance_four.get("compensation") or {}).get("compensated_count", 0) or 0) != 1:
            raise AssertionError("expected exactly one compensated recovery step")
        if int((advance_four.get("queue") or {}).get("queued_count", 0) or 0) != 1:
            raise AssertionError("expected exactly one queued recovery step after compensation")
        if (advance_four.get("queue") or {}).get("queued_steps", [{}])[0].get("step_key") != "replay_step_02":
            raise AssertionError("expected second replay step after compensation")

        assignment_four = ((advance_four.get("dispatch") or {}).get("assignments") or [None])[0]
        if not assignment_four:
            raise AssertionError("expected assignment for second replay step after compensation")
        if assignment_four.get("agent_name") == "Development Manager":
            raise AssertionError("expected worker assignment for second replay step after compensation")
        task_id_four = int(assignment_four["task_id"])
        completed_replay_two = agent_runtime.complete_task(
            str(assignment_four.get("agent_id") or agents["memory_agent"]["id"]),
            task_id_four,
            result="second replay step completed",
            success=True,
        )

        validation_advance = planner.advance_from_task(
            completed_replay_two,
            auto_dispatch=True,
            auto_compensate=True,
            dispatch_limit=3,
        )
        if validation_advance.get("service") != "AI OS Recovery Workflow Advance":
            raise AssertionError("expected recovery advance after replay completion")
        if int((validation_advance.get("queue") or {}).get("queued_count", 0) or 0) != 1:
            raise AssertionError("expected validation step to be queued after replay completion")
        if (validation_advance.get("queue") or {}).get("queued_steps", [{}])[0].get("step_key") != "validate_recovered_branch":
            raise AssertionError("expected validation step after replay completion")

        validation_assignment = ((validation_advance.get("dispatch") or {}).get("assignments") or [None])[0]
        if not validation_assignment:
            raise AssertionError("expected validation assignment after replay completion")
        if validation_assignment.get("agent_name") != "Memory Agent":
            raise AssertionError("expected Memory Agent for validation step")
        validation_task_id = int(validation_assignment["task_id"])
        completed_validation = agent_runtime.complete_task(
            str(validation_assignment.get("agent_id") or agents["memory_agent"]["id"]),
            validation_task_id,
            result="validation completed",
            success=True,
        )

        final_advance = planner.advance_from_task(
            completed_validation,
            auto_dispatch=True,
            auto_compensate=True,
            dispatch_limit=3,
        )
        if final_advance.get("service") != "AI OS Recovery Workflow Advance":
            raise AssertionError("expected recovery advance after validation completion")
        if int((final_advance.get("dispatch") or {}).get("dispatch_count", 0) or 0) != 0:
            raise AssertionError("expected no further dispatch after validation completion")

        planner_snapshot = planner.status_snapshot(plan_id=str(plan["id"]))
        plan_snapshot = planner_snapshot["plans"][0]
        workflow_after_dispatch = dict(plan_snapshot.get("recovery_workflow") or {})
        if workflow_after_dispatch.get("status") != "completed":
            raise AssertionError("expected completed recovery workflow after validation")
        if workflow_after_dispatch.get("current_phase") != "completed":
            raise AssertionError("expected completed recovery phase after validation")
        if int(workflow_after_dispatch.get("compensated_replay_steps", 0) or 0) < 1:
            raise AssertionError("expected compensated replay steps after automated compensation")
        next_actions = workflow_after_dispatch.get("next_actions") or []
        if not next_actions or next_actions[0].get("type") != "workflow_complete":
            raise AssertionError("expected workflow_complete after validation")
        branch_health = dict(workflow_after_dispatch.get("branch_health") or {})
        if branch_health.get("status") != "observe":
            raise AssertionError("expected observe branch health after compensated recovery")
        if not bool(branch_health.get("validation_passed")):
            raise AssertionError("expected validation_passed after completed recovery workflow")
        if int(branch_health.get("quality_score", 0) or 0) < 70:
            raise AssertionError("expected usable recovery quality score after compensated recovery")
        if int(branch_health.get("confidence_score", 0) or 0) < 70:
            raise AssertionError("expected usable recovery confidence score after compensated recovery")
        if str((branch_health.get("planner_gate") or {}).get("mode", "")).strip() != "guarded":
            raise AssertionError("expected guarded planner gate after compensated recovery")

        branch_snapshot = planner.branch_health_snapshot(limit=10)
        branch_summary = next(
            (
                dict(item)
                for item in branch_snapshot.get("branches", [])
                if item.get("branch_id") == branch_id
            ),
            {},
        )
        if not branch_summary:
            raise AssertionError("expected branch health summary for guarded branch")
        if int(branch_summary.get("observation_count", 0) or 0) < 2:
            raise AssertionError("expected multiple branch health observations for trend analysis")
        if str((branch_summary.get("planner_gate") or {}).get("mode", "")).strip() != "guarded":
            raise AssertionError("expected guarded branch summary gate after compensated recovery")

        operational_plan = planner.create_or_refresh_plan(
            title="Guarded operational follow-up on recovered branch",
            source="smoke_branch_health_gate",
            plan_kind="operational",
            focus_area="guarded_branch_follow_up",
            branch_id=branch_id,
            max_parallel_steps=3,
            task_specs=[
                {
                    "step_key": "guarded_followup_analysis",
                    "title": f"Analyze guarded branch follow-up for {branch_id}",
                    "preferred_role": "worker",
                    "metadata": {"owner_hint": "Research Agent"},
                },
                {
                    "step_key": "guarded_followup_patch",
                    "title": f"Patch guarded branch follow-up for {branch_id}",
                    "preferred_role": "worker",
                    "metadata": {"owner_hint": "Coding Agent"},
                },
            ],
        )
        operational_execution = planner.execute_ready_steps(plan_id=str(operational_plan["id"]))
        if int(operational_execution.get("queued_count", 0) or 0) != 1:
            raise AssertionError("expected guarded branch gate to limit operational queueing to one step")
        if int((operational_execution.get("gating") or {}).get("count", 0) or 0) < 1:
            raise AssertionError("expected operational execution to report branch gating activity")
        operational_snapshot = planner.status_snapshot(plan_id=str(operational_plan["id"]))
        operational_plan_payload = operational_snapshot["plans"][0]
        if str((operational_plan_payload.get("branch_planner_gate") or {}).get("mode", "")).strip() != "guarded":
            raise AssertionError("expected operational plan payload to expose guarded branch planner gate")

        execution_snapshot = execution_runtime.snapshot()
        if int(execution_snapshot.get("recovery_operation_counts", {}).get("total", 0) or 0) < 5:
            raise AssertionError("expected recovery operations to be visible in execution snapshot")
        if int(execution_snapshot.get("recovery_operation_counts", {}).get("committed", 0) or 0) < 3:
            raise AssertionError("expected committed recovery operations after validation")
        if int(execution_snapshot.get("recovery_compensation_counts", {}).get("completed", 0) or 0) < 1:
            raise AssertionError("expected completed recovery compensation count after auto compensation")

        result = {
            "status": "ok",
            "service": "AI OS Recovery Workflow Smoke Test",
            "branch_id": branch_id,
            "anchor_snapshot_id": anchor_snapshot["snapshot_id"],
            "plan_id": plan["id"],
            "preview": {
                "service": preview["service"],
                "replay_step_count": preview["replay_step_count"],
                "planned_replay_step_count": preview["planned_replay_step_count"],
            },
            "workflow": workflow_after_dispatch,
            "branch_health": branch_health,
            "branch_summary": branch_summary,
            "queued_sequence": [
                (advance_one.get("queue") or {}).get("queued_steps", [{}])[0].get("step_key"),
                (advance_two.get("queue") or {}).get("queued_steps", [{}])[0].get("step_key"),
                (advance_three.get("queue") or {}).get("queued_steps", [{}])[0].get("step_key"),
                (advance_four.get("queue") or {}).get("queued_steps", [{}])[0].get("step_key"),
                (validation_advance.get("queue") or {}).get("queued_steps", [{}])[0].get("step_key"),
            ],
            "assignments": [
                assignment_one.get("agent_name"),
                assignment_two.get("agent_name"),
                assignment_three.get("agent_name"),
                assignment_four.get("agent_name"),
                validation_assignment.get("agent_name"),
            ],
            "advance_dispatch_counts": [
                int((advance_one.get("dispatch") or {}).get("dispatch_count", 0) or 0),
                int((advance_two.get("dispatch") or {}).get("dispatch_count", 0) or 0),
                int((advance_three.get("dispatch") or {}).get("dispatch_count", 0) or 0),
                int((advance_four.get("dispatch") or {}).get("dispatch_count", 0) or 0),
                int((validation_advance.get("dispatch") or {}).get("dispatch_count", 0) or 0),
                int((final_advance.get("dispatch") or {}).get("dispatch_count", 0) or 0),
            ],
            "execution_recovery_counts": execution_snapshot.get("recovery_operation_counts", {}),
            "recovery_compensation_counts": execution_snapshot.get("recovery_compensation_counts", {}),
            "compensation": advance_four.get("compensation", {}),
            "branch_health_counts": branch_snapshot.get("branch_counts", {}),
            "guarded_operational_execution": {
                "plan_id": operational_plan["id"],
                "queued_count": operational_execution.get("queued_count", 0),
                "gating": operational_execution.get("gating", {}),
                "plan_gate": operational_plan_payload.get("branch_planner_gate", {}),
            },
            "validation": {
                "task_id": validation_task_id,
                "assignment": validation_assignment.get("agent_name"),
            },
            "active_recovery_workflows": len(workflows_before_dispatch.get("workflows", [])),
            "temp_files": {key: str(path) for key, path in temp_paths.items()},
        }
    except Exception as exc:
        result = {
            **result,
            "status": "error",
            "error": str(exc),
        }
    finally:
        agent_runtime_module.EXECUTION_RUNTIME = previous_execution_runtime
        execution_runtime_module.EXECUTION_RUNTIME = previous_planning_execution_runtime
        planning_runtime_module.SNAPSHOT_LINEAGE = previous_snapshot_lineage

    if args.cleanup:
        result["cleanup"] = {"remaining_files": cleanup_paths(temp_paths)}

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{result['service']}: {result['status']}")
        if result["status"] == "ok":
            print(f"plan_id={result['plan_id']}")
            print(f"workflow_phase={result['workflow'].get('current_phase')}")
            print(f"queued_sequence={', '.join(result['queued_sequence'])}")
        cleanup_info = result.get("cleanup") or {}
        remaining = cleanup_info.get("remaining_files") or []
        if remaining:
            print("cleanup_remaining=" + ", ".join(remaining))

    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
