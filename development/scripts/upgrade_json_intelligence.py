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


DESCRIBE_BLOCK = r'''
    def _safe_json_keys_preview(self, path: Path, max_size: int = 2 * 1024 * 1024) -> list[str]:
        try:
            if not path.exists() or path.stat().st_size > max_size:
                return []
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return [str(k) for k in list(data.keys())[:8]]
            if isinstance(data, list):
                if data and isinstance(data[0], dict):
                    return [str(k) for k in list(data[0].keys())[:8]]
                return ["<list>"]
        except Exception:
            return []
        return []

    def _describe_json_file(self, rel_path: str) -> str:
        rel_lower = rel_path.lower()
        name = Path(rel_path).name.lower()
        full_path = self.project_root / rel_path

        chat_markers = [
            "chat", "chats", "conversation", "dialog", "messages",
            "migration block", "all_chats", "history"
        ]
        report_markers = [
            "report", "status", "log", "snapshot", "export",
            "analysis", "result", "test_log"
        ]
        config_markers = [
            "config", "settings", "runtime", "plan", "meta", "manifest", "index"
        ]
        memory_markers = [
            "memory", "knowledge", "embedding", "vector", "parsed", "index"
        ]

        if any(marker in rel_lower for marker in ["memory/chats", "chat", "all_chats", "conversation", "messages"]):
            return "архив чатов / история проекта"

        if any(marker in rel_lower for marker in report_markers):
            return "отчёт, лог или снимок состояния проекта"

        if any(marker in rel_lower for marker in config_markers):
            return "конфигурация, статус или состояние проекта"

        if any(marker in rel_lower for marker in memory_markers):
            return "данные памяти, знаний или индекса проекта"

        keys = self._safe_json_keys_preview(full_path)
        keys_lower = [k.lower() for k in keys]

        if any(k in keys_lower for k in ["messages", "conversation", "chat", "history"]):
            return "структурированный архив переписки или истории"

        if any(k in keys_lower for k in ["status", "errors", "results", "report", "summary"]):
            return "структурированный отчёт или лог проекта"

        if any(k in keys_lower for k in ["project", "settings", "config", "runtime", "plan"]):
            return "структурированная конфигурация или состояние проекта"

        if any(k in keys_lower for k in ["memory", "knowledge", "embeddings", "index", "nodes"]):
            return "структурированные данные памяти или знаний проекта"

        return "структурированные данные проекта"

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

        if ext == ".json":
            return self._describe_json_file(rel_path)

        if ext == ".py":
            return "python-модуль проекта"
        if ext in {".md"}:
            return "документация или текстовый отчёт"
        if ext in {".yaml", ".yml", ".toml"}:
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
'''

FILES_TEXT_BLOCK = r'''
    def _group_json_files_for_export(self, snapshot: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        groups = {
            "chat_archives": [],
            "reports_logs": [],
            "config_state": [],
            "memory_data": [],
            "other_json": [],
        }

        for item in snapshot.get("files", []):
            if item.get("extension") != ".json":
                continue

            desc = (item.get("description") or "").lower()
            if "архив чатов" in desc or "переписки" in desc or "истории" in desc:
                groups["chat_archives"].append(item)
            elif "отчёт" in desc or "лог" in desc or "снимок состояния" in desc:
                groups["reports_logs"].append(item)
            elif "конфигурация" in desc or "состояние проекта" in desc or "статус" in desc:
                groups["config_state"].append(item)
            elif "памяти" in desc or "знаний" in desc or "индекса" in desc:
                groups["memory_data"].append(item)
            else:
                groups["other_json"].append(item)

        for key in groups:
            groups[key] = sorted(groups[key], key=lambda x: x["modified_at"], reverse=True)
        return groups

    def _build_files_text(self, snapshot: dict[str, Any]) -> str:
        files = snapshot.get("files", [])
        priority_files = snapshot.get("priority_files", [])
        json_groups = self._group_json_files_for_export(snapshot)

        lines: list[str] = []

        if priority_files:
            lines.append("Ключевые файлы проекта:")
            for item in priority_files[:40]:
                lines.append(
                    f"- {item['path']} | {item['extension']} | {item['description']} | {item['modified_at']}"
                )
        else:
            lines.append("Ключевые файлы проекта пока не определены автоматически.")

        lines.append("JSON-файлы проекта, потенциально важные для извлечения информации:")
        group_titles = [
            ("chat_archives", "Архивы чатов и истории проекта"),
            ("reports_logs", "Отчёты, логи и снимки состояния"),
            ("config_state", "Конфигурация и состояние проекта"),
            ("memory_data", "Данные памяти, знаний и индекса"),
            ("other_json", "Прочие JSON-данные проекта"),
        ]

        has_any_json = False
        for group_key, title in group_titles:
            items = json_groups[group_key]
            if not items:
                continue
            has_any_json = True
            lines.append(title + ":")
            for item in items[:12]:
                lines.append(
                    f"- {item['path']} | {item['description']} | {item['modified_at']}"
                )

        if not has_any_json:
            lines.append("- JSON-файлы проекта не обнаружены или не попали в аналитическую выборку.")

        lines.append("Дополнительно обнаруженные важные файлы:")
        for item in files[:60]:
            lines.append(
                f"- {item['path']} | {item['extension']} | {item['description']} | {item['modified_at']}"
            )
        if len(files) > 60:
            lines.append(f"- ... ещё {len(files) - 60} файлов проекта")

        return "\n".join(lines)
'''


