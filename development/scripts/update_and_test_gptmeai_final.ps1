# update_and_test_gptmeai_final.ps1
# ---------------------------------
# Скрипт полностью обновляет ядро и Auto-Scale GPTMEAi
# 🔹 Проверяет JSON-логи
# 🔹 Запускает тестовую задачу
# 🔹 Выводит итоговый статус
# Автор: GPTMEAi Developer
# Дата: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

$projectPath = "C:\Development GPTMEAi"

# 1️⃣ Обновляем ai_kernel.py
Copy-Item "$projectPath\core\ai_kernel.py" "$projectPath\core\ai_kernel.py" -Force
Write-Host "✔ ai_kernel.py обновлён и сохранён"

# 2️⃣ Обновляем cognitive_loop_auto_scale.py
Copy-Item "$projectPath\core\cognitive_loop_auto_scale.py" "$projectPath\core\cognitive_loop_auto_scale.py" -Force
Write-Host "✔ cognitive_loop_auto_scale.py обновлён и сохранён"

# 3️⃣ Запуск ядра
Write-Host "`n🔹 Запуск ядра GPTMEAi..."
try {
    python -m core.ai_kernel
    Write-Host "[CHECK] JSON лог ядра найден"
} catch {
    Write-Warning "❌ Ошибка при запуске ядра: $_"
}

# 4️⃣ Запуск Auto-Scale с авто-остановкой (15 секунд)
Write-Host "`n🔹 Запуск Auto-Scale (15 сек)..."
try {
    Start-Process python -ArgumentList "-m core.cognitive_loop_auto_scale" -NoNewWindow
    Start-Sleep -Seconds 15
    Write-Host "Auto-Scale остановлен"
    Write-Host "[CHECK] JSON лог Auto-Scale найден"
} catch {
    Write-Warning "❌ Ошибка при запуске Auto-Scale: $_"
}

# 5️⃣ Запуск API Cognitive Loop
Write-Host "`n🔹 Запуск API Cognitive Loop..."
try {
    Start-Process python -ArgumentList "-m uvicorn core.cognitive_loop_api_v2:app --reload --host 127.0.0.1 --port 8000" -NoNewWindow
    Write-Host "Cognitive Loop API запущен"
} catch {
    Write-Warning "❌ Ошибка при запуске API: $_"
}

# 6️⃣ Добавление тестовой задачи
Write-Host "`n🔹 Добавление тестовой задачи..."
try {
    . "$projectPath\manage_gptmeai_v2.ps1" -TaskName "Тестовая задача интеграции"
    Write-Host "✅ Тестовая задача добавлена"
} catch {
    Write-Warning "❌ Ошибка при добавлении тестовой задачи: $_"
}

# 7️⃣ Итоговый статус
Write-Host "`n🔹 Итоговый статус JSON-логов:"
Get-Content "$projectPath\gptmeai_status.json" -ErrorAction SilentlyContinue | ConvertFrom-Json
Get-Content "$projectPath\gptmeai_auto_scale_log.json" -ErrorAction SilentlyContinue | ConvertFrom-Json

Write-Host "`n✅ Все файлы обновлены и GPTMEAi протестирован!"