<div align="center">

# ◈ GPTMEAi

### Локальный прототип AI OS: память, граф связей, планирование и исполнение

**Control plane · Планировщик / исполнитель · Аудируемый operation ledger**

[![Compile](https://github.com/Alpha-Oi/GPTMEAi/actions/workflows/compile.yml/badge.svg)](https://github.com/Alpha-Oi/GPTMEAi/actions/workflows/compile.yml)
![Status](https://img.shields.io/badge/status-active-22a06b)
![License](https://img.shields.io/badge/license-proprietary-lightgrey)

[Как внести вклад](CONTRIBUTING.md) · [Правила сообщества](CODE_OF_CONDUCT.md) · [Безопасность](SECURITY.md) · [Notice](NOTICE)

</div>

---

Локальный прототип AI OS: память, граф связей, поиск, snapshot-экспорт и операторская панель.

Система состоит из control plane (ai_os), слоя планирования (planning), слоя исполнения с аудируемым ledger (execution) и ядра памяти (core). Работает локально, без внешних сервисов.

## Быстрый старт

Официальная точка запуска:

    D:\GPTMEAi_venv_candidate\Scripts\python.exe .\run_ai_os.py

Эквивалентный вариант:

    D:\GPTMEAi_venv_candidate\Scripts\python.exe -m ai_os

После запуска dashboard доступен на http://127.0.0.1:8010/dashboard

Проверить, что runtime поднялся:

    D:\GPTMEAi_venv_candidate\Scripts\python.exe -m ai_os.manifest

D:\GPTMEAi_venv_candidate — принятое официальное окружение. Проектные venv/ и venv_new/ использовать не следует, см. AGENTS.md. Справочный состав пакетов: docs/developer/ENV_SNAPSHOT_REFERENCE.txt

## Архитектура

Проект разделён на слои с односторонней зависимостью: планирование не вызывает исполнение напрямую, исполнение не принимает решений.

| Слой | Каталог | Ответственность |
|---|---|---|
| Control plane | ai_os/ | Каркас runtime, config, manifest, agent runtime, role policy |
| Планирование | planning/ | Мост planner/executor между cognitive loop и agent runtime |
| Исполнение | execution/ | Execution contracts, failure policy, compensation, operation ledger |
| Память | core/ | Память, поиск, временная шкала, граф связей |
| Ingestion | memory/ | Pipeline загрузки и данные памяти |
| Агенты | agents/ | Заготовка агентного runtime |
| API | scripts/api_server.py | Локальный API / control plane |
| UI | dashboard/ | Статический dashboard |

Persistent state:
- storage/agent_runtime.json — агенты, очередь задач, события
- storage/planner_runtime.json — планы, шаги, связь с runtime-задачами

Рабочие каталоги: development/ — временные скрипты, логи, change notes; legacy/ — исторические ветки; docs/developer/ — каноническая документация.

## Ключевые подсистемы

### Agent runtime

Хранит агентов, очередь и события между рестартами. При перезапуске незавершённые задачи in_progress мягко возвращаются в queued.

Распределение задач capability-aware: учитываются role, owner hint, capabilities и базовая модель history/load. Planner вкладывает в задачу нормализованный dispatch_policy, который agent runtime уважает даже при ручном claim.

### Planner

Строит планы с зависимыми шагами и ставит в очередь только готовые, с manager-first orchestration. Планы делятся по plan_kind:
- operational — обычная работа
- recovery — восстановление ветки
- remediation — реакция на повторные сбои recovery
- branch_stabilization — стабилизация проблемной ветки

### Recovery

Формальный workflow со стадиями:

    coordination -> anchor_review -> replay_execution -> validation

Перед созданием плана доступен preview. Replay-gap раскладывается в последовательные шаги по конкретным записям snapshot lineage и operation ledger.

Продвижение точечное: POST /planner/recovery/advance ставит в очередь следующий шаг и диспатчит задачи только этого плана. Завершённая задача возвращается в planner через POST /agents/complete, поэтому цепочка replay -> validate -> complete проходит без ручного вмешательства.

Если шаг упал и execution contract разрешает rollback/compensation — компенсация проводится автоматически. При исчерпании failure budget recovery ставится на паузу, поднимается дочерний remediation план, после его отработки workflow возвращается в recovery.

### Branch health

После валидации ветка получает quality_score, confidence_score и рекомендацию по режиму. История здоровья хранится persistent, по ней считаются trend direction и drift.

Ветка имеет gate, который применяется в execute_ready_steps:

| Gate | Эффект |
|---|---|
| open | без ограничений |
| guarded | повышенное внимание |
| restricted | ограничение non-recovery работы |
| blocked | остановка non-recovery работы |

Отдельно считается long-horizon pressure (low / medium / high / critical). Высокое давление может ужесточить gate даже когда последняя точка выглядит приемлемо, а также включает branch-level dispatch caps и сериализацию remediation.

### Cognitive loop и обучение

Loop видит branch health, замечает ветки с restricted/blocked dispatch или высоким давлением и сам поднимает branch_stabilization планы. На критических ветках parallelism ужимается до serial mode.

Завершённые stabilization-планы сохраняются в память как branch_stabilization_learning и переиспользуются. Повторяющиеся записи сворачиваются в reusable stabilization playbooks — planner может рекомендовать apply_stabilization_playbook вместо разбора сырой памяти.

### Operation ledger

Хранит delta, parent_operation_id, parent_branch_id, branch registry и lineage-представление. Прицельный просмотр:

    GET /execution/ledger?operation_id=...
    GET /execution/ledger?branch_id=...

## API

Все endpoints на http://127.0.0.1:8010

| Endpoint | Метод | Назначение |
|---|---|---|
| /health | GET | Состояние системы, включая recovery progress |
| /dashboard | GET | Операторская панель |
| /system/manifest | GET | Официальный/legacy срез проекта |
| /agents/status | GET | Состояние agent runtime |
| /agents/policy | GET | Рекомендации по назначению задач |
| /agents/dispatch | POST | Распределение queued tasks по idle agents |
| /agents/complete | POST | Завершение задачи с handoff обратно в planner |
| /cognitive/status | GET | Состояние cognitive loop |
| /planner/status | GET | Планы, шаги, recovery progress, health-counts |
| /planner/branch-health | GET | История здоровья веток, trend, drift, gate |
| /planner/playbooks | GET | Reusable stabilization playbooks |
| /planner/recovery/workflows | GET | Активные recovery workflows |
| /planner/recovery/preview | GET | Предпросмотр плана (?branch_id=main) |
| /planner/recovery/advance | POST | Продвижение workflow на шаг |
| /planner/recovery/demo | POST | Demo-seed на ветках demo/* |
| /execution/status | GET | Состояние execution layer |
| /execution/ledger | GET | Operation ledger, delta и lineage |

POST /planner/recovery/demo и кнопка Seed recovery demo создают demo-only workflows на ветках demo/* и не вмешиваются в main.

## Конфигурация

Скопируйте нужные значения из .env.example в .env

Основной runtime:
- GPTMEAI_HOST
- GPTMEAI_PORT

Legacy Flask bridge (при необходимости):
- GPTMEAI_TELEGRAM_TOKEN
- GPTMEAI_TELEGRAM_CHAT_ID

## Верификация

Воспроизводимые smoke-проверки:

    python development/scripts/smoke_recovery_workflow.py --json
    python development/scripts/smoke_recovery_remediation.py --json
    python development/scripts/smoke_branch_playbook.py --json
    python development/scripts/smoke_stabilization_replay_continuity.py --json
    python development/scripts/seed_recovery_demo.py --json

Правило из AGENTS.md: сначала самая узкая осмысленная проверка, затем более широкая по затронутой области. Для runtime/API изменений — минимум затронутый endpoint плюс /health, /planner/status, /execution/status.

## Документация

| Файл | Содержание |
|---|---|
| AGENTS.md | Операционный контракт проекта, protected zones, правила работы |
| docs/developer/DEVELOPER_CONTEXT.md | Основной onboarding для разработчика |
| AI_OS_PROJECT_AUDIT.md | Технический аудит и целевая архитектура |
| AI_OS_DEVELOPMENT_INVARIANTS.md | Инварианты, сохраняемые при переработке |
| AI_OS_LAYER_TECHNICAL_SPEC.md | Каноническая спецификация слоёв |
| CHAT_CORPUS_ARCHITECTURE_ANALYSIS.md | Выводы из анализа корпуса чатов |
| CHANGELOG.md | История развития runtime |
| development/changes/ | Заметки о серьёзных изменениях |

## Legacy

Не считать основным runtime:
- scripts/api_gui_integration.py
- core/cognitive_loop_api.py, core/cognitive_loop_api_v2.py
- apps/dashboard/
- GPTMemoryEngine/
- корневые fix_*, upgrade_*, rebuild_*, dashboard_* скрипты

Граница и документация исторических веток — в legacy/
