# AI OS Layer Technical Specification

Этот документ переводит исходную блок-схему GPTMemory AI / Persistent AI Mind System в рабочую техническую спецификацию проекта.

Цель документа:

- зафиксировать канонические слои AI OS
- привязать их к текущим модулям проекта
- определить входы, выходы и ответственность каждого слоя
- задать направление дальнейшего рефакторинга без смены исходной идеи

## 1. Каноническая модель системы

Исходная схема проекта описывает 7 логических слоёв:

1. `User`
2. `Interface Layer`
3. `Persistent AI Mind`
4. `Memory Core`
5. `Cognitive Loop`
6. `Agent Hierarchy`
7. `Execution Layer`

Для инженерной реализации они сводятся к 4 главным системным слоям, уже зафиксированным в инвариантах проекта:

- `control plane`
- `kernel`
- `memory`
- `agent runtime`

Соответствие между ними такое:

| Логический слой схемы | Инженерный слой |
| --- | --- |
| `User` + `Interface Layer` | `control plane` |
| `Persistent AI Mind` + `Cognitive Loop` | `kernel` |
| `Memory Core` | `memory` |
| `Agent Hierarchy` + `Execution Layer` | `agent runtime` |

То есть схема не противоречит инвариантам. Она просто описывает их в более детализированном виде.

## 2. Слой `User`

### Назначение

Источник внешних команд, запросов, наблюдения и операторского управления системой.

### Входы слоя

- ручные команды оператора
- запросы на анализ, поиск, выполнение задач
- запросы на наблюдение за состоянием системы

### Выходы слоя

- намерения пользователя
- задачи для AI OS
- команды управления runtime

### Текущее представление в проекте

Это не кодовый модуль, а внешний субъект системы.

## 3. Слой `Interface Layer`

### Назначение

Предоставляет человеку и внешним инструментам доступ к AI OS через GUI и API.

### Ответственность

- принимать пользовательские запросы
- маршрутизировать их в runtime
- возвращать состояние памяти, агентов и системы
- давать inspectable control plane

### Входы слоя

- HTTP-запросы
- действия в dashboard
- будущие GUI / chat / API integration points

### Выходы слоя

- вызовы к memory subsystem
- вызовы к agent runtime
- вызовы к kernel / cognitive logic
- telemetry и status-ответы наружу

### Текущие модули

- `scripts/api_server.py`
- `dashboard/index.html`
- частично legacy: `scripts/api_gui_integration.py`

### Основные API-контракты

- `GET /health`
- `GET /system/manifest`
- `GET /memory/*`
- `GET /agents/status`
- `GET /execution/status`
- `GET /execution/ledger`
- `POST /agents/*`
- `POST /memory/pipeline/*`

### Что не должно жить в этом слое

- бизнес-логика памяти
- orchestration cognitive loop
- долгоживущая логика исполнения задач

## 4. Слой `Persistent AI Mind`

### Назначение

Центральный оркестратор системы. Это не UI и не просто хранилище, а внутреннее ядро, которое координирует память, cognitive loop, агенты и системное состояние.

### Ответственность

- хранить глобальную конфигурацию runtime
- знать официальную структуру проекта
- быть точкой сборки AI OS
- связывать memory, agent runtime и control plane

### Входы слоя

- конфигурация проекта
- вызовы control plane
- события памяти
- статусы агентного runtime

### Выходы слоя

- orchestration commands
- routing к memory / agents
- системный manifest
- runtime state

### Текущие модули

- `ai_os/runtime.py`
- `ai_os/config.py`
- `ai_os/manifest.py`
- `run_ai_os.py`
- `run_ai_os.ps1`

### Текущий статус

Слой уже существует как официальный bootstrap/runtime-carrier, но пока ещё не является полноценным когнитивным ядром. Сейчас он в основном отвечает за сборку системы и выбор официального пути запуска.

### Целевое состояние

Этот слой должен стать настоящим `AI OS kernel`, который:

