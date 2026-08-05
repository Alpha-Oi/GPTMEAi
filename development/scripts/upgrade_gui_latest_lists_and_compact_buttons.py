from __future__ import annotations

import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Development GPTMEAi")
BACKUP_DIR = PROJECT_ROOT / ".gptcollector" / "backups"
COLLECTOR_PATH = PROJECT_ROOT / "chat_migration_collector.py"
LAUNCHER_PATH = PROJECT_ROOT / "chat_migration_launcher.bat"

TOOLTIP_BLOCK = '''
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
'''

HELP_UI_NEW = '''
        self.help_expanded = False
        self.help_frame = ttk.LabelFrame(self.root, text="Быстрая справка / Quick help", padding=10)
        self.help_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        self.help_frame.columnconfigure(0, weight=1)

        self.help_toolbar = ttk.Frame(self.help_frame)
        self.help_toolbar.grid(row=0, column=0, sticky="ew")
        self.help_toolbar.columnconfigure(0, weight=1)

        ttk.Label(
            self.help_toolbar,
            text="Программа для фиксации прогресса проекта и подготовки переноса в новый чат.",
        ).grid(row=0, column=0, sticky="w")

        self.toggle_help_button = ttk.Button(
            self.help_toolbar,
            text="Показать справку / Show help",
            command=self._toggle_help,
        )
        self.toggle_help_button.grid(row=0, column=1, sticky="e", padx=(8, 0))

        self.help_text = scrolledtext.ScrolledText(help_frame, wrap=tk.WORD, height=12, font=("Consolas", 10))
        self.help_text.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.help_text.insert("1.0", PROGRAM_HELP_TEXT)
        self.help_text.configure(state="disabled")
        self.help_text.grid_remove()
        self._set_help_button_text()

        top = ttk.Frame(self.root, padding=10)
'''

BUTTONS_NEW = '''
        for i in range(5):
            buttons.columnconfigure(i, weight=1)

        btn_quick = ttk.Button(buttons, text="Quick / Старт", command=self._quick_setup)
        btn_status = ttk.Button(buttons, text="Status", command=self._show_status)
        btn_export = ttk.Button(buttons, text="Export", command=self._export)
        btn_transfer = ttk.Button(buttons, text="Transfer", command=self._transfer)
        btn_daily = ttk.Button(buttons, text="Daily", command=self._daily)

        btn_backup = ttk.Button(buttons, text="Backup", command=self._stable_backup)
        btn_last_export = ttk.Button(buttons, text="Last export", command=self._open_selected_export)
        btn_last_snapshot = ttk.Button(buttons, text="Last snapshot", command=self._open_selected_snapshot)
        btn_refresh = ttk.Button(buttons, text="Refresh", command=self._refresh_recent_lists)
        btn_exit = ttk.Button(buttons, text="Exit / Выход", command=self.root.destroy)

        btn_quick.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        btn_status.grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        btn_export.grid(row=0, column=2, sticky="ew", padx=4, pady=4)
        btn_transfer.grid(row=0, column=3, sticky="ew", padx=4, pady=4)
        btn_daily.grid(row=0, column=4, sticky="ew", padx=4, pady=4)

        btn_backup.grid(row=1, column=0, sticky="ew", padx=4, pady=4)
        btn_last_export.grid(row=1, column=1, sticky="ew", padx=4, pady=4)
        btn_last_snapshot.grid(row=1, column=2, sticky="ew", padx=4, pady=4)
        btn_refresh.grid(row=1, column=3, sticky="ew", padx=4, pady=4)
        btn_exit.grid(row=1, column=4, sticky="ew", padx=4, pady=4)

        attach_tooltip(btn_quick, "Quick setup / Быстрая настройка\\nПервичная настройка проекта")
        attach_tooltip(btn_status, "Status / Статус\\nТекущее состояние проекта")
        attach_tooltip(btn_export, "Export / Экспорт\\nСоздать migration block и JSON")
        attach_tooltip(btn_transfer, "Transfer / Перенос\\nПоказать готовый текст для нового чата")
        attach_tooltip(btn_daily, "Daily workflow / Ежедневная работа\\nЗаметка + snapshot + export + stable backup")
        attach_tooltip(btn_backup, "Stable backup / Резервная точка\\nСоздать контрольную копию")
        attach_tooltip(btn_last_export, "Open latest export / Открыть последний export")
        attach_tooltip(btn_last_snapshot, "Open latest snapshot / Открыть последний snapshot")
        attach_tooltip(btn_refresh, "Refresh lists / Обновить списки последних файлов")
        attach_tooltip(btn_exit, "Exit / Выход\\nЗакрыть программу")
'''

