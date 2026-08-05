# GPTMEAi

Локальный прототип AI OS с памятью, графом связей, поиском, snapshot-экспортом и операторской панелью.

## Основной runtime

Официальная точка запуска проекта сейчас:

```powershell
D:\GPTMEAi_venv_candidate\Scripts\python.exe .\run_ai_os.py
```

или

```powershell
D:\GPTMEAi_venv_candidate\Scripts\python.exe -m ai_os
```

После запуска доступны:

- dashboard: `http://127.0.0.1:8010/dashboard`
- API health: `http://127.0.0.1:8010/health`
- agent runtime: `http://127.0.0.1:8010/agents/status`
- agent policy preview: `http://127.0.0.1:8010/agents/policy`
- cognitive loop: `http://127.0.0.1:8010/cognitive/status`
- planner runtime: `http://127.0.0.1:8010/planner/status`
- planner branch health: `http://127.0.0.1:8010/planner/branch-health`
- planner stabilization playbooks: `http://127.0.0.1:8010/planner/playbooks`
- recovery workflows: `http://127.0.0.1:8010/planner/recovery/workflows`
- recovery preview: `http://127.0.0.1:8010/planner/recovery/preview?branch_id=main`
- recovery advance: `POST http://127.0.0.1:8010/planner/recovery/advance`
- recovery demo seed: `POST http://127.0.0.1:8010/planner/recovery/demo`
- execution runtime: `http://127.0.0.1:8010/execution/status`
- operation ledger: `http://127.0.0.1:8010/execution/ledger`
- runtime manifest: `http://127.0.0.1:8010/system/manifest`

Текущий adopted runtime path:

```powershell
D:\GPTMEAi_venv_candidate\Scripts\python.exe .\run_ai_os.py
```

## Текущая структура

- `ai_os/` - новый официальный каркас runtime, config, manifest, agent runtime и role policy проекта
- `planning/` - официальный planner/executor bridge между cognitive loop и agent runtime
- `core/` - ядро памяти, поиска, временной шкалы и графа связей
- `execution/` - официальный execution layer с execution contracts, failure policy, compensation metadata и operation ledger c delta/branch/lineage model
- `storage/agent_runtime.json` - persistent state официального agent runtime
- `storage/planner_runtime.json` - persistent state официального planner runtime
- `scripts/api_server.py` - основной локальный API/control plane
- `dashboard/` - основной статический dashboard
- `memory/` - ingestion pipeline и данные памяти
- `agents/` - заготовка агентного runtime
- `docs/developer/` - каноническая документация для разработчика
- `development/` - рабочая папка для временных скриптов, логов, change notes и промежуточной деятельности
- `legacy/` - граница и документация для исторических веток

## Legacy ветки

Пока не считать основным runtime:

- `scripts/api_gui_integration.py`
- `core/cognitive_loop_api.py`
- `core/cognitive_loop_api_v2.py`
- `apps/dashboard/`
- `GPTMemoryEngine/`
- корневые `fix_*`, `upgrade_*`, `rebuild_*`, `dashboard_*` скрипты

## Конфигурация

Скопируйте значения из `.env.example` в `.env` и заполните только нужные переменные.

Основной runtime использует:

- `GPTMEAI_HOST`
- `GPTMEAI_PORT`

Legacy Flask bridge при необходимости использует:

- `GPTMEAI_TELEGRAM_TOKEN`
- `GPTMEAI_TELEGRAM_CHAT_ID`

## Состояние проекта

Технический аудит и рекомендованная целевая архитектура описаны в [`AI_OS_PROJECT_AUDIT.md`](./AI_OS_PROJECT_AUDIT.md).
Инварианты, которые мы сохраняем при дальнейшей переработке, зафиксированы в [`AI_OS_DEVELOPMENT_INVARIANTS.md`](./AI_OS_DEVELOPMENT_INVARIANTS.md).
Выводы из анализа исторического корпуса чатов зафиксированы в [`CHAT_CORPUS_ARCHITECTURE_ANALYSIS.md`](./CHAT_CORPUS_ARCHITECTURE_ANALYSIS.md).
Каноническая техническая спецификация слоёв AI OS зафиксирована в [`AI_OS_LAYER_TECHNICAL_SPEC.md`](./AI_OS_LAYER_TECHNICAL_SPEC.md).
Основной onboarding-файл для разработчика находится в [`docs/developer/DEVELOPER_CONTEXT.md`](./docs/developer/DEVELOPER_CONTEXT.md).
История серьёзных изменений и рабочая среда разработки ведутся в папке [`development/`](./development/).

Текущий официальный/legacy срез проекта можно посмотреть через:

```powershell
D:\GPTMEAi_venv_candidate\Scripts\python.exe -m ai_os.manifest
```

