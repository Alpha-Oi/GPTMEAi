"""Current project manifest separating official runtime from legacy branches."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from ai_os.config import get_project_paths


@dataclass(frozen=True)
class RuntimeManifest:
    official_runtime: list[str]
    official_packages: list[str]
    developer_docs: list[str]
    development_workspace: list[str]
    data_paths: list[str]
    legacy_paths: list[str]
    archive_paths: list[str]


def build_manifest() -> RuntimeManifest:
    paths = get_project_paths()
    root = paths.project_root

    def rel(path_text: str) -> str:
        return str((root / path_text).relative_to(root)).replace("\\", "/")

    return RuntimeManifest(
        official_runtime=[
            rel("run_ai_os.py"),
            rel("run_ai_os.ps1"),
            rel("scripts/api_server.py"),
            rel("dashboard/index.html"),
        ],
        official_packages=[
            rel("ai_os"),
            rel("core"),
            rel("agents"),
            rel("planning"),
            rel("execution"),
            rel("memory"),
            rel("scripts"),
        ],
        developer_docs=[
            rel("docs/developer"),
            rel("docs/developer/DEVELOPER_CONTEXT.md"),
        ],
        development_workspace=[
            rel("development"),
            rel("development/changes"),
            rel("development/logs"),
            rel("development/tmp"),
            rel("development/scripts"),
        ],
        data_paths=[
            rel("GPTMemory_runtime.yaml"),
            rel("storage"),
            rel("memory/chats"),
            rel("memory/parsed"),
            rel("memory/knowledge"),
            rel("memory/embeddings"),
        ],
        legacy_paths=[
            rel("scripts/api_gui_integration.py"),
            rel("core/cognitive_loop_api.py"),
            rel("core/cognitive_loop_api_v2.py"),
            rel("apps/dashboard"),
            rel("GPTMemoryEngine"),
        ],
        archive_paths=[
            rel("backup_python_files"),
            rel("backups"),
            rel("stable_backup"),
            rel("smart_trash"),
            rel("logs"),
            rel(".gptcollector"),
        ],
    )


def to_json() -> str:
    return json.dumps(asdict(build_manifest()), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    print(to_json())
