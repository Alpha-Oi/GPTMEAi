# 2026-04-09 Agent Runtime Persistence

## Что изменено

Официальный `Agent Runtime` получил persistent state:

- [`ai_os/agent_runtime.py`](/D:/Development%20GPTMEAi/ai_os/agent_runtime.py)
- [`ai_os/config.py`](/D:/Development%20GPTMEAi/ai_os/config.py)

Также обновлены:

- [`dashboard/index.html`](/D:/Development%20GPTMEAi/dashboard/index.html)
- [`README.md`](/D:/Development%20GPTMEAi/README.md)
- [`docs/developer/DEVELOPER_CONTEXT.md`](/D:/Development%20GPTMEAi/docs/developer/DEVELOPER_CONTEXT.md)
- [`AI_OS_LAYER_TECHNICAL_SPEC.md`](/D:/Development%20GPTMEAi/AI_OS_LAYER_TECHNICAL_SPEC.md)

## Что теперь умеет система

- хранить `agents / tasks / events` в `storage/agent_runtime.json`
- поднимать это состояние после перезапуска процесса
- продолжать `task_id` без сброса счётчика
- безопасно requeue-ить `in_progress` задачи после рестарта
- переводить связанных `busy` агентов обратно в `idle`
- синхронизировать recovery с `Execution Runtime`, чтобы execution contract тоже возвращался в `planned`

## Почему это важно

Это закрывает один из главных системных пробелов:

- agent hierarchy больше не живёт только в памяти процесса
- control plane переживает рестарты стабильнее
- `Murphy-style` восстановление стало частью agent runtime, а не ручной операцией

## Что дальше

1. Развить `operation ledger` до `delta / branch / lineage` уровня.
2. Затем расширять nonlinear time model и snapshot lineage.
3. После этого усиливать planner/executor слой поверх текущего cognitive loop.
