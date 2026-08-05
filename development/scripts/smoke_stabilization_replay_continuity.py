"""Consolidated isolated smoke test for stabilization and replay continuity."""

from __future__ import annotations

import argparse
import gc
import io
import json
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import ai_os.config as config

STALE_TS = "2000-01-01T00:00:00+00:00"
FRESH_TS = "2099-01-01T00:00:00+00:00"
SERVICE_NAME = "AI OS Stabilization Replay Continuity Smoke Test"


class DummyRuntime:
    def list_tasks(self):
        return []


class DummyCognitiveLoop:
    def status_snapshot(self):
        return {"running": False, "cycle_count": 0}


class DummyAgentRuntime:
    def snapshot(self):
        return {"agent_counts": {"total": 0}, "task_counts": {"queued": 0}}


class DummyExecutionRuntime:
    def snapshot(self):
        return {
            "operation_counts": {"failed": 0},
            "compensation_counts": {"pending": 0},
            "recovery_operation_counts": {"in_progress": 0},
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=SERVICE_NAME)
    parser.add_argument("--json", action="store_true", help="Print compact JSON summary.")
    parser.add_argument("--cleanup", action="store_true", help="Delete the temp root after the run.")
    return parser.parse_args()


def make_temp_root() -> Path:
    return Path(tempfile.gettempdir()) / f"gptmeai_stabilization_replay_{uuid.uuid4().hex}"


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


def bootstrap_environment(temp_root: Path) -> dict[str, object]:
    config.PROJECT_ROOT = temp_root
    config.ENV_FILE = temp_root / ".env"

    import ai_os.agent_runtime as agent_runtime_module
    import ai_os.cognitive_loop as cognitive_loop_module
    import execution.runtime as execution_runtime_module
    import planning.runtime as planning_runtime_module
    import scripts.api_server as api_server_module
    import scripts.runtime_store as runtime_store_module
    from ai_os.agent_runtime import AgentRuntime
    from ai_os.cognitive_loop import CognitiveLoop, build_task_metadata
    from execution.ledger import OperationLedger
    from execution.runtime import ExecutionRuntime
    from execution.snapshots import SnapshotLineageRegistry
    from planning.runtime import PlannerRuntime

    runtime_store_module.RUNTIME_FILE = temp_root / "GPTMemory_runtime.yaml"

    previous = {
        "agent_execution_runtime": agent_runtime_module.EXECUTION_RUNTIME,
        "planning_snapshot_lineage": planning_runtime_module.SNAPSHOT_LINEAGE,
        "execution_runtime": execution_runtime_module.EXECUTION_RUNTIME,
        "cognitive_planner": cognitive_loop_module.PLANNER_RUNTIME,
        "cognitive_execution": cognitive_loop_module.EXECUTION_RUNTIME,
        "cognitive_ledger": cognitive_loop_module.OPERATION_LEDGER,
        "cognitive_snapshots": cognitive_loop_module.SNAPSHOT_LINEAGE,
        "api_planner": api_server_module.PLANNER_RUNTIME,
        "api_snapshots": api_server_module.SNAPSHOT_LINEAGE,
        "api_agent": api_server_module.AGENT_RUNTIME,
        "api_execution": api_server_module.EXECUTION_RUNTIME,
        "api_loop": api_server_module.COGNITIVE_LOOP,
        "runtime_file": runtime_store_module.RUNTIME_FILE,
    }

    ledger = OperationLedger(temp_root / "storage" / "operation_ledger.json")
    snapshots = SnapshotLineageRegistry(temp_root / "storage" / "snapshot_lineage.json", ledger=ledger)
    execution = ExecutionRuntime(temp_root / "storage" / "execution_runtime.json", ledger=ledger)
    runtime = AgentRuntime(temp_root / "storage" / "agent_runtime.json")
    planner = PlannerRuntime(temp_root / "storage" / "planner_runtime.json", runtime=runtime)
    loop = CognitiveLoop(runtime=runtime, state_path=temp_root / "storage" / "cognitive_loop.json")

    agent_runtime_module.EXECUTION_RUNTIME = execution
    planning_runtime_module.SNAPSHOT_LINEAGE = snapshots
    execution_runtime_module.EXECUTION_RUNTIME = execution
    cognitive_loop_module.PLANNER_RUNTIME = planner
    cognitive_loop_module.EXECUTION_RUNTIME = execution
    cognitive_loop_module.OPERATION_LEDGER = ledger
    cognitive_loop_module.SNAPSHOT_LINEAGE = snapshots
    api_server_module.PLANNER_RUNTIME = planner
    api_server_module.SNAPSHOT_LINEAGE = snapshots
    api_server_module.AGENT_RUNTIME = DummyAgentRuntime()
    api_server_module.EXECUTION_RUNTIME = DummyExecutionRuntime()
    api_server_module.COGNITIVE_LOOP = DummyCognitiveLoop()

    return {
        "agent_runtime_module": agent_runtime_module,
        "cognitive_loop_module": cognitive_loop_module,
        "execution_runtime_module": execution_runtime_module,
        "planning_runtime_module": planning_runtime_module,
        "api_server_module": api_server_module,
        "runtime_store_module": runtime_store_module,
        "AgentRuntime": AgentRuntime,
        "CognitiveLoop": CognitiveLoop,
        "PlannerRuntime": PlannerRuntime,
        "OperationLedger": OperationLedger,
        "ExecutionRuntime": ExecutionRuntime,
        "SnapshotLineageRegistry": SnapshotLineageRegistry,
        "build_task_metadata": build_task_metadata,
        "previous": previous,
        "ledger": ledger,
        "snapshots": snapshots,
        "execution": execution,
        "runtime": runtime,
        "planner": planner,
        "loop": loop,
    }