RECENT_BLOCK = '''
        recent_frame = ttk.LabelFrame(self.root, text="Latest files / Последние файлы", padding=10)
        recent_frame.grid(row=4, column=0, sticky="ew", padx=10, pady=(0, 6))
        recent_frame.columnconfigure(0, weight=1)
        recent_frame.columnconfigure(1, weight=1)

        export_frame = ttk.Frame(recent_frame)
        export_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        export_frame.columnconfigure(0, weight=1)

        ttk.Label(export_frame, text="Latest exports / Последние exports").grid(row=0, column=0, sticky="w")
        self.exports_listbox = tk.Listbox(export_frame, height=6, exportselection=False)
        self.exports_listbox.grid(row=1, column=0, sticky="ew", pady=(4, 4))
        self.exports_listbox.bind("<Double-1>", self._on_export_double_click)

        snapshot_frame = ttk.Frame(recent_frame)
        snapshot_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        snapshot_frame.columnconfigure(0, weight=1)

        ttk.Label(snapshot_frame, text="Latest snapshots / Последние snapshots").grid(row=0, column=0, sticky="w")
        self.snapshots_listbox = tk.Listbox(snapshot_frame, height=6, exportselection=False)
        self.snapshots_listbox.grid(row=1, column=0, sticky="ew", pady=(4, 4))
        self.snapshots_listbox.bind("<Double-1>", self._on_snapshot_double_click)

        self._recent_export_paths = []
        self._recent_snapshot_paths = []

        self.output = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, font=("Consolas", 10))
'''

GUI_METHODS = '''
    def _set_help_button_text(self) -> None:
        if getattr(self, "help_expanded", False):
            self.toggle_help_button.configure(text="Скрыть справку / Hide help")
        else:
            self.toggle_help_button.configure(text="Показать справку / Show help")

    def _toggle_help(self) -> None:
        self.help_expanded = not getattr(self, "help_expanded", False)
        if self.help_expanded:
            self.help_text.grid()
        else:
            self.help_text.grid_remove()
        self._set_help_button_text()

    def _refresh_recent_lists(self) -> None:
        self.exports_listbox.delete(0, tk.END)
        self.snapshots_listbox.delete(0, tk.END)
        self._recent_export_paths = []
        self._recent_snapshot_paths = []

        for path in self.collector.get_recent_exports(10):
            self._recent_export_paths.append(path)
            self.exports_listbox.insert(tk.END, path.name)

        for path in self.collector.get_recent_snapshots(10):
            self._recent_snapshot_paths.append(path)
            self.snapshots_listbox.insert(tk.END, path.name)

    def _open_selected_export(self) -> None:
        sel = self.exports_listbox.curselection()
        if not sel:
            if messagebox:
                messagebox.showinfo("Export", "Сначала выбери export из списка.")
            return
        path = self._recent_export_paths[sel[0]]
        self.collector._open_path_in_system(path)
        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, "Открыт export:\\n" + path.as_posix())

    def _open_selected_snapshot(self) -> None:
        sel = self.snapshots_listbox.curselection()
        if not sel:
            if messagebox:
                messagebox.showinfo("Snapshot", "Сначала выбери snapshot из списка.")
            return
        path = self._recent_snapshot_paths[sel[0]]
        self.collector._open_path_in_system(path)
        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, "Открыт snapshot:\\n" + path.as_posix())

    def _on_export_double_click(self, _event=None) -> None:
        self._open_selected_export()

    def _on_snapshot_double_click(self, _event=None) -> None:
        self._open_selected_snapshot()

'''

COLLECTOR_METHODS = '''
    def get_recent_exports(self, limit: int = 10) -> list[Path]:
        return sorted(self.exports_dir.glob("migration_block_*.txt"), reverse=True)[:limit]

    def get_recent_snapshots(self, limit: int = 10) -> list[Path]:
        return sorted(self.snapshots_dir.glob("snapshot_*.json"), reverse=True)[:limit]

    def _open_path_in_system(self, path: Path) -> None:
        try:
            if os.name == "nt" and hasattr(os, "startfile"):
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception:
            pass

    def open_latest_export(self) -> str:
        items = self.get_recent_exports(1)
        if not items:
            return "Последний export пока не найден."
        self._open_path_in_system(items[0])
        return "Открыт export:\\n" + items[0].as_posix()

    def open_latest_snapshot(self) -> str:
        items = self.get_recent_snapshots(1)
        if not items:
            return "Последний snapshot пока не найден."
        self._open_path_in_system(items[0])
        return "Открыт snapshot:\\n" + items[0].as_posix()

'''

