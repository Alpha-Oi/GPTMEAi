from dataclasses import asdict
import json
from datetime import datetime, UTC
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler, HTTPServer

from ai_os.agent_runtime import AGENT_RUNTIME
from ai_os.cognitive_loop import COGNITIVE_LOOP
from ai_os.config import get_project_paths, get_runtime_config
from ai_os.manifest import build_manifest
from ai_os.memory_pipeline import (
    corpus_status,
    rebuild_index,
    rebuild_knowledge,
    rebuild_parsed,
    rebuild_vectors,
)
from ai_os.semantic_mesh import build_semantic_mesh
from core.memory_engine import MemoryEngine
from core.retrieval_engine import RetrievalEngine
from core.temporal_engine import TemporalMemory
from core.graph_engine import GraphMemory
from execution.ledger import OPERATION_LEDGER
from execution.snapshots import SNAPSHOT_LINEAGE
from execution.runtime import EXECUTION_RUNTIME
from planning.runtime import PLANNER_RUNTIME
from scripts.runtime_store import load_runtime

PATHS = get_project_paths()
RUNTIME = get_runtime_config()
BASE_DIR = PATHS.project_root
DASHBOARD_FILE = PATHS.dashboard_file
HOST = RUNTIME.host
PORT = RUNTIME.port


def _concept_core_status_payload():
    return {
        "status": "ok",
        "service": "AI OS Concept Core",
        "mode": "advisory_only",
        "runtime_enforcement": False,
        "storage_schema_mutation": False,
        "public_api_behavior_mutation": False,
        "capabilities": {
            "typed_primitives": True,
            "strict_memory_add": True,
            "memory_metadata_visibility": True,
            "direct_cognitive_plan_advisory": True,
            "public_decision_preview": False,
            "global_enforcement": False,
        },
        "visibility": {
            "memory_metadata_routes": [
                "/memory/all",
                "/memory/search",
                "/memory/tag",
                "/memory/recent",
            ],
            "memory_related_exposes_metadata": False,
            "cognitive_status_exposes_plan_advisory": False,
            "cognitive_run_exposes_plan_advisory": False,
            "planner_status_uses_concept_core": False,
            "dispatch_uses_concept_core": False,
        },
        "safety_contract": {
            "label": "advisory_non_enforcing",
            "internal_plan_payload_exposed": False,
            "red_button_detection": "text_heuristic_mvp_not_authoritative_policy",
        },
    }


class QuietHTTPServer(HTTPServer):
    def handle_error(self, request, client_address):
        import sys
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionAbortedError, BrokenPipeError, ConnectionResetError)):
            return
        super().handle_error(request, client_address)

class GPTMemoryAPIHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html_file(self, path: Path):
        if not path.exists():
            self._send_json({"error": "dashboard file not found"}, status=404)
            return

        body = path.read_text(encoding="utf-8").encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


    def log_message(self, format, *args):
        msg = format % args
        if "GET /favicon.ico" in msg:
            return
        super().log_message(format, *args)

    def _read_json_body(self):
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError:
            return None

        if length <= 0:
            return None

        raw = self.rfile.read(length).decode("utf-8")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/concept-core/status":
            self._send_json(_concept_core_status_payload())
            return

        memory_engine = MemoryEngine()
        retrieval_engine = RetrievalEngine(memory_engine)
        temporal_engine = TemporalMemory(memory_engine)
        graph_engine = GraphMemory(memory_engine)


        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        if path in ["/", "/dashboard"]:
            self._send_html_file(DASHBOARD_FILE)
            return

        if path == "/health":
            agent_snapshot = AGENT_RUNTIME.snapshot()
            planner_snapshot = PLANNER_RUNTIME.status_snapshot(limit=5)
            execution_snapshot = EXECUTION_RUNTIME.snapshot()
            self._send_json({
                "status": "ok",
                "service": "AI OS API",
                "memory_count": memory_engine.count(),
                "agents_total": agent_snapshot["agent_counts"]["total"],
                "tasks_queued": agent_snapshot["task_counts"]["queued"],
                "cognitive_loop_running": COGNITIVE_LOOP.status_snapshot()["running"],
                "cognitive_cycles": COGNITIVE_LOOP.status_snapshot()["cycle_count"],
                "planner_active": planner_snapshot["plan_counts"]["active"],
                "planner_blocked_steps": planner_snapshot["step_counts"]["blocked"],
                "planner_remediation_plans": planner_snapshot.get("plan_kind_counts", {}).get("remediation", 0),
                "planner_recovery_workflows": len(planner_snapshot.get("recovery_workflows", [])),
                "planner_recovery_remediation_blocked": planner_snapshot.get("recovery_counts", {}).get("remediation_blocked", 0),
                "planner_recovery_healthy": planner_snapshot.get("recovery_counts", {}).get("healthy", 0),
                "planner_recovery_observe": planner_snapshot.get("recovery_counts", {}).get("observe", 0),
                "planner_recovery_degraded": planner_snapshot.get("recovery_counts", {}).get("degraded", 0),
                "planner_recovery_blocked": planner_snapshot.get("recovery_counts", {}).get("blocked", 0),
                "planner_branch_guarded": planner_snapshot.get("branch_health_counts", {}).get("guarded", 0),
                "planner_branch_restricted": planner_snapshot.get("branch_health_counts", {}).get("restricted", 0),
                "planner_branch_blocked": planner_snapshot.get("branch_health_counts", {}).get("blocked", 0),
                "planner_dispatch_guarded": planner_snapshot.get("branch_health_counts", {}).get("dispatch_guarded", 0),
                "planner_dispatch_restricted": planner_snapshot.get("branch_health_counts", {}).get("dispatch_restricted", 0),
                "planner_dispatch_blocked": planner_snapshot.get("branch_health_counts", {}).get("dispatch_blocked", 0),
                "planner_branch_declining": planner_snapshot.get("branch_health_counts", {}).get("declining", 0),
                "planner_branch_pressure_medium": planner_snapshot.get("branch_health_counts", {}).get("pressure_medium", 0),
                "planner_branch_pressure_high": planner_snapshot.get("branch_health_counts", {}).get("pressure_high", 0),
                "planner_branch_pressure_critical": planner_snapshot.get("branch_health_counts", {}).get("pressure_critical", 0),
                "planner_playbooks_total": planner_snapshot.get("playbook_counts", {}).get("total", 0),
                "planner_playbooks_strong": planner_snapshot.get("playbook_counts", {}).get("strong", 0),
                "planner_playbooks_usable": planner_snapshot.get("playbook_counts", {}).get("usable", 0),
                "planner_playbooks_reuse_ready": planner_snapshot.get("playbook_counts", {}).get("reuse_ready", 0),
                "execution_failed": execution_snapshot["operation_counts"]["failed"],
                "execution_pending_compensation": execution_snapshot["compensation_counts"]["pending"],
                "execution_recovery_in_progress": execution_snapshot.get("recovery_operation_counts", {}).get("in_progress", 0),
            })
            return

        if path == "/system/manifest":
            self._send_json(asdict(build_manifest()))
            return

        if path == "/cognitive/status":
            self._send_json(COGNITIVE_LOOP.status_snapshot())
            return

        if path == "/planner/status":
            raw_limit = query.get("limit", ["10"])[0]
            try:
                limit = int(raw_limit)
            except ValueError:
                self._send_json({"error": "limit must be integer"}, status=400)
                return

            self._send_json(
                PLANNER_RUNTIME.status_snapshot(
                    limit=limit,
                    plan_id=query.get("plan_id", [""])[0].strip() or None,
                )
            )
            return

        if path == "/planner/recovery/workflows":
            raw_limit = query.get("limit", ["10"])[0]
            try:
                limit = int(raw_limit)
            except ValueError:
                self._send_json({"error": "limit must be integer"}, status=400)
                return

            active_only = query.get("active_only", ["0"])[0].strip().lower() in {"1", "true", "yes", "on"}
            self._send_json(PLANNER_RUNTIME.recovery_workflows_snapshot(limit=limit, active_only=active_only))
            return

        if path == "/planner/branch-health":
            raw_limit = query.get("limit", ["10"])[0]
            try:
                limit = int(raw_limit)
            except ValueError:
                self._send_json({"error": "limit must be integer"}, status=400)
                return

            self._send_json(PLANNER_RUNTIME.branch_health_snapshot(limit=limit))
            return

        if path == "/planner/playbooks":
            raw_limit = query.get("limit", ["10"])[0]
            try:
                limit = int(raw_limit)
            except ValueError:
                self._send_json({"error": "limit must be integer"}, status=400)
                return

            self._send_json(PLANNER_RUNTIME.stabilization_playbooks_snapshot(limit=limit))
            return

        if path == "/planner/recovery/preview":
            raw_parallel = query.get("max_parallel_steps", ["1"])[0]
            raw_replay = query.get("max_replay_steps", ["6"])[0]
            try:
                max_parallel_steps = int(raw_parallel)
                max_replay_steps = int(raw_replay)
            except ValueError:
                self._send_json({"error": "max_parallel_steps and max_replay_steps must be integer"}, status=400)
                return

            self._send_json(
                PLANNER_RUNTIME.preview_recovery_plan_from_replay(
                    snapshot_id=query.get("snapshot_id", [""])[0].strip() or None,
                    branch_id=query.get("branch_id", [""])[0].strip() or None,
                    operation_id=query.get("operation_id", [""])[0].strip() or None,
                    title=query.get("title", [""])[0].strip() or None,
                    max_parallel_steps=max_parallel_steps,
                    max_replay_steps=max_replay_steps,
                )
            )
            return

        if path == "/execution/status":
            self._send_json(EXECUTION_RUNTIME.snapshot())
            return

        if path == "/execution/ledger":
            operation_id = query.get("operation_id", [""])[0].strip()
            branch_id = query.get("branch_id", [""])[0].strip()
            raw_limit = query.get("limit", ["50"])[0]
            try:
                limit = int(raw_limit)
            except ValueError:
                self._send_json({"error": "limit must be integer"}, status=400)
                return

            if operation_id or branch_id:
                self._send_json(
                    OPERATION_LEDGER.lineage(
                        operation_id=operation_id or None,
                        branch_id=branch_id or None,
                        limit=limit,
                    )
                )
            else:
                self._send_json(OPERATION_LEDGER.snapshot(limit=limit))
            return

        if path == "/memory/corpus/status":
            self._send_json(corpus_status())
            return

        if path == "/memory/all":
            self._send_json({
                "memory_count": memory_engine.count(),
                "items": memory_engine.get_all()
            })
            return

        if path == "/memory/search":
            q = query.get("q", [""])[0]
            items = retrieval_engine.search(q)
            self._send_json({
                "query": q,
                "matches": len(items),
                "items": items
            })
            return

        if path == "/memory/tag":
            tag = query.get("tag", [""])[0]
            items = retrieval_engine.search_by_tag(tag)
            self._send_json({
                "tag": tag,
                "matches": len(items),
                "items": items
            })
            return

        if path == "/memory/recent":
            raw_limit = query.get("limit", ["5"])[0]
            try:
                limit = int(raw_limit)
            except ValueError:
                self._send_json({"error": "limit must be integer"}, status=400)
                return

            items = temporal_engine.get_recent(limit)
            self._send_json({
                "limit": limit,
                "matches": len(items),
                "items": items
            })
            return

        if path == "/memory/related":
            raw_id = query.get("id", [""])[0]
            try:
                block_id = int(raw_id)
            except ValueError:
                self._send_json({"error": "id must be integer"}, status=400)
                return

            items = graph_engine.get_related(block_id)
            self._send_json({
                "id": block_id,
                "matches": len(items),
                "items": items
            })
            return

        if path == "/semantic-mesh/preview":
            mesh = build_semantic_mesh(memory_engine.get_all()).to_dict()
            self._send_json({
                "status": "ok",
                "service": "AI OS Semantic Mesh Preview",
                "mode": "read_only_advisory",
                "runtime_enforcement": False,
                "storage_schema_mutation": False,
                "public_api_behavior_mutation": "additive_preview_route_only",
                "source": "memory_engine_get_all",
                "mesh": mesh,
            })
            return

        if path == "/snapshot/latest":
            branch_id = query.get("branch_id", [""])[0].strip() or None
            lineage_record = SNAPSHOT_LINEAGE.snapshot(branch_id=branch_id, limit=1)["snapshots"]
            if lineage_record:
                record = lineage_record[0]
                snapshot_path = Path(record["file"])
                if snapshot_path.exists():
                    data = json.loads(snapshot_path.read_text(encoding="utf-8"))
                    self._send_json(
                        {
                            "name": snapshot_path.name,
                            "file": str(snapshot_path),
                            "data": data,
                            "lineage": record,
                        }
                    )
                    return

            snapshot_dir = PATHS.snapshots_dir
            snapshot_dir.mkdir(parents=True, exist_ok=True)

            files = sorted(snapshot_dir.glob("project_snapshot_*.json"), reverse=True)
            if not files:
                self._send_json({"error": "no snapshots found"}, status=404)
                return

            latest = files[0]
            data = json.loads(latest.read_text(encoding="utf-8"))

            self._send_json({
                "name": latest.name,
                "file": str(latest),
                "data": data
            })
            return

        if path == "/snapshots":
            snapshot_dir = PATHS.snapshots_dir
            snapshot_dir.mkdir(parents=True, exist_ok=True)

            items = []
            for p in sorted(snapshot_dir.glob("project_snapshot_*.json"), reverse=True):
                items.append({
                    "name": p.name,
                    "file": str(p),
                    "size": p.stat().st_size
                })

            self._send_json({
                "count": len(items),
                "items": items
            })
            return

        if path == "/snapshots/lineage":
            branch_id = query.get("branch_id", [""])[0].strip() or None
            raw_limit = query.get("limit", ["50"])[0]
            try:
                limit = int(raw_limit)
            except ValueError:
                self._send_json({"error": "limit must be integer"}, status=400)
                return

            self._send_json(SNAPSHOT_LINEAGE.snapshot(branch_id=branch_id, limit=limit))
            return

        if path == "/snapshots/replay":
            raw_limit = query.get("limit", ["50"])[0]
            try:
                limit = int(raw_limit)
            except ValueError:
                self._send_json({"error": "limit must be integer"}, status=400)
                return

            self._send_json(
                SNAPSHOT_LINEAGE.replay_plan(
                    snapshot_id=query.get("snapshot_id", [""])[0].strip() or None,
                    branch_id=query.get("branch_id", [""])[0].strip() or None,
                    operation_id=query.get("operation_id", [""])[0].strip() or None,
                    limit=limit,
                )
            )
            return

        if path == "/agents/status":
            self._send_json(AGENT_RUNTIME.snapshot())
            return

        if path == "/agents/policy":
            raw_limit = query.get("limit", ["10"])[0]
            try:
                limit = int(raw_limit)
            except ValueError:
                self._send_json({"error": "limit must be integer"}, status=400)
                return

            agent_id = query.get("agent_id", [""])[0].strip()
            try:
                if agent_id:
                    self._send_json(AGENT_RUNTIME.recommend_task_for_agent(agent_id=agent_id, limit=limit))
                else:
                    self._send_json(AGENT_RUNTIME.dispatch_preview(limit=limit))
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
            return

        if path == "/agents/tasks":
            items = AGENT_RUNTIME.list_tasks()
            self._send_json({
                "label": "Очередь задач AI OS",
                "matches": len(items),
                "items": items
            })
            return

        self._send_json({
            "error": "not found",
            "available_routes": [
                "GET /",
                "GET /dashboard",
                "GET /health",
                "GET /system/manifest",
                "GET /concept-core/status",
                "GET /semantic-mesh/preview",
                "GET /cognitive/status",
                "GET /planner/status",
                "GET /planner/branch-health",
                "GET /planner/recovery/workflows",
                "GET /planner/recovery/preview",
                "GET /execution/status",
                "GET /execution/ledger",
                "GET /memory/corpus/status",
                "GET /memory/all",
                "GET /memory/search?q=память",
                "GET /memory/tag?tag=memory",
                "GET /memory/recent?limit=3",
                "GET /memory/related?id=4",
                "GET /agents/status",
                "GET /agents/policy",
                "GET /agents/tasks",
                "GET /snapshots",
                "GET /snapshots/lineage",
                "GET /snapshots/replay",
                "GET /snapshot/latest",
                "POST /agents/register",
                "POST /agents/heartbeat",
                "POST /agents/task",
                "POST /agents/claim",
                "POST /agents/dispatch",
                "POST /agents/complete",
                "POST /cognitive/run",
                "POST /cognitive/start",
                "POST /cognitive/stop",
                "POST /planner/run",
                "POST /planner/recovery",
                "POST /planner/recovery/demo",
                "POST /planner/recovery/advance",
                "POST /execution/preview",
                "POST /execution/compensate",
                "POST /memory/pipeline/index",
                "POST /memory/pipeline/parse",
                "POST /memory/pipeline/knowledge",
                "POST /memory/pipeline/vectorize",
                "POST /memory/add",
                "POST /memory/delete",
                "POST /memory/build_graph",
                "POST /snapshot/export"
            ]
        }, status=404)

    def do_POST(self):
        memory_engine = MemoryEngine()
        graph_engine = GraphMemory(memory_engine)

        parsed = urlparse(self.path)
        path = parsed.path

        def _to_bool(value, default: bool = False) -> bool:
            if value is None:
                return default
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in {"1", "true", "yes", "on"}:
                    return True
                if lowered in {"0", "false", "no", "off"}:
                    return False
            return bool(value)

        if path == "/cognitive/run":
            try:
                self._send_json(COGNITIVE_LOOP.run_cycle(trigger="manual"))
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
            return

        if path == "/cognitive/start":
            payload = self._read_json_body() or {}
            interval_seconds = payload.get("interval_seconds")
            self._send_json(COGNITIVE_LOOP.start(interval_seconds=interval_seconds))
            return

        if path == "/cognitive/stop":
            self._send_json(COGNITIVE_LOOP.stop())
            return

        if path == "/planner/run":
            payload = self._read_json_body() or {}
            if not isinstance(payload, dict):
                self._send_json({"error": "invalid json body"}, status=400)
                return

            task_specs = payload.get("steps")
            if isinstance(task_specs, list) and task_specs:
                title = str(payload.get("title", "")).strip() or "Manual planner run"
                created_plan = PLANNER_RUNTIME.create_or_refresh_plan(
                    title=title,
                    source=str(payload.get("source", "manual_api")).strip() or "manual_api",
                    plan_kind=str(payload.get("plan_kind", "manual")).strip() or "manual",
                    focus_area=payload.get("focus_area"),
                    branch_id=payload.get("branch_id"),
                    source_branch_id=payload.get("source_branch_id"),
                    source_operation_id=payload.get("source_operation_id"),
                    max_parallel_steps=payload.get("max_parallel_steps", 1),
                    context=payload.get("context", {}),
                    task_specs=task_specs,
                )
                self._send_json(
                    {
                        "status": "ok",
                        "message": "planner plan created or refreshed",
                        "plan": created_plan,
                        "execution": PLANNER_RUNTIME.execute_ready_steps(plan_id=created_plan["id"]),
                    }
                )
                return

            self._send_json(PLANNER_RUNTIME.run_once(plan_id=payload.get("plan_id")))
            return

        if path == "/planner/recovery":
            payload = self._read_json_body() or {}
            if not isinstance(payload, dict):
                self._send_json({"error": "invalid json body"}, status=400)
                return

            recovery_plan = PLANNER_RUNTIME.create_recovery_plan_from_replay(
                snapshot_id=payload.get("snapshot_id"),
                branch_id=payload.get("branch_id"),
                operation_id=payload.get("operation_id"),
                title=payload.get("title"),
                max_parallel_steps=payload.get("max_parallel_steps", 1),
                max_replay_steps=payload.get("max_replay_steps", 6),
            )
            self._send_json(
                {
                    "status": "ok",
                    "message": "planner recovery plan created or refreshed",
                    "plan": recovery_plan,
                    "advance": PLANNER_RUNTIME.advance_recovery_workflow(
                        plan_id=recovery_plan["id"],
                        auto_dispatch=_to_bool(payload.get("auto_dispatch", True), True),
                        auto_compensate=_to_bool(payload.get("auto_compensate", True), True),
                        compensation_reason=payload.get("compensation_reason"),
                        dispatch_limit=payload.get("dispatch_limit", 3),
                    ),
                }
            )
            return

        if path == "/planner/recovery/demo":
            payload = self._read_json_body() or {}
            if not isinstance(payload, dict):
                self._send_json({"error": "invalid json body"}, status=400)
                return

            try:
                self._send_json(
                    PLANNER_RUNTIME.seed_demo_recovery_state(
                        reset_existing=_to_bool(payload.get("reset_existing", True), True)
                    )
                )
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
            return

        if path == "/planner/recovery/advance":
            payload = self._read_json_body() or {}
            if not isinstance(payload, dict):
                self._send_json({"error": "invalid json body"}, status=400)
                return

            try:
                advance = PLANNER_RUNTIME.advance_recovery_workflow(
                    plan_id=payload.get("plan_id"),
                    branch_id=payload.get("branch_id"),
                    auto_dispatch=_to_bool(payload.get("auto_dispatch", True), True),
                    auto_compensate=_to_bool(payload.get("auto_compensate", True), True),
                    compensation_reason=payload.get("compensation_reason"),
                    dispatch_limit=payload.get("dispatch_limit", 3),
                )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return

            self._send_json(advance)
            return

        if path == "/execution/preview":
            payload = self._read_json_body()
            if not isinstance(payload, dict):
                self._send_json({"error": "invalid json body"}, status=400)
                return

            title = str(payload.get("title", "")).strip()
            if not title:
                self._send_json({"error": "title is required"}, status=400)
                return

            self._send_json(
                EXECUTION_RUNTIME.preview_contract(
                    title=title,
                    preferred_role=payload.get("preferred_role"),
                    metadata=payload.get("metadata", {}),
                    operation_id=payload.get("operation_id"),
                    execution_mode=payload.get("execution_mode"),
                    branch_id=payload.get("branch_id"),
                    parent_branch_id=payload.get("parent_branch_id"),
                    parent_operation_id=payload.get("parent_operation_id"),
                    failure_policy=payload.get("failure_policy"),
                    compensation_plan=payload.get("compensation_plan"),
                    delta=payload.get("delta"),
                )
            )
            return

        if path == "/execution/compensate":
            payload = self._read_json_body()
            if not isinstance(payload, dict):
                self._send_json({"error": "invalid json body"}, status=400)
                return

            raw_task_id = payload.get("task_id")
            task_id = None
            if raw_task_id is not None:
                try:
                    task_id = int(raw_task_id)
                except (TypeError, ValueError):
                    self._send_json({"error": "task_id must be integer"}, status=400)
                    return

            try:
                operation = EXECUTION_RUNTIME.compensate(
                    task_id=task_id,
                    operation_id=payload.get("operation_id"),
                    reason=str(payload.get("reason", "manual compensation")),
                )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return

            self._send_json(
                {
                    "status": "ok",
                    "message": "execution compensated",
                    "operation": operation,
                    "compensation_counts": EXECUTION_RUNTIME.snapshot()["compensation_counts"],
                }
            )
            return

        if path == "/agents/register":
            payload = self._read_json_body()
            if not isinstance(payload, dict):
                self._send_json({"error": "invalid json body"}, status=400)
                return

            try:
                agent = AGENT_RUNTIME.register_agent(
                    name=payload.get("name", ""),
                    role=payload.get("role", ""),
                    capabilities=payload.get("capabilities", []),
                    metadata=payload.get("metadata", {}),
                )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return

            self._send_json({
                "status": "ok",
                "message": "agent registered",
                "agent": agent,
                "agent_counts": AGENT_RUNTIME.snapshot()["agent_counts"],
            }, status=201)
            return

        if path == "/agents/heartbeat":
            payload = self._read_json_body()
            if not isinstance(payload, dict):
                self._send_json({"error": "invalid json body"}, status=400)
                return

            try:
                agent = AGENT_RUNTIME.heartbeat(
                    agent_id=str(payload.get("agent_id", "")).strip(),
                    status=payload.get("status"),
                )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return

            self._send_json({
                "status": "ok",
                "message": "heartbeat recorded",
                "agent": agent
            })
            return

        if path == "/agents/task":
            payload = self._read_json_body()
            if not isinstance(payload, dict):
                self._send_json({"error": "invalid json body"}, status=400)
                return

            try:
                task = AGENT_RUNTIME.queue_task(
                    title=payload.get("title", ""),
                    preferred_role=payload.get("preferred_role"),
                    metadata=payload.get("metadata", {}),
                    operation_id=payload.get("operation_id"),
                    execution_mode=payload.get("execution_mode"),
                    branch_id=payload.get("branch_id"),
                    parent_branch_id=payload.get("parent_branch_id"),
                    parent_operation_id=payload.get("parent_operation_id"),
                    failure_policy=payload.get("failure_policy"),
                    compensation_plan=payload.get("compensation_plan"),
                    delta=payload.get("delta"),
                )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return

            self._send_json({
                "status": "ok",
                "message": "task queued",
                "task": task,
                "task_counts": AGENT_RUNTIME.snapshot()["task_counts"],
            }, status=201)
            return

        if path == "/agents/claim":
            payload = self._read_json_body()
            if not isinstance(payload, dict):
                self._send_json({"error": "invalid json body"}, status=400)
                return

            try:
                task = AGENT_RUNTIME.claim_next_task(
                    agent_id=str(payload.get("agent_id", "")).strip(),
                )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return

            self._send_json({
                "status": "ok",
                "message": "task claimed" if task else "no queued task available",
                "task": task,
                "planner": PLANNER_RUNTIME.status_snapshot(limit=5),
            })
            return

        if path == "/agents/dispatch":
            payload = self._read_json_body() or {}
            try:
                limit = int(payload.get("limit", 10))
            except (TypeError, ValueError):
                self._send_json({"error": "limit must be integer"}, status=400)
                return

            self._send_json(AGENT_RUNTIME.dispatch_ready_tasks(limit=limit))
            return

        if path == "/agents/complete":
            payload = self._read_json_body()
            if not isinstance(payload, dict):
                self._send_json({"error": "invalid json body"}, status=400)
                return

            try:
                task_id = int(payload.get("task_id"))
            except (TypeError, ValueError):
                self._send_json({"error": "task_id must be integer"}, status=400)
                return

            try:
                task = AGENT_RUNTIME.complete_task(
                    agent_id=str(payload.get("agent_id", "")).strip(),
                    task_id=task_id,
                    result=str(payload.get("result", "")),
                    success=bool(payload.get("success", True)),
                )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return

            self._send_json({
                "status": "ok",
                "message": "task completed",
                "task": task,
                "task_counts": AGENT_RUNTIME.snapshot()["task_counts"],
                "planner": PLANNER_RUNTIME.advance_from_task(
                    task,
                    auto_dispatch=_to_bool(payload.get("auto_dispatch", True), True),
                    auto_compensate=_to_bool(payload.get("auto_compensate", True), True),
                    compensation_reason=payload.get("compensation_reason"),
                    dispatch_limit=payload.get("dispatch_limit", 3),
                ),
            })
            return

        if path == "/memory/pipeline/index":
            self._send_json(rebuild_index())
            return

        if path == "/memory/pipeline/parse":
            self._send_json(rebuild_parsed())
            return

        if path == "/memory/pipeline/knowledge":
            self._send_json(rebuild_knowledge())
            return

        if path == "/memory/pipeline/vectorize":
            try:
                self._send_json(rebuild_vectors())
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
            return

        if path == "/memory/add":
            payload = self._read_json_body()
            if not isinstance(payload, dict):
                self._send_json({"error": "invalid json body"}, status=400)
                return

            if payload.get("strict") is True:
                concept_payload = payload.get("concept_core")
                if not isinstance(concept_payload, dict):
                    self._send_json({"error": "concept_core must be an object"}, status=400)
                    return

                try:
                    block = memory_engine.add_concept_node(
                        concept_payload,
                        tags=payload.get("tags") if "tags" in payload else None,
                        importance=payload.get("importance") if "importance" in payload else None,
                    )
                except ValueError as exc:
                    self._send_json({"error": str(exc)}, status=400)
                    return

                self._send_json({
                    "status": "ok",
                    "message": "memory added",
                    "memory_count": memory_engine.count(),
                    "item": block
                }, status=201)
                return

            text = str(payload.get("text", "")).strip()
            if not text:
                self._send_json({"error": "text is required"}, status=400)
                return

            try:
                block = memory_engine.add(text)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return

            self._send_json({
                "status": "ok",
                "message": "memory added",
                "memory_count": memory_engine.count(),
                "item": block
            }, status=201)
            return

        if path == "/memory/delete":
            payload = self._read_json_body()
            if not isinstance(payload, dict):
                self._send_json({"error": "invalid json body"}, status=400)
                return

            raw_id = payload.get("id", None)
            if raw_id is None:
                self._send_json({"error": "id is required"}, status=400)
                return

            try:
                items = memory_engine.delete(raw_id)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return

            graph = graph_engine.save_graph()
            self._send_json({
                "status": "ok",
                "message": "memory deleted",
                "memory_count": len(items),
                "graph_nodes": len(graph)
            })
            return

        if path == "/memory/build_graph":
            graph = graph_engine.save_graph()
            relations_total = sum(len(items) for items in graph.values())

            self._send_json({
                "status": "ok",
                "message": "graph rebuilt",
                "nodes": len(graph),
                "relations_total": relations_total
            })
            return

        if path == "/snapshot/export":
            payload = self._read_json_body() or {}
            retrieval_engine = RetrievalEngine(memory_engine)
            temporal_engine = TemporalMemory(memory_engine)

            snapshot_dir = PATHS.snapshots_dir
            snapshot_dir.mkdir(parents=True, exist_ok=True)

            stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            snapshot_path = snapshot_dir / f"project_snapshot_{stamp}.json"

            runtime = load_runtime()
            all_blocks = memory_engine.get_all()
            recent_blocks = temporal_engine.get_recent(3)
            memory_matches = retrieval_engine.search("память")
            graph = graph_engine.build_graph()

            snapshot = {
                "snapshot_created_at": datetime.now(UTC).isoformat(),
                "memory_count": len(all_blocks),
                "last_updated": runtime.get("last_updated"),
                "recent_blocks": recent_blocks,
                "memory_query_top": memory_matches,
                "graph_nodes": len(graph),
                "graph_relations_total": sum(len(items) for items in graph.values()),
            }

            snapshot_record = SNAPSHOT_LINEAGE.register_snapshot(
                snapshot_path=snapshot_path,
                snapshot_data=snapshot,
                branch_id=payload.get("branch_id"),
                parent_snapshot_id=payload.get("parent_snapshot_id"),
                source_operation_id=payload.get("source_operation_id"),
                source_entry_id=payload.get("source_entry_id"),
                label=payload.get("label"),
            )
            snapshot["snapshot_lineage"] = snapshot_record

            snapshot_path.write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

            self._send_json({
                "status": "ok",
                "message": "snapshot exported",
                "file": str(snapshot_path),
                "snapshot": snapshot_record,
                "memory_count": snapshot["memory_count"],
                "graph_nodes": snapshot["graph_nodes"],
                "graph_relations_total": snapshot["graph_relations_total"]
            })
            return

        self._send_json({"error": "not found"}, status=404)


def main():
    server = QuietHTTPServer((HOST, PORT), GPTMemoryAPIHandler)
    print(f"GPTMemory API running on http://{HOST}:{PORT}")
    print(f"Dashboard: http://{HOST}:{PORT}/dashboard")
    print("Press Ctrl+C to stop")
    server.serve_forever()


if __name__ == "__main__":
    main()
