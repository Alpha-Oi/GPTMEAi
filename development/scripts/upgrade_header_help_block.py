from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Development GPTMEAi")
BACKUP_DIR = PROJECT_ROOT / ".gptcollector" / "backups"
COLLECTOR_PATH = PROJECT_ROOT / "chat_migration_collector.py"
LAUNCHER_PATH = PROJECT_ROOT / "chat_migration_launcher.bat"


GUI_HELP_BLOCK = """ЭТА ПРОГРАММА / WHAT THIS PROGRAM DOES

Эта программа нужна для:
- фиксации прогресса по проекту
- сохранения важных решений, задач, ошибок и исправлений
- создания migration block для переноса проекта в новый чат
- сохранения snapshot и export истории
- создания stable backup после важных этапов

КНОПКИ / BUTTONS

Quick setup / Быстрая настройка
- первичная настройка программы для проекта
- записывает базовый контекст
- настраивает путь к плану проекта
- создаёт stable backup

Status / Статус
- показывает текущее состояние проекта
- число файлов, заметок, задач, последние изменения

Export / Экспорт
- создаёт migration block и JSON архив
- нужен для переноса проекта в новый чат
- автоматически создаёт stable backup

Transfer / Перенос
- показывает готовый текст для вставки в новый чат
- нужен когда старая ветка чата начинает тормозить

Daily workflow / Ежедневная работа
- добавляет новую заметку
- делает snapshot
- делает export
- автоматически создаёт stable backup

Stable backup / Stable backup
- создаёт контрольную резервную копию рабочей версии
- нужна как точка отката после важных изменений

Save / Сохранить
- сохраняет название проекта и цель проекта

Add note / Добавить заметку
- добавляет запись о проделанной работе, ошибке, решении или задаче

Add context / Добавить контекст
- добавляет важный постоянный контекст проекта

Exit / Выход
- закрывает программу
"""

LAUNCHER_HELP_BLOCK = r'''echo ================================================================
echo   CHAT MIGRATION COLLECTOR / СБОРЩИК ПЕРЕНОСА ЧАТА
echo ================================================================
echo.
echo Для чего нужна программа:
echo - фиксировать прогресс по проекту
echo - сохранять задачи, решения, ошибки и исправления
echo - создавать export для переноса проекта в новый чат
echo - сохранять stable backup после важных этапов
echo.
echo Что делают кнопки:
echo [1] GUI / Интерфейс               - открыть графическое окно программы
echo [2] Quick setup / Быстрая настройка - первичная настройка проекта
echo [3] Daily workflow / Ежедневная работа - добавить заметку, snapshot, export, stable backup
echo [4] Status / Статус               - показать текущее состояние проекта
echo [5] Snapshot / Снимок             - сохранить снимок текущего состояния
echo [6] Diff / Изменения              - сравнить изменения со снимком
echo [7] Export / Экспорт              - создать migration block и JSON архив
echo [8] Transfer text / Текст переноса - показать готовый текст для нового чата
echo [9] Change project root / Сменить путь проекта - указать другой корень проекта
echo [10] Open exports / Открыть exports - открыть папку с export файлами
echo [11] Open snapshots / Открыть snapshots - открыть папку со snapshot
echo [12] Reset project root / Сбросить путь проекта - вернуть путь на папку launcher
echo [13] Stable backup now / Создать stable backup - вручную создать stable backup
echo [0] Exit / Выход                  - закрыть launcher
echo.
'''

def backup_file(path: Path) -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        return
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = BACKUP_DIR / f"{path.name}.header_help_upgrade_{stamp}.bak"
    shutil.copy2(path, dst)
    print(f"[OK] Backup created: {dst}")

