from __future__ import annotations

import json
import shutil
import subprocess
import sys
import textwrap
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Development GPTMEAi")
BACKUP_DIR = PROJECT_ROOT / ".gptcollector" / "backups"
COLLECTOR_PATH = PROJECT_ROOT / "chat_migration_collector.py"
LAUNCHER_PATH = PROJECT_ROOT / "chat_migration_launcher.bat"
STATE_PATH = PROJECT_ROOT / ".gptcollector" / "project_notes.json"

COLLECTOR_CODE = r'''
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

try:
    import tkinter as tk
    from tkinter import messagebox, scrolledtext, ttk
except Exception:
    tk = None
    messagebox = None
    scrolledtext = None
    ttk = None

try:
    import yaml  # type: ignore
except Exception:
    yaml = None


APP_DIR_NAME = ".gptcollector"
STATE_FILE_NAME = "project_notes.json"
EXPORTS_DIR_NAME = "exports"
SNAPSHOTS_DIR_NAME = "snapshots"
DEFAULT_KEEP_STABLE = 10

NOTE_TYPES = {
    "goal",
    "decision",
    "task",
    "done",
    "bug",
    "fix",
    "context",
    "command",
    "observation",
}

DEFAULT_IGNORE_DIRS = {
    ".git",
    ".idea",
    ".vscode",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "env",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".gptcollector",
    "stable_backup",
}

DEFAULT_TOOL_FILE_PATTERNS = [
    "chat_migration_collector.py",
    "chat_migration_launcher.bat",
    "*migration*collector*.py",
    "*migration*launcher*.bat",
    "*migration*.ps1",
    "restore_from_stable_backup.py",
    "make_stable_backup.py",
    "upgrade_*migration*.py",
    "rebuild_*migration*.py",
    "fix_*migration*.py",
    "cleanup_*migration*.py",
    "populate_*migration*.py",
]

DEFAULT_PRIORITY_PATTERNS = [
    "README.md",
    "pyproject.toml",
    "requirements.txt",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    ".env",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "GPTMemory_plan.yaml",
    "GPTMemoryPlan.yaml",
    "main.py",
    "app.py",
    "manage.py",
    "index.js",
    "server.js",
    "*.py",
    "*.md",
    "*.json",
    "*.yaml",
    "*.yml",
    "*.toml",
]


PROGRAM_HELP_TEXT = """БЫСТРЫЙ СТАРТ / QUICK START

1. Quick
   - выполнить первичную настройку collector для текущего проекта

2. Daily
   - добавить заметку о новом шаге
   - автоматически сохранить snapshot, export и stable backup

3. Transfer
   - получить готовый текст для вставки в новый чат

4. Backup
   - вручную создать контрольную резервную точку

ОСНОВНОЙ ПРИНЦИП / MAIN PRINCIPLE

Collector лежит в корне проекта, но анализирует не себя, а сам проект.
Служебные файлы collector и его папки исключаются из аналитических разделов,
чтобы migration block описывал именно рабочий проект.

КНОПКИ / BUTTONS

Quick
- quick setup / быстрая настройка

Status
- текущее состояние проекта

Export
- создать migration block и JSON архив

Transfer
- показать готовый текст для нового чата

Daily
- заметка + snapshot + export + stable backup

Backup
- создать резервную контрольную точку

Last export
- открыть выбранный export из списка

Last snapshot
- открыть выбранный snapshot из списка

Last backup
- открыть выбранный stable backup из списка

Refresh
- обновить списки последних файлов

Save
- сохранить название и цель проекта

Add note
- добавить запись о шаге, ошибке, решении или задаче

Add context
- добавить важный постоянный контекст проекта

Search
- искать по заметкам и контексту
"""


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def safe_label(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_")
    return cleaned or "manual"


def default_plan_path(project_root: Path) -> str:
    if (project_root / "GPTMemory_plan.yaml").exists():
        return "GPTMemory_plan.yaml"
    if (project_root / "GPTMemoryPlan.yaml").exists():
        return "GPTMemoryPlan.yaml"
    return "GPTMemory_plan.yaml"


def open_path_in_system(path: Path) -> None:
    try:
        if os.name == "nt" and hasattr(os, "startfile"):
            os.startfile(str(path))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass


class SimpleToolTip:
    def __init__(self, widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.widget.bind("<Enter>", self.show)
        self.widget.bind("<Leave>", self.hide)

    def show(self, _event=None) -> None:
        if self.tipwindow or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw,
            text=self.text,
            justify="left",
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            font=("Segoe UI", 9),
            padx=6,
            pady=4,
        )
        label.pack()

    def hide(self, _event=None) -> None:
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()


def attach_tooltip(widget, text: str) -> None:
    SimpleToolTip(widget, text)


class ProjectMigrationCollector:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.app_dir = self.project_root / APP_DIR_NAME
        self.state_file = self.app_dir / STATE_FILE_NAME
        self.exports_dir = self.app_dir / EXPORTS_DIR_NAME
        self.snapshots_dir = self.app_dir / SNAPSHOTS_DIR_NAME
        self.stable_backup_root = self.project_root / "stable_backup"

    def ensure_state(self) -> None:
        self.app_dir.mkdir(parents=True, exist_ok=True)
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.stable_backup_root.mkdir(parents=True, exist_ok=True)

        if not self.state_file.exists():
            state = {
                "project_name": self.project_root.name,
                "project_goal": "",
                "important_context": [],
                "notes": [],
                "settings": {
                    "ignore_dirs": sorted(DEFAULT_IGNORE_DIRS),
                    "tool_file_patterns": list(DEFAULT_TOOL_FILE_PATTERNS),
                    "priority_patterns": list(DEFAULT_PRIORITY_PATTERNS),
                    "focus_files": [],
                    "keep_last_stable_backups": DEFAULT_KEEP_STABLE,
                    "integration": {
                        "gptmemory_plan_enabled": True,
                        "gptmemory_plan_path": default_plan_path(self.project_root),
                    },
                },
                "export_history": [],
                "last_stable_backup": "",
                "created_at": now_iso(),
                "updated_at": now_iso(),
            }
            self._write_json(self.state_file, state)

    def _read_json(self, path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _normalize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        state.setdefault("project_name", self.project_root.name)
        state.setdefault("project_goal", "")
        state.setdefault("important_context", [])
        state.setdefault("notes", [])
        state.setdefault("export_history", [])
        state.setdefault("last_stable_backup", "")
        settings = state.setdefault("settings", {})
        settings.setdefault("ignore_dirs", sorted(DEFAULT_IGNORE_DIRS))
        settings.setdefault("tool_file_patterns", list(DEFAULT_TOOL_FILE_PATTERNS))
        settings.setdefault("priority_patterns", list(DEFAULT_PRIORITY_PATTERNS))
        settings.setdefault("focus_files", [])
        settings.setdefault("keep_last_stable_backups", DEFAULT_KEEP_STABLE)
        integration = settings.setdefault("integration", {})
        integration.setdefault("gptmemory_plan_enabled", True)
        integration.setdefault("gptmemory_plan_path", default_plan_path(self.project_root))
        if integration.get("gptmemory_plan_path") and not (self.project_root / integration["gptmemory_plan_path"]).exists():
            integration["gptmemory_plan_path"] = default_plan_path(self.project_root)
        return state

    def load_state(self) -> dict[str, Any]:
        self.ensure_state()
        state = self._read_json(self.state_file)
        normalized = self._normalize_state(state)
        if normalized != state:
            self.save_state(normalized)
        return normalized

    def save_state(self, state: dict[str, Any]) -> None:
        state["updated_at"] = now_iso()
        self._write_json(self.state_file, state)

    def init_project(self, project_name: str | None = None, goal: str | None = None) -> None:
        state = self.load_state()
        if project_name:
            state["project_name"] = project_name
        if goal:
            state["project_goal"] = goal
        self.save_state(state)

    def update_settings(
        self,
        *,
        add_focus_file: str | None = None,
        add_priority_pattern: str | None = None,
        add_ignore_dir: str | None = None,
        keep_last_stable_backups: int | None = None,
        gptmemory_plan_path: str | None = None,
    ) -> dict[str, Any]:
        state = self.load_state()
        settings = state["settings"]
        integration = settings["integration"]

        if add_focus_file and add_focus_file not in settings["focus_files"]:
            settings["focus_files"].append(add_focus_file)
        if add_priority_pattern and add_priority_pattern not in settings["priority_patterns"]:
            settings["priority_patterns"].append(add_priority_pattern)
        if add_ignore_dir and add_ignore_dir not in settings["ignore_dirs"]:
            settings["ignore_dirs"].append(add_ignore_dir)
        if keep_last_stable_backups is not None and keep_last_stable_backups > 0:
            settings["keep_last_stable_backups"] = keep_last_stable_backups
        if gptmemory_plan_path:
            integration["gptmemory_plan_path"] = gptmemory_plan_path

        self.save_state(state)
        return settings

    def add_note(self, note_type: str, text: str) -> None:
        if note_type not in NOTE_TYPES:
            raise ValueError(f"Недопустимый тип заметки: {note_type}")
        state = self.load_state()
        state["notes"].append({
            "note_type": note_type,
            "text": text.strip(),
            "created_at": now_iso(),
        })
        self.save_state(state)

    def add_context(self, text: str) -> None:
        state = self.load_state()
        state["important_context"].append({
            "text": text.strip(),
            "created_at": now_iso(),
        })
        self.save_state(state)

    def _ensure_note(self, note_type: str, text: str) -> None:
        state = self.load_state()
        if not any(item.get("note_type") == note_type and item.get("text") == text for item in state["notes"]):
            state["notes"].append({
                "note_type": note_type,
                "text": text,
                "created_at": now_iso(),
            })
            self.save_state(state)

    def _ensure_context(self, text: str) -> None:
        state = self.load_state()
        if not any(item.get("text") == text for item in state["important_context"]):
            state["important_context"].append({
                "text": text,
                "created_at": now_iso(),
            })
            self.save_state(state)

    def quick_setup(self, project_name: str | None = None, goal: str | None = None, plan_path: str | None = None) -> dict[str, Any]:
        self.init_project(project_name=project_name, goal=goal)
        self.update_settings(gptmemory_plan_path=plan_path or default_plan_path(self.project_root))

        state = self.load_state()
        detected_plan = default_plan_path(self.project_root)
        if detected_plan not in state["settings"]["focus_files"] and (self.project_root / detected_plan).exists():
            state["settings"]["focus_files"].append(detected_plan)
        self.save_state(state)

        self._ensure_note("decision", "Collector работает как универсальная утилита в корне проекта и анализирует весь проект, а не самого себя.")
        self._ensure_note("decision", "Служебные файлы collector и его каталоги исключаются из аналитических разделов migration block.")
        self._ensure_note("task", "Поддерживать notes/context в актуальном состоянии, чтобы DEBUG HISTORY, FIXES APPLIED и NEXT DEVELOPMENT TASKS заполнялись максимально сильно.")
        self._ensure_context("Программа находится в корне проекта как вспомогательный сборщик состояния; основной предмет анализа — весь проектный каталог, кроме служебных файлов collector.")
        backup_path = self.create_stable_backup("quick_setup")
        state = self.load_state()
        state["last_stable_backup"] = backup_path.as_posix()
        self.save_state(state)
        return state

    def _tool_patterns(self) -> list[str]:
        state = self.load_state()
        return list(state["settings"].get("tool_file_patterns", DEFAULT_TOOL_FILE_PATTERNS))

    def is_internal_tool_file(self, rel_path: str) -> bool:
        rel_path = rel_path.replace("\\", "/")
        name = Path(rel_path).name
        parts = Path(rel_path).parts

        if parts and parts[0] in {APP_DIR_NAME, "stable_backup"}:
            return True

        for pattern in self._tool_patterns():
            if fnmatch(name, pattern) or fnmatch(rel_path, pattern):
                return True

        top_level = len(parts) == 1
        if top_level and ("migration" in name.lower() or "stable_backup" in name.lower()):
            return True

        return False

    def get_recent_exports(self, limit: int = 10) -> list[Path]:
        return sorted(self.exports_dir.glob("migration_block_*.txt"), reverse=True)[:limit]

    def get_recent_snapshots(self, limit: int = 10) -> list[Path]:
        return sorted(self.snapshots_dir.glob("snapshot_*.json"), reverse=True)[:limit]

    def get_recent_stable_backups(self, limit: int = 10) -> list[Path]:
        candidates = sorted(
            [p for p in self.stable_backup_root.glob("chat_migration_stable_*") if p.is_dir()],
            reverse=True,
        )
        return candidates[:limit]

    def _cleanup_old_stable_backups(self) -> None:
        state = self.load_state()
        keep_last = int(state["settings"].get("keep_last_stable_backups", DEFAULT_KEEP_STABLE))
        backups = self.get_recent_stable_backups(9999)
        if len(backups) <= keep_last:
            return
        for path in backups[keep_last:]:
            try:
                shutil.rmtree(path)
            except Exception:
                pass

    def create_stable_backup(self, label: str = "manual") -> Path:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.stable_backup_root / f"chat_migration_stable_{stamp}_{safe_label(label)}"
        backup_dir.mkdir(parents=True, exist_ok=True)

        files_to_copy = [
            self.project_root / "chat_migration_collector.py",
            self.project_root / "chat_migration_launcher.bat",
        ]
        for src in files_to_copy:
            if src.exists():
                shutil.copy2(src, backup_dir / src.name)

        if self.state_file.exists():
            dst = backup_dir / APP_DIR_NAME / STATE_FILE_NAME
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.state_file, dst)

        if self.exports_dir.exists():
            shutil.copytree(self.exports_dir, backup_dir / APP_DIR_NAME / EXPORTS_DIR_NAME, dirs_exist_ok=True)

        if self.snapshots_dir.exists():
            shutil.copytree(self.snapshots_dir, backup_dir / APP_DIR_NAME / SNAPSHOTS_DIR_NAME, dirs_exist_ok=True)

        state = self.load_state()
        state["last_stable_backup"] = backup_dir.as_posix()
        self.save_state(state)
        self._cleanup_old_stable_backups()
        return backup_dir

    def open_latest_export(self) -> str:
        items = self.get_recent_exports(1)
        if not items:
            return "Последний export пока не найден."
        open_path_in_system(items[0])
        return "Открыт export:\n" + items[0].as_posix()

    def open_latest_snapshot(self) -> str:
        items = self.get_recent_snapshots(1)
        if not items:
            return "Последний snapshot пока не найден."
        open_path_in_system(items[0])
        return "Открыт snapshot:\n" + items[0].as_posix()

    def open_latest_stable_backup(self) -> str:
        items = self.get_recent_stable_backups(1)
        if not items:
            return "Последний stable backup пока не найден."
        open_path_in_system(items[0])
        return "Открыт stable backup:\n" + items[0].as_posix()

    def _classify_root_dir(self, name: str) -> str:
        mapping = {
            "src": "основной код проекта",
            "core": "ядро и бизнес-логика",
            "app": "точка входа или основное приложение",
            "apps": "набор приложений или модулей",
            "dashboard": "интерфейс или веб-панель",
            "ui": "пользовательский интерфейс",
            "frontend": "frontend-часть проекта",
            "backend": "backend-часть проекта",
            "api": "API-слой",
            "scripts": "служебные скрипты самого проекта",
            "tests": "тесты",
            "docs": "документация",
            "config": "конфигурация",
            "configs": "конфигурация",
            "data": "данные или артефакты",
            "logs": "логи",
            "storage": "хранилище данных",
            "runtime": "runtime-данные",
            "memory": "слой памяти или данных памяти",
            "agents": "агенты или исполнительные модули",
            "execution": "модули выполнения",
            "vector_db": "векторное хранилище",
        }
        return mapping.get(name.lower(), "рабочий каталог проекта")

    def _describe_file(self, rel_path: str) -> str:
        name = Path(rel_path).name.lower()
        ext = Path(rel_path).suffix.lower()

        special = {
            "readme.md": "главное текстовое описание проекта",
            "requirements.txt": "python-зависимости",
            "pyproject.toml": "python-конфигурация проекта",
            "package.json": "javascript/node-конфигурация проекта",
            "dockerfile": "docker-сборка проекта",
            ".env": "локальные переменные окружения",
            "gptmemory_plan.yaml": "план проекта",
            "gptmemoryplan.yaml": "план проекта",
            "main.py": "главная точка входа python",
            "app.py": "точка входа приложения",
            "manage.py": "служебная точка входа проекта",
            "server.js": "серверная точка входа node",
            "index.js": "базовая javascript-точка входа",
        }
        if name in special:
            return special[name]

        if ext == ".py":
            return "python-модуль проекта"
        if ext in {".md"}:
            return "документация или текстовый отчёт"
        if ext in {".json", ".yaml", ".yml", ".toml"}:
            return "конфигурация или структурированные данные"
        if ext in {".js", ".ts", ".jsx", ".tsx"}:
            return "javascript/typescript-модуль"
        if ext in {".html", ".css"}:
            return "frontend-ресурс"
        if ext in {".sql"}:
            return "SQL-скрипт"
        if ext in {".txt", ".log"}:
            return "текстовый или лог-файл"
        return "важный файл проекта"

    def collect_snapshot(self) -> dict[str, Any]:
        state = self.load_state()
        settings = state["settings"]
        ignore_dirs = set(settings.get("ignore_dirs", []))
        priority_patterns = list(settings.get("priority_patterns", []))
        focus_files = set(settings.get("focus_files", []))

        files: list[dict[str, Any]] = []
        directories: set[str] = set()
        extension_counter: dict[str, int] = {}
        root_dirs: list[dict[str, Any]] = []
        root_files: list[dict[str, Any]] = []
        excluded_tool_files: list[str] = []

        for root, dirnames, filenames in os.walk(self.project_root):
            root_path = Path(root)
            rel_root = root_path.relative_to(self.project_root)
            dirnames[:] = [d for d in dirnames if d not in ignore_dirs and not d.startswith(".")]

            for d in dirnames:
                rel_dir = (rel_root / d).as_posix()
                directories.add(rel_dir)
                if rel_root.as_posix() == ".":
                    root_dirs.append({
                        "name": d,
                        "path": d,
                        "role": self._classify_root_dir(d),
                    })

            for name in filenames:
                file_path = root_path / name
                try:
                    rel = file_path.relative_to(self.project_root).as_posix()
                except ValueError:
                    continue

                if any(part in ignore_dirs for part in Path(rel).parts):
                    continue

                if self.is_internal_tool_file(rel):
                    excluded_tool_files.append(rel)
                    continue

                stat = file_path.stat()
                ext = file_path.suffix.lower() or "<no_ext>"
                extension_counter[ext] = extension_counter.get(ext, 0) + 1

                item = {
                    "path": rel,
                    "size": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                    "extension": ext,
                    "description": self._describe_file(rel),
                    "is_priority": any(fnmatch(rel, p) or fnmatch(Path(rel).name, p) for p in priority_patterns),
                    "is_focus": rel in focus_files,
                }
                files.append(item)

                if rel_root.as_posix() == ".":
                    root_files.append({
                        "name": name,
                        "path": rel,
                        "description": self._describe_file(rel),
                    })

        files.sort(key=lambda x: x["path"])
        root_dirs.sort(key=lambda x: x["name"].lower())
        root_files.sort(key=lambda x: x["name"].lower())

        recent_files = sorted(files, key=lambda x: x["modified_at"], reverse=True)[:20]
        priority_files = [f for f in files if f["is_priority"]][:40]
        focus_file_items = [f for f in files if f["is_focus"]][:40]

        return {
            "created_at": now_iso(),
            "project_root": self.project_root.as_posix(),
            "directories": sorted(directories),
            "files": files,
            "recent_files": recent_files,
            "priority_files": priority_files,
            "focus_files": focus_file_items,
            "extension_counter": dict(sorted(extension_counter.items(), key=lambda x: (-x[1], x[0]))),
            "plan_summary": self._read_plan_summary(state),
            "root_dirs": root_dirs,
            "root_files": root_files,
            "excluded_tool_files": sorted(excluded_tool_files),
        }

    def create_snapshot_file(self, snapshot: dict[str, Any]) -> Path:
        path = self.snapshots_dir / f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        self._write_json(path, snapshot)
        return path

    def load_snapshot_files(self) -> list[Path]:
        return sorted(self.snapshots_dir.glob("snapshot_*.json"))

    def _build_snapshot_diff(self, previous: dict[str, Any], current: dict[str, Any]) -> str:
        prev_files = {item["path"]: item for item in previous.get("files", [])}
        curr_files = {item["path"]: item for item in current.get("files", [])}

        added = sorted(set(curr_files) - set(prev_files))
        removed = sorted(set(prev_files) - set(curr_files))
        changed = sorted(
            path for path in set(curr_files) & set(prev_files)
            if curr_files[path]["modified_at"] != prev_files[path]["modified_at"]
            or curr_files[path]["size"] != prev_files[path]["size"]
        )

        lines = [
            "Изменения между снимками:",
            f"- Добавлено файлов: {len(added)}",
            f"- Удалено файлов: {len(removed)}",
            f"- Изменено файлов: {len(changed)}",
        ]

        if added:
            lines.append("Добавлено:")
            lines.extend(f"  • {item}" for item in added[:25])
            if len(added) > 25:
                lines.append(f"  • ... ещё {len(added) - 25}")

        if removed:
            lines.append("Удалено:")
            lines.extend(f"  • {item}" for item in removed[:25])
            if len(removed) > 25:
                lines.append(f"  • ... ещё {len(removed) - 25}")

        if changed:
            lines.append("Изменено:")
            lines.extend(f"  • {item}" for item in changed[:25])
            if len(changed) > 25:
                lines.append(f"  • ... ещё {len(changed) - 25}")

        return "\n".join(lines)

    def diff_current(self) -> str:
        snapshot = self.collect_snapshot()
        files = self.load_snapshot_files()
        if not files:
            return "Предыдущий снимок отсутствует. Сначала выполните snapshot или export."
        previous = self._read_json(files[-1])
        return self._build_snapshot_diff(previous, snapshot)

    def _group_notes(self, notes: list[dict[str, Any]]) -> dict[str, list[str]]:
        grouped: dict[str, list[str]] = {}
        for item in notes:
            grouped.setdefault(item["note_type"], []).append(item["text"])
        return grouped

    def _join_lines(self, items: list[str] | None, fallback: str) -> str:
        if not items:
            return fallback
        return "\n".join(f"- {item}" for item in items)

    def _build_structure_text(self, snapshot: dict[str, Any]) -> str:
        lines: list[str] = []
        lines.append("Проект анализируется от корня каталога, в котором лежит collector.")
        lines.append("Служебные файлы collector и его каталоги исключены из аналитики.")
        lines.append("Корневые каталоги проекта:")

        root_dirs = snapshot.get("root_dirs", [])
        if root_dirs:
            for item in root_dirs[:40]:
                lines.append(f"- {item['name']}/ — {item['role']}")
        else:
            lines.append("- Корневые каталоги не обнаружены.")

        lines.append("Корневые файлы проекта:")
        root_files = snapshot.get("root_files", [])
        if root_files:
            for item in root_files[:40]:
                lines.append(f"- {item['path']} — {item['description']}")
        else:
            lines.append("- Корневые файлы проекта не обнаружены.")

        return "\n".join(lines)

    def _build_files_text(self, snapshot: dict[str, Any]) -> str:
        files = snapshot.get("files", [])
        priority_files = snapshot.get("priority_files", [])
        lines: list[str] = []

        if priority_files:
            lines.append("Ключевые файлы проекта:")
            for item in priority_files[:40]:
                lines.append(f"- {item['path']} | {item['extension']} | {item['description']} | {item['modified_at']}")
        else:
            lines.append("Ключевые файлы проекта пока не определены автоматически.")

        lines.append("Дополнительно обнаруженные важные файлы:")
        for item in files[:60]:
            lines.append(f"- {item['path']} | {item['extension']} | {item['description']} | {item['modified_at']}")
        if len(files) > 60:
            lines.append(f"- ... ещё {len(files) - 60} файлов проекта")

        return "\n".join(lines)

    def _build_environment_text(self, snapshot: dict[str, Any], command_notes: list[str]) -> str:
        lines: list[str] = []
        root = self.project_root

        lines.append("Автоматически определённое окружение проекта:")
        if (root / ".env").exists():
            lines.append("- Найден .env файл с локальными настройками окружения")
        if (root / "requirements.txt").exists():
            lines.append("- Найден requirements.txt: python-зависимости оформлены явно")
        if (root / "pyproject.toml").exists():
            lines.append("- Найден pyproject.toml: проект использует python-конфигурацию нового формата")
        if (root / "package.json").exists():
            lines.append("- Найден package.json: в проекте есть node/javascript-часть")
        if (root / "Dockerfile").exists():
            lines.append("- Найден Dockerfile: проект содержит docker-сборку")
        if (root / "README.md").exists():
            lines.append("- Найден README.md: в проекте есть текстовая документация")

        plan_summary = snapshot.get("plan_summary")
        if plan_summary:
            lines.append("Интеграция с планом проекта:")
            lines.append(plan_summary)

        lines.append("Базовые команды collector для работы с проектом:")
        lines.append(f'- Launcher: "{(root / "chat_migration_launcher.bat").as_posix()}"')
        lines.append(f'- Status: py -3 "{(root / "chat_migration_collector.py").as_posix()}" --project-root "{root.as_posix()}" status')
        lines.append(f'- Export: py -3 "{(root / "chat_migration_collector.py").as_posix()}" --project-root "{root.as_posix()}" export')
        lines.append(f'- Transfer: py -3 "{(root / "chat_migration_collector.py").as_posix()}" --project-root "{root.as_posix()}" transfer')
        lines.append(f'- Daily: py -3 "{(root / "chat_migration_collector.py").as_posix()}" --project-root "{root.as_posix()}" daily --type done --text "Описание шага"')

        if command_notes:
            lines.append("Ручные команды и служебные заметки:")
            lines.extend(f"- {item}" for item in command_notes)

        lines.append("Служебные данные collector:")
        lines.append(f"- Состояние и history: {(root / APP_DIR_NAME).as_posix()}")
        lines.append(f"- Stable backup: {(root / 'stable_backup').as_posix()}")

        return "\n".join(lines)

    def _build_current_state_text(self, snapshot: dict[str, Any], grouped: dict[str, list[str]]) -> str:
        lines: list[str] = []

        lines.append("Автоматически подтверждённое состояние проекта:")
        lines.append(f"- В анализе учтено {len(snapshot.get('files', []))} файлов проекта и {len(snapshot.get('directories', []))} каталогов проекта.")
        lines.append(f"- Корневых каталогов проекта обнаружено: {len(snapshot.get('root_dirs', []))}.")
        lines.append(f"- Корневых файлов проекта обнаружено: {len(snapshot.get('root_files', []))}.")
        lines.append(f"- Служебных файлов collector исключено из аналитики: {len(snapshot.get('excluded_tool_files', []))}.")

        if grouped.get("done"):
            lines.append("Что уже сделано:")
            lines.extend(f"- {item}" for item in grouped["done"])

        if grouped.get("decision"):
            lines.append("Принятые архитектурные и процессные решения:")
            lines.extend(f"- {item}" for item in grouped["decision"])

        plan_summary = snapshot.get("plan_summary")
        if plan_summary:
            lines.append("Сводка по подключённому плану проекта:")
            lines.append(plan_summary)

        if snapshot.get("recent_files"):
            lines.append("Последние важные изменения в проектных файлах:")
            for item in snapshot["recent_files"][:10]:
                lines.append(f"- {item['path']} ({item['modified_at']})")

        return "\n".join(lines)

    def _build_context_text(self, important_context: list[dict[str, Any]], snapshot: dict[str, Any], diff_text: str) -> str:
        lines: list[str] = []
        lines.append("Ключевой контекст проекта:")
        if important_context:
            lines.extend(f"- {item['text']}" for item in important_context)
        else:
            lines.append("- Важный контекст пока не заполнен вручную.")

        lines.append("Системный контекст collector:")
        lines.append("- Collector работает как инструмент анализа проекта из корня каталога.")
        lines.append("- Служебные файлы самого collector не включаются в аналитические списки проекта.")
        lines.append("- Актуальная рабочая точка проекта должна поддерживаться через notes/context/export/stable backup.")

        lines.append(diff_text)
        return "\n".join(lines)

    def _build_tasks_text(self, tasks: list[str] | None) -> str:
        if not tasks:
            return "Следующие задачи пока не зафиксированы."

        high: list[str] = []
        medium: list[str] = []
        later: list[str] = []
        standard: list[str] = []

        for item in tasks:
            lower = item.lower().strip()
            if lower.startswith("[high]") or lower.startswith("high:") or lower.startswith("!"):
                high.append(item)
            elif lower.startswith("[medium]") or lower.startswith("medium:"):
                medium.append(item)
            elif lower.startswith("[later]") or lower.startswith("later:") or lower.startswith("[low]") or lower.startswith("low:"):
                later.append(item)
            else:
                standard.append(item)

        lines: list[str] = []
        if high:
            lines.append("High priority:")
            lines.extend(f"- {item}" for item in high)
        if medium:
            lines.append("Medium priority:")
            lines.extend(f"- {item}" for item in medium)
        if standard:
            lines.append("Текущие рабочие задачи:")
            lines.extend(f"- {item}" for item in standard)
        if later:
            lines.append("Later:")
            lines.extend(f"- {item}" for item in later)

        return "\n".join(lines)

    def _read_plan_summary(self, state: dict[str, Any]) -> str | None:
        integration = state.get("settings", {}).get("integration", {})
        if not integration.get("gptmemory_plan_enabled", True):
            return None

        rel_path = integration.get("gptmemory_plan_path", default_plan_path(self.project_root))
        plan_path = self.project_root / rel_path

        if not plan_path.exists():
            return None

        if yaml is None:
            return f"- Подключён файл плана: {rel_path}"

        try:
            data = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
        except Exception:
            return f"- Подключён файл плана: {rel_path}"

        if not isinstance(data, dict):
            return f"- Подключён файл плана: {rel_path}"

        lines = [f"- Подключён файл плана: {rel_path}"]
        for key in ["project", "version", "current_stage", "status"]:
            if key in data:
                lines.append(f"- {key}: {data[key]}")
        return "\n".join(lines)

    def search_entries(self, query: str, note_type_filter: str = "all") -> list[str]:
        query = query.strip().lower()
        if not query:
            return []

        state = self.load_state()
        results: list[str] = []

        include_notes = note_type_filter in ("all", "notes")
        include_context = note_type_filter in ("all", "context")

        if include_notes:
            for item in state["notes"]:
                note_type = item.get("note_type", "")
                text = item.get("text", "")
                if note_type_filter not in ("all", "notes") and note_type != note_type_filter:
                    continue
                if query in text.lower():
                    results.append(f"[NOTE:{note_type}] {text} ({item.get('created_at', '')})")

        if include_context:
            for item in state["important_context"]:
                text = item.get("text", "")
                if query in text.lower():
                    results.append(f"[CONTEXT] {text} ({item.get('created_at', '')})")

        return results

    def status(self) -> str:
        state = self.load_state()
        snapshot = self.collect_snapshot()
        grouped = self._group_notes(state["notes"])

        lines = [
            f"Проект: {state.get('project_name') or self.project_root.name}",
            f"Цель: {state.get('project_goal') or 'не задана'}",
            f"Папок найдено: {len(snapshot['directories'])}",
            f"Файлов найдено: {len(snapshot['files'])}",
            f"Приоритетных файлов: {len(snapshot['priority_files'])}",
            f"Фокус-файлов: {len(snapshot['focus_files'])}",
            f"Заметок всего: {len(state['notes'])}",
            f"- Выполнено: {len(grouped.get('done', []))}",
            f"- Ошибки: {len(grouped.get('bug', []))}",
            f"- Исправления: {len(grouped.get('fix', []))}",
            f"- Следующие задачи: {len(grouped.get('task', []))}",
            f"- Исключено служебных файлов collector: {len(snapshot.get('excluded_tool_files', []))}",
            "Последние изменённые файлы проекта:",
        ]

        for item in snapshot["recent_files"][:5]:
            lines.append(f"  • {item['path']} ({item['modified_at']})")

        if state.get("last_stable_backup"):
            lines.append(f"Последний stable backup: {state['last_stable_backup']}")
        lines.append(f"Stable backups сохранено: {len(self.get_recent_stable_backups(9999))}")
        return "\n".join(lines)

    def export(self, auto_backup: bool = True, backup_label: str = "export") -> dict[str, str]:
        state = self.load_state()
        snapshot = self.collect_snapshot()
        files = self.load_snapshot_files()
        diff_text = self.diff_current() if files else "Предыдущий снимок отсутствует. Сначала выполните snapshot или export."
        grouped = self._group_notes(state["notes"])

        project_name = state.get("project_name") or self.project_root.name
        project_goal = state.get("project_goal") or "Цель проекта пока не заполнена вручную."

        block = f"""████████████████████████████████████████

UNIVERSAL CHAT PROJECT MIGRATION BLOCK — GENERATED

CHAT NUMBER: [новая ветка / перенос]
--- BRANCH SCHEMA ---
GLOBAL STEP 001: PROJECT NAME
{project_name}

GLOBAL STEP 002: PROJECT GOAL
{project_goal}

GLOBAL STEP 003: PROJECT STRUCTURE
{self._build_structure_text(snapshot)}

GLOBAL STEP 004: CREATED FILES
{self._build_files_text(snapshot)}

GLOBAL STEP 005: COMMANDS AND ENVIRONMENT
{self._build_environment_text(snapshot, grouped.get('command', []))}

GLOBAL STEP 006: DEBUG HISTORY
{self._join_lines(grouped.get('bug', []), 'Ошибки пока не зафиксированы.')}

GLOBAL STEP 007: FIXES APPLIED
{self._join_lines(grouped.get('fix', []), 'Исправления пока не зафиксированы.')}

GLOBAL STEP 008: CURRENT PROJECT STATE
{self._build_current_state_text(snapshot, grouped)}

GLOBAL STEP 009: IMPORTANT CONTEXT
{self._build_context_text(state.get('important_context', []), snapshot, diff_text)}

GLOBAL STEP 010: NEXT DEVELOPMENT TASKS
{self._build_tasks_text(grouped.get('task', []))}

GLOBAL STEP 011: USEFUL EXPLANATIONS / OBSERVATIONS
{self._join_lines(grouped.get('observation', []), 'Полезные наблюдения пока не зафиксированы.')}

--- CONTINUATION NOTES ---
Этот migration block построен по всему проектному каталогу от корня.
Collector выступает как внешняя утилита в корне проекта, а не как основной предмет анализа.
При продолжении в новой ветке сначала анализировать этот блок, затем выполнять новые задачи.

--- GPT META SIGNAL ---
Продолжаем этот же проект в новой ветке. Использовать этот блок как актуальную точку входа. Не начинать анализ с нуля, а опираться на текущую структуру, состояние, ошибки, исправления и следующие шаги.
"""

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        txt_path = self.exports_dir / f"migration_block_{stamp}.txt"
        json_path = self.exports_dir / f"migration_data_{stamp}.json"

        txt_path.write_text(block, encoding="utf-8")
        self._write_json(json_path, {
            "exported_at": now_iso(),
            "project_name": project_name,
            "project_goal": project_goal,
            "snapshot": snapshot,
            "state": state,
            "diff": diff_text,
            "migration_block": block,
        })

        self.create_snapshot_file(snapshot)

        state = self.load_state()
        state["export_history"].append({
            "exported_at": now_iso(),
            "txt_path": txt_path.as_posix(),
            "json_path": json_path.as_posix(),
        })
        self.save_state(state)

        backup_path = ""
        if auto_backup:
            backup_path = self.create_stable_backup(backup_label).as_posix()

        return {
            "txt_path": txt_path.as_posix(),
            "json_path": json_path.as_posix(),
            "stable_backup_path": backup_path,
        }

    def prepare_transfer_text(self) -> tuple[str, str | None]:
        files = sorted(self.exports_dir.glob("migration_block_*.txt"))
        if not files:
            return "Экспортов пока нет. Сначала выполните export.", None

        last_file = files[-1]
        content = last_file.read_text(encoding="utf-8")
        header = (
            "Ниже актуальный блок переноса проекта. "
            "Используй его как стартовую точку в новой ветке чата. "
            "Продолжай проект, не начиная анализ с нуля.\n\n"
        )
        return header + content, last_file.as_posix()

    def daily_workflow(self, note_type: str, note_text: str, context_text: str = "") -> dict[str, str]:
        self.add_note(note_type, note_text)
        if context_text.strip():
            self.add_context(context_text)

        status_text = self.status()
        snapshot = self.collect_snapshot()
        snapshot_path = self.create_snapshot_file(snapshot)

        files = self.load_snapshot_files()
        if len(files) >= 2:
            current = self._read_json(snapshot_path)
            previous = self._read_json(files[-2])
            diff_text = self._build_snapshot_diff(previous, current)
        else:
            diff_text = "Предыдущий снимок отсутствует. Сначала выполните snapshot или export."

        export_data = self.export(auto_backup=False)
        backup_path = self.create_stable_backup("daily_workflow")

        return {
            "status": status_text,
            "snapshot_path": snapshot_path.as_posix(),
            "diff": diff_text,
            "txt_path": export_data["txt_path"],
            "json_path": export_data["json_path"],
            "stable_backup_path": backup_path.as_posix(),
        }

    def launch_gui(self) -> None:
        if tk is None or ttk is None or scrolledtext is None or messagebox is None:
            raise RuntimeError("Tkinter недоступен в этой среде Python.")
        app = CollectorGUI(self)
        app.run()


class CollectorGUI:
    def __init__(self, collector: ProjectMigrationCollector) -> None:
        self.collector = collector
        self.root = tk.Tk()
        self.root.title("Chat Migration Collector / Сборщик переноса чата")
        self.root.geometry("1460x980")
        self.root.minsize(1240, 820)

        self.project_name_var = tk.StringVar()
        self.goal_var = tk.StringVar()
        self.note_type_var = tk.StringVar(value="done")
        self.note_text_var = tk.StringVar()
        self.context_text_var = tk.StringVar()
        self.search_var = tk.StringVar()
        self.search_type_var = tk.StringVar(value="all")

        self.help_expanded = False
        self._recent_export_paths: list[Path] = []
        self._recent_snapshot_paths: list[Path] = []
        self._recent_backup_paths: list[Path] = []

        self._build_ui()
        self._load_state()
        self._show_status()

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)

        self.help_frame = ttk.LabelFrame(self.root, text="Быстрая справка / Quick help", padding=10)
        self.help_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        self.help_frame.columnconfigure(0, weight=1)

        self.help_toolbar = ttk.Frame(self.help_frame)
        self.help_toolbar.grid(row=0, column=0, sticky="ew")
        self.help_toolbar.columnconfigure(0, weight=1)

        ttk.Label(
            self.help_toolbar,
            text="Collector анализирует проект от корня и не считает самого себя основным объектом анализа.",
        ).grid(row=0, column=0, sticky="w")

        self.toggle_help_button = ttk.Button(
            self.help_toolbar,
            text="Показать справку / Show help",
            command=self._toggle_help,
        )
        self.toggle_help_button.grid(row=0, column=1, sticky="e", padx=(8, 0))

        self.help_text = scrolledtext.ScrolledText(self.help_frame, wrap=tk.WORD, height=12, font=("Consolas", 10))
        self.help_text.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.help_text.insert("1.0", PROGRAM_HELP_TEXT)
        self.help_text.configure(state="disabled")
        self.help_text.grid_remove()
        self._set_help_button_text()

        top = ttk.Frame(self.root, padding=10)
        top.grid(row=1, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Project name / Название проекта:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(top, textvariable=self.project_name_var).grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(top, text="Project goal / Цель проекта:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(top, textvariable=self.goal_var).grid(row=1, column=1, sticky="ew", pady=4)

        btn_save = ttk.Button(top, text="Save", command=self._save_meta)
        btn_save.grid(row=0, column=2, rowspan=2, padx=(8, 0), pady=4, sticky="ns")
        attach_tooltip(btn_save, "Save / Сохранить\nСохранить название и цель проекта")

        mid = ttk.Frame(self.root, padding=(10, 0, 10, 0))
        mid.grid(row=2, column=0, sticky="ew")
        for i in range(4):
            mid.columnconfigure(i, weight=1)

        ttk.Label(mid, text="Note type / Тип заметки:").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Combobox(mid, textvariable=self.note_type_var, values=sorted(NOTE_TYPES), state="readonly").grid(row=0, column=1, sticky="ew", pady=4, padx=(8, 8))
        ttk.Entry(mid, textvariable=self.note_text_var).grid(row=0, column=2, sticky="ew", pady=4)

        btn_add_note = ttk.Button(mid, text="Add note", command=self._add_note)
        btn_add_note.grid(row=0, column=3, sticky="ew", padx=(8, 0), pady=4)
        attach_tooltip(btn_add_note, "Add note / Добавить заметку\nДобавить запись о шаге, задаче, решении или ошибке")

        ttk.Label(mid, text="Important context / Важный контекст:").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(mid, textvariable=self.context_text_var).grid(row=1, column=1, columnspan=2, sticky="ew", pady=4, padx=(8, 8))

        btn_add_context = ttk.Button(mid, text="Add context", command=self._add_context)
        btn_add_context.grid(row=1, column=3, sticky="ew", padx=(8, 0), pady=4)
        attach_tooltip(btn_add_context, "Add context / Добавить контекст\nДобавить важный постоянный контекст проекта")

        search_frame = ttk.LabelFrame(self.root, text="Search / Поиск", padding=10)
        search_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 6))
        for i in range(5):
            search_frame.columnconfigure(i, weight=1)

        ttk.Label(search_frame, text="Query / Запрос:").grid(row=0, column=0, sticky="w")
        ttk.Entry(search_frame, textvariable=self.search_var).grid(row=0, column=1, sticky="ew", padx=(6, 6))

        ttk.Label(search_frame, text="Type / Тип:").grid(row=0, column=2, sticky="w")
        ttk.Combobox(
            search_frame,
            textvariable=self.search_type_var,
            values=["all", "notes", "context"] + sorted(NOTE_TYPES),
            state="readonly",
        ).grid(row=0, column=3, sticky="ew", padx=(6, 6))

        btn_search = ttk.Button(search_frame, text="Search", command=self._search)
        btn_clear = ttk.Button(search_frame, text="Clear", command=self._clear_search)
        btn_search.grid(row=0, column=4, sticky="ew", padx=(6, 3))
        btn_clear.grid(row=1, column=4, sticky="ew", padx=(6, 3), pady=(6, 0))
        attach_tooltip(btn_search, "Search / Поиск\nИскать по заметкам и контексту")
        attach_tooltip(btn_clear, "Clear / Очистить\nОчистить поиск и вернуть статус")

        buttons = ttk.Frame(self.root, padding=10)
        buttons.grid(row=4, column=0, sticky="ew")
        for i in range(5):
            buttons.columnconfigure(i, weight=1)

        btn_quick = ttk.Button(buttons, text="Quick", command=self._quick_setup)
        btn_status = ttk.Button(buttons, text="Status", command=self._show_status)
        btn_export = ttk.Button(buttons, text="Export", command=self._export)
        btn_transfer = ttk.Button(buttons, text="Transfer", command=self._transfer)
        btn_daily = ttk.Button(buttons, text="Daily", command=self._daily)

        btn_backup = ttk.Button(buttons, text="Backup", command=self._stable_backup)
        btn_last_export = ttk.Button(buttons, text="Last export", command=self._open_selected_export)
        btn_last_snapshot = ttk.Button(buttons, text="Last snap", command=self._open_selected_snapshot)
        btn_last_backup = ttk.Button(buttons, text="Last backup", command=self._open_selected_backup)
        btn_refresh = ttk.Button(buttons, text="Refresh", command=self._refresh_recent_lists)

        btn_quick.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        btn_status.grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        btn_export.grid(row=0, column=2, sticky="ew", padx=4, pady=4)
        btn_transfer.grid(row=0, column=3, sticky="ew", padx=4, pady=4)
        btn_daily.grid(row=0, column=4, sticky="ew", padx=4, pady=4)

        btn_backup.grid(row=1, column=0, sticky="ew", padx=4, pady=4)
        btn_last_export.grid(row=1, column=1, sticky="ew", padx=4, pady=4)
        btn_last_snapshot.grid(row=1, column=2, sticky="ew", padx=4, pady=4)
        btn_last_backup.grid(row=1, column=3, sticky="ew", padx=4, pady=4)
        btn_refresh.grid(row=1, column=4, sticky="ew", padx=4, pady=4)

        attach_tooltip(btn_quick, "Quick setup / Быстрая настройка\nПервичная настройка collector под текущий проект")
        attach_tooltip(btn_status, "Status / Статус\nПоказать текущее состояние проекта")
        attach_tooltip(btn_export, "Export / Экспорт\nСоздать migration block и JSON")
        attach_tooltip(btn_transfer, "Transfer / Перенос\nПоказать готовый текст для нового чата")
        attach_tooltip(btn_daily, "Daily workflow / Ежедневная работа\nЗаметка + snapshot + export + stable backup")
        attach_tooltip(btn_backup, "Stable backup / Резервная точка\nСоздать контрольную копию")
        attach_tooltip(btn_last_export, "Open selected export / Открыть выбранный export")
        attach_tooltip(btn_last_snapshot, "Open selected snapshot / Открыть выбранный snapshot")
        attach_tooltip(btn_last_backup, "Open selected stable backup / Открыть выбранный stable backup")
        attach_tooltip(btn_refresh, "Refresh / Обновить\nОбновить списки последних файлов")

        recent_frame = ttk.LabelFrame(self.root, text="Latest files / Последние файлы", padding=10)
        recent_frame.grid(row=5, column=0, sticky="ew", padx=10, pady=(0, 6))
        recent_frame.columnconfigure(0, weight=1)
        recent_frame.columnconfigure(1, weight=1)
        recent_frame.columnconfigure(2, weight=1)

        export_frame = ttk.Frame(recent_frame)
        export_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        export_frame.columnconfigure(0, weight=1)
        ttk.Label(export_frame, text="Latest exports / Последние exports").grid(row=0, column=0, sticky="w")
        self.exports_listbox = tk.Listbox(export_frame, height=6, exportselection=False)
        self.exports_listbox.grid(row=1, column=0, sticky="ew", pady=(4, 4))
        self.exports_listbox.bind("<Double-1>", self._on_export_double_click)

        snapshot_frame = ttk.Frame(recent_frame)
        snapshot_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 6))
        snapshot_frame.columnconfigure(0, weight=1)
        ttk.Label(snapshot_frame, text="Latest snapshots / Последние snapshots").grid(row=0, column=0, sticky="w")
        self.snapshots_listbox = tk.Listbox(snapshot_frame, height=6, exportselection=False)
        self.snapshots_listbox.grid(row=1, column=0, sticky="ew", pady=(4, 4))
        self.snapshots_listbox.bind("<Double-1>", self._on_snapshot_double_click)

        backup_frame = ttk.Frame(recent_frame)
        backup_frame.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        backup_frame.columnconfigure(0, weight=1)
        ttk.Label(backup_frame, text="Latest backups / Последние backups").grid(row=0, column=0, sticky="w")
        self.backups_listbox = tk.Listbox(backup_frame, height=6, exportselection=False)
        self.backups_listbox.grid(row=1, column=0, sticky="ew", pady=(4, 4))
        self.backups_listbox.bind("<Double-1>", self._on_backup_double_click)

        self.output = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, font=("Consolas", 10))
        self.output.grid(row=6, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.root.rowconfigure(6, weight=1)

        self.output.tag_config("done_line", foreground="#0a7a0a")
        self.output.tag_config("bug_line", foreground="#c62828")
        self.output.tag_config("task_line", foreground="#b26a00")
        self.output.tag_config("backup_line", foreground="#1565c0")
        self.output.tag_config("title_line", foreground="#4a148c")
        self.output.tag_config("section_line", foreground="#006064")

    def _set_help_button_text(self) -> None:
        if self.help_expanded:
            self.toggle_help_button.configure(text="Скрыть справку / Hide help")
        else:
            self.toggle_help_button.configure(text="Показать справку / Show help")

    def _toggle_help(self) -> None:
        self.help_expanded = not self.help_expanded
        if self.help_expanded:
            self.help_text.grid()
        else:
            self.help_text.grid_remove()
        self._set_help_button_text()

    def _load_state(self) -> None:
        state = self.collector.load_state()
        self.project_name_var.set(state.get("project_name", ""))
        self.goal_var.set(state.get("project_goal", ""))
        self._refresh_recent_lists()

    def _refresh_recent_lists(self) -> None:
        self.exports_listbox.delete(0, tk.END)
        self.snapshots_listbox.delete(0, tk.END)
        self.backups_listbox.delete(0, tk.END)

        self._recent_export_paths = self.collector.get_recent_exports(10)
        self._recent_snapshot_paths = self.collector.get_recent_snapshots(10)
        self._recent_backup_paths = self.collector.get_recent_stable_backups(10)

        for path in self._recent_export_paths:
            self.exports_listbox.insert(tk.END, path.name)
        for path in self._recent_snapshot_paths:
            self.snapshots_listbox.insert(tk.END, path.name)
        for path in self._recent_backup_paths:
            self.backups_listbox.insert(tk.END, path.name)

    def _write_output(self, text: str, colorize_status: bool = False) -> None:
        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, text)
        if colorize_status:
            self._apply_status_tags()

    def _apply_status_tags(self) -> None:
        content = self.output.get("1.0", tk.END).splitlines()
        for idx, line in enumerate(content, start=1):
            start = f"{idx}.0"
            end = f"{idx}.end"
            if line.startswith("Проект:") or line.startswith("Цель:"):
                self.output.tag_add("title_line", start, end)
            elif line.startswith("Последние изменённые файлы"):
                self.output.tag_add("section_line", start, end)
            elif line.startswith("- Выполнено:"):
                self.output.tag_add("done_line", start, end)
            elif line.startswith("- Ошибки:"):
                self.output.tag_add("bug_line", start, end)
            elif line.startswith("- Следующие задачи:"):
                self.output.tag_add("task_line", start, end)
            elif line.startswith("Последний stable backup:") or line.startswith("Stable backups сохранено:"):
                self.output.tag_add("backup_line", start, end)

    def _save_meta(self) -> None:
        self.collector.init_project(
            project_name=self.project_name_var.get().strip() or None,
            goal=self.goal_var.get().strip() or None,
        )
        self._show_status()

    def _add_note(self) -> None:
        text = self.note_text_var.get().strip()
        if not text:
            if messagebox:
                messagebox.showwarning("Внимание", "Введите текст заметки.")
            return
        self.collector.add_note(self.note_type_var.get(), text)
        self.note_text_var.set("")
        self._show_status()

    def _add_context(self) -> None:
        text = self.context_text_var.get().strip()
        if not text:
            if messagebox:
                messagebox.showwarning("Внимание", "Введите важный контекст.")
            return
        self.collector.add_context(text)
        self.context_text_var.set("")
        self._show_status()

    def _quick_setup(self) -> None:
        state = self.collector.quick_setup(
            project_name=self.project_name_var.get().strip() or None,
            goal=self.goal_var.get().strip() or None,
            plan_path=default_plan_path(self.collector.project_root),
        )
        text = "Быстрая первичная настройка завершена.\n\n" + json.dumps(state, ensure_ascii=False, indent=2)
        self._write_output(text)
        self._refresh_recent_lists()

    def _show_status(self) -> None:
        self._write_output(self.collector.status(), colorize_status=True)
        self._refresh_recent_lists()

    def _export(self) -> None:
        data = self.collector.export(auto_backup=True, backup_label="export")
        text = (
            f"Экспорт завершён.\nTXT:  {data['txt_path']}\nJSON: {data['json_path']}\n"
            f"Stable backup: {data['stable_backup_path']}\n\n"
            + Path(data["txt_path"]).read_text(encoding="utf-8")
        )
        self._write_output(text)
        self._refresh_recent_lists()

    def _transfer(self) -> None:
        text, path = self.collector.prepare_transfer_text()
        if path:
            text = f"Источник: {path}\n\n{text}"
        self._write_output(text)

    def _daily(self) -> None:
        text = self.note_text_var.get().strip()
        if not text:
            if messagebox:
                messagebox.showwarning("Внимание", "Введите текст заметки для Daily.")
            return
        result = self.collector.daily_workflow(
            note_type=self.note_type_var.get(),
            note_text=text,
            context_text=self.context_text_var.get().strip(),
        )
        self.note_text_var.set("")
        self.context_text_var.set("")
        out = (
            "Ежедневный workflow завершён.\n\n"
            + result["status"]
            + "\n\nSnapshot: " + result["snapshot_path"]
            + "\n\n" + result["diff"]
            + "\n\nTXT export: " + result["txt_path"]
            + "\nJSON export: " + result["json_path"]
            + "\nStable backup: " + result["stable_backup_path"]
        )
        self._write_output(out, colorize_status=True)
        self._refresh_recent_lists()

    def _stable_backup(self) -> None:
        path = self.collector.create_stable_backup("manual_gui")
        self._write_output("Stable backup создан:\n" + path.as_posix())
        self._refresh_recent_lists()

    def _open_selected_export(self) -> None:
        sel = self.exports_listbox.curselection()
        if not sel:
            if messagebox:
                messagebox.showinfo("Export", "Сначала выбери export из списка.")
            return
        path = self._recent_export_paths[sel[0]]
        open_path_in_system(path)
        self._write_output("Открыт export:\n" + path.as_posix())

    def _open_selected_snapshot(self) -> None:
        sel = self.snapshots_listbox.curselection()
        if not sel:
            if messagebox:
                messagebox.showinfo("Snapshot", "Сначала выбери snapshot из списка.")
            return
        path = self._recent_snapshot_paths[sel[0]]
        open_path_in_system(path)
        self._write_output("Открыт snapshot:\n" + path.as_posix())

    def _open_selected_backup(self) -> None:
        sel = self.backups_listbox.curselection()
        if not sel:
            if messagebox:
                messagebox.showinfo("Backup", "Сначала выбери stable backup из списка.")
            return
        path = self._recent_backup_paths[sel[0]]
        open_path_in_system(path)
        self._write_output("Открыт stable backup:\n" + path.as_posix())

    def _on_export_double_click(self, _event=None) -> None:
        self._open_selected_export()

    def _on_snapshot_double_click(self, _event=None) -> None:
        self._open_selected_snapshot()

    def _on_backup_double_click(self, _event=None) -> None:
        self._open_selected_backup()

    def _search(self) -> None:
        query = self.search_var.get().strip()
        note_type_filter = self.search_type_var.get().strip() or "all"
        if not query:
            if messagebox:
                messagebox.showinfo("Поиск", "Введите запрос для поиска.")
            return
        results = self.collector.search_entries(query, note_type_filter)
        if not results:
            self._write_output("По запросу ничего не найдено.")
            return
        self._write_output("Результаты поиска:\n\n" + "\n".join(results))

    def _clear_search(self) -> None:
        self.search_var.set("")
        self.search_type_var.set("all")
        self._show_status()

    def run(self) -> None:
        self.root.mainloop()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="chat_migration_collector",
        description="Универсальный collector для сбора состояния проекта и переноса в новый чат.",
    )
    parser.add_argument("--project-root", default=".", help="Путь к корню проекта.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    p_init = subparsers.add_parser("init")
    p_init.add_argument("--name")
    p_init.add_argument("--goal")

    p_note = subparsers.add_parser("note")
    p_note.add_argument("--type", required=True, choices=sorted(NOTE_TYPES))
    p_note.add_argument("--text", required=True)

    p_context = subparsers.add_parser("context")
    p_context.add_argument("--text", required=True)

    p_settings = subparsers.add_parser("settings")
    p_settings.add_argument("--add-focus-file")
    p_settings.add_argument("--add-priority-pattern")
    p_settings.add_argument("--add-ignore-dir")
    p_settings.add_argument("--keep-last-stable-backups", type=int)
    p_settings.add_argument("--gptmemory-plan-path")

    p_quick = subparsers.add_parser("quick-setup")
    p_quick.add_argument("--name")
    p_quick.add_argument("--goal")
    p_quick.add_argument("--plan-path", default=None)

    p_daily = subparsers.add_parser("daily")
    p_daily.add_argument("--type", required=True, choices=sorted(NOTE_TYPES))
    p_daily.add_argument("--text", required=True)
    p_daily.add_argument("--context", default="")

    p_search = subparsers.add_parser("search")
    p_search.add_argument("--query", required=True)
    p_search.add_argument("--type", default="all")

    subparsers.add_parser("status")
    subparsers.add_parser("snapshot")
    subparsers.add_parser("diff")
    subparsers.add_parser("export")
    subparsers.add_parser("transfer")
    subparsers.add_parser("stable-backup")
    subparsers.add_parser("open-latest-export")
    subparsers.add_parser("open-latest-snapshot")
    subparsers.add_parser("open-latest-stable-backup")
    subparsers.add_parser("gui")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    collector = ProjectMigrationCollector(Path(args.project_root))

    try:
        if args.command == "init":
            collector.init_project(project_name=args.name, goal=args.goal)
            print("Инициализация завершена.")
            print(f"Файл состояния: {collector.state_file.as_posix()}")
            return 0

        if args.command == "note":
            collector.add_note(args.type, args.text)
            print("Заметка добавлена.")
            return 0

        if args.command == "context":
            collector.add_context(args.text)
            print("Контекст добавлен.")
            return 0

        if args.command == "settings":
            settings = collector.update_settings(
                add_focus_file=args.add_focus_file,
                add_priority_pattern=args.add_priority_pattern,
                add_ignore_dir=args.add_ignore_dir,
                keep_last_stable_backups=args.keep_last_stable_backups,
                gptmemory_plan_path=args.gptmemory_plan_path,
            )
            print("Настройки обновлены:")
            print(json.dumps(settings, ensure_ascii=False, indent=2))
            return 0

        if args.command == "quick-setup":
            state = collector.quick_setup(project_name=args.name, goal=args.goal, plan_path=args.plan_path)
            print("Быстрая первичная настройка завершена.")
            print(json.dumps(state, ensure_ascii=False, indent=2))
            if state.get("last_stable_backup"):
                print("Stable backup:", state["last_stable_backup"])
            return 0

        if args.command == "daily":
            result = collector.daily_workflow(note_type=args.type, note_text=args.text, context_text=args.context)
            print("Ежедневный workflow завершён.")
            print(result["status"])
            print()
            print("Snapshot:", result["snapshot_path"])
            print(result["diff"])
            print("TXT export:", result["txt_path"])
            print("JSON export:", result["json_path"])
            print("Stable backup:", result["stable_backup_path"])
            return 0

        if args.command == "search":
            results = collector.search_entries(args.query, args.type)
            if not results:
                print("По запросу ничего не найдено.")
            else:
                print("\n".join(results))
            return 0

        if args.command == "status":
            print(collector.status())
            return 0

        if args.command == "snapshot":
            snapshot = collector.collect_snapshot()
            path = collector.create_snapshot_file(snapshot)
            print(f"Снимок сохранён: {path.as_posix()}")
            return 0

        if args.command == "diff":
            print(collector.diff_current())
            return 0

        if args.command == "export":
            data = collector.export(auto_backup=True, backup_label="export")
            print("Экспорт завершён.")
            print(f"TXT:  {data['txt_path']}")
            print(f"JSON: {data['json_path']}")
            if data["stable_backup_path"]:
                print(f"Stable backup: {data['stable_backup_path']}")
            return 0

        if args.command == "transfer":
            text, path = collector.prepare_transfer_text()
            if path:
                print(f"Источник: {path}")
                print()
            print(text)
            return 0

        if args.command == "stable-backup":
            path = collector.create_stable_backup("manual_cli")
            print(f"Stable backup создан: {path.as_posix()}")
            return 0

        if args.command == "open-latest-export":
            print(collector.open_latest_export())
            return 0

        if args.command == "open-latest-snapshot":
            print(collector.open_latest_snapshot())
            return 0

        if args.command == "open-latest-stable-backup":
            print(collector.open_latest_stable_backup())
            return 0

        if args.command == "gui":
            collector.launch_gui()
            return 0

        parser.print_help()
        return 1

    except Exception as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''.lstrip("\n")

LAUNCHER_CODE = r'''@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

