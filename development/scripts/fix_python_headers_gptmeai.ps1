# ============================================================
# Скрипт: fix_python_headers_gptmeai.ps1
# Назначение: Исправляет шапки всех Python-файлов в проекте GPTMEAi
# Автор: Crown Aliy
# Дата: 2026-03-11
# ============================================================

$projectPath = "C:\Development GPTMEAi"
$pythonFiles = Get-ChildItem -Path $projectPath -Recurse -Include *.py

foreach ($file in $pythonFiles) {
    try {
        $content = Get-Content $file.FullName -Raw

        # Удаляем старую шапку (все многострочные строки в начале файла)
        $content = $content -replace "^[\s`]*('{3}|\"{3})[\s\S]*?\1", "", "Singleline"

        # Создаем новую корректную шапку docstring
        $header = @"
\"\"\" 
Файл: $($file.Name)
Описание: Обновлённый Python файл проекта GPTMEAi
Дата: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
Автор: Crown Aliy
\"\"\"
"@

        # Объединяем шапку и содержимое
        $newContent = $header.Trim() + "`r`n`r`n" + $content.TrimStart()

        # Сохраняем файл
        Set-Content -Path $file.FullName -Value $newContent -Encoding UTF8

        Write-Host "✔ Шапка исправлена: $($file.FullName)"
    }
    catch {
        Write-Warning "❌ Ошибка при обработке файла $($file.FullName): $_"
    }
}

Write-Host "`n✅ Все шапки Python-файлов обновлены!"