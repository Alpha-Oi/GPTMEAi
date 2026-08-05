# 2026-04-13 Planner Orchestration And Remediation

## Что изменено

Углублён официальный `planner runtime` и связь `Cognitive Loop -> Planner -> Agent Runtime`:

- [`planning/runtime.py`](/D:/Development%20GPTMEAi/planning/runtime.py)
- [`ai_os/cognitive_loop.py`](/D:/Development%20GPTMEAi/ai_os/cognitive_loop.py)
- [`scripts/api_server.py`](/D:/Development%20GPTMEAi/scripts/api_server.py)
- [`dashboard/index.html`](/D:/Development%20GPTMEAi/dashboard/index.html)

Также обновлены:

- [`README.md`](/D:/Development%20GPTMEAi/README.md)
- [`docs/developer/DEVELOPER_CONTEXT.md`](/D:/Development%20GPTMEAi/docs/developer/DEVELOPER_CONTEXT.md)
- [`AI_OS_LAYER_TECHNICAL_SPEC.md`](/D:/Development%20GPTMEAi/AI_OS_LAYER_TECHNICAL_SPEC.md)

## Что теперь умеет система

- разделять cognitive planning на отдельные persistent plan groups:
  - `operational`
  - `recovery`
  - `remediation`
  - `branch_stabilization`
- использовать `manager-first dispatch` внутри planner runtime
- ограничивать параллелизм плана через `max_parallel_steps`
- ставить worker steps только после coordination step менеджера
- строить remediation plan для execution failures / pending compensations
- строить branch stabilization plan для lineage/snapshot coverage проблем
- не дублировать queue dispatch, если в runtime уже есть активная задача с тем же title

## Почему это важно

Это переводит AI OS от просто `task queue` к более системной orchestration-модели:

- менеджеры координируют
- воркеры исполняют
- сбои превращаются в remediation flow
- branch/time проблемы превращаются в отдельный план стабилизации

## Что дальше

1. Связать planner runtime с replay/snapshot recovery flows.
2. Уточнить manager/worker role policies и auto-assignment.
3. Продолжать cleanup legacy и корня проекта без поломки рабочего runtime.
