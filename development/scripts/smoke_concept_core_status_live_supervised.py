"""Supervised live smoke controller for /concept-core/status.

The default verification path for this script is --dry-run. A live run starts
the runtime through run_ai_os.ps1 only after preflight confirms port ownership is
safe.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_PROJECT_ROOT = Path(r"D:\Development GPTMEAi")
DEFAULT_REPORT_DIR = Path(r"D:\Codex_Review_Reports\GPTMEAi")
OFFICIAL_INTERPRETER = Path(r"D:\GPTMEAi_venv_candidate\Scripts\python.exe")

SERVICE_NAME = "AI OS Concept Core Live Supervised Smoke"
REPORT_SLUG = "concept_core_status_live_supervised"
MAX_HTTP_BODY_BYTES = 1_000_000
METADATA_FILE_LIMIT = 500

PHASES = [
    "[PHASE 01 preflight_start]",
    "[PHASE 02 report_path_created]",
    "[PHASE 03 port_preflight]",
    "[PHASE 04 metadata_before]",
    "[PHASE 05 runtime_start]",
    "[PHASE 06 health_poll]",
    "[PHASE 07 endpoint_checks]",
    "[PHASE 08 concept_core_assertions]",
    "[PHASE 09 cleanup_start]",
    "[PHASE 10 process_stop_confirm]",
    "[PHASE 11 port_release_confirm]",
    "[PHASE 12 metadata_after]",
    "[PHASE 13 report_written]",
]

EXPECTED_CAPABILITIES = {
    "typed_primitives": True,
    "strict_memory_add": True,
    "memory_metadata_visibility": True,
    "direct_cognitive_plan_advisory": True,
    "public_decision_preview": False,
    "global_enforcement": False,
}

EXPECTED_MEMORY_ROUTES = {
    "/memory/all",
    "/memory/search",
    "/memory/tag",
    "/memory/recent",
}

FORBIDDEN_INTERNAL_KEYS = {
    "concept_core_advisory",
    "tasks",
    "plan_groups",
    "recovery_requests",
    "evidence",
    "task_titles",
    "planned_task_titles",
    "memory_content",
    "memoryContent",
}


class SmokeAbort(RuntimeError):
    """Expected smoke failure with a clear user-facing reason."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=SERVICE_NAME)
    parser.add_argument("--timeout-seconds", type=int, default=90, help="Hard total timeout for a live run.")
    parser.add_argument("--json", action="store_true", help="Print compact JSON summary to stdout.")
    parser.add_argument(
        "--report-dir",
        default=str(DEFAULT_REPORT_DIR),
        help="Directory for CHATGPT_REVIEW_REPORT.md output.",
    )
    parser.add_argument(
        "--project-root",
        default=str(DEFAULT_PROJECT_ROOT),
        help="GPTMEAi project root containing run_ai_os.ps1.",
    )
    parser.add_argument("--port", type=int, default=8010, help="Runtime HTTP port.")
    parser.add_argument("--host", default="127.0.0.1", help="Runtime HTTP host.")
    parser.add_argument("--dry-run", action="store_true", help="Validate config and port without starting runtime.")
    return parser.parse_args()


def now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def normalize_path(path: Path) -> str:
    try:
        return str(path.resolve())
    except OSError:
        return str(path)


def make_summary(args: argparse.Namespace) -> dict[str, Any]:
    project_root = Path(args.project_root)
    report_dir = Path(args.report_dir)
    return {
        "status": "failed",
        "service": SERVICE_NAME,
        "dry_run": bool(args.dry_run),
        "blocked_reason": None,
        "errors": [],
        "warnings": [],
        "project_root": str(project_root),
        "report_dir": str(report_dir),
        "report_path": None,
        "host": args.host,
        "port": args.port,
        "timeout_seconds": args.timeout_seconds,
        "runtime_started": False,
        "launcher_pid": None,
        "started_pids": [],
        "stdout_path": None,
        "stderr_path": None,
        "endpoints_checked": [],
        "endpoint_results": {},
        "concept_core_status_ok": False,
        "concept_core_assertion_failures": [],
        "cleanup_succeeded": None,
        "port_released": None,
        "phase_markers": [],
        "port_preflight": {},
        "metadata_before": None,
        "metadata_after": None,
        "report_write_error": None,
    }


