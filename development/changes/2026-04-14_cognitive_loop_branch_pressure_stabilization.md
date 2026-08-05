# 2026-04-14 - Cognitive loop branch pressure stabilization

## Что сделано

- `cognitive_loop` теперь читает `planner branch health`
- loop выделяет pressure-heavy ветки с `high/critical pressure` или `restricted/blocked dispatch`
- при таких ветках loop автоматически добавляет `branch_stabilization` plan group
- внутри branch stabilization теперь появляются pressure-oriented шаги:
  - `Review branch pressure controls`
  - `Stabilize dispatch policy`
- для наиболее жёстких веток branch stabilization автоматически уходит в serialized mode (`max_parallel_steps = 1`)

## Зачем это нужно

До этого `branch pressure` в основном влиял на planner/runtime policy и dispatch caps.
Теперь AI OS начинает реагировать на него как на повод для собственной работы:

- не только запрещать
- но и инициировать стабилизацию
- не только показывать риск
- но и планировать устранение причин branch pressure

Это важный переход от observability/gating к более автономному branch-aware поведению.

## Основные файлы

- `ai_os/cognitive_loop.py`
- `README.md`
- `docs/developer/DEVELOPER_CONTEXT.md`
- `AI_OS_LAYER_TECHNICAL_SPEC.md`

## Проверка

- AST-проверка `ai_os/cognitive_loop.py` и связанных Python-модулей
- isolated smoke в `development/tmp`: critical demo branch из planner branch health приводит к появлению `branch_stabilization` plan group
- smoke подтвердил наличие pressure-oriented шагов и `max_parallel_steps = 1` для критической ветки
