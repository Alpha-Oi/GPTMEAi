"""Isolated smoke test for remediation-aware recovery workflow execution."""

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
        metadata=metadata or {"source": "smoke_recovery_remediation"},
        branch_id=branch_id,
    )
    runtime.claim_task(agent_id, int(task["id"]))
    return runtime.complete_task(agent_id, int(task["id"]), result=result, success=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run isolated remediation-aware recovery workflow smoke test.")
    parser.add_argument("--tag", default="recovery_remediation", help="Temp-file prefix tag.")
    parser.add_argument("--cleanup", action="store_true", help="Attempt to delete temp state files after the run.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON summary.")
    args = parser.parse_args()

    temp_paths = make_temp_paths(args.tag)
    previous_execution_runtime = agent_runtime_module.EXECUTION_RUNTIME
    previous_planning_execution_runtime = execution_runtime_module.EXECUTION_RUNTIME
    previous_snapshot_lineage = planning_runtime_module.SNAPSHOT_LINEAGE

    result: dict[str, object] = {
        "status": "error",
        "service": "AI OS Recovery Remediation Smoke Test",
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

        branch_id = "recovery/remediation-branch"

        anchor_task = queue_and_complete_task(
            agent_runtime,
            title="Anchor remediation baseline for recovery branch",
            branch_id=branch_id,
            agent_id=agents["memory_agent"]["id"],
            result="anchor baseline committed",
        )
        temp_paths["anchor_snapshot"].write_text(
            json.dumps(
                {
                    "branch_id": branch_id,
                    "memory_count": 144,
                    "graph_nodes": 48,
                    "graph_relations_total": 72,
                    "label": "Recovery remediation smoke anchor",
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
                "memory_count": 144,
                "graph_nodes": 48,
                "graph_relations_total": 72,
                "label": "Recovery remediation smoke anchor",
            },
            branch_id=branch_id,
            source_operation_id=anchor_task.get("operation_id"),
            label="Recovery remediation smoke anchor",
        )

        queue_and_complete_task(
            agent_runtime,
            title="Update memory graph for remediation recovery branch",
            branch_id=branch_id,
            agent_id=agents["memory_agent"]["id"],
            result="memory graph replay candidate",
        )
        queue_and_complete_task(
            agent_runtime,
            title="Inspect remediation lineage drift for recovery branch",
            branch_id=branch_id,
            agent_id=agents["research_agent"]["id"],
            result="lineage review replay candidate",
        )
        queue_and_complete_task(
            agent_runtime,
            title="Patch remediation runtime handoff for recovery branch",
            branch_id=branch_id,
            agent_id=agents["coding_agent"]["id"],
            result="runtime recovery replay candidate",
        )

        preview = planner.preview_recovery_plan_from_replay(
            snapshot_id=str(anchor_snapshot["snapshot_id"]),
            branch_id=branch_id,
            max_parallel_steps=1,
            max_replay_steps=3,
        )
        if int(preview.get("planned_replay_step_count", 0) or 0) != 3:
            raise AssertionError("expected exactly three planned replay steps in preview")

        plan = planner.create_recovery_plan_from_replay(
            snapshot_id=str(anchor_snapshot["snapshot_id"]),
            branch_id=branch_id,
            max_parallel_steps=1,
            max_replay_steps=3,
        )
        if plan.get("plan_kind") != "recovery":
            raise AssertionError("expected recovery plan")

        advance_one = planner.advance_recovery_workflow(plan_id=str(plan["id"]), auto_dispatch=True, dispatch_limit=3)
        assignment_one = ((advance_one.get("dispatch") or {}).get("assignments") or [None])[0]
        if not assignment_one or assignment_one.get("agent_name") != "Development Manager":
            raise AssertionError("expected Development Manager for recovery coordination")
        completed_one = agent_runtime.complete_task(
            agents["development_manager"]["id"],
            int(assignment_one["task_id"]),
            result="recovery coordinated",
            success=True,
        )
        if completed_one.get("status") != "done":
            raise AssertionError("expected completed coordination task")

        advance_two = planner.advance_recovery_workflow(plan_id=str(plan["id"]), auto_dispatch=True, dispatch_limit=3)
        assignment_two = ((advance_two.get("dispatch") or {}).get("assignments") or [None])[0]
        if not assignment_two or assignment_two.get("agent_name") != "Research Agent":
            raise AssertionError("expected Research Agent for anchor review")
        agent_runtime.complete_task(
            agents["research_agent"]["id"],
            int(assignment_two["task_id"]),
            result="anchor reviewed",
            success=True,
        )

        advance_three = planner.advance_recovery_workflow(plan_id=str(plan["id"]), auto_dispatch=True, dispatch_limit=3)
        assignment_three = ((advance_three.get("dispatch") or {}).get("assignments") or [None])[0]
        if not assignment_three:
            raise AssertionError("expected first replay assignment")
        failed_replay_one = agent_runtime.complete_task(
            str(assignment_three.get("agent_id") or agents["memory_agent"]["id"]),
            int(assignment_three["task_id"]),
            result="forced replay failure one",
            success=False,
        )
        if failed_replay_one.get("compensation_status") != "pending":
            raise AssertionError("expected pending compensation after first replay failure")

        advance_four = planner.advance_recovery_workflow(
            plan_id=str(plan["id"]),
            auto_dispatch=True,
            auto_compensate=True,
            compensation_reason="smoke remediation compensation one",
            dispatch_limit=3,
        )
        assignment_four = ((advance_four.get("dispatch") or {}).get("assignments") or [None])[0]
        if not assignment_four:
            raise AssertionError("expected second replay assignment after first compensation")
        failed_replay_two = agent_runtime.complete_task(
            str(assignment_four.get("agent_id") or agents["memory_agent"]["id"]),
            int(assignment_four["task_id"]),
            result="forced replay failure two",
            success=False,
        )
        if failed_replay_two.get("compensation_status") != "pending":
            raise AssertionError("expected pending compensation after second replay failure")

        remediation_start = planner.advance_recovery_workflow(
            plan_id=str(plan["id"]),
            auto_dispatch=True,
            auto_compensate=True,
            compensation_reason="smoke remediation compensation two",
            dispatch_limit=3,
        )
        if remediation_start.get("advance_target") != "remediation":
            raise AssertionError("expected remediation advance target after repeated failures")
        remediation_plan = dict((remediation_start.get("remediation") or {}).get("plan") or {})
        if remediation_plan.get("plan_kind") != "remediation":
            raise AssertionError("expected remediation child plan")
        remediation_summary = dict((remediation_start.get("remediation") or {}).get("summary") or {})
        if remediation_summary.get("status") not in {"queued", "in_progress", "planned"}:
            raise AssertionError("expected active remediation summary")
        remediation_assignment_one = ((remediation_start.get("dispatch") or {}).get("assignments") or [None])[0]
        if not remediation_assignment_one or remediation_assignment_one.get("agent_name") != "Development Manager":
            raise AssertionError("expected Development Manager for remediation coordination")

        remediation_two = planner.advance_from_task(
            agent_runtime.complete_task(
                agents["development_manager"]["id"],
                int(remediation_assignment_one["task_id"]),
                result="remediation coordinated",
                success=True,
            ),
            auto_dispatch=True,
            auto_compensate=True,
            dispatch_limit=3,
        )
        if remediation_two.get("service") != "AI OS Remediation Workflow Advance":
            raise AssertionError("expected remediation workflow advance after remediation step completion")
        remediation_assignment_two = ((remediation_two.get("dispatch") or {}).get("assignments") or [None])[0]
        if not remediation_assignment_two or remediation_assignment_two.get("agent_name") != "Research Agent":
            raise AssertionError("expected Research Agent for remediation analysis")

        remediation_three = planner.advance_from_task(
            agent_runtime.complete_task(
                agents["research_agent"]["id"],
                int(remediation_assignment_two["task_id"]),
                result="remediation analysis completed",
                success=True,
            ),
            auto_dispatch=True,
            auto_compensate=True,
            dispatch_limit=3,
        )
        remediation_assignment_three = ((remediation_three.get("dispatch") or {}).get("assignments") or [None])[0]
        if not remediation_assignment_three or remediation_assignment_three.get("agent_name") != "Coding Agent":
            raise AssertionError("expected Coding Agent for remediation stabilization")

        remediation_four = planner.advance_from_task(
            agent_runtime.complete_task(
                agents["coding_agent"]["id"],
                int(remediation_assignment_three["task_id"]),
                result="branch stabilization completed",
                success=True,
            ),
            auto_dispatch=True,
            auto_compensate=True,
            dispatch_limit=3,
        )
        remediation_assignment_four = ((remediation_four.get("dispatch") or {}).get("assignments") or [None])[0]
        if not remediation_assignment_four or remediation_assignment_four.get("agent_name") != "Development Manager":
            raise AssertionError("expected Development Manager for remediation resume decision")

        recovery_resume = planner.advance_from_task(
            agent_runtime.complete_task(
                agents["development_manager"]["id"],
                int(remediation_assignment_four["task_id"]),
                result="recovery resume approved",
                success=True,
            ),
            auto_dispatch=True,
            auto_compensate=True,
            dispatch_limit=3,
        )
        if recovery_resume.get("service") != "AI OS Recovery Workflow Advance":
            raise AssertionError("expected recovery workflow advance after remediation completion")
        if recovery_resume.get("advance_target") != "recovery":
            raise AssertionError("expected recovery to resume after remediation completion")
        replay_three_assignment = ((recovery_resume.get("dispatch") or {}).get("assignments") or [None])[0]
        if not replay_three_assignment:
            raise AssertionError("expected replay_step_03 assignment after remediation completion")

        validation_advance = planner.advance_from_task(
            agent_runtime.complete_task(
                str(replay_three_assignment.get("agent_id") or agents["memory_agent"]["id"]),
                int(replay_three_assignment["task_id"]),
                result="third replay step completed",
                success=True,
            ),
            auto_dispatch=True,
            auto_compensate=True,
            dispatch_limit=3,
        )
        validation_assignment = ((validation_advance.get("dispatch") or {}).get("assignments") or [None])[0]
        if not validation_assignment or validation_assignment.get("agent_name") != "Memory Agent":
            raise AssertionError("expected Memory Agent for validation after remediation")

        final_advance = planner.advance_from_task(
            agent_runtime.complete_task(
                agents["memory_agent"]["id"],
                int(validation_assignment["task_id"]),
                result="validation completed",
                success=True,
            ),
            auto_dispatch=True,
            auto_compensate=True,
            dispatch_limit=3,
        )
        if final_advance.get("service") != "AI OS Recovery Workflow Advance":
            raise AssertionError("expected recovery workflow advance after validation")
        if int((final_advance.get("dispatch") or {}).get("dispatch_count", 0) or 0) != 0:
            raise AssertionError("expected no further dispatch after final validation")

        planner_snapshot = planner.status_snapshot(plan_id=str(plan["id"]))
        plan_snapshot = planner_snapshot["plans"][0]
        workflow = dict(plan_snapshot.get("recovery_workflow") or {})
        remediation = dict(workflow.get("remediation") or {})
        branch_health = dict(workflow.get("branch_health") or {})
        if workflow.get("status") != "completed":
            raise AssertionError("expected completed recovery workflow")
        if workflow.get("current_phase") != "completed":
            raise AssertionError("expected completed recovery phase")
        if remediation.get("status") != "completed":
            raise AssertionError("expected completed remediation summary")
        if int(remediation.get("resolved_disruption_count", 0) or 0) < 2:
            raise AssertionError("expected remediation to resolve two disruptions")
        if int(workflow.get("compensated_replay_steps", 0) or 0) < 2:
            raise AssertionError("expected two compensated replay steps")
        if branch_health.get("status") != "observe":
            raise AssertionError("expected observe branch health after remediated recovery")
        if not bool(branch_health.get("validation_passed")):
            raise AssertionError("expected validation_passed after remediated recovery")
        if int(branch_health.get("quality_score", 0) or 0) < 70:
            raise AssertionError("expected observe-grade quality score after remediated recovery")
        if int(branch_health.get("confidence_score", 0) or 0) < 65:
            raise AssertionError("expected medium confidence after remediated recovery")
        if str((branch_health.get("planner_gate") or {}).get("mode", "")).strip() != "guarded":
            raise AssertionError("expected guarded planner gate after remediated recovery")

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
            raise AssertionError("expected branch health summary after remediated recovery")

        execution_snapshot = execution_runtime.snapshot()
        if int(execution_snapshot.get("recovery_compensation_counts", {}).get("completed", 0) or 0) < 2:
            raise AssertionError("expected two completed recovery compensations")

        result = {
            "status": "ok",
            "service": "AI OS Recovery Remediation Smoke Test",
            "branch_id": branch_id,
            "anchor_snapshot_id": anchor_snapshot["snapshot_id"],
            "plan_id": plan["id"],
            "recovery_workflow": workflow,
            "remediation": remediation,
            "branch_health": branch_health,
            "branch_summary": branch_summary,
            "branch_health_counts": branch_snapshot.get("branch_counts", {}),
            "remediation_plan_id": remediation_plan.get("id"),
            "advance_targets": [
                advance_one.get("advance_target", "recovery"),
                advance_two.get("advance_target", "recovery"),
                advance_three.get("advance_target", "recovery"),
                advance_four.get("advance_target", "recovery"),
                remediation_start.get("advance_target", "recovery"),
                recovery_resume.get("advance_target", "recovery"),
            ],
            "recovery_sequence": [
                (advance_one.get("queue") or {}).get("queued_steps", [{}])[0].get("step_key"),
                (advance_two.get("queue") or {}).get("queued_steps", [{}])[0].get("step_key"),
                (advance_three.get("queue") or {}).get("queued_steps", [{}])[0].get("step_key"),
                (advance_four.get("queue") or {}).get("queued_steps", [{}])[0].get("step_key"),
                (remediation_start.get("queue") or {}).get("queued_steps", [{}])[0].get("step_key"),
                (recovery_resume.get("queue") or {}).get("queued_steps", [{}])[0].get("step_key"),
                (validation_advance.get("queue") or {}).get("queued_steps", [{}])[0].get("step_key"),
            ],
            "remediation_sequence": [
                (remediation_start.get("queue") or {}).get("queued_steps", [{}])[0].get("step_key"),
                (remediation_two.get("queue") or {}).get("queued_steps", [{}])[0].get("step_key"),
                (remediation_three.get("queue") or {}).get("queued_steps", [{}])[0].get("step_key"),
                (remediation_four.get("queue") or {}).get("queued_steps", [{}])[0].get("step_key"),
            ],
            "assignments": {
                "recovery": [
                    assignment_one.get("agent_name"),
                    assignment_two.get("agent_name"),
                    assignment_three.get("agent_name"),
                    assignment_four.get("agent_name"),
                    replay_three_assignment.get("agent_name"),
                    validation_assignment.get("agent_name"),
                ],
                "remediation": [
                    remediation_assignment_one.get("agent_name"),
                    remediation_assignment_two.get("agent_name"),
                    remediation_assignment_three.get("agent_name"),
                    remediation_assignment_four.get("agent_name"),
                ],
            },
            "execution_recovery_counts": execution_snapshot.get("recovery_operation_counts", {}),
            "recovery_compensation_counts": execution_snapshot.get("recovery_compensation_counts", {}),
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
            print(f"remediation_plan_id={result['remediation_plan_id']}")
            print(f"workflow_phase={result['recovery_workflow'].get('current_phase')}")
        cleanup_info = result.get("cleanup") or {}
        remaining = cleanup_info.get("remaining_files") or []
        if remaining:
            print("cleanup_remaining=" + ", ".join(remaining))

    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
