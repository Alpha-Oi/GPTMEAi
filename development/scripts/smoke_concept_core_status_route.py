"""Handler-level smoke for read-only /concept-core/status route."""

from __future__ import annotations

import argparse
import io
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

EXPECTED_CAPABILITIES = {
    "typed_primitives": True,
    "strict_memory_add": True,
    "memory_metadata_visibility": True,
    "direct_cognitive_plan_advisory": True,
    "public_decision_preview": False,
    "global_enforcement": False,
}

EXPECTED_VISIBILITY = {
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
}

EXPECTED_SAFETY_CONTRACT = {
    "label": "advisory_non_enforcing",
    "internal_plan_payload_exposed": False,
    "red_button_detection": "text_heuristic_mvp_not_authoritative_policy",
}

EXPECTED_OUTER_KEYS = {
    "status",
    "service",
    "mode",
    "runtime_enforcement",
    "storage_schema_mutation",
    "public_api_behavior_mutation",
    "capabilities",
    "visibility",
    "safety_contract",
}

FORBIDDEN_INTERNAL_KEYS = {
    "concept_core_advisory",
    "tasks",
    "plan_groups",
    "recovery_requests",
    "evidence",
    "decision",
    "decisions",
    "decision_payload",
    "task_titles",
    "planned_task_titles",
    "memory_content",
    "metadata_concept_core",
    "red_button_terms",
}

PROJECT_STATE_PATHS = [
    PROJECT_ROOT / "GPTMemory_runtime.yaml",
    PROJECT_ROOT / "storage" / "cognitive_loop_state.json",
    PROJECT_ROOT / "storage" / "agent_runtime.json",
    PROJECT_ROOT / "storage" / "planner_runtime.json",
    PROJECT_ROOT / "storage" / "execution_runtime.json",
    PROJECT_ROOT / "storage" / "operation_ledger.json",
    PROJECT_ROOT / "storage" / "snapshot_lineage.json",
    PROJECT_ROOT / "memory" / "db.json",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test /concept-core/status handler route.")
    parser.add_argument("--json", action="store_true", help="Print compact JSON output.")
    parser.add_argument("--cleanup", action="store_true", help="Remove temp pycache root after the smoke.")
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


def project_state_metadata() -> dict[str, dict[str, object]]:
    return {str(path): file_metadata(path) for path in PROJECT_STATE_PATHS}


def collect_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        keys = set(value)
        for item in value.values():
            keys.update(collect_keys(item))
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for item in value:
            keys.update(collect_keys(item))
        return keys
    return set()


class RouteHarness:
    def __init__(self, path: str):
        self.path = path
        self.headers: dict[str, str] = {}
        self.rfile = io.BytesIO()
        self.wfile = io.BytesIO()
        self.status_code: int | None = None
        self.response_headers: list[tuple[str, str]] = []

    def send_response(self, status: int) -> None:
        self.status_code = status

    def send_header(self, key: str, value: str) -> None:
        self.response_headers.append((key, value))

    def end_headers(self) -> None:
        return None


class ForbiddenRuntime:
    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"Concept Core status route must not access runtime attribute: {name}")


class ForbiddenMemoryEngine:
    def __init__(self, *args: object, **kwargs: object) -> None:
        raise AssertionError("Concept Core status route must not construct MemoryEngine")


def call_get(api_server: object, path: str) -> tuple[int | None, dict[str, Any]]:
    handler = RouteHarness(path)
    handler._send_json = api_server.GPTMemoryAPIHandler._send_json.__get__(handler, RouteHarness)
    api_server.GPTMemoryAPIHandler.do_GET(handler)
    raw_body = handler.wfile.getvalue().decode("utf-8")
    if not raw_body:
        return handler.status_code, {}
    return handler.status_code, json.loads(raw_body)


def call_concept_status_with_forbidden_dependencies(api_server: object) -> tuple[int | None, dict[str, Any], str | None]:
    saved = {
        "COGNITIVE_LOOP": api_server.COGNITIVE_LOOP,
        "PLANNER_RUNTIME": api_server.PLANNER_RUNTIME,
        "EXECUTION_RUNTIME": api_server.EXECUTION_RUNTIME,
        "AGENT_RUNTIME": api_server.AGENT_RUNTIME,
        "OPERATION_LEDGER": api_server.OPERATION_LEDGER,
        "SNAPSHOT_LINEAGE": api_server.SNAPSHOT_LINEAGE,
        "MemoryEngine": api_server.MemoryEngine,
        "RetrievalEngine": api_server.RetrievalEngine,
        "TemporalMemory": api_server.TemporalMemory,
        "GraphMemory": api_server.GraphMemory,
    }
    try:
        forbidden = ForbiddenRuntime()
        api_server.COGNITIVE_LOOP = forbidden
        api_server.PLANNER_RUNTIME = forbidden
        api_server.EXECUTION_RUNTIME = forbidden
        api_server.AGENT_RUNTIME = forbidden
        api_server.OPERATION_LEDGER = forbidden
        api_server.SNAPSHOT_LINEAGE = forbidden
        api_server.MemoryEngine = ForbiddenMemoryEngine
        api_server.RetrievalEngine = forbidden
        api_server.TemporalMemory = forbidden
        api_server.GraphMemory = forbidden
        return (*call_get(api_server, "/concept-core/status"), None)
    except Exception as exc:  # noqa: BLE001 - smoke reports the exact route failure.
        return None, {}, f"{type(exc).__name__}: {exc}"
    finally:
        for name, value in saved.items():
            setattr(api_server, name, value)


