# 2026-04-13 Agent Role Policy And Dispatch

## Что изменено

В официальный `Agent Hierarchy` добавлен capability-aware policy layer и управляемый dispatch:

- [`ai_os/role_policy.py`](/D:/Development%20GPTMEAi/ai_os/role_policy.py)
- [`ai_os/agent_runtime.py`](/D:/Development%20GPTMEAi/ai_os/agent_runtime.py)
- [`scripts/api_server.py`](/D:/Development%20GPTMEAi/scripts/api_server.py)
- [`dashboard/index.html`](/D:/Development%20GPTMEAi/dashboard/index.html)

Также обновлены:

- [`README.md`](/D:/Development%20GPTMEAi/README.md)
- [`docs/developer/DEVELOPER_CONTEXT.md`](/D:/Development%20GPTMEAi/docs/developer/DEVELOPER_CONTEXT.md)
- [`AI_OS_LAYER_TECHNICAL_SPEC.md`](/D:/Development%20GPTMEAi/AI_OS_LAYER_TECHNICAL_SPEC.md)

## Что теперь умеет система

- ранжировать queued tasks для конкретного агента по `role`, `owner_hint`, `capabilities` и базовой `history/load` модели
- строить global policy preview для queued tasks и idle agents
- выполнять managed dispatch через `POST /agents/dispatch`
- сохранять расширенные agent metrics:
  - `tasks_failed`
  - `tasks_claimed`
  - `last_assigned_at`
- показывать policy preview и dispatch result прямо в dashboard

## Почему это важно

Это переводит `Agent Hierarchy` от минимальной очереди и ручного claim к более осмысленной исполнительной модели AI OS:

- менеджеры и воркеры начинают назначаться не случайно, а по профилю
- planner orchestration получает более реалистичную исполнительную основу
- control plane может наблюдать не только очередь, но и логику назначения

## Проверка

- AST-проверка прошла для:
  - [`ai_os/role_policy.py`](/D:/Development%20GPTMEAi/ai_os/role_policy.py)
  - [`ai_os/agent_runtime.py`](/D:/Development%20GPTMEAi/ai_os/agent_runtime.py)
  - [`scripts/api_server.py`](/D:/Development%20GPTMEAi/scripts/api_server.py)
- import smoke прошёл для:
  - `ai_os.role_policy`
  - `ai_os.agent_runtime`
  - `scripts.api_server`
- isolated smoke test подтвердил:
  - `Memory Agent` забирает профильную memory-задачу, даже если она не первая в очереди
  - `Research Agent` забирает профильную analysis-задачу
  - managed dispatch доназначает `Development Manager` на recovery-задачу

## Что дальше

1. Связать role policy с deeper replay/recovery execution flows.
2. Добавить richer capability semantics и failure-history weighting.
3. Постепенно расширять branch-aware orchestration поверх текущей policy foundation.