- держит lifecycle подсистем
- управляет cognitive loop
- координирует память и агентов
- даёт единый runtime state

## 5. Слой `Memory Core`

### Назначение

Долговременная память AI OS. Содержит не только записи, но и поиск, временную шкалу, граф связей, knowledge graph и vector artifacts.

### Ответственность

- хранить memory blocks
- нормализовать память
- выполнять retrieval
- строить temporal ordering
- строить graph relations
- обслуживать chat corpus ingestion
- поддерживать knowledge/vector artifacts

### Входы слоя

- новые memory entries
- исторический chat corpus
- запросы поиска
- запросы на temporal / graph / semantic retrieval

### Выходы слоя

- memory blocks
- ranked search results
- timeline results
- related-memory graph
- parsed corpus
- knowledge graph
- vector memory

### Текущие модули

- `core/memory_engine.py`
- `core/retrieval_engine.py`
- `core/graph_engine.py`
- `core/temporal_engine.py`
- `memory/chat_loader.py`
- `memory/chat_parser.py`
- `memory/knowledge_builder.py`
- `memory/vector_memory.py`
- `ai_os/memory_pipeline.py`
- `scripts/runtime_store.py`

### Основные данные

- `GPTMemory_runtime.yaml`
- `memory/chats/`
- `memory/index/`
- `memory/parsed/`
- `memory/knowledge/`
- `memory/embeddings/`

### Важное правило

`Memory Core` не является обслуживающим модулем для dashboard. Наоборот, dashboard и агенты должны работать поверх памяти.

Поверх этого слоя теперь уже формируется и procedural branch memory:

- completed `branch_stabilization` outcomes сохраняются как `branch_stabilization_learning`
- repeated learning records сворачиваются в reusable `stabilization playbooks`
- эти playbooks становятся входом для planner policy, branch health snapshots и cognitive planning

## 6. Слой `Cognitive Loop`

### Назначение

Преобразует состояние памяти и системный контекст в цикл мышления:

- perception
- reasoning
- planning
- action
- learning

Это слой когнитивной оркестрации, а не просто очередь задач.

### Ответственность

- воспринимать состояние системы
- формировать интерпретацию текущего контекста
- порождать план
- ставить задачи агентам
- принимать результаты исполнения
- обновлять состояние системы после выполнения

### Входы слоя

- текущий runtime state
- memory context
- операторские задачи
- статусы агентов
- результаты исполнения

### Выходы слоя

- планы
- очереди задач
- изменения приоритетов
- команды исполнителям
- обновления памяти и системного состояния

### Текущие модули

- `ai_os/cognitive_loop.py`
- `ai_os/stabilization_playbook.py`
- `planning/runtime.py`
- transition/compat:
  - `ai_os/cognitive_loop_compat.py`
- legacy-ветки:
  - `core/cognitive_loop.py`
  - `core/cognitive_loop_live.py`
  - `core/cognitive_loop_live_v2.py`
  - `core/cognitive_loop_api.py`
  - `core/cognitive_loop_api_v2.py`
  - `core/cognitive_loop_auto_scale.py`

### Текущий статус

