# 2026-04-13 Recovery Remediation Policy

## Что изменено

В официальный recovery workflow встроена remediation policy для repeated recovery failures:

- [`planning/runtime.py`](/D:/Development%20GPTMEAi/planning/runtime.py)
- [`scripts/api_server.py`](/D:/Development%20GPTMEAi/scripts/api_server.py)
- [`dashboard/index.html`](/D:/Development%20GPTMEAi/dashboard/index.html)
- [`development/scripts/smoke_recovery_remediation.py`](/D:/Development%20GPTMEAi/development/scripts/smoke_recovery_remediation.py)

Также обновлены:

- [`README.md`](/D:/Development%20GPTMEAi/README.md)
- [`docs/developer/DEVELOPER_CONTEXT.md`](/D:/Development%20GPTMEAi/docs/developer/DEVELOPER_CONTEXT.md)
- [`AI_OS_LAYER_TECHNICAL_SPEC.md`](/D:/Development%20GPTMEAi/AI_OS_LAYER_TECHNICAL_SPEC.md)
- [`development/scripts/README.md`](/D:/Development%20GPTMEAi/development/scripts/README.md)

## Что теперь умеет система

- recovery workflow ведёт failure budget по disrupted replay steps
- после достижения порога repeated recovery failures planner:
  - ставит recovery progression на паузу
  - поднимает child `remediation` plan
  - queue/dispatch-ит remediation chain
  - после completion remediation-plan автоматически возвращает workflow в recovery path
- `planner/status`, `planner/recovery/workflows`, `health` и dashboard теперь показывают remediation status, blocking state и remediation plan linkage
- completion remediation task теперь тоже продвигает свой workflow через planner, а не остаётся ручным шагом

## Почему это важно

Это делает recovery контур устойчивее:

- repeated recovery failures больше не ведут к слепому продолжению replay
- система умеет останавливаться в контролируемой точке
- remediation становится частью официальной orchestration-логики AI OS, а не внешним ручным процессом
- после remediation recovery может штатно resume-иться и завершаться

## Проверка

- AST и import-check прошли для:
  - [`planning/runtime.py`](/D:/Development%20GPTMEAi/planning/runtime.py)
  - [`scripts/api_server.py`](/D:/Development%20GPTMEAi/scripts/api_server.py)
  - [`development/scripts/smoke_recovery_remediation.py`](/D:/Development%20GPTMEAi/development/scripts/smoke_recovery_remediation.py)
- новый isolated smoke helper подтвердил полный путь:
  - `coordinate_snapshot_recovery`
  - `review_recovery_anchor`
  - `replay_step_01`
  - forced failure
  - compensation
  - `replay_step_02`
  - forced failure
  - compensation
  - `coordinate_recovery_remediation`
  - `analyze_recovery_disruption`
  - `stabilize_recovery_branch_state`
  - `approve_recovery_resume`
  - `replay_step_03`
  - `validate_recovered_branch`
  - `workflow_complete`
- smoke также подтвердил:
  - `advance_target = remediation` на момент repeated failures
  - `remediation.status = completed` после remediation chain
  - `resolved_disruption_count = 2`
  - `recovery_compensation_counts.completed = 2`

## Ограничения

- execution snapshot сохраняет исторические failed recovery operations даже после того, как planner перевёл workflow в compensated/remediated state
- временные isolated JSON-файлы в [`development/tmp/`](/D:/Development%20GPTMEAi/development/tmp) могут остаться из-за `WinError 5 / Access denied`

## Что дальше

1. Добавить post-validation branch health и confidence signals.
2. Связать remediation outcome с richer recovery quality summary.
3. Продолжить расширять branch/time model без потери inspectable control plane.