title Chat Migration Collector Launcher
color 0A

set "LOCAL_COLLECTOR=%~dp0chat_migration_collector.py"
for %%I in ("%~dp0.") do set "PROJECT_ROOT=%%~fI"

set "PYTHON_EXE="
where py >nul 2>&1
if not errorlevel 1 set "PYTHON_EXE=py -3"
if not defined PYTHON_EXE (
    where python >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=python"
)
if not defined PYTHON_EXE (
    echo.
    echo [ОШИБКА] Не найден Python в PATH.
    pause
    exit /b 1
)

if not exist "%LOCAL_COLLECTOR%" (
    echo.
    echo [ОШИБКА] Не найден файл chat_migration_collector.py рядом с launcher.
    echo Ожидаемый путь:
    echo %LOCAL_COLLECTOR%
    pause
    exit /b 1
)

:menu
cls
echo ================================================
echo   CHAT MIGRATION COLLECTOR / СБОРЩИК ПЕРЕНОСА ЧАТА
echo ================================================
echo.
echo Этот инструмент лежит в корне проекта и собирает состояние всего проекта,
echo а не самого себя. Служебные файлы collector исключаются из аналитики.
echo.
echo Быстрые действия:
echo [H] Help / Помощь
echo [1] GUI / Интерфейс
echo [3] Daily / Ежедневная работа
echo [7] Export / Экспорт
echo [8] Transfer / Перенос
echo [13] Backup / Stable backup
echo [14] Last export / Последний export
echo [15] Last snapshot / Последний snapshot
echo [16] Last backup / Последний backup
echo.
echo Python:
echo %PYTHON_EXE%
echo.
echo Collector file:
echo %LOCAL_COLLECTOR%
echo.
echo Current project root:
echo %PROJECT_ROOT%
echo.
echo [1] GUI / Интерфейс
echo [2] Quick setup / Быстрая настройка
echo [3] Daily / Ежедневная работа
echo [4] Status / Статус
echo [5] Snapshot / Снимок
echo [6] Diff / Изменения
echo [7] Export / Экспорт
echo [8] Transfer / Перенос
echo [9] Change root / Сменить путь
echo [10] Open exports / Открыть exports
echo [11] Open snapshots / Открыть snapshots
echo [12] Reset root / Сбросить путь
echo [13] Backup now / Создать backup
echo [14] Last export / Последний export
echo [15] Last snapshot / Последний snapshot
echo [16] Last backup / Последний backup
echo [0] Exit / Выход
echo.
set /p CHOICE=Выбери пункт меню: 

