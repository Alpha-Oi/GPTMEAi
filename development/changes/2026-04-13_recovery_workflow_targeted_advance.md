# 2026-04-13 Recovery Workflow Targeted Advance

## Что изменено

Следующий слой recovery orchestration переведён из ручной сцепки вызовов в targeted advance flow:

- [`planning/runtime.py`](/D:/Development%20GPTMEAi/planning/runtime.py)
- [`ai_os/agent_runtime.py`](/D:/Development%20GPTMEAi/ai_os/agent_runtime.py)
- [`scripts/api_server.py`](/D:/Development%20GPTMEAi/scripts/api_server.py)
- [`dashboard/index.html`](/D:/Development%20GPTMEAi/dashboard/index.html)
- [`development/scripts/smoke_recovery_workflow.py`](/D:/Development%20GPTMEAi/development/scripts/smoke_recovery_workflow.py)

Также обновлены:

- [`README.md`](/D:/Development%20GPTMEAi/README.md)
- [`docs/developer/DEVELOPER_CONTEXT.md`](/D:/Development%20GPTMEAi/docs/developer/DEVELOPER_CONTEXT.md)
- [`AI_OS_LAYER_TECHNICAL_SPEC.md`](/D:/Development%20GPTMEAi/AI_OS_LAYER_TECHNICAL_SPEC.md)

## Что теперь умеет система

- planner умеет делать `advance_recovery_workflow(...)` для конкретного recovery plan
- `POST /planner/recovery/advance` продвигает recovery workflow без глобального dispatch по всей очереди
- agent runtime умеет делать filtered dispatch по `plan_id` и `task_ids`
- recovery workflow теперь отдаёт `next_actions`, чтобы control plane видел, что делать дальше:
  - `dispatch_ready_steps`
  - `await_step_completion`
  - `queue_next_phase`
  - `compensate_failed_step`
- создание recovery plan через `POST /planner/recovery` сразу использует новый targeted advance path

## Почему это важно

Это важный инженерный шаг, потому что recovery orchestration перестаёт быть побочным эффектом общего task queue:

- recovery можно продвигать адресно
- planner не вмешивается в unrelated queued tasks
- dashboard и API получают inspectable recovery steering, а не просто снимок статусов

## Проверка

- AST и import-check прошли для:
  - [`ai_os/agent_runtime.py`](/D:/Development%20GPTMEAi/ai_os/agent_runtime.py)
  - [`planning/runtime.py`](/D:/Development%20GPTMEAi/planning/runtime.py)
  - [`scripts/api_server.py`](/D:/Development%20GPTMEAi/scripts/api_server.py)
  - [`development/scripts/smoke_recovery_workflow.py`](/D:/Development%20GPTMEAi/development/scripts/smoke_recovery_workflow.py)
- обновлённый smoke test через [`smoke_recovery_workflow.py`](/D:/Development%20GPTMEAi/development/scripts/smoke_recovery_workflow.py) подтвердил:
  - три последовательных `advance` вызова продвигают workflow по цепочке:
    - `coordinate_snapshot_recovery`
    - `review_recovery_anchor`
    - `replay_step_01`
  - каждый `advance` делает ровно один targeted dispatch
  - workflow доходит до `replay_execution`
  - `next_actions` показывают `await_step_completion` для активного replay step
  - выбранные агенты соответствуют recovery semantics:
    - `Development Manager`
    - `Research Agent`
    - `Memory Agent`

## Ограничения

- временные isolated JSON-файлы в [`development/tmp/`](/D:/Development%20GPTMEAi/development/tmp) всё ещё могут не удаляться из-за `WinError 5 / Access denied`
- recovery advance пока ещё не завершает replay step автоматически и не запускает compensation chains без явного execution outcome

## Что дальше

1. Добавить richer automated flow для `replay_execution -> validation -> compensation`.
2. Связать `next_actions` с execution failure policy и compensation candidates глубже.
3. Продолжить расширять branch/time model без потери inspectable control plane.
