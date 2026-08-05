# 2026-04-14 Branch Health Trends And Planner Gating

## Что изменено

В официальный planner/runtime добавлен history-aware слой для здоровья веток и planner-side gating:

- [`planning/runtime.py`](/D:/Development%20GPTMEAi/planning/runtime.py)
- [`scripts/api_server.py`](/D:/Development%20GPTMEAi/scripts/api_server.py)
- [`dashboard/index.html`](/D:/Development%20GPTMEAi/dashboard/index.html)
- [`development/scripts/smoke_recovery_workflow.py`](/D:/Development%20GPTMEAi/development/scripts/smoke_recovery_workflow.py)
- [`development/scripts/smoke_recovery_remediation.py`](/D:/Development%20GPTMEAi/development/scripts/smoke_recovery_remediation.py)

Также обновлены:

- [`README.md`](/D:/Development%20GPTMEAi/README.md)
- [`docs/developer/DEVELOPER_CONTEXT.md`](/D:/Development%20GPTMEAi/docs/developer/DEVELOPER_CONTEXT.md)
- [`AI_OS_LAYER_TECHNICAL_SPEC.md`](/D:/Development%20GPTMEAi/AI_OS_LAYER_TECHNICAL_SPEC.md)

## Что теперь умеет система

- planner хранит persistent `branch_health_history`
- recovery workflow публикует не только `branch_health`, но и `trend` + `planner_gate`
- появился отдельный branch-level snapshot: `GET /planner/branch-health`
- `planner/status` теперь показывает branch health summaries и aggregate counts
- `/health` теперь включает branch gate / declining-trend counters
- `execute_ready_steps()` реально использует planner gate:
  - `guarded` снижает параллелизм
  - `restricted` и `blocked` останавливают non-recovery работу на ветке
- dashboard показывает trend/gate для recovery workflows, plans и branch health view

## Почему это важно

Теперь recovery quality перестал быть только наблюдаемой телеметрией.

Planner начал использовать состояние ветки как policy-input:

- качество восстановления влияет на дальнейшее исполнение задач
- branch-aware orchestration стала частью официального runtime
- control plane получил inspectable объяснение, почему ветка идёт в `open / guarded / restricted / blocked`

## Проверка

- AST и import-check прошли для:
  - [`planning/runtime.py`](/D:/Development%20GPTMEAi/planning/runtime.py)
  - [`scripts/api_server.py`](/D:/Development%20GPTMEAi/scripts/api_server.py)
  - [`development/scripts/smoke_recovery_workflow.py`](/D:/Development%20GPTMEAi/development/scripts/smoke_recovery_workflow.py)
  - [`development/scripts/smoke_recovery_remediation.py`](/D:/Development%20GPTMEAi/development/scripts/smoke_recovery_remediation.py)
- `python development/scripts/smoke_recovery_workflow.py --json` подтвердил:
  - `branch_health.status = observe`
  - `trend.direction = improving`
  - `planner_gate.mode = guarded`
  - operational follow-up на той же ветке был ограничен до `queued_count = 1`
- `python development/scripts/smoke_recovery_remediation.py --json` подтвердил:
  - `branch_health.status = observe`
  - `trend.direction = improving`
  - `planner_gate.mode = guarded`
- cleanup helper успешно удалил временные recovery/remediation smoke JSON через [`cleanup_tmp_artifacts.py`](/D:/Development%20GPTMEAi/development/scripts/cleanup_tmp_artifacts.py)

## Ограничения

- это пока short-horizon branch history, а не долгосрочная branch memory
- gate пока влияет на planner queue/execution policy, но ещё не связан с отдельным approval layer
- quality drift и branch memory ещё не заведены как самостоятельные runtime artifacts

## Что дальше

1. Добавить long-horizon `branch quality drift` и branch health memory поверх текущей history.
2. Связать planner gate с более строгими recovery/approval policies.
3. Продолжать расширять branch/time model и snapshot lineage без потери inspectable control plane.