if /I "%CHOICE%"=="H" goto show_help
if "%CHOICE%"=="1" goto gui
if "%CHOICE%"=="2" goto quicksetup
if "%CHOICE%"=="3" goto daily
if "%CHOICE%"=="4" goto status
if "%CHOICE%"=="5" goto snapshot
if "%CHOICE%"=="6" goto diff
if "%CHOICE%"=="7" goto export
if "%CHOICE%"=="8" goto transfer
if "%CHOICE%"=="9" goto change_root
if "%CHOICE%"=="10" goto open_exports
if "%CHOICE%"=="11" goto open_snapshots
if "%CHOICE%"=="12" goto reset_root
if "%CHOICE%"=="13" goto stable_backup
if "%CHOICE%"=="14" goto open_latest_export
if "%CHOICE%"=="15" goto open_latest_snapshot
if "%CHOICE%"=="16" goto open_latest_backup
if "%CHOICE%"=="0" goto end
goto menu

:show_help
cls
echo ================================================================
echo   HELP / ПОМОЩЬ
echo ================================================================
echo.
echo Для чего нужна программа:
echo - собирать состояние проекта от корня каталога
echo - хранить notes, context, snapshot, export и stable backup
echo - формировать сильный migration block для нового чата
echo.
echo Важно:
echo - collector лежит в корне проекта как утилита
echo - collector не является основным объектом анализа
echo - .gptcollector, stable_backup и migration utility files не входят в аналитические разделы
echo.
echo Быстрый старт:
echo 1. [2] Quick setup
echo 2. [3] Daily
echo 3. [7] Export
echo 4. [8] Transfer
echo.
pause
goto menu

