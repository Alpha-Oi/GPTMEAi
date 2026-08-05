"""Temp-state smoke for raw /snapshots/replay replay_metadata behavior."""

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

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import ai_os.config as config

SERVICE_NAME = "AI OS /snapshots/replay Replay Metadata Smoke"
STALE_TS = "2000-01-01T00:00:00+00:00"
FRESH_TS = "2099-01-01T00:00:00+00:00"
PLANNER_ONLY_FIELDS = {
    "branch_recovery_signal",
    "anchor_bias",
    "recovery_continuity",
    "policy_scope",
    "planner_gate_scope",
    "dispatch_policy_scope",
}


class DummyCognitiveLoop:
    def status_snapshot(self) -> dict:
        return {"running": False, "cycle_count": 0}


class DummyAgentRuntime:
    def snapshot(self) -> dict:
        return {"agent_counts": {"total": 0}, "task_counts": {"queued": 0}}


class DummyExecutionRuntime:
    def snapshot(self) -> dict:
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
    return Path(tempfile.gettempdir()) / f"gptmeai_snapshots_replay_metadata_{uuid.uuid4().hex}"


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
    from ai_os.cognitive_loop import build_task_metadata
    from execution.ledger import OperationLedger
    from execution.runtime import ExecutionRuntime
    from execution.snapshots import SnapshotLineageRegistry
    from planning.runtime import PlannerRuntime

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

    runtime_store_module.RUNTIME_FILE = temp_root / "GPTMemory_runtime.yaml"

    ledger = OperationLedger(temp_root / "storage" / "operation_ledger.json")
    snapshots = SnapshotLineageRegistry(temp_root / "storage" / "snapshot_lineage.json", ledger=ledger)
    execution = ExecutionRuntime(temp_root / "storage" / "execution_runtime.json", ledger=ledger)
    runtime = AgentRuntime(temp_root / "storage" / "agent_runtime.json")
    planner = PlannerRuntime(temp_root / "storage" / "planner_runtime.json", runtime=runtime)

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
        "build_task_metadata": build_task_metadata,
        "previous": previous,
        "ledger": ledger,
        "snapshots": snapshots,
        "execution": execution,
        "runtime": runtime,
        "planner": planner,
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


def call_get(api_server_module, path: str) -> tuple[int, dict]:
    captured: dict[str, object] = {}
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


def operation(branch_id: str, operation_id: str, title: str, task_id: int) -> dict:
    return {
        "operation_id": operation_id,
        "task_id": task_id,
        "task_title": title,
        "branch_id": branch_id,
        "status": "planned",
        "compensation_status": None,
        "attempts": 0,
        "failure_policy": {},
        "metadata": {"branch_id": branch_id, "source": "smoke_snapshots_replay_metadata"},
        "result": "",
        "last_error": "",
        "compensation_plan": [],
        "execution_mode": "commit",
    }


def record_event(env: dict[str, object], branch_id: str, operation_id: str, title: str, task_id: int) -> dict:
    return env["ledger"].record_event(
        "operation_registered",
        operation(branch_id, operation_id, title, task_id),
        summary=title,
    )


def seed_snapshot(
    env: dict[str, object],
    *,
    temp_root: Path,
    branch_id: str,
    label: str,
    created_at: str,
    source_operation_id: str | None = None,
) -> dict:
    snapshot_path = temp_root / "storage" / "snapshots" / f"{branch_id}_{label}.json"
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


def step_specs(build_task_metadata, branch_id: str) -> list[dict]:
    metadata = build_task_metadata(
        owner_hint="Research Agent",
        timeout_seconds=180,
        max_retries=0,
        rollback_on_error=True,
        compensation_action="report_only",
        compensation_description="Preserve smoke-test intent only.",
    )
    metadata["branch_id"] = branch_id
    return [
        {
            "step_key": "stabilization_step",
            "title": f"Stabilization step for {branch_id}",
            "preferred_role": "worker",
            "metadata": metadata,
        }
    ]


