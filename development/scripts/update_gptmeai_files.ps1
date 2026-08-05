# --------------------------------------------
# Скрипт: update_gptmeai_files.ps1
# Назначение: [КОРОТКОЕ ОПИСАНИЕ ФАЙЛА, УКАЖИ ЧТО ДЕЛАЕТ]
# Автор: Crown Aliy
# Дата создания/обновления: 2026-03-12 18:37:08
# --------------------------------------------
# update_gptmeai_files.ps1
$root = "C:\Development GPTMEAi"

$filesToUpdate = @(
    "core\cognitive_loop_auto_scale.py",  # последняя версия с авто-остановкой
    "core\cognitive_loop_live_v2.py",
    "core\cognitive_loop_api_v2.py"
)

foreach ($f in $filesToUpdate) {
    $src = ".\$f"
    $dst = Join-Path $root (Split-Path $f -Leaf)
    Copy-Item $src $dst -Force
    Write-Host "Обновлён файл: $dst"
    if (Test-Path $dst) { Write-Host "Проверка: файл существует ✔ $dst" }
}

Write-Host "✅ Все выбранные файлы обновлены и проверены!"
