# 2026-04-28 - Stabilization replay continuity smoke

## Что добавлено

- добавлен `development/scripts/smoke_stabilization_replay_continuity.py` как reusable smoke для stabilization/replay continuity
- скрипт использует только isolated temp-root state под `%TEMP%`, поддерживает `--json` и `--cleanup`
- smoke проверяет terminal `branch_stabilization completed/failed` branch health outcomes, planner gate и dispatch policy continuity, `branch_recovery_signal` в planner preview и через `/planner/recovery/preview`, snapshot coverage freshness behavior, recovery anchor bias behavior, API visibility для `anchor_bias`, authoritative `snapshot_id`, `no-signal` compatibility, safe `no-fresh` fallback и сохранение `operation_id` в preview context

## Результат проверки

- `py_compile` для smoke script прошёл с `pycache_prefix`
- `.\venv\Scripts\python.exe .\development\scripts\smoke_stabilization_replay_continuity.py --json --cleanup` прошёл
- `cleanup_succeeded=true`
- `temp_root_exists_after_cleanup=false`

## Семантическая заметка

- текущий smoke фиксирует, что failed `branch_stabilization` может давать более строгий execution dispatch behavior, тогда как replay preview остаётся advisory/restricted; это пока следует считать follow-up semantic consistency check, если позже понадобится выровнять policy surfaces