def seed_terminal_stabilization(env: dict[str, object], branch_id: str, plan_status: str) -> None:
    planner = env["planner"]
    created = planner.create_or_refresh_plan(
        title=f"Stabilization smoke for {branch_id}",
        source="smoke_snapshots_replay_metadata",
        plan_kind="branch_stabilization",
        focus_area="branch_time_model",
        branch_id=branch_id,
        max_parallel_steps=1,
        task_specs=step_specs(env["build_task_metadata"], branch_id),
    )
    plan = planner._find_plan(created["id"])
    if plan is None:
        raise AssertionError(f"expected branch stabilization plan for {branch_id}")
    plan.status = plan_status
    step = plan.steps[0]
    step.status = "completed" if plan_status == "completed" else "failed"
    step.completed_at = step.completed_at or env["planning_runtime_module"].utc_now()
    if not planner._record_branch_health_observation(plan, runtime_tasks={}):
        raise AssertionError(f"expected branch health observation for {branch_id}")
    planner._save_state()


def collect_keys(payload: object) -> set[str]:
    if isinstance(payload, dict):
        keys = set(payload)
        for value in payload.values():
            keys.update(collect_keys(value))
        return keys
    if isinstance(payload, list):
        keys: set[str] = set()
        for item in payload:
            keys.update(collect_keys(item))
        return keys
    return set()


def logical_times(payload: dict, key: str) -> list[int]:
    values: list[int] = []
    for item in payload.get(key, []):
        try:
            values.append(int(item.get("logical_time", -1)))
        except (AttributeError, TypeError, ValueError):
            values.append(-1)
    return values


def metadata_is_raw(payload: dict) -> bool:
    metadata = dict(payload.get("replay_metadata") or {})
    return (
        bool(metadata)
        and metadata.get("source") == "raw_snapshot_lineage"
        and metadata.get("planner_context_included") is False
        and metadata.get("planner_context_endpoint") == "/planner/recovery/preview"
        and metadata.get("replay_order") == "logical_time_ascending_after_anchor"
        and metadata.get("replay_entry_count") == len(payload.get("replay_entries") or [])
        and metadata.get("replay_step_count") == len(payload.get("replay_steps") or [])
    )


def has_recovery_continuity_task_metadata(preview: dict) -> bool:
    for spec in preview.get("task_specs", []):
        metadata = dict((spec or {}).get("metadata") or {})
        continuity = dict(metadata.get("recovery_continuity") or {})
        if continuity.get("branch_recovery_signal"):
            return True
    return False


