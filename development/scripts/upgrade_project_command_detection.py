from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Development GPTMEAi")
COLLECTOR_PATH = PROJECT_ROOT / "chat_migration_collector.py"
STATE_PATH = PROJECT_ROOT / ".gptcollector" / "project_notes.json"
BACKUP_DIR = PROJECT_ROOT / ".gptcollector" / "backups"


SECTION_REPLACEMENT = r'''
    def _read_package_scripts(self, package_json_path: Path) -> list[str]:
        try:
            data = json.loads(package_json_path.read_text(encoding="utf-8"))
        except Exception:
            return []

        scripts = data.get("scripts", {})
        if not isinstance(scripts, dict):
            return []

        return [str(key) for key in scripts.keys()]

    def _detect_project_runtime_environment(self) -> list[str]:
        root = self.project_root
        lines: list[str] = []

        if (root / ".env").exists():
            lines.append("- Найден .env файл с локальными настройками окружения")

        if (root / "requirements.txt").exists():
            lines.append("- Найден requirements.txt: python-зависимости оформлены явно")

        if (root / "pyproject.toml").exists():
            lines.append("- Найден pyproject.toml: проект использует современную python-конфигурацию")

        if (root / "package.json").exists():
            lines.append("- Найден package.json в корне: в проекте есть node/javascript-часть")

        if (root / "apps" / "dashboard" / "package.json").exists():
            lines.append("- Найден apps/dashboard/package.json: у проекта есть отдельный dashboard/frontend-модуль")

        if (root / "dashboard" / "package.json").exists():
            lines.append("- Найден dashboard/package.json: у проекта есть отдельный dashboard/frontend-модуль")

        if (root / "Dockerfile").exists():
            lines.append("- Найден Dockerfile: проект поддерживает docker-сборку")

        if (root / "docker-compose.yml").exists() or (root / "docker-compose.yaml").exists():
            lines.append("- Найден docker-compose файл: проект поддерживает многосервисный запуск")

        if (root / "README.md").exists():
            lines.append("- Найден README.md: в проекте есть текстовая документация")

        return lines

    def _detect_python_project_commands(self) -> list[str]:
        root = self.project_root
        commands: list[str] = []

        if (root / "requirements.txt").exists():
            commands.append('- Установка python-зависимостей: py -3 -m pip install -r requirements.txt')

        if (root / "pyproject.toml").exists():
            commands.append('- Установка проекта в editable-режиме: py -3 -m pip install -e .')

        python_entry_candidates = [
            ("main.py", 'py -3 "main.py"', "вероятная главная python-точка входа"),
            ("app.py", 'py -3 "app.py"', "вероятная точка входа приложения"),
            ("manage.py", 'py -3 "manage.py" runserver', "типичный Django-style запуск"),
            ("scripts/api_server.py", 'py -3 "scripts/api_server.py"', "вероятный запуск API-сервера"),
            ("GPTMemoryEngine/run_gptmemory.py", 'py -3 "GPTMemoryEngine/run_gptmemory.py"', "запуск основного GPTMemory-модуля"),
            ("cognitive_loop_auto_scale.py", 'py -3 "cognitive_loop_auto_scale.py"', "запуск auto-scale цикла"),
            ("cognitive_loop_auto_scale_live.py", 'py -3 "cognitive_loop_auto_scale_live.py"', "запуск live auto-scale цикла"),
        ]

        for rel_path, cmd, desc in python_entry_candidates:
            if (root / rel_path).exists():
                commands.append(f"- {desc}: {cmd}")

        return commands

    def _detect_node_project_commands(self) -> list[str]:
        root = self.project_root
        commands: list[str] = []

        package_dirs = [
            root,
            root / "apps" / "dashboard",
            root / "dashboard",
        ]

        for package_dir in package_dirs:
            package_json = package_dir / "package.json"
            if not package_json.exists():
                continue

            rel_dir = package_dir.relative_to(root).as_posix()
            prefix = "" if rel_dir == "." else f'cd "{rel_dir}" && '

            if (package_dir / "pnpm-lock.yaml").exists():
                manager = "pnpm"
                install_cmd = f"{prefix}pnpm install"
            elif (package_dir / "yarn.lock").exists():
                manager = "yarn"
                install_cmd = f"{prefix}yarn install"
            else:
                manager = "npm"
                install_cmd = f"{prefix}npm install"

            label = "корень проекта" if rel_dir == "." else rel_dir
            commands.append(f"- Установка frontend/node-зависимостей ({label}): {install_cmd}")

            script_names = self._read_package_scripts(package_json)
            preferred_order = ["dev", "start", "build", "preview", "test", "lint"]

            def make_run_command(script_name: str) -> str:
                if manager == "pnpm":
                    return f"{prefix}pnpm {script_name}"
                if manager == "yarn":
                    return f"{prefix}yarn {script_name}"
                return f"{prefix}npm run {script_name}"

            for script_name in preferred_order:
                if script_name in script_names:
                    commands.append(
                        f"- Команда {script_name} для {label}: {make_run_command(script_name)}"
                    )

            other_scripts = [name for name in script_names if name not in preferred_order]
            for script_name in other_scripts[:8]:
                commands.append(
                    f"- Дополнительная script-команда {script_name} для {label}: {make_run_command(script_name)}"
                )

        return commands

    def _detect_docker_commands(self) -> list[str]:
        root = self.project_root
        commands: list[str] = []
        project_slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", root.name).lower() or "project"

        if (root / "Dockerfile").exists():
            commands.append(f"- Docker build: docker build -t {project_slug} .")

        if (root / "docker-compose.yml").exists() or (root / "docker-compose.yaml").exists():
            commands.append("- Docker compose: docker compose up --build")

        return commands

    def _detect_project_commands(self) -> list[str]:
        raw_commands: list[str] = []
        raw_commands.extend(self._detect_python_project_commands())
        raw_commands.extend(self._detect_node_project_commands())
        raw_commands.extend(self._detect_docker_commands())

        unique: list[str] = []
        seen: set[str] = set()
        for item in raw_commands:
            if item not in seen:
                seen.add(item)
                unique.append(item)
        return unique

    def _collector_commands(self) -> list[str]:
        root = self.project_root
        return [
            f'- Launcher: "{(root / "chat_migration_launcher.bat").as_posix()}"',
            f'- Status: py -3 "{(root / "chat_migration_collector.py").as_posix()}" --project-root "{root.as_posix()}" status',
            f'- Export: py -3 "{(root / "chat_migration_collector.py").as_posix()}" --project-root "{root.as_posix()}" export',
            f'- Transfer: py -3 "{(root / "chat_migration_collector.py").as_posix()}" --project-root "{root.as_posix()}" transfer',
            f'- Daily: py -3 "{(root / "chat_migration_collector.py").as_posix()}" --project-root "{root.as_posix()}" daily --type done --text "Описание шага"',
        ]

    def _build_environment_text(self, snapshot: dict[str, Any], command_notes: list[str]) -> str:
        lines: list[str] = []

        lines.append("Автоматически определённое окружение проекта:")
        env_lines = self._detect_project_runtime_environment()
        if env_lines:
            lines.extend(env_lines)
        else:
            lines.append("- Явные файлы окружения автоматически не определены")

        plan_summary = snapshot.get("plan_summary")
        if plan_summary:
            lines.append("Интеграция с планом проекта:")
            lines.append(plan_summary)

        project_commands = self._detect_project_commands()
        lines.append("Вероятные рабочие команды самого проекта (определены автоматически по структуре и конфигурации):")
        if project_commands:
            lines.extend(project_commands)
        else:
            lines.append("- Явные команды проекта автоматически не определены; требуется ручное добавление note type=command")

        if command_notes:
            lines.append("Ручные команды и заметки пользователя:")
            lines.extend(f"- {item}" for item in command_notes)

        lines.append("Команды collector для сопровождения и переноса проекта:")
        lines.extend(self._collector_commands())

        lines.append("Служебные данные collector:")
        lines.append(f"- Состояние и history: {(self.project_root / APP_DIR_NAME).as_posix()}")
        lines.append(f"- Stable backup: {(self.project_root / 'stable_backup').as_posix()}")

        return "\n".join(lines)
'''


