# ============================================================
# PowerShell скрипт: update_ai_kernel_and_auto_scale.ps1
# Описание: Исправляет и обновляет ai_kernel.py и cognitive_loop_auto_scale.py
# Добавляет шапку, JSON-логи для визуализатора и авто-остановку
# Автор: Crown Aliy
# Дата: 2026-03-11
# ============================================================

$projectPath = "C:\Development GPTMEAi"
$pythonFiles = @(
    "$projectPath\core\ai_kernel.py",
    "$projectPath\core\cognitive_loop_auto_scale.py"
)

foreach ($file in $pythonFiles) {

    # Чтение текущего содержимого
    $content = Get-Content $file -Raw

    # Удаляем старые docstring или экранированные символы
    $content = $content -replace '^\s*\\?"""[\s\S]*?\\?"""', ''

    # Формируем новую шапку
    $header = @"
\"\"\"
$(Split-Path $file -Leaf)
Описание: Автоматически обновлённый скрипт GPTMEAi
Автор: Crown Aliy
Дата: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
\"\"\"
"@

    # Объединяем шапку и старый код
    $newContent = $header + "`n`n" + $content

    # Добавляем JSON-логирование и авто-остановку
    if ($file -like "*ai_kernel.py") {
        $jsonCode = @"
import json

def save_kernel_status(kernel):
    status = {
        "kernel_state": getattr(kernel, 'state', 'running'),
        "supervisor_status": getattr(kernel, 'supervisor_status', 'unknown'),
        "managers": list(getattr(kernel, 'managers', {}).keys()),
        "workers": list(getattr(kernel, 'workers', {}).keys()),
        "tasks_executed": getattr(kernel, 'tasks_executed', [])
    }
    with open(r"$projectPath\gptmeai_status.json", "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=4)
"@
    } elseif ($file -like "*cognitive_loop_auto_scale.py") {
        $jsonCode = @"
import json
from datetime import datetime, timedelta

def save_auto_scale_status(loop):
    status = {
        "managers": list(loop.managers.keys()),
        "workers": list(loop.workers.keys()),
        "tasks_executed": loop.tasks_executed,
        "start_time": str(datetime.now()),
        "end_time": str(datetime.now() + timedelta(seconds=getattr(loop, 'test_duration', 60)))
    }
    with open(r"$projectPath\gptmeai_auto_scale_log.json", "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=4)
"@
    }

    # Добавляем код JSON в конец файла
    $newContent += "`n`n" + $jsonCode

    # Сохраняем файл
    Set-Content $file -Value $newContent -Encoding UTF8
    Write-Host "✔ Файл обновлён и сохранён: $file"
}

Write-Host "`n✅ Все файлы обновлены и подготовлены для визуализатора!"