:gui
cls
echo === GUI / Интерфейс ===
call :run_collector gui
goto return_menu

:quicksetup
cls
echo === QUICK SETUP / БЫСТРАЯ НАСТРОЙКА ===
set /p QS_NAME=Название проекта [%~n0]: 
if "%QS_NAME%"=="" set "QS_NAME=%~n0"
set /p QS_GOAL=Цель проекта [Сбор состояния проекта и перенос в новый чат]: 
if "%QS_GOAL%"=="" set "QS_GOAL=Сбор состояния проекта и перенос в новый чат"
set /p QS_PLAN=Путь к файлу плана [GPTMemory_plan.yaml]: 
if "%QS_PLAN%"=="" set "QS_PLAN=GPTMemory_plan.yaml"
call :run_collector quick-setup --name "%QS_NAME%" --goal "%QS_GOAL%" --plan-path "%QS_PLAN%"
goto return_menu

:daily
cls
echo === DAILY / ЕЖЕДНЕВНАЯ РАБОТА ===
echo.
echo Допустимые типы:
echo goal, decision, task, done, bug, fix, context, command, observation
echo.
set /p D_TYPE=Тип заметки: 
if "%D_TYPE%"=="" (
    echo Тип заметки обязателен.
    goto return_menu
)
set /p D_TEXT=Текст заметки: 
if "%D_TEXT%"=="" (
    echo Текст заметки обязателен.
    goto return_menu
)
set /p D_CONTEXT=Дополнительный контекст [можно пусто]: 
call :run_collector daily --type "%D_TYPE%" --text "%D_TEXT%" --context "%D_CONTEXT%"
goto return_menu

