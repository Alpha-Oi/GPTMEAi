"""Temp-state smoke for optional strict Concept Core /memory/add route mode."""

from __future__ import annotations

import argparse
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test /memory/add Concept Core strict route mode.")
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


def outer_shape_preserved(body: dict) -> bool:
    return set(body) == {"status", "message", "memory_count", "item"}


def legacy_shape_compatible(block: dict) -> bool:
    required = {"id", "text", "importance", "tags", "created_at"}
    return required.issubset(set(block)) and isinstance(block.get("tags"), list)


class RouteHarness:
    def __init__(self, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.path = "/memory/add"
        self.headers = {"Content-Length": str(len(body))}
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()
        self.status_code: int | None = None
        self.response_headers: list[tuple[str, str]] = []

    def send_response(self, status: int) -> None:
        self.status_code = status

    def send_header(self, key: str, value: str) -> None:
        self.response_headers.append((key, value))

    def end_headers(self) -> None:
        return None


def call_memory_add(api_server, payload: dict) -> tuple[int | None, dict]:
    handler = RouteHarness(payload)
    handler._send_json = api_server.GPTMemoryAPIHandler._send_json.__get__(handler, RouteHarness)
    handler._read_json_body = api_server.GPTMemoryAPIHandler._read_json_body.__get__(handler, RouteHarness)
    api_server.GPTMemoryAPIHandler.do_POST(handler)
    raw_body = handler.wfile.getvalue().decode("utf-8")
    return handler.status_code, json.loads(raw_body)


def valid_concept_payload() -> dict:
    return {
        "id": "memory:route-concept-core-valid",
        "type": "decision",
        "title": "Route Concept Core memory",
        "content": "Route Concept Core memory content.",
        "status": "confirmed",
        "source": "smoke_memory_add_concept_route",
        "confidence": 0.92,
        "context": {"route": "/memory/add", "mode": "strict"},
        "relations": [{"type": "supports", "target": "route:/memory/add"}],
    }


def run_smoke(temp_root: Path) -> dict:
    from ai_os.config import get_project_paths
    from core.memory_engine import MemoryEngine
    import scripts.api_server as api_server
    import scripts.runtime_store as runtime_store

    temp_root.mkdir(parents=True, exist_ok=True)
    temp_runtime_file = temp_root / "GPTMemory_runtime.json"
    project_runtime_file = get_project_paths().runtime_file
    project_runtime_before = file_metadata(project_runtime_file)
    previous_runtime_file = runtime_store.RUNTIME_FILE

    checks: dict[str, bool] = {}
    details: dict[str, object] = {
        "temp_runtime_file": str(temp_runtime_file),
        "project_runtime_file": str(project_runtime_file),
        "responses": {},
    }

    try:
        runtime_store.RUNTIME_FILE = temp_runtime_file

        legacy_status, legacy_body = call_memory_add(api_server, {"text": "plain route memory"})
        details["responses"]["legacy"] = {"status": legacy_status, "body": legacy_body}
        legacy_item = dict(legacy_body.get("item") or {})
        checks["legacy_text_only_request_succeeds"] = legacy_status == 201 and legacy_body.get("status") == "ok"
        checks["legacy_success_status_code_preserved"] = legacy_status == 201
        checks["legacy_outer_response_shape_preserved"] = outer_shape_preserved(legacy_body)
        checks["legacy_item_shape_compatible"] = legacy_shape_compatible(legacy_item)
        checks["legacy_item_has_no_concept_core_metadata_by_default"] = not bool(
            (legacy_item.get("metadata") or {}).get("concept_core")
        )

        concept_payload = valid_concept_payload()
        strict_status, strict_body = call_memory_add(
            api_server,
            {
                "strict": True,
                "concept_core": concept_payload,
                "tags": ["concept-core", "route"],
                "importance": 8,
            },
        )
        details["responses"]["strict_valid"] = {"status": strict_status, "body": strict_body}
        strict_item = dict(strict_body.get("item") or {})
        strict_metadata = dict((strict_item.get("metadata") or {}).get("concept_core") or {})
        checks["strict_valid_concept_core_request_succeeds"] = strict_status == 201 and strict_body.get("status") == "ok"
        checks["strict_outer_response_shape_preserved"] = outer_shape_preserved(strict_body)
        checks["strict_item_text_equals_memory_node_content"] = strict_item.get("text") == concept_payload["content"]
        checks["strict_item_shape_compatible"] = legacy_shape_compatible(strict_item)
        checks["strict_item_includes_concept_core_metadata"] = bool(strict_metadata)
        checks["strict_metadata_preserves_source"] = strict_metadata.get("source") == "smoke_memory_add_concept_route"
        checks["strict_metadata_preserves_context"] = strict_metadata.get("context") == concept_payload["context"]

        invalid_cases = {
            "missing_source": ("strict_invalid_missing_source_returns_400", dict(concept_payload)),
            "missing_context": ("strict_invalid_missing_context_returns_400", dict(concept_payload)),
            "invalid_confidence": ("strict_invalid_confidence_returns_400", dict(concept_payload)),
        }
        invalid_cases["missing_source"][1].pop("source")
        invalid_cases["missing_context"][1].pop("context")
        invalid_cases["invalid_confidence"][1]["confidence"] = 1.5

        before_invalid_count = MemoryEngine().count()
        for name, (check_name, payload) in invalid_cases.items():
            status, body = call_memory_add(api_server, {"strict": True, "concept_core": payload})
            details["responses"][name] = {"status": status, "body": body}
            checks[check_name] = status == 400 and isinstance(body.get("error"), str) and bool(body.get("error"))

        after_invalid_count = MemoryEngine().count()
        checks["invalid_strict_requests_do_not_write_memory_blocks"] = (
            before_invalid_count == 2 and after_invalid_count == before_invalid_count
        )
        checks["temp_runtime_file_used"] = temp_runtime_file.exists()
    finally:
        runtime_store.RUNTIME_FILE = previous_runtime_file

    project_runtime_after = file_metadata(project_runtime_file)
    checks["project_runtime_file_unchanged_before_after"] = project_runtime_before == project_runtime_after
    details["project_runtime_before"] = project_runtime_before
    details["project_runtime_after"] = project_runtime_after

    return {
        "status": "ok" if all(checks.values()) else "failed",
        "service": "AI OS /memory/add Concept Core Route Smoke",
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
    temp_root = Path(tempfile.gettempdir()) / f"gptmeai_memory_add_concept_route_{uuid.uuid4().hex}"
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
