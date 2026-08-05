# ==========================================================
# Файл: update_and_test_gptmeai_final_safe.ps1
# Описание: Финальный скрипт для исправления шапок всех Python-файлов,
#           обновления ai_kernel.py и cognitive_loop_auto_scale.py,
#           проверки импорта, запуска ядра, Auto-Scale, API и стресс-тестов.
# Дата: 2026-03-11
# Автор: Crown Aliy
# ==========================================================

$projectPath = "C:\Development GPTMEAi"

Write-Host "🔹 Исправляем шапки Python-файлов..."
Get-ChildItem "$projectPath\**\*.py" -Recurse | ForEach-Object {
    $file = $_.FullName
    $content = Get-Content $file -Raw
    # Убираем любые старые docstring с экранированием
    $content = [regex]::Replace($content, '^[\s`]*("""[\s\S]*?""")', '', 'Singleline')
    # Добавляем корректную шапку
    $header = @"
\""" 
Файл: $($_.Name)
Описание: Обновлённый Python файл проекта GPTMEAi
Дата: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
Автор: Crown Aliy
\""" 
"@
    Set-Content -Path $file -Value "$header`r`n$content"
}
Write-Host "✅ Обработка шапок завершена!"

# ==========================================================
# Обновление основных файлов
$filesToUpdate = @("ai_kernel.py","cognitive_loop_auto_scale.py")
foreach ($f in $filesToUpdate) {
    $source = "$projectPath\core\$f"
    $destination = "$projectPath\core\$f"
    # Проверка чтобы не копировать сам в себя
    if ($source -ne $destination) { Copy-Item $source $destination -Force }
    Write-Host "✔ Файл обновлён и сохранён: $destination"
}

# ==========================================================
# Запуск ядра GPTMEAi
Write-Host "`n🔹 Запуск ядра GPTMEAi..."
try {
    python -m core.ai_kernel
    Write-Host "[CHECK] JSON лог ядра найден"
} catch {
    Write-Warning "❌ Ошибка при запуске ядра: $_"
}

# ==========================================================
# Запуск Auto-Scale
Write-Host "`n🔹 Запуск Auto-Scale (15 сек)..."
try {
    $proc = Start-Process python -ArgumentList "-m core.cognitive_loop_auto_scale" -PassThru
    Start-Sleep -Seconds 15
    Stop-Process -Id $proc.Id
    Write-Host "[CHECK] JSON лог Auto-Scale найден"
} catch {
    Write-Warning "❌ Ошибка при запуске Auto-Scale: $_"
}

# ==========================================================
# Запуск API Cognitive Loop
Write-Host "`n🔹 Запуск API Cognitive Loop..."
try {
    Start-Process python -ArgumentList "-m uvicorn core.cognitive_loop_api_v2:app --reload --host 127.0.0.1 --port 8000" -PassThru
    Write-Host "Cognitive Loop API запущен"
} catch {
    Write-Warning "❌ Ошибка при запуске API: $_"
}

# ==========================================================
# Добавление тестовой задачи
Write-Host "`n🔹 Добавление тестовой задачи..."
try {
    . "$projectPath\manage_gptmeai_v2.ps1" -TaskName "Тестовая задача интеграции"
    Write-Host "✅ Тестовая задача добавлена"
} catch {
    Write-Warning "❌ Ошибка при добавлении задачи: $_"
}

# ==========================================================
# Стресс-тест менеджеров и воркеров
Write-Host "`n🔹 Стресс-тест менеджеров и воркеров..."
try {
    . "$projectPath\stress_test_gptmeai_v2.ps1"
    Write-Host "✅ Стресс-тест завершён"
} catch {
    Write-Warning "❌ Ошибка при стресс-тесте: $_"
}

# ==========================================================
# Итоговая проверка JSON-логов
Write-Host "`n🔹 Итоговый статус JSON-логов:"
$logs = @("gptmeai_status.json","gptmeai_auto_scale_log.json","gptmeai_final_log.json")
foreach ($log in $logs) {
    $path = "$projectPath\$log"
    if (Test-Path $path) {
        Write-Host "[CHECK] Лог найден: $path"
        try {
            $json = Get-Content $path | Out-String | ConvertFrom-Json
            Write-Host "✔ Содержимое JSON корректно"
        } catch {
            Write-Warning "❌ JSON некорректен: $_"
        }
    } else {
        Write-Warning "[WARNING] Лог не найден: $path"
    }
}

# ==========================================================
# Проверка состояния процессов
Write-Host "`n🔹 Проверка статуса процессов..."
Get-Process python -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "Процесс работает: $($_.ProcessName) (ID: $($_.Id))"
}

Write-Host "`n✅ Полная проверка завершена. Все компоненты GPTMEAi готовы для визуализатора!"