:status
cls
echo === STATUS / СТАТУС ===
call :run_collector status
goto return_menu

:snapshot
cls
echo === SNAPSHOT / СНИМОК ===
call :run_collector snapshot
goto return_menu

:diff
cls
echo === DIFF / ИЗМЕНЕНИЯ ===
call :run_collector diff
goto return_menu

:export
cls
echo === EXPORT / ЭКСПОРТ ===
call :run_collector export
goto return_menu

:transfer
cls
echo === TRANSFER / ПЕРЕНОС ===
call :run_collector transfer
goto return_menu

:stable_backup
cls
echo === STABLE BACKUP / СОЗДАТЬ BACKUP ===
call :run_collector stable-backup
goto return_menu

:open_latest_export
cls
echo === LAST EXPORT / ПОСЛЕДНИЙ EXPORT ===
call :run_collector open-latest-export
goto return_menu

:open_latest_snapshot
cls
echo === LAST SNAPSHOT / ПОСЛЕДНИЙ SNAPSHOT ===
call :run_collector open-latest-snapshot
goto return_menu

:open_latest_backup
cls
echo === LAST BACKUP / ПОСЛЕДНИЙ BACKUP ===
call :run_collector open-latest-stable-backup
goto return_menu

:change_root
cls
echo === CHANGE ROOT / СМЕНИТЬ ПУТЬ ===
echo Текущий путь:
echo %PROJECT_ROOT%
echo.
set /p NEW_ROOT=Новый путь к проекту: 
if "%NEW_ROOT%"=="" goto menu
if not exist "%NEW_ROOT%" (
    echo Указанный путь не существует.
    goto return_menu
)
for %%I in ("%NEW_ROOT%") do set "PROJECT_ROOT=%%~fI"
echo Новый project root установлен:
echo %PROJECT_ROOT%
goto return_menu

