
from __future__ import annotations

import re
import shutil
import sys
import py_compile
from datetime import datetime
from pathlib import Path
from textwrap import dedent


NEW_BLOCK = dedent(
    r"""
    def _note_texts(self, note_type: str, limit: int = 8) -> list[str]:
        notes = [item for item in self.load_state()["notes"] if item.get("note_type") == note_type]
        notes.sort(key=lambda item: (int(item.get("importance", 1)), item.get("created_at", "")), reverse=True)
        return [str(item.get("text", "")).strip() for item in notes[:limit] if str(item.get("text", "")).strip()]

    def _notes_full(self, note_type: str, limit: int = 20) -> list[dict[str, Any]]:
        notes = [item for item in self.load_state()["notes"] if item.get("note_type") == note_type]
        notes.sort(key=lambda item: (int(item.get("importance", 1)), item.get("created_at", "")), reverse=True)
        return notes[:limit]

    def _branch_status(self, state: dict[str, Any]) -> tuple[str, str]:
        tasks_count = sum(1 for item in state.get("notes", []) if item.get("note_type") == "task")
        bugs_count = sum(1 for item in state.get("notes", []) if item.get("note_type") == "bug")
        fixes_count = sum(1 for item in state.get("notes", []) if item.get("note_type") == "fix")
        done_count = sum(1 for item in state.get("notes", []) if item.get("note_type") == "done")
        if bugs_count > fixes_count:
            return "stabilization", "Есть незакрытые проблемы; ветка требует стабилизации перед переносом."
        if tasks_count > 0:
            return "active-development", "Ветка рабочая: есть зафиксированные следующие задачи и активное развитие."
        if done_count > 0:
            return "migration-ready", "Основной результат ветки уже зафиксирован; перенос в новый чат можно делать без повторного анализа с нуля."
        return "draft", "Ветка пока в базовом состоянии; контекст собран частично."

    def _bucket_tasks(self, tasks: list[str]) -> dict[str, list[str]]:
        buckets = {"HIGH": [], "MEDIUM": [], "LATER": []}
        high_keywords = [
            "ошиб", "fix", "исправ", "critical", "экспорт", "export", "migration block",
            "перенос", "реальной структуре", "проверить", "stabil", "слом", "bug",
        ]
        later_keywords = ["потом", "later", "когда-нибудь", "в будущем", "опцион", "nice to have"]
        for text in tasks:
            low = text.lower()
            if any(word in low for word in high_keywords):
                buckets["HIGH"].append(text)
            elif any(word in low for word in later_keywords):
                buckets["LATER"].append(text)
            else:
                buckets["MEDIUM"].append(text)
        return buckets

    def _group_key_files_by_role(self, snapshot: dict[str, Any]) -> dict[str, list[str]]:
        groups: dict[str, list[str]] = {
            "entry_points": [],
            "ui_files": [],
            "plan_and_config": [],
            "memory_and_storage": [],
            "automation_and_tools": [],
            "docs_and_notes": [],
            "runtime_and_logs": [],
            "other_key_files": [],
        }
        important_files = [
            item for item in snapshot["files"]
            if item.get("is_priority") or item.get("is_focus")
        ]
        for item in important_files:
            path = item["path"]
            name = Path(path).name.lower()
            low = path.lower()
            if name in {"main.py", "app.py", "run.py", "manage.py"} or "launcher" in low:
                groups["entry_points"].append(path)
            elif any(part in low for part in ["gui", "dashboard", "frontend", "ui"]):
                groups["ui_files"].append(path)
            elif any(part in low for part in ["plan", ".env", "requirements", "pyproject", "package.json", "dockerfile", "docker-compose", "runtime.yaml", "runtime_backup"]):
                groups["plan_and_config"].append(path)
            elif any(part in low for part in ["memory", "storage", "vector", "db", "sqlite", "runtime/", "logs/"]):
                groups["memory_and_storage"].append(path)
            elif any(part in low for part in ["migration", "collector", "launcher", "cleanup", "script", "scripts/"]):
                groups["automation_and_tools"].append(path)
            elif any(part in low for part in ["readme", ".md", "note", "docs/"]):
                groups["docs_and_notes"].append(path)
            elif any(part in low for part in ["runtime", "log"]):
                groups["runtime_and_logs"].append(path)
            else:
                groups["other_key_files"].append(path)
        for key, values in groups.items():
            groups[key] = sorted(normalize_list_unique(values))[:20]
        return groups

    def _architecture_map(self, snapshot: dict[str, Any]) -> list[str]:
        lines: list[str] = []
        root_dirs = snapshot.get("root_directories", [])
        if not root_dirs:
            lines.append("- Корневые каталоги пока не обнаружены.")
            return lines
        for item in root_dirs[:30]:
            name = item["name"]
            role = item.get("role", "подсистема проекта")
            lines.append(f"- {name}/ — {role}")
        return lines

    def _evidence_sources(self, snapshot: dict[str, Any], state: dict[str, Any], plan_path: str | None, plan_data: dict[str, Any] | None, diff_text: str | None) -> list[str]:
        lines = [
            f"- notes: {len(state.get('notes', []))}",
            f"- important_context: {len(state.get('important_context', []))}",
            f"- file_scan: {snapshot['counts']['files']} файлов, {snapshot['counts']['directories']} каталогов",
            f"- priority_files: {snapshot['counts']['priority_files']}",
            f"- focus_files: {snapshot['counts']['focus_files']}",
        ]
        snapshots_count = len(self._list_snapshots())
        lines.append(f"- snapshots: {snapshots_count}")
        if diff_text and not diff_text.startswith("Недостаточно"):
            lines.append("- last_diff: доступен")
        else:
            lines.append("- last_diff: пока нет или недостаточно snapshot")
        if plan_path:
            lines.append(f"- gptmemory_plan_path: {plan_path}")
        if plan_data:
            lines.append("- gptmemory_plan_data: загружены структурированные данные")
        else:
            lines.append("- gptmemory_plan_data: не загружены или файл не найден")
        if snapshot.get("detected_commands"):
            lines.append(f"- detected_commands: {len(snapshot['detected_commands'])}")
        return lines

    def _top_risks(self, snapshot: dict[str, Any], state: dict[str, Any], plan_data: dict[str, Any] | None, diff_text: str | None) -> list[str]:
        risks: list[str] = []
        if not plan_data:
            risks.append("Файл плана не прочитан автоматически; часть выводов строится только по scan/notes/context.")
        if diff_text and diff_text.startswith("Изменения между снимками: diff пока не сформирован"):
            risks.append("История изменений между snapshot пока слабая; стоит накопить минимум два snapshot для надёжного diff.")
        if snapshot["counts"]["focus_files"] == 0:
            risks.append("Не заданы focus_files; важные файлы проекта могут теряться в общем списке.")
        if snapshot["counts"]["priority_files"] < 5:
            risks.append("Приоритетные шаблоны пока покрывают мало файлов; архитектурная сводка может быть неполной.")
        if any(item.get("note_type") == "bug" for item in state.get("notes", [])) and not any(item.get("note_type") == "fix" for item in state.get("notes", [])):
            risks.append("Есть bug-заметки без явной цепочки fix; новая ветка может переоценить стабильность программы.")
        if not state.get("important_context"):
            risks.append("Важный контекст почти не заполнен; перенос будет зависеть в основном от структуры файлов.")
        if not risks:
            risks.append("Критичных архитектурных рисков по текущему export не обнаружено; блок готов для переноса.")
        return risks[:8]

    def _build_migration_block(self, snapshot: dict[str, Any], diff_text: str | None = None) -> str:
        state = self.load_state()
        plan_path, plan_data = self._load_plan_data(state)
        status_code, status_text = self._branch_status(state)

        tasks = self._note_texts("task", 12)
        done = self._note_texts("done", 12)
        bugs = self._note_texts("bug", 12)
        fixes = self._note_texts("fix", 12)
        decisions = self._note_texts("decision", 12)
        commands_notes = self._note_texts("command", 12)
        observations = self._note_texts("observation", 12)
        important_context = [str(item.get("text", "")).strip() for item in state.get("important_context", []) if str(item.get("text", "")).strip()]
        key_files = self._group_key_files_by_role(snapshot)
        task_buckets = self._bucket_tasks(tasks)
        risks = self._top_risks(snapshot, state, plan_data, diff_text)

        lines: list[str] = []
        lines.append("████████████████████████████████████████")
        lines.append("")
        lines.append("UNIVERSAL CHAT PROJECT MIGRATION BLOCK — GENERATED V3")
        lines.append("")
        lines.append("CHAT NUMBER: [новая ветка / перенос]")
        lines.append("--- BRANCH SCHEMA ---")

        lines.append("GLOBAL STEP 001: PROJECT NAME")
        lines.append(str(state.get("project_name")))
        lines.append("")

        lines.append("GLOBAL STEP 002: PROJECT GOAL")
        lines.append(str(state.get("project_goal")))
        lines.append("")

        lines.append("GLOBAL STEP 003: BRANCH ROLE AND STATUS")
        lines.append(f"Branch status: {status_code}")
        lines.append(status_text)
        lines.append("Эта ветка должна восприниматься как рабочая точка входа для продолжения, а не как повод пересобирать анализ проекта с нуля.")
        lines.append("")

        lines.append("GLOBAL STEP 004: PROJECT ARCHITECTURE MAP")
        lines.append("Проект анализируется от корня каталога, в котором лежит collector.")
        lines.append("Служебные файлы collector и его каталоги исключены из основной аналитики.")
        for item in self._architecture_map(snapshot):
            lines.append(item)
        if snapshot.get("root_files"):
            lines.append("Ключевые корневые файлы:")
            for item in snapshot["root_files"][:30]:
                lines.append(f"- {item['name']} — {item['description']}")
        lines.append("")

        lines.append("GLOBAL STEP 005: KEY FILES BY ROLE")
        role_titles = {
            "entry_points": "Entry points",
            "ui_files": "UI / dashboard",
            "plan_and_config": "Plan / config / env",
            "memory_and_storage": "Memory / storage / runtime",
            "automation_and_tools": "Automation / collector tools",
            "docs_and_notes": "Docs / notes",
            "runtime_and_logs": "Runtime / logs",
            "other_key_files": "Other key files",
        }
        for key, title in role_titles.items():
            values = key_files.get(key, [])
            if not values:
                continue
            lines.append(f"{title}:")
            for path in values:
                lines.append(f"- {path}")
        lines.append("")

        lines.append("GLOBAL STEP 006: EVIDENCE SOURCES")
        lines.append("Блок собран не из одного summary, а из нескольких источников фактов:")
        for item in self._evidence_sources(snapshot, state, plan_path, plan_data, diff_text):
            lines.append(item)
        lines.append("")

        lines.append("GLOBAL STEP 007: DECISIONS / BUGS / FIXES CHAIN")
        if decisions:
            lines.append("Decisions:")
            for item in decisions:
                lines.append(f"- {item}")
        if bugs:
            lines.append("Bugs:")
            for item in bugs:
                lines.append(f"- {item}")
        if fixes:
            lines.append("Fixes:")
            for item in fixes:
                lines.append(f"- {item}")
        if not decisions and not bugs and not fixes:
            lines.append("- Явные decision/bug/fix цепочки пока почти не заполнены.")
        lines.append("")

        lines.append("GLOBAL STEP 008: COMMANDS AND ENVIRONMENT")
        if (self.project_root / ".env").exists():
            lines.append("- [verified] Найден .env файл с локальными настройками окружения.")
        if any(item["path"].endswith("package.json") for item in snapshot["files"]):
            lines.append("- [verified] Найдены Node/frontend-модули с package.json.")
        if any(Path(item["path"]).name in {"Dockerfile", "docker-compose.yml", "docker-compose.yaml"} for item in snapshot["files"]):
            lines.append("- [verified] Найдены Docker-конфигурации.")
        if plan_path:
            lines.append(f"- [verified] Подключён путь к плану: {plan_path}")
        if plan_data:
            interesting_keys = [str(key) for key in list(plan_data.keys())[:12]]
            if interesting_keys:
                lines.append(f"- [verified] В плане найдены ключи: {', '.join(interesting_keys)}")
        lines.append("Вероятные рабочие команды проекта:")
        for command in snapshot.get("detected_commands", [])[:20]:
            lines.append(f"- {command}")
        if commands_notes:
            lines.append("Ручные команды и заметки пользователя:")
            for item in commands_notes:
                lines.append(f"- {item}")
        lines.append("")

        lines.append("GLOBAL STEP 009: CURRENT PROJECT STATE")
        lines.append(self.status_report())
        if done:
            lines.append("Ключевые выполненные шаги:")
            for item in done:
                lines.append(f"- {item}")
        if diff_text:
            lines.append("Последний diff:")
            lines.append(diff_text)
        lines.append("")

        lines.append("GLOBAL STEP 010: IMPORTANT CONTEXT")
        if important_context:
            for item in important_context[-15:]:
                lines.append(f"- {item}")
        else:
            lines.append("- Важный контекст пока почти не заполнен.")
        lines.append("")

        lines.append("GLOBAL STEP 011: NEXT DEVELOPMENT TASKS")
        for bucket in ["HIGH", "MEDIUM", "LATER"]:
            values = task_buckets.get(bucket, [])
            if not values:
                continue
            lines.append(f"[{bucket}]")
            for item in values:
                lines.append(f"- {item}")
        if not tasks:
            lines.append("- Следующие задачи пока не заполнены.")
        lines.append("")

        lines.append("GLOBAL STEP 012: RISKS / WEAK POINTS")
        for item in risks:
            lines.append(f"- {item}")
        if observations:
            lines.append("Дополнительные наблюдения:")
            for item in observations[:10]:
                lines.append(f"- {item}")
        lines.append("")

        lines.append("GLOBAL STEP 013: TRANSFER STARTER")
        lines.append("В новой ветке нужно продолжать проект от этой точки, а не повторно анализировать всё с самого начала.")
        lines.append("Сначала опирайся на CURRENT PROJECT STATE, IMPORTANT CONTEXT, NEXT DEVELOPMENT TASKS и KEY FILES BY ROLE.")
        lines.append("Если файл слегка сломан — делай точечный автоскрипт; если collector снова станет перегружен патчами — делай чистую пересборку файла, а не новый слой ремонта.")
        lines.append("")

        lines.append("--- GPT META SIGNAL ---")
        lines.append("Используй этот блок как стартовую точку в новой ветке. Не начинай анализ проекта с нуля.")
        lines.append("")
        return "\n".join(lines)
    """
).strip("\n")