def mark(summary: dict[str, Any], marker: str, detail: str | None = None) -> None:
    entry = {"time": now_iso(), "marker": marker, "detail": detail}
    summary["phase_markers"].append(entry)
    line = marker if detail is None else f"{marker} {detail}"
    print(line, file=sys.stderr, flush=True)


def create_report_path(report_dir: Path, summary: dict[str, Any]) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{now_stamp()}_{REPORT_SLUG}_CHATGPT_REVIEW_REPORT.md"
    summary["report_path"] = str(report_path)
    return report_path


def path_is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def is_running_from_damaged_venv(project_root: Path) -> bool:
    executable = Path(sys.executable)
    damaged_venv = project_root / "venv"
    return path_is_relative_to(executable, damaged_venv)


def local_address_matches(local_address: str, host: str, port: int) -> bool:
    if not local_address.endswith(f":{port}"):
        return False
    address_part = local_address[: -(len(str(port)) + 1)].strip("[]")
    return address_part in {host, "0.0.0.0", "::", "::1", "[::]", ""}


def netstat_listeners(host: str, port: int) -> list[dict[str, Any]]:
    listeners: list[dict[str, Any]] = []
    try:
        completed = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return [{"source": "netstat", "error": f"{type(exc).__name__}: {exc}"}]

    for line in completed.stdout.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0].upper() != "TCP":
            continue
        local_address, state, pid = parts[1], parts[3].upper(), parts[4]
        if state != "LISTENING" or not local_address_matches(local_address, host, port):
            continue
        listeners.append(
            {
                "source": "netstat",
                "local_address": local_address,
                "state": state,
                "pid": int(pid) if pid.isdigit() else pid,
            }
        )
    return listeners


def socket_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def port_status(host: str, port: int) -> dict[str, Any]:
    listeners = netstat_listeners(host, port)
    netstat_has_listener = any("pid" in item for item in listeners)
    socket_open = socket_port_open(host, port)
    if socket_open and not netstat_has_listener:
        listeners.append({"source": "socket", "pid": None, "state": "LISTENING"})
    return {
        "host": host,
        "port": port,
        "listening": bool(netstat_has_listener or socket_open),
        "listeners": listeners,
        "socket_open": socket_open,
    }


def file_metadata(path: Path, base: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "name": str(path.relative_to(base)),
        "size": stat.st_size,
        "last_write_time": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
    }