:reset_root
for %%I in ("%~dp0.") do set "PROJECT_ROOT=%%~fI"
echo Project root сброшен на папку launcher:
echo %PROJECT_ROOT%
goto return_menu

:open_exports
set "EXPORT_DIR=%PROJECT_ROOT%\.gptcollector\exports"
if not exist "%EXPORT_DIR%" (
    echo Папка exports пока не существует:
    echo %EXPORT_DIR%
    goto return_menu
)
start "" "%EXPORT_DIR%"
goto menu

:open_snapshots
set "SNAP_DIR=%PROJECT_ROOT%\.gptcollector\snapshots"
if not exist "%SNAP_DIR%" (
    echo Папка snapshots пока не существует:
    echo %SNAP_DIR%
    goto return_menu
)
start "" "%SNAP_DIR%"
goto menu

:return_menu
echo.
pause
goto menu

:run_collector
pushd "%PROJECT_ROOT%" >nul
call %PYTHON_EXE% "%LOCAL_COLLECTOR%" --project-root "%PROJECT_ROOT%" %*
set "RUN_ERR=%ERRORLEVEL%"
popd >nul
echo.
if not "%RUN_ERR%"=="0" (
    echo [ОШИБКА] Код возврата: %RUN_ERR%
)
exit /b %RUN_ERR%