def main() -> int:
    project_root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
    collector_path = project_root / "chat_migration_collector.py"

    if not collector_path.exists():
        print(f"[ERROR] Collector not found: {collector_path}")
        return 1

    source = collector_path.read_text(encoding="utf-8")
    pattern = r"    def _note_texts\(self, note_type: str, limit: int = 8\) -> list\[str\]:.*?^    def export\(self\) -> tuple\[str, str, dict\[str, Any\]\]:"
    replacement = "    " + NEW_BLOCK.replace("\n", "\n    ") + "\n\n    def export(self) -> tuple[str, str, dict[str, Any]]:"

    new_source, count = re.subn(pattern, lambda m: replacement, source, flags=re.S | re.M)
    if count != 1:
        print("[ERROR] Patch anchor not found or ambiguous. The collector file structure differs from the expected v2 layout.")
        return 2

    backup_dir = project_root / ".gptcollector" / "backups" / "architecture_v3"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"chat_migration_collector_before_v3_{stamp}.py"
    shutil.copy2(collector_path, backup_path)

    collector_path.write_text(new_source, encoding="utf-8", newline="\n")
    py_compile.compile(str(collector_path), cfile=str(project_root / ".gptcollector" / f"collector_v3_{stamp}.pyc"), doraise=True)

    print("[OK] Migration block architecture upgraded to V3.")
    print(f"[BACKUP] {backup_path}")
    print(f"[UPDATED] {collector_path}")
    print()
    print("Next commands:")
    print(f'py -3 "{collector_path}" --project-root "{project_root}" export')
    print(f'py -3 "{collector_path}" --project-root "{project_root}" transfer')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