def capture_directory_metadata(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "files": [], "truncated": False}
    files: list[dict[str, Any]] = []
    truncated = False
    try:
        for child in sorted(path.rglob("*")):
            if not child.is_file():
                continue
            if len(files) >= METADATA_FILE_LIMIT:
                truncated = True
                break
            files.append(file_metadata(child, path))
    except OSError as exc:
        return {
            "exists": True,
            "files": files,
            "truncated": truncated,
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {"exists": True, "files": files, "truncated": truncated}


def capture_project_metadata(project_root: Path) -> dict[str, Any]:
    return {
        str(project_root / "storage"): capture_directory_metadata(project_root / "storage"),
        str(project_root / "logs"): capture_directory_metadata(project_root / "logs"),
        str(project_root / "runtime"): capture_directory_metadata(project_root / "runtime"),
    }


def preflight(args: argparse.Namespace, summary: dict[str, Any]) -> list[str]:
    project_root = Path(args.project_root)
    blockers: list[str] = []
    if args.timeout_seconds <= 0:
        blockers.append("timeout_seconds_must_be_positive")
    if args.port < 1 or args.port > 65535:
        blockers.append("port_must_be_between_1_and_65535")
    if not project_root.exists():
        blockers.append(f"project_root_missing:{project_root}")
    elif not project_root.is_dir():
        blockers.append(f"project_root_not_directory:{project_root}")
    run_script = project_root / "run_ai_os.ps1"
    if not run_script.exists():
        blockers.append(f"run_ai_os_ps1_missing:{run_script}")
    if not OFFICIAL_INTERPRETER.exists():
        blockers.append(f"official_interpreter_missing:{OFFICIAL_INTERPRETER}")
    if is_running_from_damaged_venv(project_root):
        blockers.append("script_is_running_from_damaged_project_venv")

    mark(summary, PHASES[2])
    current_port = port_status(args.host, args.port)
    summary["port_preflight"] = current_port
    if current_port["listening"]:
        owners = [
            str(item.get("pid"))
            for item in current_port.get("listeners", [])
            if item.get("pid") not in (None, "")
        ]
        owner_text = ",".join(sorted(set(owners))) if owners else "unknown"
        blockers.append(f"port_{args.port}_already_listening_owner_pid:{owner_text}")
    return blockers


def remaining_seconds(deadline: float) -> float:
    return deadline - time.monotonic()


def ensure_time_remaining(deadline: float) -> None:
    if remaining_seconds(deadline) <= 0:
        raise SmokeAbort("timeout_reached")


def read_http(url: str, deadline: float) -> dict[str, Any]:
    ensure_time_remaining(deadline)
    request = urllib.request.Request(url, method="GET")
    timeout = max(0.1, min(5.0, remaining_seconds(deadline)))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_HTTP_BODY_BYTES + 1)
            truncated = len(raw) > MAX_HTTP_BODY_BYTES
            if truncated:
                raw = raw[:MAX_HTTP_BODY_BYTES]
            body_text = raw.decode("utf-8", errors="replace")
            content_type = response.headers.get("Content-Type", "")
            parsed_json = None
            if "json" in content_type.lower():
                parsed_json = json.loads(body_text) if body_text else None
            return {
                "ok": 200 <= response.status < 300,
                "status_code": response.status,
                "content_type": content_type,
                "body_bytes": len(raw),
                "body_truncated": truncated,
                "json": parsed_json,
            }
    except urllib.error.HTTPError as exc:
        body = exc.read(MAX_HTTP_BODY_BYTES).decode("utf-8", errors="replace")
        return {
            "ok": False,
            "status_code": exc.code,
            "content_type": exc.headers.get("Content-Type", "") if exc.headers else "",
            "body_bytes": len(body.encode("utf-8")),
            "body_truncated": False,
            "json": None,
            "error": f"HTTPError: {exc}",
        }
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "status_code": None,
            "content_type": "",
            "body_bytes": 0,
            "body_truncated": False,
            "json": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def poll_health(base_url: str, deadline: float) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    while remaining_seconds(deadline) > 0:
        result = read_http(f"{base_url}/health", deadline)
        attempts.append({k: v for k, v in result.items() if k != "json"})
        if result.get("status_code") == 200:
            return {"ok": True, "attempts": attempts, "result": result}
        time.sleep(min(1.0, max(0.1, remaining_seconds(deadline))))
    return {"ok": False, "attempts": attempts, "result": attempts[-1] if attempts else None}


