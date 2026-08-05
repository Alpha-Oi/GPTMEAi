# 2026-04-13 Recovery Compensation Advance

## Что изменено

Углублён recovery advance слой так, чтобы он мог автоматически компенсировать failed recovery steps и продолжать workflow:

- [`ai_os/agent_runtime.py`](/D:/Development%20GPTMEAi/ai_os/agent_runtime.py)
- [`planning/runtime.py`](/D:/Development%20GPTMEAi/planning/runtime.py)
- [`execution/runtime.py`](/D:/Development%20GPTMEAi/execution/runtime.py)
- [`scripts/api_server.py`](/D:/Development%20GPTMEAi/scripts/api_server.py)
- [`dashboard/index.html`](/D:/Development%20GPTMEAi/dashboard/index.html)
- [`development/scripts/smoke_recovery_workflow.py`](/D:/Development%20GPTMEAi/development/scripts/smoke_recovery_workflow.py)

Также обновлены:

- [`README.md`](/D:/Development%20GPTMEAi/README.md)
- [`docs/developer/DEVELOPER_CONTEXT.md`](/D:/Development%20GPTMEAi/docs/developer/DEVELOPER_CONTEXT.md)
- [`AI_OS_LAYER_TECHNICAL_SPEC.md`](/D:/Development%20GPTMEAi/AI_OS_LAYER_TECHNICAL_SPEC.md)

## Что теперь умеет система

- agent runtime выдаёт task payload уже с `compensation_status`, `execution_status` и `compensated_at`
- planner sync понимает compensated recovery failures и переводит такой step в `completed`, не теряя `last_error`
- `advance_recovery_workflow(...)` умеет:
  - находить failed recovery steps
  - вызывать execution compensation там, где она доступна
  - синхронизировать workflow после compensation
  - ставить следующий recovery step в очередь
  - dispatch-ить его через targeted plan-scoped dispatch
- execution snapshot теперь показывает `recovery_compensation_counts`
- dashboard показывает:
  - `replay compensated`
  - `recovery comp pending/available/completed`
  - `compensated_count` в recovery advance response

## Почему это важно

Это уже не просто observability, а первый operational recovery loop:

- failed replay step можно не останавливать вручную
- compensation становится частью recovery steering, а не отдельной ручной операцией
- planner начинает двигаться дальше после разрешённого recovery failure

## Проверка

- AST и import-check прошли для:
  - [`ai_os/agent_runtime.py`](/D:/Development%20GPTMEAi/ai_os/agent_runtime.py)
  - [`planning/runtime.py`](/D:/Development%20GPTMEAi/planning/runtime.py)
  - [`execution/runtime.py`](/D:/Development%20GPTMEAi/execution/runtime.py)
  - [`scripts/api_server.py`](/D:/Development%20GPTMEAi/scripts/api_server.py)
  - [`development/scripts/smoke_recovery_workflow.py`](/D:/Development%20GPTMEAi/development/scripts/smoke_recovery_workflow.py)
- обновлённый smoke test подтвердил цепочку:
  - `coordinate_snapshot_recovery`
  - `review_recovery_anchor`
  - `replay_step_01`
  - forced failure
  - automatic compensation
  - `replay_step_02`
- smoke также подтвердил:
  - `compensated_replay_steps = 1`
  - `recovery_compensation_counts.completed = 1`
  - `next_actions = await_step_completion` для активного второго replay step

## Ограничения

- execution operation после compensation сохраняет факт `failed` как исторический outcome, даже если planner трактует compensated recovery step как завершённый с точки зрения продвижения workflow
- временные isolated JSON-файлы в [`development/tmp/`](/D:/Development%20GPTMEAi/development/tmp) всё ещё могут не удаляться из-за `WinError 5 / Access denied`

## Что дальше

1. Автоматизировать переход от завершённого `replay_execution` к `validation`.
2. Добавить richer compensation policy и remediation policy для повторных recovery failures.
3. Продолжить расширять branch/time model без потери inspectable control plane.
