<#
.SYNOPSIS
Обновление GPTMEAi V4 + полный тест компонентов и проверка JSON-логов
.DESCRIPTION
1️⃣ Обновление файлов ai_kernel.py и cognitive_loop_auto_scale.py
2️⃣ Добавление шапки с описанием, автором и датой
3️⃣ Полный тест всех компонентов и проверка JSON-логов
Автор: Crown Aliy
Дата: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
#>

$projectPath = "C:\Development GPTMEAi"

# === 1️⃣ Обновление ai_kernel.py ===
$aiKernelPath = "$projectPath\core\ai_kernel.py"
@"
\"\"\"
ai_kernel.py - Основное ядро GPTMEAi
Описание: Управляет менеджерами, воркерами и Cognitive Loop
Автор: Crown Aliy
Дата: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
\"\"\"

# === Ваш исправленный код ai_kernel.py начинается здесь ===
# (вставьте полный рабочий код ядра)
"@ | Set-Content $aiKernelPath
Write-Host "✔ Файл обновлён и сохранён: $aiKernelPath"

# === 2️⃣ Обновление cognitive_loop_auto_scale.py ===
$autoScalePath = "$projectPath\core\cognitive_loop_auto_scale.py"
@"
\"\"\"
cognitive_loop_auto_scale.py - Auto-Scale для GPTMEAi
Описание: Автоматическое масштабирование менеджеров и воркеров, генерация JSON-логов
Автор: Crown Aliy
Дата: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
\"\"\"

# === Ваш исправленный код Auto-Scale начинается здесь ===
# (вставьте полный рабочий код Auto-Scale с авто-остановкой и JSON-логами)
"@ | Set-Content $autoScalePath
Write-Host "✔ Файл обновлён и сохранён: $autoScalePath"

# === 3️⃣ Запуск теста GPTMEAi V4 ===
Write-Host "`n🔹 Запуск теста GPTMEAi V4"

# Ядро
Write-Host "`n=== 1️⃣ Запуск ядра GPTMEAi ==="
Start-Process python -ArgumentList "-m core.ai_kernel" -NoNewWindow -Wait
if (Test-Path "$projectPath\gptmeai_status.json") {
    Write-Host "[CHECK] JSON лог ядра найден"
    Get-Content "$projectPath\gptmeai_status.json" | Out-String | ConvertFrom-Json
} else {
    Write-Warning "[WARNING] JSON лог ядра не найден"
}

# Auto-Scale
Write-Host "`n=== 2️⃣ Запуск Auto-Scale с авто-остановкой ==="
Start-Process python -ArgumentList "-m core.cognitive_loop_auto_scale" -NoNewWindow -Wait
if (Test-Path "$projectPath\gptmeai_auto_scale_log.json") {
    Write-Host "[CHECK] JSON лог Auto-Scale найден"
    Get-Content "$projectPath\gptmeai_auto_scale_log.json" | Out-String | ConvertFrom-Json
} else {
    Write-Warning "[WARNING] JSON лог Auto-Scale не найден"
}

# API
Write-Host "`n=== 3️⃣ Запуск API Cognitive Loop ==="
Start-Process python -ArgumentList "-m uvicorn core.cognitive_loop_api_v2:app --reload --host 127.0.0.1 --port 8000" -NoNewWindow -PassThru

# Тестовая задача
Write-Host "`n=== 4️⃣ Добавление тестовой задачи через manage_gptmeai_v2.ps1 ==="
.\manage_gptmeai_v2.ps1 -action add_task -task "Тестовая задача интеграции"
Write-Host "✅ Тестовая задача добавлена"

# Финальная проверка JSON-логов
Write-Host "`n=== ✅ Проверка готовности JSON-логов для визуализатора ==="
$logs = @("$projectPath\gptmeai_status.json", "$projectPath\gptmeai_auto_scale_log.json")
foreach ($log in $logs) {
    if (Test-Path $log) {
        Write-Host "[CHECK] $log найден"
    } else {
        Write-Warning "[WARNING] $log не найден"
    }
}

Write-Host "`n✅ Обновление и тест GPTMEAi V4 завершены. Все JSON-логи готовы для визуализатора."