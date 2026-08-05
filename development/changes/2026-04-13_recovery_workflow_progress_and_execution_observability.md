# 2026-04-13 Recovery Workflow Progress And Execution Observability

## Что изменено

Углублён следующий слой official recovery/runtime orchestration:

- [`planning/runtime.py`](/D:/Development%20GPTMEAi/planning/runtime.py)
- [`execution/runtime.py`](/D:/Development%20GPTMEAi/execution/runtime.py)
- [`execution/snapshots.py`](/D:/Development%20GPTMEAi/execution/snapshots.py)
- [`scripts/api_server.py`](/D:/Development%20GPTMEAi/scripts/api_server.py)
- [`dashboard/index.html`](/D:/Development%20GPTMEAi/dashboard/index.html)
- [`development/scripts/smoke_recovery_workflow.py`](/D:/Development%20GPTMEAi/development/scripts/smoke_recovery_workflow.py)

Также обновлены:

- [`README.md`](/D:/Development%20GPTMEAi/README.md)
- [`docs/developer/DEVELOPER_CONTEXT.md`](/D:/Development%20GPTMEAi/docs/developer/DEVELOPER_CONTEXT.md)
- [`AI_OS_LAYER_TECHNICAL_SPEC.md`](/D:/Development%20GPTMEAi/AI_OS_LAYER_TECHNICAL_SPEC.md)
- [`development/scripts/README.md`](/D:/Development%20GPTMEAi/development/scripts/README.md)

## Что теперь умеет система

- вести formal recovery workflow по фазам:
  - `coordination`
  - `anchor_review`
  - `replay_execution`
  - `validation`
- отдавать активные и завершённые recovery workflows через `GET /planner/recovery/workflows`
- показывать recovery progress внутри `planner/status`
- показывать отдельные recovery operation counts внутри `execution/status`
- прокидывать recovery observability в `health` и dashboard
- строить replay steps с более семантичным summary, чтобы capability/role inference опирался на смысл операции, а не на слишком общий ledger text
- прогонять isolated smoke test recovery workflow через project-local Python helper

## Почему это важно

Этот шаг переводит recovery из состояния "preview + набор replay steps" в более оформленный operational workflow:

- planner теперь не только создаёт recovery plan, но и может показать, на какой фазе recovery реально находится
- execution layer начинает быть наблюдаемым именно как recovery substrate, а не только как общий runtime задач
- replay execution становится лучше совместим с capability-aware dispatch, потому что replay summary ближе к смыслу восстанавливаемой операции

## Проверка

- AST и import-check прошли для:
  - [`planning/runtime.py`](/D:/Development%20GPTMEAi/planning/runtime.py)
  - [`execution/runtime.py`](/D:/Development%20GPTMEAi/execution/runtime.py)
  - [`execution/snapshots.py`](/D:/Development%20GPTMEAi/execution/snapshots.py)
  - [`scripts/api_server.py`](/D:/Development%20GPTMEAi/scripts/api_server.py)
  - [`development/scripts/smoke_recovery_workflow.py`](/D:/Development%20GPTMEAi/development/scripts/smoke_recovery_workflow.py)
- isolated smoke test через [`smoke_recovery_workflow.py`](/D:/Development%20GPTMEAi/development/scripts/smoke_recovery_workflow.py) подтвердил:
  - recovery preview возвращает `planned_replay_step_count = 2` при `max_replay_steps=2`
  - planner queues steps по порядку:
    - `coordinate_snapshot_recovery`
    - `review_recovery_anchor`
    - `replay_step_01`
  - workflow реально доходит до фазы `replay_execution`
  - `execution/status` показывает отдельные recovery operation counts
  - capability-aware dispatch выбрал:
    - `Development Manager` для coordination
    - `Research Agent` для anchor review
    - `Memory Agent` для первого replay step

## Ограничения

- временные isolated state-файлы в [`development/tmp/`](/D:/Development%20GPTMEAi/development/tmp) после smoke всё ещё могут не удаляться из-за `WinError 5 / Access denied`
- recovery workflow пока ещё не доведён до полностью автоматизированных replay chains и compensation chains

## Что дальше

1. Довести `replay_execution` от phase-aware orchestration к более автоматизированному execution/validation flow.
2. Добавить richer recovery policy для failover, retry budget и compensation-aware replay.
3. Расширять branch/time model без потери inspectable control plane.