NEW_LAUNCHER = r"""@echo off
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
echo Быстрые действия:
echo [H] Help / Помощь
echo [1] GUI / Интерфейс
echo [3] Daily workflow / Ежедневная работа
echo [7] Export / Экспорт
echo [8] Transfer text / Текст переноса
echo [14] Open latest export / Открыть последний export
echo [15] Open latest snapshot / Открыть последний snapshot
echo [13] Stable backup / Stable backup
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
echo [3] Daily workflow / Ежедневная работа
echo [4] Status / Статус
echo [5] Snapshot / Снимок
echo [6] Diff / Изменения
echo [7] Export / Экспорт
echo [8] Transfer text / Текст переноса
echo [9] Change project root / Сменить путь проекта
echo [10] Open exports / Открыть exports
echo [11] Open snapshots / Открыть snapshots
echo [12] Reset project root / Сбросить путь проекта
echo [13] Stable backup now / Создать stable backup
echo [14] Open latest export / Открыть последний export
echo [15] Open latest snapshot / Открыть последний snapshot
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
if "%CHOICE%"=="0" goto end
goto menu

:show_help
cls
echo ================================================================
echo   HELP / ПОМОЩЬ
echo ================================================================
echo.
echo Для чего нужна программа:
echo - сохранять прогресс проекта
echo - создавать export для нового чата
echo - хранить snapshot, заметки и stable backup
echo.
echo Быстрый старт:
echo 1. [2] Quick setup / Быстрая настройка
echo 2. [3] Daily workflow / Ежедневная работа
echo 3. [8] Transfer text / Текст переноса
echo 4. [13] Stable backup / Stable backup
echo.
echo Что делают кнопки:
echo [1] GUI / Интерфейс
echo [2] Quick setup / Быстрая настройка
echo [3] Daily workflow / Ежедневная работа
echo [4] Status / Статус
echo [5] Snapshot / Снимок
echo [6] Diff / Изменения
echo [7] Export / Экспорт
echo [8] Transfer text / Текст переноса
echo [9] Change project root / Сменить путь проекта
echo [10] Open exports / Открыть exports
echo [11] Open snapshots / Открыть snapshots
echo [12] Reset project root / Сбросить путь проекта
echo [13] Stable backup / Stable backup
echo [14] Open latest export / Открыть последний export
echo [15] Open latest snapshot / Открыть последний snapshot
echo [0] Exit / Выход
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
set /p QS_NAME=Название проекта [GPTMemory Ai-OS]: 
if "%QS_NAME%"=="" set "QS_NAME=GPTMemory Ai-OS"
set /p QS_GOAL=Цель проекта [Сбор прогресса проекта и перенос в новый чат]: 
if "%QS_GOAL%"=="" set "QS_GOAL=Сбор прогресса проекта и перенос в новый чат"
set /p QS_PLAN=Путь к GPTMemory_plan.yaml [GPTMemory_plan.yaml]: 
if "%QS_PLAN%"=="" set "QS_PLAN=GPTMemory_plan.yaml"
call :run_collector quick-setup --name "%QS_NAME%" --goal "%QS_GOAL%" --plan-path "%QS_PLAN%"
goto return_menu

:daily
cls
echo === DAILY WORKFLOW / ЕЖЕДНЕВНАЯ РАБОТА ===
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
echo === STABLE BACKUP / СОЗДАТЬ STABLE BACKUP ===
call :run_collector stable-backup
goto return_menu

:open_latest_export
cls
echo === OPEN LATEST EXPORT / ОТКРЫТЬ ПОСЛЕДНИЙ EXPORT ===
call :run_collector open-latest-export
goto return_menu

:open_latest_snapshot
cls
echo === OPEN LATEST SNAPSHOT / ОТКРЫТЬ ПОСЛЕДНИЙ SNAPSHOT ===
call :run_collector open-latest-snapshot
goto return_menu

:change_root
cls
echo === CHANGE PROJECT ROOT / СМЕНИТЬ ПУТЬ ПРОЕКТА ===
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
"""

def backup_file(path: Path) -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        return
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = BACKUP_DIR / f"{path.name}.latest_lists_{stamp}.bak"
    shutil.copy2(path, dst)
    print(f"[OK] Backup created: {dst}")

