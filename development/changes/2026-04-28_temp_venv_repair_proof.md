# 2026-04-28 - Temp venv repair proof

## Что проверено

- side-by-side repair `venv` был создан под `%TEMP%`: `C:\Users\Crown-Aliy\AppData\Local\Temp\gptmeai_venv_repair_test_e4f96ff91028471b85e511504d2db7dd`
- current project `venv` не изменялся
- repair `venv` использует Python `3.14.3`
- `pip` работает в repair `venv`
- package install from `*.dist-info` inventory succeeded
- third-party imports passed: `flask`, `flask_cors`, `flask_socketio`, `requests`, `yaml`, `psutil`, `eventlet`, `socketio`, `engineio`
- project imports passed: `ai_os.runtime`, `scripts.api_server`
- consolidated smoke passed: `development/scripts/smoke_stabilization_replay_continuity.py --json --cleanup`
- smoke cleanup succeeded: `cleanup_succeeded=true`, `temp_root_exists_after_cleanup=false`

## Остаточные риски

- current damaged `venv` still passes project import comparison, but `pip` / `site-packages` corruption remains
- `eventlet` emitted a deprecation warning during import; this is not a current blocker, but should remain a future dependency risk
- current `venv` should not be replaced yet

## Следующий environment step

- replacement must be a separate approved plan: create `venv_new` or equivalent final candidate, verify it, then decide whether to retire the current `venv`