def collect_key_paths(value: Any, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            path = f"{prefix}.{key_text}" if prefix else key_text
            paths.append(path)
            paths.extend(collect_key_paths(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(collect_key_paths(item, f"{prefix}[{index}]"))
    return paths


def assert_concept_core_status(payload: Any) -> tuple[bool, list[str]]:
    failures: list[str] = []
    if not isinstance(payload, dict):
        return False, ["concept_core_payload_not_object"]

    expected_top_level = {
        "status": "ok",
        "service": "AI OS Concept Core",
        "mode": "advisory_only",
        "runtime_enforcement": False,
        "storage_schema_mutation": False,
        "public_api_behavior_mutation": False,
    }
    for key, expected in expected_top_level.items():
        if payload.get(key) != expected:
            failures.append(f"{key}_mismatch")

    capabilities = payload.get("capabilities")
    if not isinstance(capabilities, dict):
        failures.append("capabilities_missing_or_not_object")
    else:
        for key, expected in EXPECTED_CAPABILITIES.items():
            if capabilities.get(key) is not expected:
                failures.append(f"capabilities.{key}_mismatch")

    visibility = payload.get("visibility")
    if not isinstance(visibility, dict):
        failures.append("visibility_missing_or_not_object")
    else:
        routes = set(visibility.get("memory_metadata_routes") or [])
        if not EXPECTED_MEMORY_ROUTES.issubset(routes):
            failures.append("visibility.memory_metadata_routes_missing_expected")
        expected_visibility_flags = {
            "memory_related_exposes_metadata": False,
            "cognitive_status_exposes_plan_advisory": False,
            "cognitive_run_exposes_plan_advisory": False,
            "planner_status_uses_concept_core": False,
            "dispatch_uses_concept_core": False,
        }
        for key, expected in expected_visibility_flags.items():
            if visibility.get(key) is not expected:
                failures.append(f"visibility.{key}_mismatch")

    safety_contract = payload.get("safety_contract")
    if not isinstance(safety_contract, dict):
        failures.append("safety_contract_missing_or_not_object")
    else:
        if safety_contract.get("label") != "advisory_non_enforcing":
            failures.append("safety_contract.label_mismatch")
        if safety_contract.get("internal_plan_payload_exposed") is not False:
            failures.append("safety_contract.internal_plan_payload_exposed_mismatch")
        red_button_detection = str(safety_contract.get("red_button_detection") or "").lower()
        if "heuristic" not in red_button_detection:
            failures.append("safety_contract.red_button_detection_missing_heuristic")
        if "not_authoritative" not in red_button_detection and "not authoritative" not in red_button_detection:
            failures.append("safety_contract.red_button_detection_missing_not_authoritative")
        if "policy" not in red_button_detection:
            failures.append("safety_contract.red_button_detection_missing_policy")

    forbidden_paths: list[str] = []
    for path in collect_key_paths(payload):
        key = path.split(".")[-1]
        key_without_index = key.split("[", 1)[0]
        if key_without_index in FORBIDDEN_INTERNAL_KEYS:
            forbidden_paths.append(path)
        lowered_path = path.lower()
        if lowered_path == "metadata.concept_core" or ".metadata.concept_core" in lowered_path:
            forbidden_paths.append(path)
        if ".metadata." in lowered_path and key_without_index.lower().startswith("concept_core"):
            forbidden_paths.append(path)
    if forbidden_paths:
        failures.append(f"forbidden_internal_fields_exposed:{','.join(sorted(set(forbidden_paths)))}")

    return not failures, failures


def endpoint_checks(base_url: str, deadline: float) -> dict[str, Any]:
    endpoints = [
        "/health",
        "/planner/status",
        "/execution/status",
        "/dashboard",
        "/concept-core/status",
    ]
    results: dict[str, Any] = {}
    for endpoint in endpoints:
        ensure_time_remaining(deadline)
        result = read_http(f"{base_url}{endpoint}", deadline)
        compact_result = {k: v for k, v in result.items() if k != "json"}
        if endpoint == "/concept-core/status":
            compact_result["json_keys"] = sorted((result.get("json") or {}).keys())
            compact_result["assertion_payload_available"] = isinstance(result.get("json"), dict)
        results[endpoint] = compact_result
        results[f"{endpoint}__json"] = result.get("json") if endpoint == "/concept-core/status" else None
    return results


def import_psutil() -> Any | None:
    try:
        import psutil  # type: ignore[import-not-found]
    except Exception:
        return None
    return psutil


def collect_process_tree_pids(root_pid: int) -> list[int]:
    psutil = import_psutil()
    if psutil is not None:
        try:
            root = psutil.Process(root_pid)
            children = root.children(recursive=True)
            return [root_pid, *[child.pid for child in children]]
        except Exception:
            return [root_pid]
    return [root_pid]


def process_exists(pid: int) -> bool:
    psutil = import_psutil()
    if psutil is not None:
        return psutil.pid_exists(pid)
    if os.name == "nt":
        try:
            completed = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return True
        return str(pid) in completed.stdout
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def wait_for_processes_stopped(pids: list[int], timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if all(not process_exists(pid) for pid in pids):
            return True
        time.sleep(0.25)
    return all(not process_exists(pid) for pid in pids)


def wait_for_port_released(host: str, port: int, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not port_status(host, port)["listening"]:
            return True
        time.sleep(0.25)
    return not port_status(host, port)["listening"]


def start_runtime(project_root: Path, summary: dict[str, Any]) -> tuple[subprocess.Popen[bytes], Any, Any]:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    stdout_path = Path(tempfile.gettempdir()) / f"gptmeai_live_supervised_{run_id}_stdout.log"
    stderr_path = Path(tempfile.gettempdir()) / f"gptmeai_live_supervised_{run_id}_stderr.log"
    stdout_handle = stdout_path.open("wb")
    stderr_handle = stderr_path.open("wb")
    command = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        r".\run_ai_os.ps1",
    ]
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    child_env = os.environ.copy()
    child_env["GPTMEAI_PYTHON"] = str(OFFICIAL_INTERPRETER)
    process = subprocess.Popen(
        command,
        cwd=str(project_root),
        stdin=subprocess.DEVNULL,
        stdout=stdout_handle,
        stderr=stderr_handle,
        env=child_env,
        creationflags=creationflags,
    )
    summary["runtime_started"] = True
    summary["launcher_pid"] = process.pid
    summary["started_pids"] = [process.pid]
    summary["stdout_path"] = str(stdout_path)
    summary["stderr_path"] = str(stderr_path)
    return process, stdout_handle, stderr_handle


def stop_started_tree(process: subprocess.Popen[bytes] | None, summary: dict[str, Any]) -> None:
    mark(summary, PHASES[8])
    if process is None:
        summary["cleanup_succeeded"] = True
        mark(summary, PHASES[9], "no_runtime_started")
        return

    pids = collect_process_tree_pids(process.pid)
    summary["started_pids"] = sorted(set([*summary.get("started_pids", []), *pids]))
    if process.poll() is None:
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            else:
                process.terminate()
                process.wait(timeout=5)
        except (OSError, subprocess.SubprocessError) as exc:
            summary["errors"].append(f"cleanup_stop_failed:{type(exc).__name__}:{exc}")
    stopped = wait_for_processes_stopped(summary["started_pids"], timeout_seconds=10)
    summary["cleanup_succeeded"] = stopped
    mark(summary, PHASES[9], "stopped" if stopped else "not_confirmed")


def close_handles(handles: list[Any]) -> None:
    for handle in handles:
        if handle is None:
            continue
        try:
            handle.close()
        except OSError:
            pass


def run_controller(args: argparse.Namespace, summary: dict[str, Any]) -> int:
    project_root = Path(args.project_root)
    process: subprocess.Popen[bytes] | None = None
    stdout_handle = None
    stderr_handle = None
    deadline = time.monotonic() + args.timeout_seconds

    try:
        mark(summary, PHASES[0])
        report_path = create_report_path(Path(args.report_dir), summary)
        mark(summary, PHASES[1], str(report_path))

        blockers = preflight(args, summary)
        if blockers:
            summary["status"] = "blocked"
            summary["blocked_reason"] = ";".join(blockers)
            for phase in PHASES[3:8]:
                mark(summary, phase, "skipped_preflight_blocked")
            return 0

        if args.dry_run:
            summary["status"] = "ok"
            for phase in PHASES[3:8]:
                mark(summary, phase, "skipped_dry_run")
            summary["cleanup_succeeded"] = True
            summary["port_released"] = None
            return 0

        mark(summary, PHASES[3])
        summary["metadata_before"] = capture_project_metadata(project_root)

        mark(summary, PHASES[4])
        process, stdout_handle, stderr_handle = start_runtime(project_root, summary)

        base_url = f"http://{args.host}:{args.port}"
        mark(summary, PHASES[5])
        health = poll_health(base_url, deadline)
        summary["endpoint_results"]["/health_poll"] = health
        if not health["ok"]:
            raise SmokeAbort("health_did_not_reach_200_before_timeout")

        mark(summary, PHASES[6])
        results = endpoint_checks(base_url, deadline)
        summary["endpoint_results"].update(
            {key: value for key, value in results.items() if not key.endswith("__json")}
        )
        summary["endpoints_checked"] = [
            "/health",
            "/planner/status",
            "/execution/status",
            "/dashboard",
            "/concept-core/status",
        ]
        for endpoint in summary["endpoints_checked"]:
            endpoint_result = summary["endpoint_results"].get(endpoint) or {}
            if not endpoint_result.get("ok"):
                raise SmokeAbort(f"endpoint_check_failed:{endpoint}")

        mark(summary, PHASES[7])
        concept_payload = results.get("/concept-core/status__json")
        concept_ok, failures = assert_concept_core_status(concept_payload)
        summary["concept_core_status_ok"] = concept_ok
        summary["concept_core_assertion_failures"] = failures
        if not concept_ok:
            raise SmokeAbort("concept_core_status_assertions_failed")

        summary["status"] = "ok"
        return 0
    except SmokeAbort as exc:
        summary["status"] = "failed"
        summary["errors"].append(str(exc))
        return 1
    except Exception as exc:  # noqa: BLE001 - controller report must preserve exact failure class.
        summary["status"] = "failed"
        summary["errors"].append(f"{type(exc).__name__}: {exc}")
        return 1
    finally:
        try:
            stop_started_tree(process, summary)
        finally:
            close_handles([stdout_handle, stderr_handle])
        if summary["runtime_started"]:
            released = wait_for_port_released(args.host, args.port, timeout_seconds=10)
            summary["port_released"] = released
            mark(summary, PHASES[10], "released" if released else "not_released")
            mark(summary, PHASES[11])
            summary["metadata_after"] = capture_project_metadata(project_root)
        elif summary["port_released"] is None:
            mark(summary, PHASES[10], "skipped_no_runtime_started")
            mark(summary, PHASES[11], "skipped_no_runtime_started")


def markdown_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def build_report(summary: dict[str, Any]) -> str:
    report_path = summary.get("report_path")
    commands = [
        "dry-run verification: D:\\GPTMEAi_venv_candidate\\Scripts\\python.exe "
        ".\\development\\scripts\\smoke_concept_core_status_live_supervised.py --dry-run --json --timeout-seconds 10",
        "future live run only after explicit approval: D:\\GPTMEAi_venv_candidate\\Scripts\\python.exe "
        ".\\development\\scripts\\smoke_concept_core_status_live_supervised.py --timeout-seconds 90",
    ]
    return "\n".join(
        [
            "# CHATGPT_REVIEW_REPORT.md",
            "",
            "## 1. Task",
            "",
            "Supervised live smoke controller run report for `/concept-core/status`.",
            "",
            "## 2. Project root",
            "",
            f"`{summary.get('project_root')}`",
            "",
            "## 3. Files changed",
            "",
            "The controller run does not edit project files.",
            "",
            "## 4. What was implemented",
            "",
            "No implementation is performed by this run. The script orchestrates dry-run checks or a future approved live smoke.",
            "",
            "## 5. What was intentionally not changed",
            "",
            "- production code",
            "- `scripts/api_server.py`",
            "- `run_ai_os.ps1`",
            "- dependencies, packages, lockfiles",
            "- damaged `venv/`",
            "- storage/memory contents",
            "",
            "## 6. Commands run",
            "",
            "```text",
            *commands,
            "```",
            "",
            "## 7. Command results",
            "",
            "```json",
            markdown_json(summary),
            "```",
            "",
            "## 8. Verification status",
            "",
            f"Final status: `{summary.get('status')}`.",
            "",
            "## 9. Risks / remaining debt",
            "",
            "- Live smoke remains unverified when this report is from `--dry-run`.",
            "- If port preflight is blocked, existing port ownership must be resolved before a live run.",
            "- Cleanup confirmation can be limited by Windows process-inspection permissions.",
            "",
            "## 10. Next safest step",
            "",
            "Run the live smoke only after explicit approval and only if preflight confirms port `8010` is free.",
            "",
            "## 11. Copy-paste handoff summary",
            "",
            f"Report path: `{report_path}`",
            "",
            f"Status: `{summary.get('status')}`",
            "",
            f"Dry run: `{summary.get('dry_run')}`",
            "",
            f"Runtime started: `{summary.get('runtime_started')}`",
            "",
            f"Blocked reason: `{summary.get('blocked_reason')}`",
            "",
        ]
    )


def write_report(summary: dict[str, Any]) -> None:
    mark(summary, PHASES[12])
    report_path_text = summary.get("report_path")
    if not report_path_text:
        raise SmokeAbort("report_path_not_available")
    report_path = Path(str(report_path_text))
    report_path.write_text(build_report(summary), encoding="utf-8")


def output_summary(summary: dict[str, Any], as_json: bool) -> None:
    compact = {
        "status": summary.get("status"),
        "dry_run": summary.get("dry_run"),
        "blocked_reason": summary.get("blocked_reason"),
        "endpoints_checked": summary.get("endpoints_checked"),
        "concept_core_status_ok": summary.get("concept_core_status_ok"),
        "runtime_started": summary.get("runtime_started"),
        "cleanup_succeeded": summary.get("cleanup_succeeded"),
        "port_released": summary.get("port_released"),
        "report_path": summary.get("report_path"),
    }
    if as_json:
        print(json.dumps(compact, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(compact, ensure_ascii=False, indent=2, sort_keys=True))


def main() -> int:
    args = parse_args()
    summary = make_summary(args)
    exit_code = run_controller(args, summary)
    try:
        write_report(summary)
    except Exception as exc:  # noqa: BLE001 - fallback JSON is required if report writing fails.
        summary["report_write_error"] = f"{type(exc).__name__}: {exc}"
        if summary["status"] == "ok":
            summary["status"] = "failed"
        exit_code = 1
    output_summary(summary, as_json=args.json)
    if summary.get("status") in {"ok", "blocked"}:
        return 0
    return exit_code or 1


if __name__ == "__main__":
    raise SystemExit(main())