Agent runtime теперь сохраняет агентов, очередь задач и события в `storage/agent_runtime.json` и при рестарте мягко возвращает незавершённые `in_progress` задачи обратно в `queued`.
Поверх этого теперь есть capability-aware role policy: `GET /agents/policy` показывает рекомендации по назначению, а `POST /agents/dispatch` умеет распределять queued tasks по idle agents с учётом role, owner hint, capabilities и базовой history/load модели.
Planner runtime теперь сохраняет планы, шаги и их связь с runtime-задачами в `storage/planner_runtime.json`, умеет строить зависимые шаги, разделять планы по `plan_kind` (`operational`, `recovery`, `remediation`, `branch_stabilization`) и автоматически ставить в очередь только готовые шаги с manager-first orchestration.
Recovery planning теперь умеет строить `preview` перед созданием плана и раскладывать replay-gap не только в общий recovery flow, но и в последовательные replay steps по конкретным `snapshot lineage / operation ledger` entries.
Поверх этого recovery слой теперь ведёт формальный workflow со стадиями `coordination -> anchor_review -> replay_execution -> validation`, отдаёт активные recovery workflows через `GET /planner/recovery/workflows`, а также показывает recovery progress в `planner/status`, `execution/status`, `health` и dashboard.
Следующий orchestration-слой теперь тоже на месте: `POST /planner/recovery/advance` продвигает recovery workflow точечно, сам ставит следующий step в очередь и dispatch-ит только задачи конкретного recovery plan, не трогая остальную очередь runtime.
Поверх этого recovery advance теперь умеет автоматически проводить compensation для failed recovery steps, если execution contract разрешает rollback/compensation, и после этого продолжать workflow к следующему replay/validation step.
Следующий переход теперь тоже автоматизирован: `POST /agents/complete` возвращает завершённую recovery task обратно в planner через completion-driven handoff, поэтому recovery может пройти путь `replay_step_02 -> validate_recovered_branch -> workflow_complete` без отдельного ручного запуска planner.
Поверх этого recovery теперь получил remediation policy для повторных recovery failures: после исчерпания failure budget planner автоматически ставит recovery на паузу, поднимает child `remediation` plan, проводит remediation-step chain и затем возвращает workflow обратно в recovery/resume path.
Поверх validation/recovery completion теперь есть и post-validation quality layer: recovery workflow публикует `branch_health`, `quality_score`, `confidence_score`, рекомендации по режиму ветки и агрегированные health-counts в `planner/status`, `planner/recovery/workflows`, `/health` и dashboard.
Следующий слой этого же качества теперь тоже на месте: planner ведёт persistent `branch health history`, считает `trend direction / drift`, отдаёт отдельный `GET /planner/branch-health`, показывает branch-level gate (`open / guarded / restricted / blocked`) и реально использует этот gate в `execute_ready_steps`, ограничивая или останавливая non-recovery работу на ветке по её recovery quality.
Поверх этого теперь появился и более строгий `branch quality drift` слой: planner считает long-horizon pressure по накопленной recovery history, различает `low / medium / high / critical` pressure и умеет эскалировать branch gate до более жёсткого режима даже тогда, когда последняя точка выглядит не катастрофически, но исторически ветка остаётся нестабильной.
Следующий policy-слой теперь тоже встроен в runtime: planner вкладывает в queued tasks нормализованный `dispatch_policy`, agent runtime уважает его даже при ручном `claim/dispatch`, ветки с высоким давлением получают branch-level dispatch caps, а recovery remediation policy адаптируется по `branch pressure`, снижая disruption threshold и сериализуя remediation execution на критических ветках.
Следующий шаг автономии теперь тоже на месте: `cognitive loop` видит `planner branch health`, замечает ветки с `restricted/blocked dispatch` или `high/critical pressure` и сам поднимает `branch_stabilization` plans с pressure-oriented задачами на review/stabilization branch controls, а на самых жёстких ветках автоматически ужимает parallelism до serial mode.
Следующий learning-слой теперь тоже работает: completed `branch_stabilization` планы сохраняются в memory как `branch_stabilization_learning`, perception видит эти записи как stabilization memory, reasoning привязывает их к pressure-heavy веткам, а новые stabilization-планы начинают включать шаг `Review prior stabilization memory`, чтобы система опиралась на собственный прошлый branch-recovery опыт.
Следующий procedural reuse-слой теперь тоже оформлен: repeated `branch_stabilization_learning` записи сворачиваются в reusable `stabilization playbooks`, planner и branch health snapshots отдают их через `GET /planner/playbooks`, planner gate может рекомендовать `apply_stabilization_playbook`, а cognitive loop для pressure-heavy веток уже умеет заменять raw memory review на шаги `review/apply branch stabilization playbook`.
Чтобы это было видно не только в isolated smoke-проверках, dashboard и API теперь умеют безопасно поднимать `demo recovery seed`: `POST /planner/recovery/demo` и кнопка `Seed recovery demo` создают demo-only recovery/remediation workflows на ветках `demo/*`, не вмешиваясь в `main`, и сразу наполняют `Recovery workflows` и `Branch health` живыми данными для визуальной проверки.
Operation ledger теперь умеет хранить `delta`, `parent_operation_id`, `parent_branch_id`, branch registry и lineage-представление. Для прицельного просмотра можно использовать `GET /execution/ledger?operation_id=...` или `GET /execution/ledger?branch_id=...`.

Для воспроизводимой проверки recovery-ветки добавлен helper:

- `python development/scripts/smoke_recovery_workflow.py --json`
- `python development/scripts/smoke_recovery_remediation.py --json`
- `python development/scripts/smoke_branch_playbook.py --json`
- `python development/scripts/seed_recovery_demo.py --json`
