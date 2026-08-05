"""Temp-state smoke for the read-only Semantic Mesh API preview route."""

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

SERVICE_NAME = "AI OS Semantic Mesh API Preview Smoke"
REQUIRED_DIAGNOSTICS = {
    "total_blocks",
    "strict_concept_blocks",
    "legacy_blocks",
    "malformed_concept_blocks",
    "relation_count",
    "dangling_relation_count",
    "weak_derived_relation_count",
    "unknown_relation_type_count",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=SERVICE_NAME)
    parser.add_argument("--json", action="store_true", help="Print compact JSON summary.")
    parser.add_argument("--cleanup", action="store_true", help="Delete the temp root after the smoke.")
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


class RouteHarness:
    def __init__(self, path: str):
        self.path = path
        self.headers = {"Content-Length": "0"}
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


def bind_handler_methods(api_server, handler: RouteHarness) -> RouteHarness:
    handler._send_json = api_server.GPTMemoryAPIHandler._send_json.__get__(handler, RouteHarness)
    handler._read_json_body = api_server.GPTMemoryAPIHandler._read_json_body.__get__(handler, RouteHarness)
    return handler


def call_get(api_server, path: str) -> tuple[int | None, dict[str, Any]]:
    handler = bind_handler_methods(api_server, RouteHarness(path))
    api_server.GPTMemoryAPIHandler.do_GET(handler)
    raw = handler.wfile.getvalue().decode("utf-8")
    return handler.status_code, json.loads(raw) if raw else {}


def fixture_runtime() -> dict[str, Any]:
    return {
        "last_updated": "2026-05-02T00:00:00+00:00",
        "memory_blocks": [
            {
                "id": 1,
                "text": "Legacy mesh signal note for API preview weak derived coverage.",
                "importance": 4,
                "tags": ["mesh-signal", "legacy"],
                "created_at": "2026-05-02T00:00:00+00:00",
            },
            {
                "id": 2,
                "text": "Strict alpha concept supports beta concept.",
                "importance": 8,
                "tags": ["mesh-signal", "concept-core"],
                "created_at": "2026-05-02T00:01:00+00:00",
                "metadata": {
                    "concept_core": {
                        "id": "concept:alpha",
                        "type": "decision",
                        "title": "Alpha API preview concept",
                        "content": "Strict alpha concept supports beta concept.",
                        "status": "confirmed",
                        "source": "smoke_semantic_mesh_api_preview",
                        "confidence": 0.91,
                        "context": {"stage": "D", "role": "source"},
                        "relations": [{"type": "supports", "target": "concept:beta"}],
                        "created_at": "2026-05-02T00:01:00+00:00",
                        "updated_at": "2026-05-02T00:01:00+00:00",
                    }
                },
            },
            {
                "id": 3,
                "text": "Strict beta concept is the explicit target.",
                "importance": 7,
                "tags": ["concept-target"],
                "created_at": "2026-05-02T00:02:00+00:00",
                "metadata": {
                    "concept_core": {
                        "id": "concept:beta",
                        "type": "fact",
                        "title": "Beta API preview concept",
                        "content": "Strict beta concept is the explicit target.",
                        "status": "confirmed",
                        "source": "smoke_semantic_mesh_api_preview",
                        "confidence": 0.89,
                        "context": {"stage": "D", "role": "target"},
                        "relations": [],
                        "created_at": "2026-05-02T00:02:00+00:00",
                        "updated_at": "2026-05-02T00:02:00+00:00",
                    }
                },
            },
            {
                "id": 4,
                "text": "Dangling strict concept reports missing target.",
                "importance": 6,
                "tags": ["dangling"],
                "created_at": "2026-05-02T00:03:00+00:00",
                "metadata": {
                    "concept_core": {
                        "id": "concept:dangling",
                        "type": "risk",
                        "title": "Dangling API preview concept",
                        "content": "Dangling strict concept reports missing target.",
                        "status": "hypothesis",
                        "source": "smoke_semantic_mesh_api_preview",
                        "confidence": 0.61,
                        "context": {"stage": "D", "role": "dangling"},
                        "relations": [{"type": "depends_on", "target": "concept:missing"}],
                    }
                },
            },
            {
                "id": 5,
                "text": "Unknown relation type stays diagnostic only.",
                "importance": 5,
                "tags": ["unknown-relation"],
                "created_at": "2026-05-02T00:04:00+00:00",
                "metadata": {
                    "concept_core": {
                        "id": "concept:unknown",
                        "type": "note",
                        "title": "Unknown relation API preview concept",
                        "content": "Unknown relation type stays diagnostic only.",
                        "status": "unknown",
                        "source": "smoke_semantic_mesh_api_preview",
                        "confidence": 0.52,
                        "context": {"stage": "D", "role": "unknown_relation"},
                        "relations": [{"type": "blocks", "target": "concept:beta"}],
                    }
                },
            },
            {
                "id": 6,
                "text": "Malformed strict concept is reported, not repaired.",
                "importance": 3,
                "tags": ["malformed"],
                "created_at": "2026-05-02T00:05:00+00:00",
                "metadata": {"concept_core": {"id": "concept:broken", "confidence": 2, "relations": "bad"}},
            },
        ],
    }


