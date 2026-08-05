"""Temp-state smoke for optional strict Concept Core memory commits."""

from __future__ import annotations

import argparse
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
    parser = argparse.ArgumentParser(description="Smoke-test Concept Core memory validation with temp runtime state.")
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


def legacy_shape_compatible(block: dict) -> bool:
    required = {"id", "text", "importance", "tags", "created_at"}
    return required.issubset(set(block)) and isinstance(block.get("tags"), list)


def expect_rejected(name: str, engine, payload: dict, checks: dict) -> None:
    before = engine.count()
    try:
        engine.add_concept_node(payload)
    except ValueError:
        checks[name] = engine.count() == before
        return
    checks[name] = False


def run_smoke(temp_root: Path) -> dict:
    from ai_os.config import get_project_paths
    from core.memory_engine import MemoryEngine
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
    }

    try:
        runtime_store.RUNTIME_FILE = temp_runtime_file
        engine = MemoryEngine()

        legacy_block = engine.add("plain text")
        checks["legacy_add_plain_text_still_works"] = legacy_block.get("text") == "plain text"
        checks["legacy_block_shape_compatible"] = legacy_shape_compatible(legacy_block)
        checks["legacy_block_has_no_concept_core_metadata_by_default"] = not bool(
            (legacy_block.get("metadata") or {}).get("concept_core")
        )

        valid_payload = {
            "id": "memory:concept-core-valid",
            "type": "decision",
            "title": "Validated Concept Core memory",
            "content": "Validated Concept Core memory content.",
            "status": "confirmed",
            "source": "smoke_concept_core_memory",
            "confidence": 0.91,
            "context": {"goal": "verify strict concept memory commit"},
            "relations": [{"type": "supports", "target": "decision:concept-core-memory"}],
        }
        strict_block = engine.add_concept_node(valid_payload, tags=["concept-core"], importance=8)
        concept_metadata = dict((strict_block.get("metadata") or {}).get("concept_core") or {})
        checks["valid_strict_payload_accepted"] = strict_block.get("text") == valid_payload["content"]
        checks["strict_block_shape_compatible"] = legacy_shape_compatible(strict_block)
        checks["strict_block_includes_concept_core_metadata"] = bool(concept_metadata)
        checks["strict_block_concept_core_status_preserved"] = concept_metadata.get("status") == "confirmed"
        checks["strict_block_concept_core_source_preserved"] = concept_metadata.get("source") == "smoke_concept_core_memory"
        checks["strict_block_concept_core_context_preserved"] = concept_metadata.get("context") == valid_payload["context"]

        missing_source = dict(valid_payload)
        missing_source.pop("source")
        expect_rejected("strict_payload_without_source_rejected_without_write", engine, missing_source, checks)

        missing_context = dict(valid_payload)
        missing_context.pop("context")
        expect_rejected("strict_payload_without_context_rejected_without_write", engine, missing_context, checks)

        invalid_confidence = dict(valid_payload)
        invalid_confidence["confidence"] = 1.5
        expect_rejected("strict_payload_invalid_confidence_rejected_without_write", engine, invalid_confidence, checks)

        all_blocks = engine.get_all()
        checks["invalid_strict_payloads_did_not_write_blocks"] = len(all_blocks) == 2
        checks["temp_runtime_file_used"] = temp_runtime_file.exists()
    finally:
        runtime_store.RUNTIME_FILE = previous_runtime_file

    project_runtime_after = file_metadata(project_runtime_file)
    checks["project_runtime_file_untouched"] = project_runtime_before == project_runtime_after
    details["project_runtime_before"] = project_runtime_before
    details["project_runtime_after"] = project_runtime_after

    return {
        "status": "ok" if all(checks.values()) else "failed",
        "service": "AI OS Concept Core Memory Smoke",
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
    temp_root = Path(tempfile.gettempdir()) / f"gptmeai_concept_core_memory_{uuid.uuid4().hex}"
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
