"""Temp-state smoke for exact opt-in Semantic Relation API writer wiring."""

from __future__ import annotations

import argparse
import copy
import io
import json
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SERVICE_NAME = "AI OS Semantic Relation API Writer Smoke"
CONTRACT_VERSION = "semantic_relation.v1"
OUTER_RESPONSE_FIELDS = {"status", "message", "memory_count", "item"}


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
    def __init__(self, payload: dict[str, Any]):
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


def call_memory_add(api_server: object, payload: dict[str, Any]) -> tuple[int | None, dict[str, Any]]:
    handler = RouteHarness(payload)
    handler._send_json = api_server.GPTMemoryAPIHandler._send_json.__get__(handler, RouteHarness)
    handler._read_json_body = api_server.GPTMemoryAPIHandler._read_json_body.__get__(handler, RouteHarness)
    api_server.GPTMemoryAPIHandler.do_POST(handler)
    raw_body = handler.wfile.getvalue().decode("utf-8")
    return handler.status_code, json.loads(raw_body)


def concept_payload(**overrides: object) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": "concept:api-writer-source",
        "type": "decision",
        "title": "Semantic Relation API writer source",
        "content": "Validate authored API relations before the memory write.",
        "status": "confirmed",
        "source": "smoke_semantic_relation_api_writer",
        "confidence": 0.94,
        "context": {"stage": "F2B", "mode": "explicit-api-opt-in"},
        "relations": [
            {
                "contract_version": CONTRACT_VERSION,
                "type": "supports",
                "target": "concept:api-writer-dangling-target",
                "evidence_ref": "memory:api-writer-evidence",
            }
        ],
    }
    payload.update(overrides)
    return payload


def strict_request(payload: dict[str, Any], *, include_version: bool = True) -> dict[str, Any]:
    request: dict[str, Any] = {
        "strict": True,
        "concept_core": payload,
        "tags": ["semantic-relation", "api"],
        "importance": 8,
    }
    if include_version:
        request["relation_contract_version"] = CONTRACT_VERSION
    return request


def concept_core_from_response(body: dict[str, Any]) -> dict[str, Any]:
    item = body.get("item") or {}
    metadata = item.get("metadata") or {}
    return dict(metadata.get("concept_core") or {})


