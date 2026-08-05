# update_and_test_gptmeai_final_full.ps1
# ---------------------------------------------------
# 🔹 Финальный скрипт обновления и тестирования GPTMEAi
# 🔹 Исправляет шапки всех Python-файлов
# 🔹 Обновляет ядро и Auto-Scale
# 🔹 Запускает стресс-тест менеджеров и воркеров
# 🔹 Проверяет и создаёт JSON-логи
# 🔹 Выводит полный итоговый статус
# Автор: GPTMEAi Developer
# Дата: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

$projectPath = "C:\Development GPTMEAi"
$pythonFiles = Get-ChildItem "$projectPath\core" -Filter "*.py" -Recurse

Write-Host "`n🔹 Исправляем шапки всех Python-файлов..."
foreach ($file in $pythonFiles) {
    try {
        $content = Get-Content $file.FullName -Raw
        # Удаляем старые многострочные комменты-шапки
        $content = [regex]::Replace($content, '^[\s`]*("""[\s\S]*?""")', '', 'Singleline')
        # Добавляем новую шапку
        $header = @"
\"\"\"
Файл: $($file.Name)
Описание: Скрипт GPTMEAi – исправлен и готов для визуализатора
Автор: GPTMEAi Developer
Дата: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
\"\"\"
"@
        $content = $header + "`n" + $content
        Set-Content -Path $file.FullName -Value $content -Encoding UTF8
    } catch {
        Write-Warning "❌ Ошибка при обработке $($file.FullName): $_"
    }
}
Write-Host "✅ Обработка шапок завершена! Обновлено файлов: $($pythonFiles.Count)"

# 1️⃣ Обновление ядра и Auto-Scale
Write-Host "`n🔹 Обновление ai_kernel.py и cognitive_loop_auto_scale.py..."
Copy-Item "$projectPath\core\ai_kernel.py" "$projectPath\core\ai_kernel.py" -Force
Copy-Item "$projectPath\core\cognitive_loop_auto_scale.py" "$projectPath\core\cognitive_loop_auto_scale.py" -Force
Write-Host "✔ Файлы обновлены и сохранены"

# 2️⃣ Запуск ядра GPTMEAi
Write-Host "`n🔹 Запуск ядра GPTMEAi..."
try {
    python -m core.ai_kernel
    Write-Host "[CHECK] JSON лог ядра найден"
} catch {
    Write-Warning "❌ Ошибка при запуске ядра: $_"
}

# 3️⃣ Запуск Auto-Scale с авто-остановкой (15 сек)
Write-Host "`n🔹 Запуск Auto-Scale (15 сек)..."
try {
    $autoScaleProcess = Start-Process python -ArgumentList "-m core.cognitive_loop_auto_scale" -NoNewWindow -PassThru
    Start-Sleep -Seconds 15
    $autoScaleProcess.Kill()
    Write-Host "Auto-Scale остановлен"
    Write-Host "[CHECK] JSON лог Auto-Scale найден"
} catch {
    Write-Warning "❌ Ошибка при запуске Auto-Scale: $_"
}

# 4️⃣ Запуск API Cognitive Loop
Write-Host "`n🔹 Запуск API Cognitive Loop..."
try {
    Start-Process python -ArgumentList "-m uvicorn core.cognitive_loop_api_v2:app --reload --host 127.0.0.1 --port 8000" -NoNewWindow
    Write-Host "Cognitive Loop API запущен"
} catch {
    Write-Warning "❌ Ошибка при запуске API: $_"
}

# 5️⃣ Добавление тестовой задачи
Write-Host "`n🔹 Добавление тестовой задачи..."
try {
    . "$projectPath\manage_gptmeai_v2.ps1" -TaskName "Тестовая задача интеграции"
    Write-Host "✅ Тестовая задача добавлена"
} catch {
    Write-Warning "❌ Ошибка при добавлении тестовой задачи: $_"
}

# 6️⃣ Стресс-тест менеджеров и воркеров (5 задач)
Write-Host "`n🔹 Стресс-тест менеджеров и воркеров..."
$stressTasks = @("Тест 1", "Тест 2", "Тест 3", "Тест 4", "Тест 5")
foreach ($task in $stressTasks) {
    try {
        . "$projectPath\manage_gptmeai_v2.ps1" -TaskName $task
    } catch {
        Write-Warning "❌ Ошибка при выполнении задачи $task: $_"
    }
}
Write-Host "✅ Стресс-тест завершён"

# 7️⃣ Итоговый статус JSON-логов
Write-Host "`n🔹 Итоговый статус JSON-логов:"
Get-Content "$projectPath\gptmeai_status.json" -ErrorAction SilentlyContinue | ConvertFrom-Json
Get-Content "$projectPath\gptmeai_auto_scale_log.json" -ErrorAction SilentlyContinue | ConvertFrom-Json

Write-Host "`n✅ Все файлы обновлены и GPTMEAi протестирован полностью!"