Слой уже оформлен как официальный `kernel-level` модуль в `ai_os/cognitive_loop.py`. Сейчас он умеет проходить цикл `perception -> reasoning -> planning -> action -> learning`, видеть memory state, agent runtime и execution feedback, а также опираться на официальный `planner runtime` в `planning/runtime.py` для persistent plan state, dependency-aware step sequencing, grouped `plan_kind` orchestration (`operational`, `recovery`, `remediation`, `branch_stabilization`), manager-first dispatch в task queue и replay-aware recovery preview/plan generation поверх `snapshot lineage`. Поверх recovery planner теперь есть явный workflow со стадиями `coordination -> anchor_review -> replay_execution -> validation`, workflow snapshot для control plane, targeted advance-слой, который dispatch-ит только задачи конкретного recovery plan, compensation-aware progression для failed recovery steps, completion-driven handoff от `agents/complete` обратно в planner, remediation-aware pause/resume chain для repeated recovery failures, post-validation `branch_health / confidence / quality` signals, history-aware branch health trends с branch-level planner gating, а теперь ещё и long-horizon `branch quality drift / pressure` layer, который усиливает planner policy по накопленной recovery history. Следующий runtime policy слой тоже уже оформлен: planner вкладывает в queued tasks нормализованный `dispatch_policy`, agent runtime уважает branch-level dispatch caps даже при manual claim/dispatch, а remediation policy адаптируется под критическое pressure, снижая disruption threshold и сериализуя remediation execution. Поверх этого cognitive loop теперь сам видит planner branch health и поднимает `branch_stabilization` plans для веток с `restricted/blocked dispatch` или `high/critical pressure`, превращая branch pressure из пассивного сигнала в проактивную stabilization-нагрузку. Следующий learning слой тоже появился: completed `branch_stabilization` outcomes записываются в memory как отдельный класс procedural memory (`branch_stabilization_learning`), perception читает их как stabilization memory, а planner-side branch stabilization может ссылаться на prior lessons вместо полного старта “с нуля”. Поверх этого теперь уже есть и reusable `stabilization playbooks`: repeated stabilization lessons сворачиваются в отдельный procedural layer с `support_level / reuse_ready / recommended_actions`, planner и branch health snapshots отдают playbook signals через control plane, а cognitive loop умеет менять plan shape с raw memory review на `review/apply stabilization playbook` orchestration для pressure-heavy branch paths. Для визуального контроля этого слоя в live dashboard planner теперь также умеет безопасно поднимать demo-only recovery/remediation workflows на ветках `demo/*`, чтобы `Recovery workflows`, `Branch health` и playbook-aware branch policy можно было проверять без ожидания реального incident path. Полноразмерная branch-aware orchestration уже получила рабочий foundation, но ещё не доведены full branch memory и более глубокие policy layers.

### Целевое состояние

Нужен официальный модуль cognitive loop внутри `ai_os`, который:

- получает контекст из памяти
- создаёт план
- отправляет задачи в agent runtime
- сохраняет результаты обратно в memory/core state

## 7. Слой `Agent Hierarchy`

### Назначение

Исполнительная иерархия AI OS. Разделяет управляющие и исполняющие роли.

### Внутренние сущности

- `manager agents`
- `worker agents`
- `tasks`
- `queue`
- `events`
- `agent state`
- `role policy`

### Ответственность

- регистрация агентов
- хранение статуса агентов
- распределение задач
- capability-aware выбор исполнителя
- claim / complete lifecycle
- журнал событий

### Входы слоя

- задачи от cognitive loop
- регистрация агентов
- heartbeats
- результаты выполнения

### Выходы слоя

- состояние очереди
- состояние агентов
- события runtime
- сигналы для control plane и kernel

### Текущие модули

- `ai_os/agent_runtime.py`
- `ai_os/role_policy.py`
- `agents/managers/manager_base.py`
- `agents/workers/worker_base.py`

### Текущий статус

Базовый официальный runtime уже есть. Сейчас он покрывает lifecycle:

- register
- heartbeat
- queue task
- claim task
- complete task
- snapshot
- policy preview
- managed dispatch

Теперь runtime также сохраняет `agents / tasks / events` в persistent state, при рестарте безопасно requeue-ит незавершённые `in_progress` задачи и умеет строить capability-aware dispatch recommendations по `role`, `owner_hint`, `capabilities` и базовой `history/load` модели. Это уже foundation для manager/worker governance, но richer policy и deeper capability semantics ещё впереди.

## 8. Слой `Execution Layer`

### Назначение

Фактическое выполнение задач, назначенных агентам, и возврат результата в систему.

### Ответственность

- принять назначенную задачу
- исполнить команду или workflow
- вернуть результат
- инициировать пост-обработку и learning feedback