def run_smoke(temp_root: Path) -> dict[str, Any]:
    from core.memory_engine import MemoryEngine
    import scripts.api_server as api_server
    import scripts.runtime_store as runtime_store

    temp_root.mkdir(parents=True, exist_ok=True)
    temp_runtime_file = temp_root / "GPTMemory_runtime.json"
    project_runtime_file = PROJECT_ROOT / "GPTMemory_runtime.yaml"
    project_runtime_before = file_metadata(project_runtime_file)
    previous_runtime_file = runtime_store.RUNTIME_FILE
    original_add_concept_node = MemoryEngine.add_concept_node
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {
        "temp_runtime_file": str(temp_runtime_file),
        "project_runtime_file": str(project_runtime_file),
        "responses": {},
        "writer_calls": [],
    }

    def recording_add_concept_node(
        engine: MemoryEngine,
        payload: dict[str, Any],
        **kwargs: object,
    ) -> dict[str, Any]:
        details["writer_calls"].append(
            {
                "concept_id": payload.get("id"),
                "keyword_names": sorted(kwargs),
                "relation_contract_version": kwargs.get("relation_contract_version", "<absent>"),
            }
        )
        return original_add_concept_node(engine, payload, **kwargs)

    def record_response(name: str, status: int | None, body: dict[str, Any]) -> None:
        details["responses"][name] = {
            "status": status,
            "error": body.get("error"),
            "outer_fields": sorted(body),
        }

    def run_rejection(
        name: str,
        request: dict[str, Any],
        expected_error: str,
        *,
        expect_writer_call: bool,
    ) -> None:
        before_count = MemoryEngine().count()
        before_calls = len(details["writer_calls"])
        status, body = call_memory_add(api_server, request)
        record_response(name, status, body)
        after_count = MemoryEngine().count()
        after_calls = len(details["writer_calls"])
        checks[f"{name}_returns_expected_400"] = status == 400 and body == {"error": expected_error}
        checks[f"{name}_does_not_write"] = after_count == before_count
        expected_calls = before_calls + (1 if expect_writer_call else 0)
        checks[f"{name}_writer_call_boundary"] = after_calls == expected_calls

    try:
        runtime_store.RUNTIME_FILE = temp_runtime_file
        with patch.object(MemoryEngine, "add_concept_node", new=recording_add_concept_node):
            legacy_status, legacy_body = call_memory_add(api_server, {"text": "plain API memory"})
            record_response("legacy", legacy_status, legacy_body)
            checks["legacy_request_succeeds"] = legacy_status == 201 and set(legacy_body) == OUTER_RESPONSE_FIELDS
            checks["legacy_request_does_not_call_strict_writer"] = len(details["writer_calls"]) == 0

            permissive = concept_payload(
                id="concept:api-permissive",
                relations=[{"type": "supports", "target": "concept:legacy-target"}],
            )
            permissive_status, permissive_body = call_memory_add(
                api_server,
                strict_request(permissive, include_version=False),
            )
            record_response("permissive", permissive_status, permissive_body)
            permissive_call = details["writer_calls"][-1] if details["writer_calls"] else {}
            permissive_relations = concept_core_from_response(permissive_body).get("relations")
            checks["strict_without_opt_in_remains_permissive"] = (
                permissive_status == 201 and permissive_relations == permissive["relations"]
            )
            checks["strict_without_opt_in_omits_version_keyword"] = (
                "relation_contract_version" not in permissive_call.get("keyword_names", [])
            )

            authored_without_opt_in = concept_payload(id="concept:api-authored-without-opt-in")
            authored_status, authored_body = call_memory_add(
                api_server,
                strict_request(authored_without_opt_in, include_version=False),
            )
            record_response("authored_without_opt_in", authored_status, authored_body)
            authored_call = details["writer_calls"][-1] if details["writer_calls"] else {}
            checks["authored_relation_does_not_auto_activate_contract"] = (
                authored_status == 201
                and "relation_contract_version" not in authored_call.get("keyword_names", [])
            )

            valid_payload = concept_payload()
            valid_payload_before = copy.deepcopy(valid_payload)
            valid_status, valid_body = call_memory_add(api_server, strict_request(valid_payload))
            record_response("strict_exact_valid", valid_status, valid_body)
            valid_call = details["writer_calls"][-1] if details["writer_calls"] else {}
            valid_item = dict(valid_body.get("item") or {})
            stored_relations = list(concept_core_from_response(valid_body).get("relations") or [])
            checks["strict_exact_valid_succeeds"] = valid_status == 201 and valid_body.get("status") == "ok"
            checks["strict_exact_outer_response_shape_preserved"] = set(valid_body) == OUTER_RESPONSE_FIELDS
            checks["strict_exact_forwards_exact_version"] = (
                valid_call.get("relation_contract_version") == CONTRACT_VERSION
            )
            checks["strict_exact_preserves_tags_and_importance"] = (
                valid_item.get("tags") == ["semantic-relation", "api"]
                and valid_item.get("importance") == 8
            )
            checks["strict_exact_stores_canonical_relation"] = stored_relations == valid_payload["relations"]
            checks["strict_exact_relation_has_only_authored_fields"] = (
                len(stored_relations) == 1
                and set(stored_relations[0]) == {"contract_version", "type", "target", "evidence_ref"}
            )
            checks["transport_opt_in_not_persisted"] = (
                "relation_contract_version" not in valid_item
                and "relation_contract_version" not in (valid_item.get("metadata") or {})
                and "relation_contract_version"
                not in ((valid_item.get("metadata") or {}).get("concept_core") or {})
            )
            checks["api_input_payload_not_mutated"] = valid_payload == valid_payload_before

            missing_relations = concept_payload(id="concept:api-no-relations")
            missing_relations.pop("relations")
            missing_status, missing_body = call_memory_add(api_server, strict_request(missing_relations))
            record_response("missing_relations", missing_status, missing_body)
            checks["missing_relations_defaults_to_empty_list"] = (
                missing_status == 201
                and concept_core_from_response(missing_body).get("relations") == []
            )

            invalid_cases: dict[str, tuple[dict[str, Any], str]] = {
                "explicit_null_relations": (
                    strict_request(concept_payload(relations=None)),
                    "relations_not_list;field=relations",
                ),
                "missing_evidence": (
                    strict_request(
                        concept_payload(
                            relations=[
                                {
                                    "contract_version": CONTRACT_VERSION,
                                    "type": "supports",
                                    "target": "concept:api-writer-dangling-target",
                                }
                            ]
                        )
                    ),
                    "relation_missing_fields;index=0",
                ),
                "unknown_type": (
                    strict_request(
                        concept_payload(
                            relations=[
                                {
                                    **valid_payload["relations"][0],
                                    "type": "private-invalid-type",
                                    "target": "concept:private-target",
                                    "evidence_ref": "memory:private-evidence",
                                }
                            ]
                        )
                    ),
                    "relation_type_not_allowed;index=0;field=type",
                ),
                "duplicate": (
                    strict_request(
                        concept_payload(
                            relations=[valid_payload["relations"][0], valid_payload["relations"][0]]
                        )
                    ),
                    "relation_duplicate;index=1",
                ),
                "self_reference": (
                    strict_request(
                        concept_payload(
                            relations=[
                                {
                                    **valid_payload["relations"][0],
                                    "target": "concept:api-writer-source",
                                }
                            ]
                        )
                    ),
                    "relation_self_reference;index=0;field=target",
                ),
                "unknown_field": (
                    strict_request(
                        concept_payload(
                            relations=[
                                {
                                    **valid_payload["relations"][0],
                                    "relation_id": "generated:not-allowed",
                                }
                            ]
                        )
                    ),
                    "relation_unknown_fields;index=0",
                ),
            }
            for name, (request, expected_error) in invalid_cases.items():
                run_rejection(name, request, expected_error, expect_writer_call=True)

            version_cases: dict[str, object] = {
                "unsupported_version": "semantic_relation.v2",
                "non_string_version": True,
                "null_version": None,
            }
            for name, version in version_cases.items():
                request = strict_request(concept_payload(id=f"concept:{name}"))
                request["relation_contract_version"] = version
                run_rejection(
                    name,
                    request,
                    "unsupported_contract_version;field=contract_version",
                    expect_writer_call=False,
                )

            run_rejection(
                "opt_in_outside_strict",
                {
                    "text": "must not be written",
                    "relation_contract_version": CONTRACT_VERSION,
                },
                "relation_contract_requires_strict_mode;field=relation_contract_version",
                expect_writer_call=False,
            )
            run_rejection(
                "strict_missing_concept_core",
                {
                    "strict": True,
                    "relation_contract_version": None,
                },
                "concept_core must be an object",
                expect_writer_call=False,
            )

            unknown_error = str(
                details["responses"]["unknown_type"].get("error", "")
            )
            checks["errors_do_not_echo_rejected_relation_values"] = (
                "private-target" not in unknown_error
                and "private-evidence" not in unknown_error
                and "private-invalid-type" not in unknown_error
            )
            checks["valid_dangling_target_requires_no_lookup"] = (
                bool(stored_relations)
                and stored_relations[0].get("target") == "concept:api-writer-dangling-target"
            )
            checks["no_reverse_edge_or_target_block_created"] = MemoryEngine().count() == 5
            checks["temp_runtime_file_used"] = temp_runtime_file.exists()
            details["final_temp_memory_count"] = MemoryEngine().count()
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


