# Root Cleanup Backlog

Этот файл фиксирует, что ещё стоит постепенно вынести из корня проекта, чтобы основной runtime оставался чистым.

## Кандидаты на постепенный перенос

- `fix_*`
  статус: `phase 1 moved to development/scripts`
- `update_*`
  статус: `phase 1 moved to development/scripts`
- `upgrade_*`
  статус: `phase 1 moved to development/scripts`
- `rebuild_*`
  статус: `phase 1 moved to development/scripts`
- `dashboard_*`
  статус: `phase 1 moved to development/scripts`
- `test_*`
- `run_*`, которые не являются официальными entrypoint-файлами
- одиночные `.log`, `.txt`, `.json` диагностические артефакты
  статус: `phase 1 moved to development/logs and development/tmp`

## Что уже сделано

В рамках первой фазы из корня уже вынесены:

- одноразовые `fix_*`
- одноразовые `update_*`
- одноразовые `upgrade_*`
- одноразовые `rebuild_*`
- одноразовые `dashboard_*`
- диагностические `.log`
- диагностические `.txt`
- диагностические `.json`

Это не считается полной очисткой корня, но уже убирает самый шумный слой временных артефактов.

## Принцип переноса

Переносить только после проверки, что:

- файл не участвует в текущем official runtime
- файл не нужен как историческая точка входа для безопасного восстановления
- у переноса не сломаются существующие относительные пути

## Целевые места

- временные скрипты -> `development/scripts/`
- change notes -> `development/changes/`
- рабочие логи -> `development/logs/`
- временные файлы и черновики -> `development/tmp/`