def ensure_imports(text: str) -> str:
    if "import subprocess" not in text:
        text = text.replace("import shutil\n", "import shutil\nimport subprocess\n")
    return text

def patch_collector() -> None:
    if not COLLECTOR_PATH.exists():
        raise FileNotFoundError(f"Collector not found: {COLLECTOR_PATH}")

    text = COLLECTOR_PATH.read_text(encoding="utf-8", errors="ignore")
    original = text

    text = ensure_imports(text)

    if "class SimpleToolTip:" not in text:
        marker = "class CollectorGUI:\n"
        if marker not in text:
            raise RuntimeError("Could not find insertion point for tooltip helper.")
        text = text.replace(marker, TOOLTIP_BLOCK + "\n" + marker, 1)

    text = text.replace('self.root.geometry("1180x820")', 'self.root.geometry("1360x930")')
    text = text.replace('self.root.minsize(1040, 720)', 'self.root.minsize(1160, 780)')
    text = text.replace('self.root.rowconfigure(4, weight=1)', 'self.root.rowconfigure(5, weight=1)')

    old_help_visible = '''        help_frame = ttk.LabelFrame(self.root, text="Описание программы / Program description", padding=10)
        help_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        help_frame.columnconfigure(0, weight=1)

        self.help_text = scrolledtext.ScrolledText(help_frame, wrap=tk.WORD, height=16, font=("Consolas", 10))
        self.help_text.grid(row=0, column=0, sticky="ew")
        self.help_text.insert("1.0", PROGRAM_HELP_TEXT)
        self.help_text.configure(state="disabled")

        top = ttk.Frame(self.root, padding=10)
'''
    if old_help_visible in text:
        text = text.replace(old_help_visible, HELP_UI_NEW, 1)

    old_buttons = '''        for i in range(7):
            buttons.columnconfigure(i, weight=1)

        ttk.Button(buttons, text="Quick setup / Быстрая настройка", command=self._quick_setup).grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        ttk.Button(buttons, text="Status / Статус", command=self._show_status).grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        ttk.Button(buttons, text="Export / Экспорт", command=self._export).grid(row=0, column=2, sticky="ew", padx=4, pady=4)
        ttk.Button(buttons, text="Transfer / Перенос", command=self._transfer).grid(row=0, column=3, sticky="ew", padx=4, pady=4)
        ttk.Button(buttons, text="Daily workflow / Ежедневная работа", command=self._daily).grid(row=0, column=4, sticky="ew", padx=4, pady=4)
        ttk.Button(buttons, text="Stable backup / Stable backup", command=self._stable_backup).grid(row=0, column=5, sticky="ew", padx=4, pady=4)
        ttk.Button(buttons, text="Exit / Выход", command=self.root.destroy).grid(row=0, column=6, sticky="ew", padx=4, pady=4)
'''
    if old_buttons in text:
        text = text.replace(old_buttons, BUTTONS_NEW, 1)

    if 'recent_frame = ttk.LabelFrame(self.root, text="Latest files / Последние файлы", padding=10)' not in text:
        text = text.replace(
            '        self.output = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, font=("Consolas", 10))\n',
            RECENT_BLOCK,
            1
        )

    text = text.replace(
        '        self.output.grid(row=4, column=0, sticky="nsew", padx=10, pady=(0, 10))',
        '        self.output.grid(row=5, column=0, sticky="nsew", padx=10, pady=(0, 10))'
    )

    if "def _set_help_button_text(self) -> None:" not in text:
        marker = "    def _load_state(self) -> None:\n"
        if marker not in text:
            raise RuntimeError("Could not find insertion point for GUI helper methods.")
        text = text.replace(marker, GUI_METHODS + marker, 1)

    if "def get_recent_exports(self, limit: int = 10) -> list[Path]:" not in text:
        marker = "    def launch_gui(self) -> None:\n"
        if marker not in text:
            raise RuntimeError("Could not find insertion point for collector latest methods.")
        text = text.replace(marker, COLLECTOR_METHODS + marker, 1)

    if 'subparsers.add_parser("open-latest-export")' not in text:
        text = text.replace(
            '    subparsers.add_parser("stable-backup")\n    subparsers.add_parser("gui")\n',
            '    subparsers.add_parser("stable-backup")\n'
            '    subparsers.add_parser("open-latest-export")\n'
            '    subparsers.add_parser("open-latest-snapshot")\n'
            '    subparsers.add_parser("gui")\n'
        )

    if 'if args.command == "open-latest-export":' not in text:
        text = text.replace(
            '        if args.command == "stable-backup":\n'
            '            path = collector.create_stable_backup("manual_cli")\n'
            '            print(f"Stable backup создан: {path.as_posix()}")\n'
            '            return 0\n'
            '\n'
            '        if args.command == "gui":\n',
            '        if args.command == "stable-backup":\n'
            '            path = collector.create_stable_backup("manual_cli")\n'
            '            print(f"Stable backup создан: {path.as_posix()}")\n'
            '            return 0\n'
            '\n'
            '        if args.command == "open-latest-export":\n'
            '            print(collector.open_latest_export())\n'
            '            return 0\n'
            '\n'
            '        if args.command == "open-latest-snapshot":\n'
            '            print(collector.open_latest_snapshot())\n'
            '            return 0\n'
            '\n'
            '        if args.command == "gui":\n'
        )

    if "def _open_selected_export(self) -> None:" not in text:
        marker = "    def _stable_backup(self) -> None:\n"
        if marker not in text:
            raise RuntimeError("Could not find insertion point for latest list GUI methods.")
        text = text.replace(marker, GUI_METHODS.split("    def _load_state")[0] if False else marker)  # no-op safety

    if "def _open_selected_export(self) -> None:" not in text:
        stable_marker = "    def _stable_backup(self) -> None:\n"
        extra_methods = '''
    def _open_selected_export(self) -> None:
        sel = self.exports_listbox.curselection()
        if not sel:
            if messagebox:
                messagebox.showinfo("Export", "Сначала выбери export из списка.")
            return
        path = self._recent_export_paths[sel[0]]
        self.collector._open_path_in_system(path)
        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, "Открыт export:\\n" + path.as_posix())

    def _open_selected_snapshot(self) -> None:
        sel = self.snapshots_listbox.curselection()
        if not sel:
            if messagebox:
                messagebox.showinfo("Snapshot", "Сначала выбери snapshot из списка.")
            return
        path = self._recent_snapshot_paths[sel[0]]
        self.collector._open_path_in_system(path)
        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, "Открыт snapshot:\\n" + path.as_posix())

    def _on_export_double_click(self, _event=None) -> None:
        self._open_selected_export()

    def _on_snapshot_double_click(self, _event=None) -> None:
        self._open_selected_snapshot()

'''
        if stable_marker in text:
            text = text.replace(stable_marker, extra_methods + stable_marker, 1)

    text = text.replace(
        '        self.output.insert(tk.END, self.collector.status())\n',
        '        self.output.insert(tk.END, self.collector.status())\n        self._refresh_recent_lists()\n',
        1
    )

    text = text.replace(
        '        self.output.insert(tk.END, json.dumps(state, ensure_ascii=False, indent=2))\n',
        '        self.output.insert(tk.END, json.dumps(state, ensure_ascii=False, indent=2))\n        self._refresh_recent_lists()\n',
        1
    )

    text = text.replace(
        '        self.output.insert(tk.END, Path(data["txt_path"]).read_text(encoding="utf-8"))\n',
        '        self.output.insert(tk.END, Path(data["txt_path"]).read_text(encoding="utf-8"))\n        self._refresh_recent_lists()\n',
        1
    )

    text = text.replace(
        '        self.output.insert(tk.END, "Stable backup: " + result["stable_backup_path"] + "\\n")\n',
        '        self.output.insert(tk.END, "Stable backup: " + result["stable_backup_path"] + "\\n")\n        self._refresh_recent_lists()\n',
        1
    )

    text = text.replace(
        '        self.output.insert(tk.END, f"Stable backup создан:\\n{path.as_posix()}\\n")\n',
        '        self.output.insert(tk.END, f"Stable backup создан:\\n{path.as_posix()}\\n")\n        self._refresh_recent_lists()\n',
        1
    )

    if text != original:
        COLLECTOR_PATH.write_text(text, encoding="utf-8", newline="\n")
        compile(text, str(COLLECTOR_PATH), "exec")
        print(f"[OK] Collector updated: {COLLECTOR_PATH}")
    else:
        print("[OK] Collector already up to date.")

def patch_launcher() -> None:
    LAUNCHER_PATH.write_text(NEW_LAUNCHER, encoding="utf-8", newline="\r\n")
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
    run_check([sys.executable, str(COLLECTOR_PATH), "--project-root", str(PROJECT_ROOT), "open-latest-export"])
    run_check([sys.executable, str(COLLECTOR_PATH), "--project-root", str(PROJECT_ROOT), "open-latest-snapshot"])

    print()
    print("[DONE] GUI latest lists and compact buttons were added successfully.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())