def apply_cleanup_outcome(
    result: dict[str, Any],
    *,
    cleanup_requested: bool,
    cleanup_succeeded: bool | None,
    temp_root_exists: bool,
    cleanup_error: str | None,
) -> int:
    result["cleanup_requested"] = cleanup_requested
    result["cleanup_succeeded"] = cleanup_succeeded
    result["temp_root_exists_after_cleanup"] = temp_root_exists
    if cleanup_error:
        result["cleanup_error"] = cleanup_error

    cleanup_failed = cleanup_requested and (
        cleanup_succeeded is not True or temp_root_exists
    )
    if cleanup_failed and result.get("status") == "ok":
        result["status"] = "failed"
    return 0 if result.get("status") == "ok" and not cleanup_failed else 1


def print_result(result: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
        return
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


def main() -> int:
    args = parse_args()
    temp_root = Path(tempfile.gettempdir()) / f"gptmeai_semantic_relation_api_writer_{uuid.uuid4().hex}"
    result: dict[str, Any] = {
        "status": "error",
        "service": SERVICE_NAME,
        "temp_root": str(temp_root),
    }
    cleanup_succeeded = None
    cleanup_error = None
    try:
        result = run_smoke(temp_root)
    except Exception as exc:
        result = {
            "status": "error",
            "service": SERVICE_NAME,
            "temp_root": str(temp_root),
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    finally:
        if args.cleanup:
            cleanup_succeeded, cleanup_error = cleanup_temp_root(temp_root)

    exit_code = apply_cleanup_outcome(
        result,
        cleanup_requested=bool(args.cleanup),
        cleanup_succeeded=cleanup_succeeded,
        temp_root_exists=temp_root.exists(),
        cleanup_error=cleanup_error,
    )
    result["temp_root"] = str(temp_root)
    print_result(result, as_json=bool(args.json))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
