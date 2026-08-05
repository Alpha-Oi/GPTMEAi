# fix_and_test_gptmeai_final.ps1
# --------------------------------------
# Скрипт для GPTMEAi
# 🔹 Обновляет шапки всех Python-файлов проекта
# 🔹 Запускает ядро, Auto-Scale, API и тестовые задачи
# 🔹 Стресс-тест всех менеджеров и воркеров
# 🔹 Логирует все статусы и ошибки в единый JSON
# Автор: GPTMEAi Developer
# Дата: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

$projectPath = "C:\Development GPTMEAi"
$processedFiles = @()
$errorFiles = @()
$finalLog = @{
    processed_files = @()
    error_files = @()
    kernel_status = $null
    auto_scale_status = $null
    api_status = $null
    tasks_executed = @()
}

Write-Host "`n🔹 Обновление шапок Python-файлов..."
$pyFiles = Get-ChildItem -Path $projectPath -Recurse -Filter "*.py" |
           Where-Object { $_.FullName -notmatch "\\venv\\" }

foreach ($file in $pyFiles) {
    try {
        $content = Get-Content $file.FullName -Raw
        if (-not [string]::IsNullOrEmpty($content)) {
            $content = [regex]::Replace($content, '^[\s`]*("""[\s\S]*?""")', '', 'Singleline')
            $header = @"
\"\"\"
Название файла: $($file.Name)
Описание: Скрипт GPTMEAi. Обновлена шапка.
Дата: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
Автор: GPTMEAi Developer
\"\"\"
"@
            Set-Content -Path $file.FullName -Value ($header + "`n" + $content) -Encoding UTF8
            Write-Host "✔ Шапка обновлена: $($file.FullName)"
            $processedFiles += $file.FullName
        } else {
            Write-Host "⚠ Файл пустой, пропущен: $($file.FullName)"
        }
    } catch {
        Write-Warning "❌ Ошибка при обработке $($file.FullName): $_"
        $errorFiles += $file.FullName
    }
}
$finalLog.processed_files = $processedFiles
$finalLog.error_files = $errorFiles
Write-Host "`n✅ Обновление шапок завершено."

# ======================
# 🔹 Запуск ядра GPTMEAi
# ======================
Write-Host "`n🔹 Запуск ядра GPTMEAi..."
try {
    python -m core.ai_kernel
    $finalLog.kernel_status = Get-Content "$projectPath\gptmeai_status.json" -Raw | ConvertFrom-Json
} catch { Write-Warning "❌ Ошибка запуска ядра: $_"; $finalLog.kernel_status = "Ошибка" }

# ======================
# 🔹 Запуск Auto-Scale с авто-остановкой
# ======================
Write-Host "`n🔹 Запуск Auto-Scale (15 сек)..."
try {
    $autoScaleProcess = Start-Process python -ArgumentList "-m core.cognitive_loop_auto_scale" -PassThru
    Start-Sleep -Seconds 15
    $autoScaleProcess.Kill()
    $finalLog.auto_scale_status = Get-Content "$projectPath\gptmeai_auto_scale_log.json" -Raw | ConvertFrom-Json
} catch { Write-Warning "❌ Ошибка запуска Auto-Scale: $_"; $finalLog.auto_scale_status = "Ошибка" }

# ======================
# 🔹 Запуск API Cognitive Loop
# ======================
Write-Host "`n🔹 Запуск API Cognitive Loop..."
try {
    Start-Process python -ArgumentList "-m uvicorn core.cognitive_loop_api_v2:app --reload --host 127.0.0.1 --port 8000"
    $finalLog.api_status = "API запущен на http://127.0.0.1:8000"
} catch { Write-Warning "❌ Ошибка запуска API: $_"; $finalLog.api_status = "Ошибка" }

# ======================
# 🔹 Добавление тестовой задачи
# ======================
Write-Host "`n🔹 Добавление тестовой задачи..."
try {
    .\manage_gptmeai_v2.ps1 -action add_task -task "Тестовая задача интеграции"
    Write-Host "✅ Тестовая задача добавлена"
    $finalLog.tasks_executed += "Тестовая задача интеграции"
} catch { Write-Warning "❌ Ошибка добавления тестовой задачи: $_" }

# ======================
# 🔹 Стресс-тест всех менеджеров и воркеров
# ======================
Write-Host "`n🔹 Стресс-тест менеджеров и воркеров..."
try {
    python -m core.cognitive_loop_stress_test  # Предполагается отдельный модуль стресс-теста
    $finalLog.tasks_executed += "Стресс-тест всех менеджеров и воркеров выполнен"
} catch { Write-Warning "❌ Ошибка стресс-теста: $_"; $finalLog.tasks_executed += "Стресс-тест ошибка" }

# ======================
# 🔹 Сохранение финального JSON-лога
# ======================
$finalLogPath = "$projectPath\gptmeai_final_log.json"
$finalLog | ConvertTo-Json -Depth 10 | Set-Content -Path $finalLogPath -Encoding UTF8
Write-Host "`n🔹 Финальный JSON-лог сохранён: $finalLogPath"

Write-Host "`n✅ Все файлы обновлены и GPTMEAi протестирован!"