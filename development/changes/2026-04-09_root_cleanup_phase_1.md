# 2026-04-09 Root Cleanup Phase 1

## Что изменено

Из корня проекта вынесены в `development/`:

- диагностические `.log` -> [`development/logs/`](/D:/Development%20GPTMEAi/development/logs)
- диагностические `.txt` и `.json` -> [`development/tmp/`](/D:/Development%20GPTMEAi/development/tmp)
- одноразовые `fix_*`, `update_*`, `upgrade_*`, `rebuild_*`, `dashboard_*` -> [`development/scripts/`](/D:/Development%20GPTMEAi/development/scripts)

## Почему это важно

Это первый реальный шаг к чистому корню проекта:

- основной runtime теперь читается заметно проще
- временная инженерная деятельность отделена от официальной структуры AI OS
- developer workspace начинает работать не как идея, а как реальный слой проекта

## Что осталось на следующих фазах

Следующие кандидаты на перенос:

- `test_*`
- неофициальные `run_*`
- неофициальные `setup_*`
- неофициальные `manage_*`
- часть `move_*`, `analyze_*`, `collect_*` и других исторических служебных root-скриптов

## Примечание

Официальные entrypoint-файлы и постоянные data/doc-файлы не переносились.