def run_smoke(env: dict[str, object], temp_root: Path) -> dict[str, object]:
    api_server_module = env["api_server_module"]

    explicit_branch = "replay-metadata-explicit"
    operation_branch = "replay-metadata-operation"
    branch_latest_branch = "replay-metadata-branch"
    planner_branch = "replay-metadata-planner"
    global_branch = "replay-metadata-global"

    record_event(env, explicit_branch, "op-explicit-anchor", "explicit anchor event", 101)
    explicit_snapshot = seed_snapshot(
        env,
        temp_root=temp_root,
        branch_id=explicit_branch,
        label="explicit",
        created_at=STALE_TS,
        source_operation_id="op-explicit-anchor",
    )
    record_event(env, explicit_branch, "op-explicit-after-1", "explicit replay first", 102)
    record_event(env, explicit_branch, "op-explicit-after-2", "explicit replay second", 103)

    record_event(env, operation_branch, "op-operation-anchor", "operation anchor event", 201)
    operation_snapshot = seed_snapshot(
        env,
        temp_root=temp_root,
        branch_id=operation_branch,
        label="operation",
        created_at=STALE_TS,
        source_operation_id="op-operation-anchor",
    )
    record_event(env, operation_branch, "op-operation-anchor", "operation replay second event", 201)

    record_event(env, branch_latest_branch, "op-branch-old", "branch old event", 301)
    seed_snapshot(
        env,
        temp_root=temp_root,
        branch_id=branch_latest_branch,
        label="old",
        created_at=STALE_TS,
        source_operation_id="op-branch-old",
    )
    record_event(env, branch_latest_branch, "op-branch-latest", "branch latest event", 302)
    branch_latest_snapshot = seed_snapshot(
        env,
        temp_root=temp_root,
        branch_id=branch_latest_branch,
        label="latest",
        created_at=FRESH_TS,
        source_operation_id="op-branch-latest",
    )
    record_event(env, branch_latest_branch, "op-branch-after", "branch replay event", 303)

    record_event(env, planner_branch, "op-planner-base", "planner base event", 401)
    stale_planner_snapshot = seed_snapshot(
        env,
        temp_root=temp_root,
        branch_id=planner_branch,
        label="stale",
        created_at=STALE_TS,
        source_operation_id="op-planner-base",
    )
    seed_terminal_stabilization(env, planner_branch, "completed")
    record_event(env, planner_branch, "op-planner-post", "planner post stabilization event", 402)
    fresh_planner_snapshot = seed_snapshot(
        env,
        temp_root=temp_root,
        branch_id=planner_branch,
        label="fresh",
        created_at=FRESH_TS,
        source_operation_id="op-planner-post",
    )

    record_event(env, global_branch, "op-global-anchor", "global latest event", 501)
    global_snapshot = seed_snapshot(
        env,
        temp_root=temp_root,
        branch_id=global_branch,
        label="global",
        created_at=FRESH_TS,
        source_operation_id="op-global-anchor",
    )

    explicit_status, explicit_route = call_get(
        api_server_module,
        f"/snapshots/replay?snapshot_id={explicit_snapshot['snapshot_id']}&branch_id={explicit_branch}&limit=20",
    )
    operation_status, operation_route = call_get(
        api_server_module,
        f"/snapshots/replay?operation_id=op-operation-anchor&branch_id={operation_branch}&limit=20",
    )
    branch_status, branch_route = call_get(
        api_server_module,
        f"/snapshots/replay?branch_id={branch_latest_branch}&limit=20",
    )
    global_status, global_route = call_get(api_server_module, "/snapshots/replay?limit=20")
    planner_status, planner_route = call_get(
        api_server_module,
        f"/planner/recovery/preview?branch_id={planner_branch}&operation_id=op-planner-base&max_replay_steps=6",
    )

    raw_routes = {
        "explicit": explicit_route,
        "operation": operation_route,
        "branch": branch_route,
        "global": global_route,
    }
    raw_keys = {name: collect_keys(route) for name, route in raw_routes.items()}

    explicit_entry_times = logical_times(explicit_route, "replay_entries")
    explicit_step_times = logical_times(explicit_route, "replay_steps")
    operation_entry_times = logical_times(operation_route, "replay_entries")
    branch_entry_times = logical_times(branch_route, "replay_entries")

    planner_signal = dict(planner_route.get("branch_recovery_signal") or {})
    planner_bias = dict(planner_route.get("anchor_bias") or {})
    planner_context = dict(planner_route.get("context") or {})

    checks = {
        "snapshots_replay_explicit_http_200": explicit_status == 200,
        "snapshots_replay_operation_http_200": operation_status == 200,
        "snapshots_replay_branch_http_200": branch_status == 200,
        "snapshots_replay_global_http_200": global_status == 200,
        "snapshots_replay_returns_replay_metadata": all(
            bool(route.get("replay_metadata")) for route in raw_routes.values()
        ),
        "replay_metadata_source_raw_snapshot_lineage": all(
            dict(route.get("replay_metadata") or {}).get("source") == "raw_snapshot_lineage"
            for route in raw_routes.values()
        ),
        "replay_metadata_planner_context_included_false": all(
            dict(route.get("replay_metadata") or {}).get("planner_context_included") is False
            for route in raw_routes.values()
        ),
        "replay_metadata_planner_context_endpoint_preview": all(
            dict(route.get("replay_metadata") or {}).get("planner_context_endpoint") == "/planner/recovery/preview"
            for route in raw_routes.values()
        ),
        "replay_metadata_order_logical_time_ascending": all(
            dict(route.get("replay_metadata") or {}).get("replay_order") == "logical_time_ascending_after_anchor"
            for route in raw_routes.values()
        ),
        "raw_replay_metadata_counts_match_payloads": all(metadata_is_raw(route) for route in raw_routes.values()),
        "raw_replay_has_no_planner_only_fields": all(
            not (keys & PLANNER_ONLY_FIELDS) for keys in raw_keys.values()
        ),
        "explicit_snapshot_id_selects_requested_snapshot": (
            dict(explicit_route.get("anchor_snapshot") or {}).get("snapshot_id") == explicit_snapshot["snapshot_id"]
        ),
        "operation_id_anchor_behavior_unchanged": (
            dict(operation_route.get("anchor_snapshot") or {}).get("snapshot_id") == operation_snapshot["snapshot_id"]
            and operation_entry_times == sorted(operation_entry_times)
            and len(operation_entry_times) == 1
        ),
        "branch_latest_fallback_unchanged": (
            dict(branch_route.get("anchor_snapshot") or {}).get("snapshot_id") == branch_latest_snapshot["snapshot_id"]
            and branch_entry_times == sorted(branch_entry_times)
            and len(branch_entry_times) == 1
        ),
        "global_latest_fallback_unchanged": (
            dict(global_route.get("anchor_snapshot") or {}).get("snapshot_id") == global_snapshot["snapshot_id"]
        ),
        "replay_entries_order_unchanged": explicit_entry_times == sorted(explicit_entry_times),
        "replay_steps_order_unchanged": explicit_step_times == sorted(explicit_step_times),
        "replay_entries_and_steps_have_same_order": explicit_entry_times == explicit_step_times,
        "planner_preview_http_200": planner_status == 200,
        "planner_preview_exposes_branch_recovery_signal": bool(planner_signal),
        "planner_preview_exposes_anchor_bias": bool(planner_bias),
        "planner_preview_context_exposes_branch_recovery_signal": bool(planner_context.get("branch_recovery_signal")),
        "planner_preview_context_exposes_anchor_bias": bool(planner_context.get("anchor_bias")),
        "planner_preview_task_metadata_exposes_recovery_continuity": has_recovery_continuity_task_metadata(planner_route),
        "planner_preview_anchor_bias_can_prefer_fresh_snapshot": (
            planner_route.get("snapshot_id") == fresh_planner_snapshot["snapshot_id"]
            and planner_bias.get("applied") is True
            and planner_bias.get("original_anchor_snapshot_id") == stale_planner_snapshot["snapshot_id"]
        ),
    }

    failed_checks = [name for name, passed in checks.items() if not passed]
    if failed_checks:
        raise AssertionError("verification failed: " + ", ".join(failed_checks))

    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "checks": checks,
        "details": {
            "raw_route_statuses": {
                "explicit": explicit_status,
                "operation": operation_status,
                "branch": branch_status,
                "global": global_status,
            },
            "planner_route_status": planner_status,
            "anchor_snapshot_ids": {
                "explicit": dict(explicit_route.get("anchor_snapshot") or {}).get("snapshot_id"),
                "operation": dict(operation_route.get("anchor_snapshot") or {}).get("snapshot_id"),
                "branch": dict(branch_route.get("anchor_snapshot") or {}).get("snapshot_id"),
                "global": dict(global_route.get("anchor_snapshot") or {}).get("snapshot_id"),
                "planner": planner_route.get("snapshot_id"),
            },
            "expected_snapshot_ids": {
                "explicit": explicit_snapshot["snapshot_id"],
                "operation": operation_snapshot["snapshot_id"],
                "branch": branch_latest_snapshot["snapshot_id"],
                "global": global_snapshot["snapshot_id"],
                "planner_stale": stale_planner_snapshot["snapshot_id"],
                "planner_fresh": fresh_planner_snapshot["snapshot_id"],
            },
            "raw_forbidden_key_hits": {
                name: sorted(keys & PLANNER_ONLY_FIELDS)
                for name, keys in raw_keys.items()
            },
            "explicit_replay_entry_logical_times": explicit_entry_times,
            "explicit_replay_step_logical_times": explicit_step_times,
            "operation_replay_entry_logical_times": operation_entry_times,
            "branch_replay_entry_logical_times": branch_entry_times,
            "temp_root": str(temp_root),
        },
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
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


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
