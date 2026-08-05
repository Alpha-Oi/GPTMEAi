# 2026-04-14 - Dashboard recovery demo seed

## Что изменено

- В [`planning/runtime.py`](/D:/Development%20GPTMEAi/planning/runtime.py) добавлен `seed_demo_recovery_state()` и внутренние helper-методы для безопасного создания demo-only recovery/remediation workflow.
- В [`scripts/api_server.py`](/D:/Development%20GPTMEAi/scripts/api_server.py) добавлен endpoint `POST /planner/recovery/demo`.
- В [`dashboard/index.html`](/D:/Development%20GPTMEAi/dashboard/index.html) добавлена кнопка `Seed recovery demo`, а `Recovery workflows` теперь показывает полный recovery snapshot, а не только active-only view.
- Добавлен project-local helper [`development/scripts/seed_recovery_demo.py`](/D:/Development%20GPTMEAi/development/scripts/seed_recovery_demo.py).

## Зачем

Recovery workflow, remediation и branch health уже работали в isolated smoke-tests, но в живом dashboard оставались пустыми, пока в runtime не происходил реальный recovery incident. Новый demo seed даёт безопасный способ визуально показать эти слои прямо в интерфейсе без воздействия на `main` branch.

## Как это работает

- Создаются только demo-only workflow на ветках `demo/recovery-observe` и `demo/recovery-remediation`.
- Первый workflow показывает compensated recovery с успешной validation.
- Второй workflow показывает remediation-aware recovery path с history-aware branch health.
- Demo data можно пере-seed-ить с reset существующих demo workflows.

## Что дальше

- При желании можно расширить demo seed до отдельного `AI OS demo dataset`, который будет включать не только recovery/branch health, но и planner/execution lineage walkthrough для onboarding.