EXTRA_TOOL_PATTERNS = [
    "chat_migration_collector.py",
    "chat_migration_launcher.bat",
    "fix_*.py",
    "upgrade_*.py",
    "rebuild_*.py",
    "restore_*.py",
    "cleanup_*.py",
    "compact_*.py",
    "split_*.py",
    "polish_*.py",
    "populate_*.py",
    "remove_bom*.py",
    "make_stable_backup.py",
    "auto_fix_*.py",
    "final_*fix*.py",
    "finish_*cleanup*.py",
    "*header_help*.py",
    "add_open_latest_buttons.py",
    "fix_missing_refresh_recent_lists.py",
    "upgrade_gui_latest_lists_and_compact_buttons.py",
    "rebuild_full_gui_suite.py",
    "rebuild_generic_root_project_collector.py",
    "refine_generic_export_quality.py",
    "upgrade_project_command_detection.py",
]


def backup_file(path: Path) -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = BACKUP_DIR / f"{path.name}.project_command_detection_{stamp}.bak"
    shutil.copy2(path, dst)
    print(f"[OK] Backup created: {dst}")


def update_state_patterns() -> None:
    if not STATE_PATH.exists():
        print(f"[SKIP] State file not found: {STATE_PATH}")
        return

    data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    settings = data.setdefault("settings", {})
    patterns = settings.setdefault("tool_file_patterns", [])

    added = 0
    for pattern in EXTRA_TOOL_PATTERNS:
        if pattern not in patterns:
            patterns.append(pattern)
            added += 1

    data["updated_at"] = datetime.now().isoformat(timespec="seconds")
    STATE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    print(f"[OK] State updated: {STATE_PATH}")
    print(f"[OK] tool_file_patterns added: {added}")


