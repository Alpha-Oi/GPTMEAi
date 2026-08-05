# 2026-04-13 Python Dev Automation Preference

## Что изменено

Зафиксировано правило для служебной разработки: по умолчанию использовать project-local Python-скрипты вместо одноразовых PowerShell-команд.

Добавлен helper:

- [`cleanup_tmp_artifacts.py`](/D:/Development%20GPTMEAi/development/scripts/cleanup_tmp_artifacts.py)

Также обновлены:

- [`development/scripts/README.md`](/D:/Development%20GPTMEAi/development/scripts/README.md)
- [`development/README.md`](/D:/Development%20GPTMEAi/development/README.md)
- [`docs/developer/DEVELOPER_CONTEXT.md`](/D:/Development%20GPTMEAi/docs/developer/DEVELOPER_CONTEXT.md)

## Что теперь умеет система

- удалять project-local временные smoke/state-файлы через Python helper с retry logic
- держать cleanup workflow внутри workspace
- использовать более воспроизводимые служебные automation-paths

## Важная граница

Это уменьшает зависимость от ad-hoc shell-команд, но не гарантирует снятие всех ограничений:

- если Windows удерживает файл открытым, Python тоже может получить `PermissionError`
- если действие выходит за границы workspace или связано с риском, отдельные ограничения всё равно возможны

## Что дальше

1. По возможности переводить новые служебные workflow в Python helpers внутри [`development/scripts/`](/D:/Development%20GPTMEAi/development/scripts).
2. Использовать shell только там, где Python-путь реально не подходит.
