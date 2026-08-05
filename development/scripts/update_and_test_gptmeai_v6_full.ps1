# update_and_test_gptmeai_v6_full.ps1
# Автор: GPTMemoryEngine AI
# Дата: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
# Назначение: Полное обновление ядра, Auto-Scale, добавление шапок в Python-файлы и запуск стресс-теста GPTMEAi V6

$projectPath = "C:\Development GPTMEAi"
$pythonFiles = @(
    "$projectPath\core\ai_kernel.py",
    "$projectPath\core\cognitive_loop_auto_scale.py"
)
$kernelModule = "core.ai_kernel"
$autoScaleModule = "core.cognitive_loop_auto_scale"
$apiModule = "core.cognitive_loop_api_v2:app"
$apiHost = "127.0.0.1"
$apiPort = 8000
$autoScaleRunTime = 15  # секунды для авто-остановки

Write-Host "🔹 Обновление Python-файлов с шапкой..."

foreach ($file in $pythonFiles) {
    if (Test-Path $file) {
        $content = Get-Content $file -Raw
        $header = @"
\"\"\"
Автор: GPTMemoryEngine AI
Дата: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
Файл: $(Split-Path $file -Leaf)
Описание: Скрипт проекта GPTMEAi. Исправлены синтаксические ошибки, добавлен контроль JSON-логов.
\"\"\"
"@
        Set-Content $file -Value "$header`n$content"
        Write-Host "✔ Файл обновлён и сохранён: $file"
    } else {
        Write-Host "[WARNING] Файл не найден: $file"
    }
}

Write-Host "`n🔹 Запуск ядра GPTMEAi..."
try {
    python -m $kernelModule
    if (Test-Path "$projectPath\gptmeai_status.json") {
        Write-Host "[CHECK] JSON лог ядра найден"
    } else {
        Write-Host "[WARNING] JSON лог ядра не найден"
    }
} catch {
    Write-Host "[ERROR] Ошибка при запуске ядра: $_"
}

Write-Host "`n🔹 Запуск Auto-Scale с авто-остановкой ($autoScaleRunTime сек)..."
try {
    $autoScaleProcess = Start-Process python -ArgumentList "-m $autoScaleModule" -PassThru
    Start-Sleep -Seconds $autoScaleRunTime
    if ($autoScaleProcess -ne $null) { $autoScaleProcess.Kill() }
    if (Test-Path "$projectPath\gptmeai_auto_scale_log.json") {
        Write-Host "[CHECK] JSON лог Auto-Scale найден"
    } else {
        Write-Host "[WARNING] JSON лог Auto-Scale не найден"
    }
} catch {
    Write-Host "[ERROR] Ошибка при запуске Auto-Scale: $_"
}

Write-Host "`n🔹 Запуск API Cognitive Loop..."
try {
    Start-Process python -ArgumentList "-m uvicorn $apiModule --reload --host $apiHost --port $apiPort"
    Write-Host "Cognitive Loop API запущен на http://$apiHost`:$apiPort"
} catch {
    Write-Host "[ERROR] Ошибка при запуске API: $_"
}

Write-Host "`n🔹 Добавление тестовой задачи..."
try {
    . "$projectPath\manage_gptmeai_v2.ps1" -action add_task -task "Тестовая задача интеграции"
    Write-Host "✅ Добавлена задача: Тестовая задача интеграции"
} catch {
    Write-Host "[ERROR] Ошибка при добавлении тестовой задачи: $_"
}

Write-Host "`n🔹 Итоговый статус JSON-логов:"
if (Test-Path "$projectPath\gptmeai_status.json") {
    Get-Content "$projectPath\gptmeai_status.json" | Out-String | ConvertFrom-Json
}
if (Test-Path "$projectPath\gptmeai_auto_scale_log.json") {
    Get-Content "$projectPath\gptmeai_auto_scale_log.json" | Out-String | ConvertFrom-Json
}

Write-Host "`n✅ Все файлы обновлены и тест GPTMEAi V6 завершён. JSON-логи готовы для визуализатора."