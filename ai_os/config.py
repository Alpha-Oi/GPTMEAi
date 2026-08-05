"""Shared configuration and path helpers for the AI OS runtime."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


@dataclass(frozen=True)
class ProjectPaths:
    project_root: Path
    env_file: Path
    runtime_file: Path
    agent_runtime_file: Path
    planner_runtime_file: Path
    execution_runtime_file: Path
    operation_ledger_file: Path
    snapshot_lineage_file: Path
    docs_dir: Path
    developer_docs_dir: Path
    dashboard_dir: Path
    dashboard_file: Path
    development_dir: Path
    development_changes_dir: Path
    development_logs_dir: Path
    development_tmp_dir: Path
    development_scripts_dir: Path
    storage_dir: Path
    snapshots_dir: Path
    memory_dir: Path
    legacy_dir: Path


@dataclass(frozen=True)
class RuntimeConfig:
    host: str
    port: int


def load_env_file(env_path: Path = ENV_FILE) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def get_project_paths() -> ProjectPaths:
    return ProjectPaths(
        project_root=PROJECT_ROOT,
        env_file=ENV_FILE,
        runtime_file=PROJECT_ROOT / "GPTMemory_runtime.yaml",
        agent_runtime_file=PROJECT_ROOT / "storage" / "agent_runtime.json",
        planner_runtime_file=PROJECT_ROOT / "storage" / "planner_runtime.json",
        execution_runtime_file=PROJECT_ROOT / "storage" / "execution_runtime.json",
        operation_ledger_file=PROJECT_ROOT / "storage" / "operation_ledger.json",
        snapshot_lineage_file=PROJECT_ROOT / "storage" / "snapshot_lineage.json",
        docs_dir=PROJECT_ROOT / "docs",
        developer_docs_dir=PROJECT_ROOT / "docs" / "developer",
        dashboard_dir=PROJECT_ROOT / "dashboard",
        dashboard_file=PROJECT_ROOT / "dashboard" / "index.html",
        development_dir=PROJECT_ROOT / "development",
        development_changes_dir=PROJECT_ROOT / "development" / "changes",
        development_logs_dir=PROJECT_ROOT / "development" / "logs",
        development_tmp_dir=PROJECT_ROOT / "development" / "tmp",
        development_scripts_dir=PROJECT_ROOT / "development" / "scripts",
        storage_dir=PROJECT_ROOT / "storage",
        snapshots_dir=PROJECT_ROOT / "storage" / "snapshots",
        memory_dir=PROJECT_ROOT / "memory",
        legacy_dir=PROJECT_ROOT / "legacy",
    )


def get_runtime_config() -> RuntimeConfig:
    load_env_file()

    host = os.getenv("GPTMEAI_HOST", "127.0.0.1").strip() or "127.0.0.1"

    try:
        port = int(os.getenv("GPTMEAI_PORT", "8010"))
    except ValueError:
        port = 8010

    return RuntimeConfig(host=host, port=port)