def patch_collector() -> None:
    if not COLLECTOR_PATH.exists():
        raise FileNotFoundError(f"Collector not found: {COLLECTOR_PATH}")

    text = COLLECTOR_PATH.read_text(encoding="utf-8", errors="ignore")
    original = text

    old_title = 'self.root.title("Chat Migration Collector / Сборщик переноса чата")'
    new_title = 'self.root.title("Chat Migration Collector / Сборщик переноса чата")'
    text = text.replace(old_title, new_title)

    old_build_ui_anchor = '        top = ttk.Frame(self.root, padding=10)\n        top.grid(row=0, column=0, sticky="ew")\n        top.columnconfigure(1, weight=1)\n'
    new_build_ui_anchor = '''        help_frame = ttk.LabelFrame(self.root, text="Описание программы / Program description", padding=10)
        help_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        help_frame.columnconfigure(0, weight=1)

        self.help_text = scrolledtext.ScrolledText(help_frame, wrap=tk.WORD, height=16, font=("Consolas", 10))
        self.help_text.grid(row=0, column=0, sticky="ew")
        self.help_text.insert("1.0", PROGRAM_HELP_TEXT)
        self.help_text.configure(state="disabled")

        top = ttk.Frame(self.root, padding=10)
        top.grid(row=1, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)
'''
    if old_build_ui_anchor in text:
        text = text.replace(old_build_ui_anchor, new_build_ui_anchor, 1)

    text = text.replace('        mid.grid(row=1, column=0, sticky="ew")', '        mid.grid(row=2, column=0, sticky="ew")')
    text = text.replace('        buttons.grid(row=2, column=0, sticky="ew")', '        buttons.grid(row=3, column=0, sticky="ew")')
    text = text.replace('        self.output.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))', '        self.output.grid(row=4, column=0, sticky="nsew", padx=10, pady=(0, 10))')
    text = text.replace('        self.root.rowconfigure(3, weight=1)', '        self.root.rowconfigure(4, weight=1)')

    if 'PROGRAM_HELP_TEXT =' not in text:
        insert_after = 'DEFAULT_PRIORITY_PATTERNS = [\n'
        idx = text.find(insert_after)
        if idx == -1:
            raise RuntimeError("Could not find insertion point for PROGRAM_HELP_TEXT")
        end_idx = text.find(']\n\n', idx)
        if end_idx == -1:
            raise RuntimeError("Could not find end of DEFAULT_PRIORITY_PATTERNS")
        end_idx += 3
        program_help = '\nPROGRAM_HELP_TEXT = """' + GUI_HELP_BLOCK + '"""\n\n'
        text = text[:end_idx] + program_help + text[end_idx:]

    if text == original:
        print("[OK] Collector already contains header help block or no changes were needed.")
    else:
        COLLECTOR_PATH.write_text(text, encoding="utf-8", newline="\n")
        compile(text, str(COLLECTOR_PATH), "exec")
        print(f"[OK] Collector updated: {COLLECTOR_PATH}")

def patch_launcher() -> None:
    if not LAUNCHER_PATH.exists():
        raise FileNotFoundError(f"Launcher not found: {LAUNCHER_PATH}")

    text = LAUNCHER_PATH.read_text(encoding="utf-8", errors="ignore")
    original = text

    start_marker = ':menu\r\ncls\r\n'
    if start_marker not in text:
        start_marker = ':menu\ncls\n'
    if start_marker not in text:
        raise RuntimeError("Could not find :menu section in launcher.")

    menu_header_start = text.find(start_marker)
    menu_echo_start = menu_header_start + len(start_marker)

    next_marker = 'echo Python:'
    next_pos = text.find(next_marker, menu_echo_start)
    if next_pos == -1:
        raise RuntimeError("Could not find menu echo block in launcher.")

    text = text[:menu_echo_start] + LAUNCHER_HELP_BLOCK.replace('\n', '\r\n') + text[next_pos:]

    if text == original:
        print("[OK] Launcher already contains help header or no changes were needed.")
    else:
        LAUNCHER_PATH.write_text(text, encoding="utf-8", newline="\r\n")
        print(f"[OK] Launcher updated: {LAUNCHER_PATH}")

def run_check(args: list[str]) -> None:
    print()
    print(">", " ".join(args))
    result = subprocess.run(args, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        raise SystemExit(result.returncode)

def main() -> int:
    print(f"Project root: {PROJECT_ROOT}")

    backup_file(COLLECTOR_PATH)
    backup_file(LAUNCHER_PATH)

    patch_collector()
    patch_launcher()

    run_check([sys.executable, str(COLLECTOR_PATH), "--project-root", str(PROJECT_ROOT), "status"])
    run_check([sys.executable, str(COLLECTOR_PATH), "--project-root", str(PROJECT_ROOT), "transfer"])

    print()
    print("[DONE] Header help block upgrade completed successfully.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())