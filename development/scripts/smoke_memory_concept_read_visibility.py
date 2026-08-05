"""Temp-state smoke for Concept Core metadata visibility in memory read routes."""

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
    parser = argparse.ArgumentParser(description="Smoke-test Concept Core memory read-path visibility.")
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


class RouteHarness:
    def __init__(self, path: str, payload: dict | None = None):
        self.path = path
        body = b""
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
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


def _bind_handler_methods(api_server, handler: RouteHarness) -> RouteHarness:
    handler._send_json = api_server.GPTMemoryAPIHandler._send_json.__get__(handler, RouteHarness)
    handler._read_json_body = api_server.GPTMemoryAPIHandler._read_json_body.__get__(handler, RouteHarness)
    return handler


def call_post(api_server, path: str, payload: dict) -> tuple[int | None, dict]:
    handler = _bind_handler_methods(api_server, RouteHarness(path, payload))
    api_server.GPTMemoryAPIHandler.do_POST(handler)
    return handler.status_code, json.loads(handler.wfile.getvalue().decode("utf-8"))


def call_get(api_server, path: str) -> tuple[int | None, dict]:
    handler = _bind_handler_methods(api_server, RouteHarness(path))
    api_server.GPTMemoryAPIHandler.do_GET(handler)
    return handler.status_code, json.loads(handler.wfile.getvalue().decode("utf-8"))


def valid_concept_payload() -> dict:
    return {
        "id": "memory:read-visibility-concept-core",
        "type": "decision",
        "title": "Read visibility Concept Core memory",
        "content": "Strict visibility concept memory content.",
        "status": "confirmed",
        "source": "smoke_memory_concept_read_visibility",
        "confidence": 0.93,
        "context": {"route": "/memory/add", "visibility": "read_paths"},
        "relations": [{"type": "supports", "target": "route:/memory/all"}],
    }


def has_concept_core(block: dict) -> bool:
    return bool((block.get("metadata") or {}).get("concept_core"))


def concept_core_payload(block: dict) -> dict:
    return dict((block.get("metadata") or {}).get("concept_core") or {})


def find_block(items: list[dict], block_id: int) -> dict:
    for item in items:
        if int(item.get("id", 0)) == int(block_id):
            return dict(item)
    return {}


def response_items(body: dict) -> list[dict]:
    return [dict(item) for item in list(body.get("items") or []) if isinstance(item, dict)]


def graph_summary_shaped(items: list[dict]) -> bool:
    if not items:
        return False
    required = {"id", "shared_tags", "shared_words", "relation_score", "importance", "text"}
    for item in items:
        if not required.issubset(set(item)):
            return False
        if "metadata" in item or "concept_core" in item:
            return False
    return True


def run_smoke(temp_root: Path) -> dict:
    from ai_os.config import get_project_paths
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

        import scripts.api_server as api_server

        legacy_status, legacy_body = call_post(
            api_server,
            "/memory/add",
            {"text": "Legacy visibility bridge memory content."},
        )
        strict_payload = valid_concept_payload()
        strict_status, strict_body = call_post(
            api_server,
            "/memory/add",
            {
                "strict": True,
                "concept_core": strict_payload,
                "tags": ["concept-core", "visibility"],
                "importance": 8,
            },
        )
        details["responses"]["legacy_add"] = {"status": legacy_status, "body": legacy_body}
        details["responses"]["strict_add"] = {"status": strict_status, "body": strict_body}

        legacy_item = dict(legacy_body.get("item") or {})
        strict_item = dict(strict_body.get("item") or {})
        legacy_id = int(legacy_item.get("id", 0))
        strict_id = int(strict_item.get("id", 0))

        checks["legacy_memory_add_text_only_write_succeeds"] = legacy_status == 201 and legacy_body.get("status") == "ok"
        checks["strict_memory_add_valid_concept_core_write_succeeds"] = (
            strict_status == 201 and strict_body.get("status") == "ok" and has_concept_core(strict_item)
        )

        all_status, all_body = call_get(api_server, "/memory/all")
        all_items = response_items(all_body)
        all_legacy = find_block(all_items, legacy_id)
        all_strict = find_block(all_items, strict_id)
        details["responses"]["memory_all"] = {"status": all_status, "body": all_body}
        checks["memory_all_returns_legacy_block_without_concept_core_metadata"] = (
            all_status == 200 and bool(all_legacy) and not has_concept_core(all_legacy)
        )
        checks["memory_all_returns_strict_block_with_concept_core_metadata"] = (
            all_status == 200
            and bool(all_strict)
            and concept_core_payload(all_strict).get("source") == "smoke_memory_concept_read_visibility"
        )

        search_status, search_body = call_get(api_server, "/memory/search?q=Strict%20visibility")
        search_items = response_items(search_body)
        search_strict = find_block(search_items, strict_id)
        details["responses"]["memory_search"] = {"status": search_status, "body": search_body}
        checks["memory_search_returns_strict_block_with_concept_core_metadata"] = (
            search_status == 200 and bool(search_strict) and has_concept_core(search_strict)
        )

        tag_status, tag_body = call_get(api_server, "/memory/tag?tag=concept-core")
        tag_items = response_items(tag_body)
        tag_strict = find_block(tag_items, strict_id)
        details["responses"]["memory_tag"] = {"status": tag_status, "body": tag_body}
        checks["memory_tag_returns_strict_block_with_concept_core_metadata"] = (
            tag_status == 200 and bool(tag_strict) and has_concept_core(tag_strict)
        )

        recent_status, recent_body = call_get(api_server, "/memory/recent?limit=5")
        recent_items = response_items(recent_body)
        recent_strict = find_block(recent_items, strict_id)
        details["responses"]["memory_recent"] = {"status": recent_status, "body": recent_body}
        checks["memory_recent_returns_strict_block_with_concept_core_metadata"] = (
            recent_status == 200 and bool(recent_strict) and has_concept_core(recent_strict)
        )

        related_status, related_body = call_get(api_server, f"/memory/related?id={legacy_id}")
        related_items = response_items(related_body)
        details["responses"]["memory_related"] = {"status": related_status, "body": related_body}
        checks["memory_related_remains_graph_summary_shaped"] = (
            related_status == 200 and graph_summary_shaped(related_items)
        )
        checks["memory_related_does_not_expose_full_concept_core_record"] = (
            related_status == 200 and all(not has_concept_core(item) for item in related_items)
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
        "service": "AI OS Concept Core Memory Read Visibility Smoke",
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
    temp_root = Path(tempfile.gettempdir()) / f"gptmeai_memory_concept_read_visibility_{uuid.uuid4().hex}"
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