def backup_file(path: Path, tag: str) -> None:
    if not path.exists():
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = BACKUP_DIR / f"{path.name}.{tag}_{stamp}.bak"
    shutil.copy2(path, dst)
    print(f"[OK] Backup created: {dst}")


def replace_block(text: str, start_marker: str, end_marker: str, replacement: str) -> str:
    start = text.find(start_marker)
    if start == -1:
        raise RuntimeError(f"Start marker not found: {start_marker!r}")
    end = text.find(end_marker, start)
    if end == -1:
        raise RuntimeError(f"End marker not found: {end_marker!r}")
    return text[:start] + replacement + "\n\n" + text[end:]


def patch_collector() -> None:
    original = COLLECTOR_PATH.read_text(encoding="utf-8", errors="ignore")
    text = original

    text = replace_block(
        text,
        "    def _describe_file(self, rel_path: str) -> str:\n",
        "    def collect_snapshot(self) -> dict[str, Any]:\n",
        DESCRIBE_BLOCK,
    )

    text = replace_block(
        text,
        "    def _build_files_text(self, snapshot: dict[str, Any]) -> str:\n",
        "    def _build_environment_text(self, snapshot: dict[str, Any], command_notes: list[str]) -> str:\n",
        FILES_TEXT_BLOCK,
    )

    try:
        compile(text, str(COLLECTOR_PATH), "exec")
    except Exception as exc:
        print(f"[ERROR] Syntax check failed: {exc}")
        raise

    COLLECTOR_PATH.write_text(text, encoding="utf-8", newline="\n")
    print(f"[OK] Collector upgraded: {COLLECTOR_PATH}")


def enrich_state() -> None:
    if not STATE_PATH.exists():
        print(f"[SKIP] State file not found: {STATE_PATH}")
        return

    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    notes = state.setdefault("notes", [])
    contexts = state.setdefault("important_context", [])

    def ensure_note(note_type: str, text: str) -> None:
        for item in notes:
            if item.get("note_type") == note_type and item.get("text") == text:
                return
        notes.append({
            "note_type": note_type,
            "text": text,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        })

    def ensure_context(text: str) -> None:
        for item in contexts:
            if item.get("text") == text:
                return
        contexts.append({
            "text": text,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        })

    ensure_note(
        "decision",
        "Для универсального collector все *.json считаются потенциально полезными для анализа; исключение делается по пути и роли файла, а не по расширению."
    )
    ensure_note(
        "observation",
        "JSON-файлы проекта нужно оценивать по содержимому и назначению: архивы чатов, отчёты, конфигурация, memory/knowledge data и прочие структурированные данные."
    )
    ensure_task = "[MEDIUM] Добавить ещё более глубокое извлечение структуры из крупных JSON: top-level keys, тип содержимого, пример полей и роль файла без вывода полного содержимого."
    ensure_note("task", ensure_task)
    ensure_context(
        "Универсальная логика collector: любые JSON-файлы проекта потенциально информативны; служебный шум надо отсекать по каталогам и шаблонам имён, а не по расширению .json."
    )

    state["updated_at"] = datetime.now().isoformat(timespec="seconds")
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    print(f"[OK] State updated: {STATE_PATH}")


def run_cmd(args: list[str]) -> None:
    print()
    print(">", " ".join(args))
    result = subprocess.run(args, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> int:
    print(f"Project root: {PROJECT_ROOT}")

    if not COLLECTOR_PATH.exists():
        print(f"[ERROR] Collector not found: {COLLECTOR_PATH}")
        return 1

    backup_file(COLLECTOR_PATH, "json_intelligence")
    backup_file(STATE_PATH, "json_intelligence")

    patch_collector()
    enrich_state()

    py = sys.executable
    run_cmd([py, str(COLLECTOR_PATH), "--project-root", str(PROJECT_ROOT), "status"])
    run_cmd([py, str(COLLECTOR_PATH), "--project-root", str(PROJECT_ROOT), "export"])

    print()
    print("[DONE] JSON intelligence upgrade completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())