# 2026-04-14 - Pressure-aware dispatch and remediation policy

## Что сделано

- planner runtime теперь рассчитывает отдельный `dispatch_policy` поверх `branch gate / branch pressure`
- queued tasks получают branch-aware `dispatch_policy` metadata
- agent runtime уважает этот policy не только в managed dispatch preview, но и при manual `claim_task`
- recovery remediation policy теперь адаптируется к `branch pressure`
- dashboard показывает `dispatch mode / dispatch cap` и adaptive remediation details
- `/health` и planner snapshots получили dispatch-aware branch aggregates

## Инженерный смысл

Раньше `branch pressure` влиял в основном на planner gate и шаги планов.
Теперь он влияет и на сам execution path:

- критические ветки ограничивают branch-level dispatch
- manual claim больше не может обойти branch policy
- recovery/remediation ветки получают сериализованное исполнение под давлением
- remediation threshold сжимается на критических ветках, чтобы система раньше переходила в stabilizing behaviour

## Основные файлы

- `planning/runtime.py`
- `ai_os/role_policy.py`
- `ai_os/agent_runtime.py`
- `scripts/api_server.py`
- `dashboard/index.html`
- `README.md`
- `docs/developer/DEVELOPER_CONTEXT.md`
- `AI_OS_LAYER_TECHNICAL_SPEC.md`

## Проверка

- `py_compile` для `planning/runtime.py`, `ai_os/role_policy.py`, `ai_os/agent_runtime.py`, `scripts/api_server.py`
- isolated smoke: branch dispatch limit blocks second assignment on same critical branch
- isolated smoke: manual `claim_task` no longer bypasses branch dispatch policy
- isolated smoke: demo remediation branch produces `pressure_level=critical`, `threshold=1`, `dispatch_policy.mode=restricted` inside recovery workflow
