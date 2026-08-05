# 2026-04-13 Recovery Branch Health And Confidence

## Что изменено

В recovery workflow добавлен post-validation quality layer, который оценивает здоровье ветки после завершения recovery:

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

- recovery workflow публикует `branch_health`
- `branch_health` включает:
  - `status`
  - `summary`
  - `recommendation`
  - `quality_score`
  - `quality_grade`
  - `confidence_score`
  - `confidence_level`
  - validation/remediation/replay signals
- planner aggregates теперь считают recovery health-срезы: `healthy / observe / degraded / recovering / blocked`
- `/health` отдаёт aggregate view по recovery health
- dashboard показывает health/quality/confidence и для plan cards, и для recovery workflow cards

## Почему это важно

Это делает recovery понятнее для оператора и самого runtime:

- система больше не ограничивается `workflow completed`
- теперь видно, насколько ветка действительно восстановлена
- compensation и remediation начинают влиять не только на steering, но и на итоговую оценку качества восстановления
- control plane получает основу для будущих automated gating и planner-side decisions

## Проверка

- AST и import-check прошли для:
  - [`planning/runtime.py`](/D:/Development%20GPTMEAi/planning/runtime.py)
  - [`scripts/api_server.py`](/D:/Development%20GPTMEAi/scripts/api_server.py)
  - [`development/scripts/smoke_recovery_workflow.py`](/D:/Development%20GPTMEAi/development/scripts/smoke_recovery_workflow.py)
  - [`development/scripts/smoke_recovery_remediation.py`](/D:/Development%20GPTMEAi/development/scripts/smoke_recovery_remediation.py)
- обычный compensated recovery smoke подтвердил:
  - `branch_health.status = observe`
  - `quality_score = 86`
  - `confidence_score = 92`
  - `validation_passed = true`
- remediation-aware recovery smoke подтвердил:
  - `branch_health.status = observe`
  - `quality_score = 70`
  - `confidence_score = 74`
  - `validation_passed = true`
  - `remediation.status = completed`

## Ограничения

- это пока point-in-time оценка по текущему recovery workflow, а не долгосрочный trend analysis
- historical failed execution operations по-прежнему сохраняются в execution snapshot даже после successful recovery/remediation
- временные isolated JSON-файлы в [`development/tmp/`](/D:/Development%20GPTMEAi/development/tmp) могут остаться из-за `WinError 5 / Access denied`

## Что дальше

1. Добавить history-aware health trends и branch quality drift.
2. Связать `branch_health.recommendation` с planner-side gating и runtime policy.
3. Продолжить расширять branch/time model без потери inspectable control plane.