def restore_environment(env: dict[str, object]) -> None:
    previous = dict(env["previous"])
    env["agent_runtime_module"].EXECUTION_RUNTIME = previous["agent_execution_runtime"]
    env["planning_runtime_module"].SNAPSHOT_LINEAGE = previous["planning_snapshot_lineage"]
    env["execution_runtime_module"].EXECUTION_RUNTIME = previous["execution_runtime"]
    env["cognitive_loop_module"].PLANNER_RUNTIME = previous["cognitive_planner"]
    env["cognitive_loop_module"].EXECUTION_RUNTIME = previous["cognitive_execution"]
    env["cognitive_loop_module"].OPERATION_LEDGER = previous["cognitive_ledger"]
    env["cognitive_loop_module"].SNAPSHOT_LINEAGE = previous["cognitive_snapshots"]
    env["api_server_module"].PLANNER_RUNTIME = previous["api_planner"]
    env["api_server_module"].SNAPSHOT_LINEAGE = previous["api_snapshots"]
    env["api_server_module"].AGENT_RUNTIME = previous["api_agent"]
    env["api_server_module"].EXECUTION_RUNTIME = previous["api_execution"]
    env["api_server_module"].COGNITIVE_LOOP = previous["api_loop"]
    env["runtime_store_module"].RUNTIME_FILE = previous["runtime_file"]


def build_metadata(build_task_metadata, *, branch_id: str, owner_hint: str) -> dict:
    return build_task_metadata(
        owner_hint=owner_hint,
        timeout_seconds=180,
        max_retries=0,
        rollback_on_error=True,
        compensation_action="report_only",
        compensation_description="Preserve smoke-test intent only.",
    ) | {"branch_id": branch_id}


def single_step_specs(build_task_metadata, *, branch_id: str, step_key: str, title: str, owner_hint: str = "Research Agent") -> list[dict]:
    return [
        {
            "step_key": step_key,
            "title": title,
            "preferred_role": "worker",
            "metadata": build_metadata(build_task_metadata, branch_id=branch_id, owner_hint=owner_hint),
        }
    ]


def record_event(env: dict[str, object], branch_id: str, operation_id: str, summary: str) -> dict:
    op = {
        "operation_id": operation_id,
        "task_id": abs(hash((branch_id, operation_id))) % 100000 + 1,
        "task_title": summary,
        "branch_id": branch_id,
        "status": "planned",
        "compensation_status": None,
        "attempts": 0,
        "failure_policy": {},
        "metadata": {"branch_id": branch_id},
        "result": "",
        "last_error": "",
        "compensation_plan": [],
        "execution_mode": "commit",
    }
    return env["ledger"].record_event("operation_registered", op, summary=summary)