def write_fixture_runtime(temp_runtime_file: Path) -> None:
    temp_runtime_file.write_text(
        json.dumps(fixture_runtime(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def relation_has_diagnostic(relations: list[dict[str, Any]], diagnostic: str) -> bool:
    for relation in relations:
        diagnostics = list((relation.get("metadata") or {}).get("diagnostics") or [])
        if diagnostic in diagnostics:
            return True
    return False


def run_smoke(temp_root: Path) -> dict[str, Any]:
    from ai_os.config import get_project_paths
    import scripts.runtime_store as runtime_store

    temp_root.mkdir(parents=True, exist_ok=True)
    temp_runtime_file = temp_root / "GPTMemory_runtime.json"
    write_fixture_runtime(temp_runtime_file)

    project_runtime_file = get_project_paths().runtime_file
    project_runtime_before = file_metadata(project_runtime_file)
    temp_runtime_before = temp_runtime_file.read_text(encoding="utf-8")
    previous_runtime_file = runtime_store.RUNTIME_FILE

    checks: dict[str, bool] = {}
    details: dict[str, Any] = {
        "temp_runtime_file": str(temp_runtime_file),
        "project_runtime_file": str(project_runtime_file),
        "responses": {},
    }

    try:
        runtime_store.RUNTIME_FILE = temp_runtime_file

        import scripts.api_server as api_server

        preview_status, preview_body = call_get(api_server, "/semantic-mesh/preview")
        details["responses"]["semantic_mesh_preview"] = {
            "status": preview_status,
            "body": preview_body,
        }

        mesh = dict(preview_body.get("mesh") or {})
        diagnostics = dict(mesh.get("diagnostics") or {})
        nodes = [dict(node) for node in list(mesh.get("nodes") or []) if isinstance(node, dict)]
        relations = [
            dict(relation) for relation in list(mesh.get("relations") or []) if isinstance(relation, dict)
        ]
        malformed_blocks = [
            dict(item) for item in list(mesh.get("malformed_blocks") or []) if isinstance(item, dict)
        ]
        weak_relations = [
            relation for relation in relations if relation.get("relation_source") == "weak_derived"
        ]

        checks["semantic_mesh_preview_http_200"] = preview_status == 200
        checks["response_status_ok"] = preview_body.get("status") == "ok"
        checks["response_service_semantic_mesh_preview"] = (
            preview_body.get("service") == "AI OS Semantic Mesh Preview"
        )
        checks["response_mode_read_only_advisory"] = preview_body.get("mode") == "read_only_advisory"
        checks["runtime_enforcement_false"] = preview_body.get("runtime_enforcement") is False
        checks["storage_schema_mutation_false"] = preview_body.get("storage_schema_mutation") is False
        checks["source_memory_engine_get_all"] = preview_body.get("source") == "memory_engine_get_all"
        checks["mesh_shape_present"] = {"nodes", "relations", "diagnostics", "malformed_blocks"}.issubset(mesh)
        checks["required_diagnostics_present"] = REQUIRED_DIAGNOSTICS.issubset(diagnostics)
        checks["strict_concept_block_appears_as_node"] = any(
            node.get("concept_id") == "concept:alpha" for node in nodes
        )
        checks["legacy_block_counted_not_forced_into_strict_node"] = diagnostics.get("legacy_blocks") == 1 and any(
            node.get("concept_id") is None and node.get("concept_type") == "legacy_memory" for node in nodes
        )
        checks["malformed_concept_reported_not_fatal"] = (
            diagnostics.get("malformed_concept_blocks") == 1 and bool(malformed_blocks)
        )
        checks["dangling_relation_reported_not_fatal"] = (
            diagnostics.get("dangling_relation_count") == 1
            and relation_has_diagnostic(relations, "dangling_relation_target")
        )
        checks["unknown_relation_type_reported_not_fatal"] = (
            diagnostics.get("unknown_relation_type_count") == 1
            and relation_has_diagnostic(relations, "unknown_relation_type")
        )
        checks["weak_derived_relation_labeled"] = (
            diagnostics.get("weak_derived_relation_count", 0) >= 1
            and bool(weak_relations)
            and all((relation.get("metadata") or {}).get("weak_signal") for relation in weak_relations)
        )
        checks["temp_runtime_file_unchanged"] = temp_runtime_file.read_text(encoding="utf-8") == temp_runtime_before
    finally:
        runtime_store.RUNTIME_FILE = previous_runtime_file

    project_runtime_after = file_metadata(project_runtime_file)
    checks["project_runtime_file_unchanged"] = project_runtime_before == project_runtime_after
    details["project_runtime_before"] = project_runtime_before
    details["project_runtime_after"] = project_runtime_after

    return {
        "status": "ok" if all(checks.values()) else "failed",
        "service": SERVICE_NAME,
        "checks": checks,
        "details": details,
    }


def cleanup_temp_root(temp_root: Path) -> tuple[bool, str | None]:
    if not temp_root.exists():
        return True, None
    try:
        shutil.rmtree(temp_root, ignore_errors=False)
    except OSError as exc:
        return (not temp_root.exists(), str(exc))
    return (not temp_root.exists(), None)


def print_result(result: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
        return
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


def main() -> int:
    args = parse_args()
    temp_root = Path(tempfile.gettempdir()) / f"gptmeai_semantic_mesh_api_preview_{uuid.uuid4().hex}"
    result: dict[str, Any] = {
        "status": "error",
        "service": SERVICE_NAME,
        "temp_root": str(temp_root),
    }

    try:
        result = run_smoke(temp_root)
        exit_code = 0 if result["status"] == "ok" else 1
    except Exception as exc:
        result = {
            "status": "error",
            "service": SERVICE_NAME,
            "temp_root": str(temp_root),
            "error": str(exc),
        }
        exit_code = 1
    finally:
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