:end
endlocal
exit /b 0
'''

def backup_file(path: Path) -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        return
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"{path.name}.generic_root_mode_{stamp}.bak"
    shutil.copy2(path, backup_path)
    print(f"[OK] Backup created: {backup_path}")

def write_text(path: Path, text: str, newline: str = "\n") -> None:
    path.write_text(text, encoding="utf-8", newline=newline)
    print(f"[OK] Written: {path}")

def normalize_state() -> None:
    if not STATE_PATH.exists():
        return
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8", errors="ignore"))
    except Exception as exc:
        print(f"[WARN] Could not normalize state file: {exc}")
        return

    settings = data.setdefault("settings", {})
    settings.setdefault("ignore_dirs", sorted([
        ".git", ".idea", ".mypy_cache", ".pytest_cache", ".ruff_cache",
        ".venv", ".vscode", "__pycache__", "build", "dist", "env",
        "node_modules", "venv", ".gptcollector", "stable_backup"
    ]))
    settings.setdefault("tool_file_patterns", [
        "chat_migration_collector.py",
        "chat_migration_launcher.bat",
        "*migration*collector*.py",
        "*migration*launcher*.bat",
        "*migration*.ps1",
        "restore_from_stable_backup.py",
        "make_stable_backup.py",
        "upgrade_*migration*.py",
        "rebuild_*migration*.py",
        "fix_*migration*.py",
        "cleanup_*migration*.py",
        "populate_*migration*.py",
    ])
    settings.setdefault("priority_patterns", [
        "README.md", "pyproject.toml", "requirements.txt", "package.json",
        "package-lock.json", "pnpm-lock.yaml", "yarn.lock", ".env",
        "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
        "GPTMemory_plan.yaml", "GPTMemoryPlan.yaml", "main.py", "app.py",
        "manage.py", "index.js", "server.js", "*.py", "*.md", "*.json",
        "*.yaml", "*.yml", "*.toml"
    ])
    settings.setdefault("focus_files", [])
    settings.setdefault("keep_last_stable_backups", 10)

    integration = settings.setdefault("integration", {})
    if (PROJECT_ROOT / "GPTMemory_plan.yaml").exists():
        integration["gptmemory_plan_path"] = "GPTMemory_plan.yaml"
    elif (PROJECT_ROOT / "GPTMemoryPlan.yaml").exists():
        integration["gptmemory_plan_path"] = "GPTMemoryPlan.yaml"

    data.setdefault("last_stable_backup", "")
    STATE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    print(f"[OK] State normalized: {STATE_PATH}")

def syntax_check_python(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    compile(source, str(path), "exec")
    print(f"[OK] Python syntax check passed: {path}")

def run_check(args: list[str]) -> None:
    print()
    print(">", " ".join(args))
    result = subprocess.run(args, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        raise SystemExit(result.returncode)

def main() -> int:
    print(f"Project root: {PROJECT_ROOT}")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    backup_file(COLLECTOR_PATH)
    backup_file(LAUNCHER_PATH)

    collector_text = textwrap.dedent(COLLECTOR_CODE)
    launcher_text = LAUNCHER_CODE.replace("\r\n", "\n")

    write_text(COLLECTOR_PATH, collector_text, newline="\n")
    write_text(LAUNCHER_PATH, launcher_text, newline="\r\n")

    syntax_check_python(COLLECTOR_PATH)
    normalize_state()

    py = sys.executable
    run_check([py, str(COLLECTOR_PATH), "--project-root", str(PROJECT_ROOT), "status"])
    run_check([py, str(COLLECTOR_PATH), "--project-root", str(PROJECT_ROOT), "export"])

    print()
    print("[DONE] Generic root-project collector rebuild completed successfully.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())