def seed_snapshot(
    env: dict[str, object],
    *,
    temp_root: Path,
    branch_id: str,
    label: str,
    created_at: str,
    source_operation_id: str | None = None,
) -> dict:
    snapshot_path = temp_root / "storage" / "snapshots" / f"{branch_id.replace('/', '_')}_{label}.json"
    snapshot_body = {
        "snapshot_created_at": created_at,
        "memory_count": 0,
        "last_updated": created_at,
        "graph_nodes": 0,
        "graph_relations_total": 0,
    }
    snapshot_path.write_text(json.dumps(snapshot_body, ensure_ascii=False, indent=2), encoding="utf-8")
    return env["snapshots"].register_snapshot(
        snapshot_path=snapshot_path,
        snapshot_data=snapshot_body,
        branch_id=branch_id,
        source_operation_id=source_operation_id,
        label=label,
    )


def seed_terminal_stabilization(
    env: dict[str, object],
    *,
    branch_id: str,
    plan_status: str,
) -> dict:
    planner = env["planner"]
    build_task_metadata = env["build_task_metadata"]
    created = planner.create_or_refresh_plan(
        title=f"Stabilization smoke for {branch_id}",
        source="smoke_stabilization_replay_continuity",
        plan_kind="branch_stabilization",
        focus_area="branch_time_model",
        branch_id=branch_id,
        max_parallel_steps=1,
        task_specs=single_step_specs(
            build_task_metadata,
            branch_id=branch_id,
            step_key="stabilization_step",
            title=f"Stabilization step for {branch_id}",
        ),
    )
    plan = planner._find_plan(created["id"])
    if plan is None:
        raise AssertionError(f"expected plan for {branch_id}")
    plan.status = plan_status
    plan.updated_at = planner.utc_now() if hasattr(planner, "utc_now") else None
    step = plan.steps[0]
    step.status = "completed" if plan_status == "completed" else "failed"
    step.completed_at = step.completed_at or env["planning_runtime_module"].utc_now()
    changed = planner._record_branch_health_observation(plan, runtime_tasks={})
    if not changed:
        raise AssertionError(f"expected branch health observation for {branch_id}")
    planner._save_state()
    return {"plan_id": created["id"], "plan_status": plan_status}


def find_branch_summary(planner, branch_id: str) -> dict:
    snapshot = planner.branch_health_snapshot(limit=100)
    for item in snapshot.get("branches", []):
        if str(item.get("branch_id") or "").strip() == branch_id:
            return dict(item)
    raise AssertionError(f"branch summary not found for {branch_id}")


def find_task_by_plan_id(runtime, plan_id: str) -> dict | None:
    for task in runtime.list_tasks():
        metadata = dict(task.get("metadata") or {})
        if metadata.get("plan_id") == plan_id:
            return dict(task)
    return None


def call_preview_route(api_server_module, path: str) -> tuple[int, dict]:
    captured: dict = {}
    handler = object.__new__(api_server_module.GPTMemoryAPIHandler)
    handler.path = path
    handler.headers = {}
    handler.rfile = io.BytesIO()
    handler.wfile = io.BytesIO()
    handler.request_version = "HTTP/1.1"
    handler.command = "GET"
    handler.requestline = f"GET {path} HTTP/1.1"
    handler.client_address = ("127.0.0.1", 0)
    handler.server = None

    def send_json(data, status=200):
        captured["status"] = status
        captured["data"] = data

    handler._send_json = send_json
    handler._send_html_file = lambda path_value: captured.update({"status": 200, "html": str(path_value)})
    handler.send_response = lambda status: captured.setdefault("raw_status", status)
    handler.send_header = lambda *args, **kwargs: None
    handler.end_headers = lambda: None

    api_server_module.GPTMemoryAPIHandler.do_GET(handler)
    return int(captured.get("status", 0)), dict(captured.get("data") or {})