def replace_method_block(text: str) -> str:
    start_marker = "    def _build_environment_text(self, snapshot: dict[str, Any], command_notes: list[str]) -> str:\n"
    end_marker = "    def _build_current_state_text(self, snapshot: dict[str, Any], grouped: dict[str, list[str]]) -> str:\n"

    start = text.find(start_marker)
    if start == -1:
        raise RuntimeError("Could not find _build_environment_text() start marker.")

    end = text.find(end_marker, start)
    if end == -1:
        raise RuntimeError("Could not find _build_current_state_text() marker after _build_environment_text().")

    return text[:start] + SECTION_REPLACEMENT + "\n\n" + text[end:]


def main() -> int:
    print(f"Project root: {PROJECT_ROOT}")

    if not COLLECTOR_PATH.exists():
        print(f"[ERROR] Collector not found: {COLLECTOR_PATH}")
        return 1

    backup_file(COLLECTOR_PATH)
    if STATE_PATH.exists():
        backup_file(STATE_PATH)

    text = COLLECTOR_PATH.read_text(encoding="utf-8", errors="ignore")
    original = text

    text = replace_method_block(text)
    COLLECTOR_PATH.write_text(text, encoding="utf-8", newline="\n")

    try:
        compile(text, str(COLLECTOR_PATH), "exec")
    except Exception as exc:
        COLLECTOR_PATH.write_text(original, encoding="utf-8", newline="\n")
        print(f"[ERROR] Syntax check failed: {exc}")
        print("[OK] Original collector restored.")
        return 1

    print(f"[OK] Collector upgraded: {COLLECTOR_PATH}")
    print("[OK] Python syntax check passed.")

    update_state_patterns()

    py = sys.executable

    for cmd in [
        [py, str(COLLECTOR_PATH), "--project-root", str(PROJECT_ROOT), "status"],
        [py, str(COLLECTOR_PATH), "--project-root", str(PROJECT_ROOT), "export"],
    ]:
        print()
        print(">", " ".join(cmd))
        result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
        if result.returncode != 0:
            return result.returncode

    print()
    print("[DONE] Project command detection upgrade completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())