def run_smoke(temp_root: Path) -> dict[str, object]:
    sys.pycache_prefix = str(temp_root / "pycache")
    project_state_before = project_state_metadata()

    import scripts.api_server as api_server

    checks: dict[str, bool] = {}
    details: dict[str, object] = {
        "route_response": {},
        "route_exception": None,
        "existing_route_response": {},
        "not_found_response": {},
        "temp_root": str(temp_root),
        "pycache_prefix": sys.pycache_prefix,
    }

    status_code, body, route_exception = call_concept_status_with_forbidden_dependencies(api_server)
    details["route_response"] = {"status": status_code, "body": body}
    details["route_exception"] = route_exception

    checks["concept_core_status_returns_200"] = status_code == 200
    checks["status_is_ok"] = body.get("status") == "ok"
    checks["service_is_concept_core"] = body.get("service") == "AI OS Concept Core"
    checks["mode_is_advisory_only"] = body.get("mode") == "advisory_only"
    checks["runtime_enforcement_false"] = body.get("runtime_enforcement") is False
    checks["storage_schema_mutation_false"] = body.get("storage_schema_mutation") is False
    checks["public_api_behavior_mutation_false"] = body.get("public_api_behavior_mutation") is False
    checks["capabilities_match_expected"] = body.get("capabilities") == EXPECTED_CAPABILITIES
    checks["visibility_matches_expected"] = body.get("visibility") == EXPECTED_VISIBILITY
    checks["safety_contract_label_matches"] = (
        (body.get("safety_contract") or {}).get("label") == "advisory_non_enforcing"
    )
    checks["internal_plan_payload_exposed_false"] = (
        (body.get("safety_contract") or {}).get("internal_plan_payload_exposed") is False
    )
    checks["red_button_detection_is_heuristic_not_authoritative"] = (
        (body.get("safety_contract") or {}).get("red_button_detection")
        == "text_heuristic_mvp_not_authoritative_policy"
    )
    checks["safety_contract_matches_expected"] = body.get("safety_contract") == EXPECTED_SAFETY_CONTRACT
    checks["outer_response_keys_match_expected"] = set(body) == EXPECTED_OUTER_KEYS
    checks["no_internal_plan_fields_exposed"] = not bool(collect_keys(body) & FORBIDDEN_INTERNAL_KEYS)
    checks["route_does_not_call_forbidden_runtime_or_memory_dependencies"] = route_exception is None

    manifest_status, manifest_body = call_get(api_server, "/system/manifest")
    details["existing_route_response"] = {"status": manifest_status, "body": manifest_body}
    checks["existing_system_manifest_route_still_returns_manifest"] = (
        manifest_status == 200
        and {
            "official_runtime",
            "official_packages",
            "developer_docs",
            "development_workspace",
            "data_paths",
            "legacy_paths",
            "archive_paths",
        }.issubset(set(manifest_body))
    )
    checks["existing_system_manifest_has_no_concept_core_status_payload"] = not bool(
        set(manifest_body) & EXPECTED_OUTER_KEYS
    )

    not_found_status, not_found_body = call_get(api_server, "/__missing_concept_core_status_smoke__")
    details["not_found_response"] = {"status": not_found_status, "body": not_found_body}
    existing_route_entries = {
        "GET /health",
        "GET /system/manifest",
        "GET /cognitive/status",
        "GET /planner/status",
        "GET /planner/recovery/preview",
        "GET /memory/all",
        "GET /memory/search?q=память",
        "GET /memory/tag?tag=memory",
        "GET /memory/recent?limit=3",
        "GET /memory/related?id=4",
        "POST /cognitive/run",
        "POST /memory/add",
    }
    available_routes = set(not_found_body.get("available_routes") or [])
    checks["not_found_route_shape_still_available_routes"] = (
        not_found_status == 404
        and not_found_body.get("error") == "not found"
        and isinstance(not_found_body.get("available_routes"), list)
    )
    checks["existing_available_route_entries_preserved"] = existing_route_entries.issubset(available_routes)

    project_state_after = project_state_metadata()
    checks["project_runtime_storage_state_untouched"] = project_state_before == project_state_after
    details["project_state_before"] = project_state_before
    details["project_state_after"] = project_state_after

    return {
        "status": "ok" if all(checks.values()) else "failed",
        "service": "AI OS Concept Core Status Route Smoke",
        "checks": checks,
        "details": details,
    }


def print_result(result: dict[str, object], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


def main() -> int:
    args = parse_args()
    temp_root = Path(tempfile.gettempdir()) / f"gptmeai_concept_core_status_route_{uuid.uuid4().hex}"
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

    result["cleanup_requested"] = bool(args.cleanup)
    result["cleanup_succeeded"] = cleanup_succeeded if args.cleanup else None
    result["cleanup_error"] = cleanup_error
    result["temp_root_exists_after_cleanup"] = temp_root.exists()
    print_result(result, as_json=args.json)
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
