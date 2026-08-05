# 2026-04-13 Recovery Validation Handoff

## Что изменено

Recovery workflow доведён до completion-driven handoff, при котором завершённая задача сразу возвращается в planner и может продвинуть workflow к следующей фазе:

- [`planning/runtime.py`](/D:/Development%20GPTMEAi/planning/runtime.py)
- [`scripts/api_server.py`](/D:/Development%20GPTMEAi/scripts/api_server.py)
- [`development/scripts/smoke_recovery_workflow.py`](/D:/Development%20GPTMEAi/development/scripts/smoke_recovery_workflow.py)

Также обновлены:

- [`README.md`](/D:/Development%20GPTMEAi/README.md)
- [`docs/developer/DEVELOPER_CONTEXT.md`](/D:/Development%20GPTMEAi/docs/developer/DEVELOPER_CONTEXT.md)
- [`AI_OS_LAYER_TECHNICAL_SPEC.md`](/D:/Development%20GPTMEAi/AI_OS_LAYER_TECHNICAL_SPEC.md)

## Что теперь умеет система

- planner runtime получил `advance_from_task(...)`
- `POST /agents/complete` теперь не делает слепой `run_once()`, а возвращает завершённую task в planner с её `plan_id/plan_kind`
- recovery workflow может автоматически пройти путь:
  - `replay_step_02`
  - `validate_recovered_branch`
  - `workflow_complete`
- для recovery-hand-off сохраняются `auto_dispatch`, `auto_compensate` и `dispatch_limit`, поэтому workflow остаётся phase-aware и plan-scoped

## Почему это важно

Это замыкает recovery loop уже не только на уровне queue/dispatch, но и на уровне завершения шага:

- planner начинает реагировать на фактический completion recovery-step
- validation становится частью штатного recovery flow, а не отдельным ручным действием
- workflow теперь может закрыться в `completed` через официальный control-plane путь

## Проверка

- AST и import-check прошли для:
  - [`planning/runtime.py`](/D:/Development%20GPTMEAi/planning/runtime.py)
  - [`scripts/api_server.py`](/D:/Development%20GPTMEAi/scripts/api_server.py)
  - [`development/scripts/smoke_recovery_workflow.py`](/D:/Development%20GPTMEAi/development/scripts/smoke_recovery_workflow.py)
- обновлённый smoke test подтвердил цепочку:
  - `coordinate_snapshot_recovery`
  - `review_recovery_anchor`
  - `replay_step_01`
  - forced failure
  - automatic compensation
  - `replay_step_02`
  - `validate_recovered_branch`
  - `workflow_complete`
- smoke также подтвердил:
  - `workflow.status = completed`
  - `workflow.current_phase = completed`
  - `phase_counts.validation.completed = 1`
  - `recovery_operation_counts.committed = 4`
  - `recovery_compensation_counts.completed = 1`

## Ограничения

- execution snapshot сохраняет исторический `failed` outcome для первой неуспешной replay-operation, даже если planner после compensation продвинул workflow дальше
- временные isolated JSON-файлы в [`development/tmp/`](/D:/Development%20GPTMEAi/development/tmp) всё ещё могут не удаляться из-за `WinError 5 / Access denied`

## Что дальше

1. Добавить remediation policy для повторных recovery failures.
2. Расширить post-validation summaries, branch health и confidence signals.
3. Продолжить развивать branch/time model без потери inspectable control plane.
