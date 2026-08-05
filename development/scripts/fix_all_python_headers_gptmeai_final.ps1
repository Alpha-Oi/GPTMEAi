# fix_all_python_headers_gptmeai_final.ps1
# -----------------------------------------
# Скрипт исправляет шапки всех Python-файлов GPTMEAi
# 🔹 Убирает старые некорректные многострочные строки
# 🔹 Добавляет корректные """ в начале файла
# 🔹 Вставляет описание, дату и автора
# 🔹 Обрабатывает __init__.py и все файлы в core и agents
# Автор: GPTMEAi Developer
# Дата: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

$projectPath = "C:\Development GPTMEAi"
$processedFiles = @()
$errorFiles = @()

# Получаем все Python-файлы, кроме виртуального окружения
$pyFiles = Get-ChildItem -Path $projectPath -Recurse -Filter "*.py" |
           Where-Object { $_.FullName -notmatch "\\venv\\" }

foreach ($file in $pyFiles) {
    try {
        $content = Get-Content $file.FullName -Raw

        if (-not [string]::IsNullOrWhiteSpace($content)) {

            # Удаляем старые шапки, любые """ в начале файла
            $content = [regex]::Replace($content, '^\s*("""[\s\S]*?""")\s*', '', 'Singleline')

            # Создаём новую корректную шапку
            $header = @"
\"\"\"
Название файла: $($file.Name)
Описание: Скрипт GPTMEAi — обновлена шапка.
Дата: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
Автор: GPTMEAi Developer
\"\"\"
"@

            # Сохраняем файл с новой шапкой
            Set-Content -Path $file.FullName -Value ($header + "`n" + $content) -Encoding UTF8
            Write-Host "✔ Шапка обновлена: $($file.FullName)"
            $processedFiles += $file.FullName
        } else {
            Write-Warning "⚠ Файл пустой, пропущен: $($file.FullName)"
        }
    } catch {
        Write-Warning "❌ Ошибка при обработке $($file.FullName): $_"
        $errorFiles += $file.FullName
    }
}

# Вывод результатов
Write-Host "`n✅ Обработка шапок завершена!"
Write-Host "Обновлено файлов: $($processedFiles.Count)"
if ($errorFiles.Count -gt 0) {
    Write-Host "Файлы с ошибками: $($errorFiles.Count)"
    $errorFiles | ForEach-Object { Write-Host "❌ $_" }
}