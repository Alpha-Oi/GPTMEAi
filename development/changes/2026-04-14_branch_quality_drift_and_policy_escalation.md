# 2026-04-14 - Branch quality drift and policy escalation

## Что изменено

- В [`planning/runtime.py`](/D:/Development%20GPTMEAi/planning/runtime.py) добавлен long-horizon `branch quality drift` summary поверх уже существующего trend layer.
- Planner теперь считает `pressure_level` (`low / medium / high / critical`) и `pressure_score` по накопленной recovery history.
- `planner gate` теперь может эскалироваться не только от текущего branch status, но и от накопленного branch pressure.
- В `branch_health_snapshot` и `status_snapshot` добавлены новые счётчики `pressure_medium / pressure_high / pressure_critical`.
- В [`scripts/api_server.py`](/D:/Development%20GPTMEAi/scripts/api_server.py) `/health` теперь отдаёт planner branch pressure counts.
- В [`dashboard/index.html`](/D:/Development%20GPTMEAi/dashboard/index.html) drift/pressure выведены в:
  - branch health cards
  - recovery workflow cards
  - plan cards
  - branch/recovery overview summaries

## Зачем

Обычного `trend` уже было недостаточно: ветка могла выглядеть “терпимо” по последнему состоянию, но при этом иметь накопленную историю compensation/remediation и оставаться фактически нестабильной. Новый pressure layer позволяет AI OS учитывать не только последний recovery outcome, но и качество ветки во времени.

## Проверка

Изолированная проверка на временном planner state подтвердила:

- `demo/recovery-remediation` -> `pressure_level=critical`, `gate=restricted`
- `demo/recovery-observe` -> `pressure_level=low`, `gate=guarded`

## Результат

Planner стал строже и ближе к реальной AI OS policy-модели: ветка теперь может быть ограничена не только по текущему incident status, но и по накопленной истории её нестабильности.