### Входы слоя

- task assignment
- execution context
- инструменты выполнения

### Выходы слоя

- result payload
- success / failure state
- execution traces
- сигналы для memory update и learning loop

### Текущие модули

Пока слой существует как официальный пакет:

- `agents/workers/worker_base.py`
- task lifecycle внутри `ai_os/agent_runtime.py`
- совместимый цикл исполнения в `ai_os/cognitive_loop_compat.py`
- `execution/contracts.py`
- `execution/runtime.py`
- `execution/ledger.py`
- `execution/__init__.py`

### Текущий статус

Слой уже выделен как официальный execution runtime. Сейчас в нём есть execution contracts, failure policy, compensation metadata, operation ledger foundation и delta/branch/lineage model, а также feedback-контур обратно в cognitive loop. Поверх этого execution snapshot уже показывает отдельные recovery operation counts и recovery compensation counts, а replay steps начали использовать более семантичные summaries для role/capability inference. Через completion-driven planner handoff execution-результаты теперь могут замыкать recovery workflow вплоть до `validation` и `workflow_complete`, repeated recovery failures могут переводить workflow в remediation-aware pause/resume режим, post-validation quality layer оценивает здоровье ветки после recovery, а planner теперь использует history-aware branch trends для branch-level execution gating. Ещё не реализованы полноценные rollback chains, long-horizon branch health memory, branching execution и полностью автоматизированная replay orchestration.

## 9. Сквозные системные потоки

## 9.1. Operator Request Flow

`User -> Interface Layer -> Persistent AI Mind -> Cognitive Loop -> Agent Hierarchy -> Execution Layer -> Memory/Core update -> Interface response`

## 9.2. Memory Ingestion Flow

`Chat Corpus -> Memory Pipeline -> Parsed Chats -> Knowledge Graph -> Vector Memory -> Memory Core`

## 9.3. Autonomous Task Flow

`Persistent AI Mind -> Cognitive Loop -> Task Queue -> Manager/Worker selection -> Execution -> Result -> Memory update -> Next planning cycle`

## 10. Привязка к текущему проекту

### Уже официальный слой

- `Interface Layer`
- `Persistent AI Mind` как runtime/bootstrap
- `Memory Core`
- `Agent Hierarchy` с role-policy foundation
- `Planner/Executor bridge` в базовом виде

### Частично официальный слой

- `Cognitive Loop`
- `Execution Layer`

### Пока legacy / transition zone

- старые `core/cognitive_loop*`
- `scripts/api_gui_integration.py`
- `apps/dashboard/`
- `GPTMemoryEngine/`

## 11. Технические границы слоёв

### Что допустимо

- `Interface Layer` вызывает `kernel`, `memory` и `agent runtime`
- `Cognitive Loop` использует `Memory Core` и `Agent Hierarchy`
- `Execution Layer` возвращает результат в `Memory Core` и `Cognitive Loop`

### Что нежелательно

- прямое смешивание dashboard с логикой памяти
- смешивание API-layer с очередью исполнения
- дублирование cognitive loop в нескольких entrypoint-модулях
- обход официального runtime через параллельные legacy-paths

## 12. Следующий порядок реализации

1. Углублять branch health layer: переходить от history-aware trends и planner gating к branch quality drift, health memory и более строгим runtime policies.
2. Развивать role policy foundation в richer manager/worker governance.
3. Постепенно расширять branch/time model и snapshot lineage.
4. Перевести legacy cognitive-loop ветки на новый официальный слой без дублирования логики.
5. После стабилизации логики уже переносить физическую структуру файлов.

## 13. Канонический вывод

Проект GPTMEAi должен трактоваться как:

`Persistent AI Mind System`, в котором:

- память является фундаментом
- cognitive loop является механизмом мышления
- agent hierarchy является механизмом исполнения
- execution layer является operational substrate
- interface layer является control plane

Именно эта модель считается канонической для дальнейшей разработки проекта.
