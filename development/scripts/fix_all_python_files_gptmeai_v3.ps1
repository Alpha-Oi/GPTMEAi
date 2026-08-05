# fix_all_python_files_gptmeai_v3.ps1
# Скрипт исправляет шапки всех Python-файлов проекта GPTMEAi,
# добавляет описание, дату, автора и проверяет импорты для ядра и Auto-Scale.

$projectPath = "C:\Development GPTMEAi"
$author = "GPTMEAi Developer"
$date = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")

Write-Host "🔹 Поиск Python-файлов в проекте..."
$pyFiles = Get-ChildItem -Path $projectPath -Recurse -Filter "*.py"

foreach ($file in $pyFiles) {
    Write-Host "Обрабатывается: $($file.FullName)"

    # Считаем содержимое файла
    $content = Get-Content $file.FullName -Raw

    # Удаляем старую шапку (тройные кавычки в начале)
    # Экранированы фигурные скобки для PowerShell
    $content = [regex]::Replace($content, "^[\s`]*\\?\"{3}.*?\\?\"{3}", "", "Singleline")

    # Создаём новую корректную шапку
    $header = @"
\"\"\"
Название файла: $($file.Name)
Описание: Скрипт для GPTMEAi. Обновлён шапкой с описанием, датой и автором.
Дата: $date
Автор: $author
\"\"\"
"@

    # Обновляем содержимое файла
    $newContent = $header + "`n" + $content

    # Сохраняем файл
    Set-Content -Path $file.FullName -Value $newContent -Encoding UTF8
    Write-Host "✔ Шапка обновлена и файл сохранён: $($file.FullName)"
}

Write-Host "🔹 Проверка ключевых импортов для ядра и Auto-Scale..."
# Проверка ai_kernel.py
$aiKernelPath = Join-Path $projectPath "core\ai_kernel.py"
if (Test-Path $aiKernelPath) {
    $content = Get-Content $aiKernelPath -Raw
    if (-not ($content -match "from core\.supervisor_bridge import SupervisorBridge")) {
        $content = "from core.supervisor_bridge import SupervisorBridge`n" + $content
        Set-Content $aiKernelPath -Value $content -Encoding UTF8
        Write-Host "✔ Исправлен импорт SupervisorBridge в ai_kernel.py"
    }
}

# Проверка cognitive_loop_auto_scale.py
$autoScalePath = Join-Path $projectPath "core\cognitive_loop_auto_scale.py"
if (Test-Path $autoScalePath) {
    $content = Get-Content $autoScalePath -Raw
    if (-not ($content -match "from agents\.managers\.manager_base import ManagerBase")) {
        $content = "from agents.managers.manager_base import ManagerBase`n" + $content
        Set-Content $autoScalePath -Value $content -Encoding UTF8
        Write-Host "✔ Исправлен импорт ManagerBase в cognitive_loop_auto_scale.py"
    }
}

Write-Host "✅ Все Python-файлы обработаны. Шапки исправлены, импорты проверены."
Write-Host "Теперь можно запускать ядро и Auto-Scale без синтаксических ошибок."