def run_smoke(env: dict[str, object], temp_root: Path) -> dict[str, object]:
    planner = env["planner"]
    runtime = env["runtime"]
    loop = env["loop"]
    build_task_metadata = env["build_task_metadata"]
    api_server_module = env["api_server_module"]

    completed_branch = "branch/replay-completed"
    failed_branch = "branch/replay-failed"
    no_signal_branch = "branch/replay-no-signal"
    no_fresh_branch = "branch/replay-no-fresh"

    completed_stale_branch = "branch/coverage-completed-stale"
    failed_stale_branch = "branch/coverage-failed-stale"
    completed_missing_branch = "branch/coverage-completed-missing"
    completed_fresh_branch = "branch/coverage-completed-fresh"
    coverage_no_signal_branch = "branch/coverage-no-signal"

    record_event(env, completed_branch, "op-completed-base", "base operation completed")
    stale_completed_snapshot = seed_snapshot(
        env,
        temp_root=temp_root,
        branch_id=completed_branch,
        label="stale",
        created_at=STALE_TS,
        source_operation_id="op-completed-base",
    )
    seed_terminal_stabilization(env, branch_id=completed_branch, plan_status="completed")
    record_event(env, completed_branch, "op-completed-post", "post stabilization operation completed")
    fresh_completed_snapshot = seed_snapshot(
        env,
        temp_root=temp_root,
        branch_id=completed_branch,
        label="fresh",
        created_at=FRESH_TS,
        source_operation_id="op-completed-post",
    )

    record_event(env, failed_branch, "op-failed-base", "base operation failed")
    stale_failed_snapshot = seed_snapshot(
        env,
        temp_root=temp_root,
        branch_id=failed_branch,
        label="stale",
        created_at=STALE_TS,
        source_operation_id="op-failed-base",
    )
    seed_terminal_stabilization(env, branch_id=failed_branch, plan_status="failed")
    record_event(env, failed_branch, "op-failed-post", "post stabilization operation failed")
    fresh_failed_snapshot = seed_snapshot(
        env,
        temp_root=temp_root,
        branch_id=failed_branch,
        label="fresh",
        created_at=FRESH_TS,
        source_operation_id="op-failed-post",
    )

    record_event(env, no_signal_branch, "op-no-signal-base", "base operation no signal")
    stale_no_signal_snapshot = seed_snapshot(
        env,
        temp_root=temp_root,
        branch_id=no_signal_branch,
        label="stale",
        created_at=STALE_TS,
        source_operation_id="op-no-signal-base",
    )
    record_event(env, no_signal_branch, "op-no-signal-post", "post operation no signal")
    fresh_no_signal_snapshot = seed_snapshot(
        env,
        temp_root=temp_root,
        branch_id=no_signal_branch,
        label="fresh",
        created_at=FRESH_TS,
        source_operation_id="op-no-signal-post",
    )

    record_event(env, no_fresh_branch, "op-no-fresh-base", "base operation no fresh snapshot")
    stale_no_fresh_snapshot = seed_snapshot(
        env,
        temp_root=temp_root,
        branch_id=no_fresh_branch,
        label="stale",
        created_at=STALE_TS,
        source_operation_id="op-no-fresh-base",
    )
    seed_terminal_stabilization(env, branch_id=no_fresh_branch, plan_status="completed")

    seed_snapshot(
        env,
        temp_root=temp_root,
        branch_id=completed_stale_branch,
        label="stale",
        created_at=STALE_TS,
    )
    seed_terminal_stabilization(env, branch_id=completed_stale_branch, plan_status="completed")

    seed_snapshot(
        env,
        temp_root=temp_root,
        branch_id=failed_stale_branch,
        label="stale",
        created_at=STALE_TS,
    )
    seed_terminal_stabilization(env, branch_id=failed_stale_branch, plan_status="failed")

    seed_terminal_stabilization(env, branch_id=completed_missing_branch, plan_status="completed")

    seed_terminal_stabilization(env, branch_id=completed_fresh_branch, plan_status="completed")
    seed_snapshot(
        env,
        temp_root=temp_root,
        branch_id=completed_fresh_branch,
        label="fresh",
        created_at=FRESH_TS,
    )

    seed_snapshot(
        env,
        temp_root=temp_root,
        branch_id=coverage_no_signal_branch,
        label="fresh",
        created_at=FRESH_TS,
    )

    completed_summary = find_branch_summary(planner, completed_branch)
    failed_summary = find_branch_summary(planner, failed_branch)

    completed_operational_plan = planner.create_or_refresh_plan(
        title=f"Operational follow-up for {completed_branch}",
        source="smoke_stabilization_replay_continuity",
        plan_kind="operational",
        focus_area="smoke_operational_dispatch",
        branch_id=completed_branch,
        max_parallel_steps=2,
        task_specs=single_step_specs(
            build_task_metadata,
            branch_id=completed_branch,
            step_key="inspect_completed_branch",
            title=f"Inspect operational follow-up for {completed_branch}",
        ),
    )
    completed_queue = planner.execute_ready_steps(plan_id=str(completed_operational_plan["id"]))
    completed_task = find_task_by_plan_id(runtime, str(completed_operational_plan["id"]))
    if completed_task is None:
        raise AssertionError("expected queued operational task for completed branch")

    failed_operational_plan = planner.create_or_refresh_plan(
        title=f"Operational follow-up for {failed_branch}",
        source="smoke_stabilization_replay_continuity",
        plan_kind="operational",
        focus_area="smoke_operational_dispatch",
        branch_id=failed_branch,
        max_parallel_steps=2,
        task_specs=single_step_specs(
            build_task_metadata,
            branch_id=failed_branch,
            step_key="inspect_failed_branch",
            title=f"Inspect operational follow-up for {failed_branch}",
        ),
    )
    failed_queue = planner.execute_ready_steps(plan_id=str(failed_operational_plan["id"]))

    completed_preview = planner.preview_recovery_plan_from_replay(branch_id=completed_branch, operation_id="op-completed-base")
    failed_preview = planner.preview_recovery_plan_from_replay(branch_id=failed_branch, operation_id="op-failed-base")
    no_signal_preview = planner.preview_recovery_plan_from_replay(branch_id=no_signal_branch, operation_id="op-no-signal-base")
    explicit_preview = planner.preview_recovery_plan_from_replay(
        snapshot_id=stale_completed_snapshot["snapshot_id"],
        branch_id=completed_branch,
        operation_id="op-completed-base",
    )
    no_fresh_preview = planner.preview_recovery_plan_from_replay(branch_id=no_fresh_branch, operation_id="op-no-fresh-base")

    completed_route_status, completed_route = call_preview_route(
        api_server_module,
        f"/planner/recovery/preview?branch_id={completed_branch}&operation_id=op-completed-base",
    )
    failed_route_status, failed_route = call_preview_route(
        api_server_module,
        f"/planner/recovery/preview?branch_id={failed_branch}&operation_id=op-failed-base",
    )
    explicit_route_status, explicit_route = call_preview_route(
        api_server_module,
        f"/planner/recovery/preview?snapshot_id={stale_completed_snapshot['snapshot_id']}&branch_id={completed_branch}&operation_id=op-completed-base",
    )
    no_signal_route_status, no_signal_route = call_preview_route(
        api_server_module,
        f"/planner/recovery/preview?branch_id={no_signal_branch}&operation_id=op-no-signal-base",
    )
    no_fresh_route_status, no_fresh_route = call_preview_route(
        api_server_module,
        f"/planner/recovery/preview?branch_id={no_fresh_branch}&operation_id=op-no-fresh-base",
    )

    perception = loop.perceive()
    reasoning = loop.reason(perception)
    plan = loop.plan(perception, reasoning)
    coverage_branch_ids = {
        str(item.get("branch_id"))
        for item in reasoning.get("snapshot_coverage_branches", [])
        if item.get("branch_id")
    }
    coverage_states = {
        str(item.get("branch_id")): str(item.get("coverage_state"))
        for item in reasoning.get("snapshot_coverage_branches", [])
        if item.get("branch_id")
    }
    planned_step_keys = [str(item.get("step_key")) for item in plan.get("tasks", []) if item.get("step_key")]

    completed_signal = dict(completed_preview.get("branch_recovery_signal") or {})
    failed_signal = dict(failed_preview.get("branch_recovery_signal") or {})
    completed_route_signal = dict(completed_route.get("branch_recovery_signal") or {})
    failed_route_signal = dict(failed_route.get("branch_recovery_signal") or {})

    completed_bias = dict(completed_preview.get("anchor_bias") or {})
    failed_bias = dict(failed_preview.get("anchor_bias") or {})
    explicit_bias = dict(explicit_preview.get("anchor_bias") or {})
    no_fresh_bias = dict(no_fresh_preview.get("anchor_bias") or {})
    completed_route_bias = dict(completed_route.get("anchor_bias") or {})
    failed_route_bias = dict(failed_route.get("anchor_bias") or {})
    explicit_route_bias = dict(explicit_route.get("anchor_bias") or {})
    no_fresh_route_bias = dict(no_fresh_route.get("anchor_bias") or {})

    completed_task_metadata = dict(completed_task.get("metadata") or {})
    completed_task_dispatch_policy = dict(completed_task_metadata.get("dispatch_policy") or {})

    checks = {
        "completed_branch_health_status": completed_summary.get("status") == "observe",
        "completed_branch_health_recommendation": completed_summary.get("recommendation") == "heightened_monitoring",
        "failed_branch_health_status": failed_summary.get("status") == "degraded",
        "failed_branch_health_recommendation": failed_summary.get("recommendation") == "manual_review",
        "completed_planner_gate_guarded": str((completed_summary.get("planner_gate") or {}).get("mode")) == "guarded",
        "completed_dispatch_policy_guarded": str((completed_summary.get("dispatch_policy") or {}).get("mode")) == "guarded",
        "failed_planner_gate_restricted": str((failed_summary.get("planner_gate") or {}).get("mode")) == "restricted",
        "failed_dispatch_policy_blocked": str((failed_summary.get("dispatch_policy") or {}).get("mode")) == "blocked",
        "completed_operational_task_guarded": str(completed_task_dispatch_policy.get("mode")) == "guarded",
        "failed_operational_plan_gated": int((failed_queue.get("gating") or {}).get("count", 0) or 0) >= 1,
        "completed_preview_has_branch_recovery_signal": bool(completed_signal),
        "failed_preview_has_branch_recovery_signal": bool(failed_signal),
        "completed_preview_signal_observe": completed_signal.get("status") == "observe",
        "failed_preview_signal_degraded": failed_signal.get("status") == "degraded",
        "completed_route_http_200": completed_route_status == 200,
        "failed_route_http_200": failed_route_status == 200,
        "completed_route_exposes_branch_recovery_signal": bool(completed_route_signal),
        "failed_route_exposes_branch_recovery_signal": bool(failed_route_signal),
        "coverage_completed_stale_flagged": completed_stale_branch in coverage_branch_ids,
        "coverage_failed_stale_flagged": failed_stale_branch in coverage_branch_ids,
        "coverage_completed_missing_flagged": completed_missing_branch in coverage_branch_ids,
        "coverage_completed_fresh_not_flagged": completed_fresh_branch not in coverage_branch_ids,
        "coverage_no_signal_not_flagged": coverage_no_signal_branch not in coverage_branch_ids,
        "coverage_capture_task_present": "capture_snapshot_coverage" in planned_step_keys,
        "anchor_bias_completed_prefers_fresh": completed_preview.get("snapshot_id") == fresh_completed_snapshot["snapshot_id"],
        "anchor_bias_failed_prefers_fresh": failed_preview.get("snapshot_id") == fresh_failed_snapshot["snapshot_id"],
        "anchor_bias_completed_applied": completed_bias.get("applied") is True,
        "anchor_bias_failed_applied": failed_bias.get("applied") is True,
        "anchor_bias_explicit_snapshot_wins": explicit_preview.get("snapshot_id") == stale_completed_snapshot["snapshot_id"],
        "anchor_bias_explicit_bypassed": explicit_bias.get("applied") is False and explicit_bias.get("explicit_snapshot_bypassed") is True,
        "anchor_bias_no_signal_unchanged": no_signal_preview.get("snapshot_id") == stale_no_signal_snapshot["snapshot_id"] and not bool(no_signal_preview.get("anchor_bias")),
        "anchor_bias_no_fresh_fallback": no_fresh_preview.get("snapshot_id") == stale_no_fresh_snapshot["snapshot_id"],
        "anchor_bias_no_fresh_reason": no_fresh_bias.get("reason") == "no_fresh_post_stabilization_snapshot",
        "anchor_bias_operation_id_visible": str((completed_preview.get("context") or {}).get("operation_id")) == "op-completed-base",
        "route_anchor_bias_completed_visible": completed_route_bias.get("applied") is True and completed_route_bias == dict((completed_route.get("context") or {}).get("anchor_bias") or {}),
        "route_anchor_bias_failed_visible": failed_route_bias.get("applied") is True and failed_route_bias == dict((failed_route.get("context") or {}).get("anchor_bias") or {}),
        "route_anchor_bias_explicit_visible": explicit_route_bias.get("applied") is False and explicit_route_bias.get("explicit_snapshot_bypassed") is True,
        "route_anchor_bias_no_signal_absent": not bool(no_signal_route.get("anchor_bias")),
        "route_anchor_bias_no_fresh_reason": no_fresh_route_bias.get("reason") == "no_fresh_post_stabilization_snapshot",
        "route_operation_id_visible_completed": str((completed_route.get("context") or {}).get("operation_id")) == "op-completed-base",
        "route_operation_id_visible_failed": str((failed_route.get("context") or {}).get("operation_id")) == "op-failed-base",
        "explicit_route_http_200": explicit_route_status == 200,
        "no_signal_route_http_200": no_signal_route_status == 200,
        "no_fresh_route_http_200": no_fresh_route_status == 200,
    }

    failed_checks = [name for name, passed in checks.items() if not passed]
    if failed_checks:
        raise AssertionError("verification failed: " + ", ".join(failed_checks))

    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "checks": checks,
        "branch_health": {
            "completed": {
                "branch_id": completed_branch,
                "status": completed_summary.get("status"),
                "recommendation": completed_summary.get("recommendation"),
                "planner_gate_mode": (completed_summary.get("planner_gate") or {}).get("mode"),
                "dispatch_policy_mode": (completed_summary.get("dispatch_policy") or {}).get("mode"),
            },
            "failed": {
                "branch_id": failed_branch,
                "status": failed_summary.get("status"),
                "recommendation": failed_summary.get("recommendation"),
                "planner_gate_mode": (failed_summary.get("planner_gate") or {}).get("mode"),
                "dispatch_policy_mode": (failed_summary.get("dispatch_policy") or {}).get("mode"),
            },
        },
        "preview": {
            "completed_signal": completed_signal,
            "failed_signal": failed_signal,
            "completed_anchor_bias": completed_bias,
            "failed_anchor_bias": failed_bias,
            "explicit_anchor_bias": explicit_bias,
            "no_fresh_anchor_bias": no_fresh_bias,
        },
        "route": {
            "behavior": "passthrough",
            "completed_signal": completed_route_signal,
            "failed_signal": failed_route_signal,
            "completed_anchor_bias": completed_route_bias,
            "failed_anchor_bias": failed_route_bias,
            "explicit_anchor_bias": explicit_route_bias,
            "no_fresh_anchor_bias": no_fresh_route_bias,
        },
        "snapshot_coverage": {
            "branch_ids": sorted(coverage_branch_ids),
            "coverage_states": coverage_states,
            "planned_step_keys": planned_step_keys,
        },
        "temp_root": str(temp_root),
    }


def cleanup_temp_root(temp_root: Path) -> tuple[bool, str | None]:
    gc.collect()
    try:
        shutil.rmtree(temp_root, ignore_errors=False)
    except OSError as exc:
        return (not temp_root.exists(), str(exc))
    return (not temp_root.exists(), None)


def print_result(result: dict[str, object], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
        return
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> int:
    args = parse_args()
    temp_root = make_temp_root()
    ensure_temp_layout(temp_root)

    env: dict[str, object] | None = None
    result: dict[str, object] = {
        "status": "error",
        "service": SERVICE_NAME,
        "temp_root": str(temp_root),
    }

    try:
        env = bootstrap_environment(temp_root)
        result = run_smoke(env, temp_root)
        exit_code = 0
    except Exception as exc:
        result = {
            "status": "error",
            "service": SERVICE_NAME,
            "temp_root": str(temp_root),
            "error": str(exc),
        }
        exit_code = 1
    finally:
        if env is not None:
            restore_environment(env)
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
