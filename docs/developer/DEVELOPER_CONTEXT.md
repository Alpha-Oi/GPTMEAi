# Developer Context

Последнее обновление: `2026-05-01`
Статус документа: `canonical developer onboarding file`

## Что это за программа

`GPTMEAi` это локальная `AI OS` для построения `Persistent AI Mind System`.

Проект вырос из `GPTMemory` и развился в архитектуру, где память, cognitive loop, агентная иерархия и control plane образуют единую операционную среду для ИИ.

Система задумывается не как обычный чат, не как просто dashboard и не как parser архива, а как:

- память как фундамент
- когнитивный цикл как механизм мышления
- агентная иерархия как механизм исполнения
- локальный API и dashboard как control plane

## Для чего нужна система

Практическая идея проекта:

- хранить долговременную память разработки и взаимодействий
- извлекать знания из исторического корпуса чатов
- строить контекст, граф связей и retrieval
- планировать и исполнять задачи через agent hierarchy
- давать человеку наблюдаемый и управляемый AI runtime

## Каноническая архитектура

Система опирается на такую логическую модель:

1. `User`
2. `Interface Layer`
3. `Persistent AI Mind`
4. `Memory Core`
5. `Cognitive Loop`
6. `Agent Hierarchy`
7. `Execution Layer`

Инженерно это сводится к 4 главным слоям:

- `control plane`
- `kernel`
- `memory`
- `agent runtime`

Каноническая техническая спецификация слоёв подробно описана в [`AI_OS_LAYER_TECHNICAL_SPEC.md`](/D:/Development%20GPTMEAi/AI_OS_LAYER_TECHNICAL_SPEC.md).

## Как устроен проект сейчас

### Официальный runtime

Текущая официальная точка запуска:

- [`run_ai_os.py`](/D:/Development%20GPTMEAi/run_ai_os.py)
- [`run_ai_os.ps1`](/D:/Development%20GPTMEAi/run_ai_os.ps1)

Environment risk note: current project `venv` uses Python `3.14.3`; direct runtime imports `ai_os.runtime` and `scripts.api_server` were previously ok, but `pip` import and `python -m pip` are broken due to corrupted injected headers in `venv\Lib\site-packages\pip\__init__.py`, and read-only `*.dist-info` inventory showed damage may be broader across third-party `site-packages`; targeted pip-only repair is not recommended, and `AGENTS.md` now treats `venv/` plus `venv/Lib/site-packages/` as no-edit zones. A side-by-side proof `venv` was created under `%TEMP%` at `C:\Users\Crown-Aliy\AppData\Local\Temp\gptmeai_venv_repair_test_e4f96ff91028471b85e511504d2db7dd`; it uses Python `3.14.3`, has working `pip`, installed the `*.dist-info` package inventory successfully, passed third-party imports (`flask`, `flask_cors`, `flask_socketio`, `requests`, `yaml`, `psutil`, `eventlet`, `socketio`, `engineio`), passed project imports (`ai_os.runtime`, `scripts.api_server`) and passed `development/scripts/smoke_stabilization_replay_continuity.py --json --cleanup` with `cleanup_succeeded=true` and `temp_root_exists_after_cleanup=false`; current damaged `venv` still passes project import comparison but corruption remains, `eventlet` emitted a deprecation warning that is a future dependency risk, and current `venv` should not be replaced until explicit promotion approval. Final candidate proof removed failed partial `D:\Development GPTMEAi\venv_new`, created `D:\GPTMEAi_venv_candidate`, left current damaged `D:\Development GPTMEAi\venv` unmodified, verified candidate Python `3.14.3`, candidate `pip 25.3`, successful package install from inventory, passing third-party imports, passing project imports, and passing consolidated smoke with `cleanup_succeeded=true` and `temp_root_exists_after_cleanup=false`; `PIP_NO_INDEX=1` was present and not changed, install succeeded from cached wheels, and `D:\GPTMEAi_venv_candidate` is ready for a separate promotion approval step. A later project-root `D:\Development GPTMEAi\venv_new` retry failed again even after `PIP_NO_INDEX` was cleared process-locally for creation and restored afterward; Python `3.14.3` exists in `venv_new`, but pip bootstrap failed with `No module named pip`, so `venv_new` is a failed partial candidate and must not be promoted, current `venv` was untouched, and `D:\GPTMEAi_venv_candidate` remains the only verified healthy candidate; stop retrying project-root `venv_new` creation for now and prepare a read-only external-runtime promotion/adoption plan next.

External runtime adoption note: `D:\GPTMEAi_venv_candidate\Scripts\python.exe` is now the adopted official healthy interpreter path without moving or copying the environment into the project root; `D:\Development GPTMEAi\venv` remains a protected damaged no-edit artifact, project-root `venv_new` creation failed and should not be retried for now, and the `eventlet` deprecation warning remains a future dependency risk rather than a current blocker.

External runtime adoption verification: `run_ai_os.ps1` now uses `D:\GPTMEAi_venv_candidate\Scripts\python.exe` by default, supports `GPTMEAI_PYTHON` override, does not fall back to damaged `.\venv`, and passed PowerShell parse-check without starting the runtime server. The adopted external interpreter was verified as Python `3.14.3` with `pip 25.3`; third-party imports (`flask`, `flask_cors`, `flask_socketio`, `requests`, `yaml`, `psutil`, `eventlet`, `socketio`, `engineio`) and project imports (`ai_os.runtime`, `scripts.api_server`) passed, and `development/scripts/smoke_stabilization_replay_continuity.py --json --cleanup` passed with `cleanup_succeeded=true` and `temp_root_exists_after_cleanup=false`. At that stage, live runtime/API startup was not performed and remained an optional separate approval.

Live runtime/API smoke: after approval, `run_ai_os.ps1` launched `D:\GPTMEAi_venv_candidate\Scripts\python.exe -m ai_os`; port `8010` was free before startup, runtime became ready, `/health`, `/planner/status`, `/execution/status`, and `/dashboard` each returned `200`, runtime stopped cleanly via `CTRL_BREAK_EVENT`, final process check showed the runtime PIDs were not running, port `8010` was released, and captured metadata for `storage/`, `logs/`, and `runtime/` showed no observed changed files. The live runtime/API smoke is accepted, current damaged project `venv` remained untouched/protected, and the external interpreter remains the adopted official healthy runtime path.

Основной control plane:

- [`scripts/api_server.py`](/D:/Development%20GPTMEAi/scripts/api_server.py)
- [`dashboard/index.html`](/D:/Development%20GPTMEAi/dashboard/index.html)

### Основные подсистемы

- `ai_os/`
  главный runtime-каркас, config, manifest, официальный cognitive loop, agent runtime
- `planning/`
  официальный planner/executor bridge: persistent планы, plan kinds, manager/worker orchestration, зависимости, recovery preview, phase-aware recovery workflows и replay-aware dispatch в agent runtime
- `core/`
  memory engine, retrieval, temporal memory, graph memory и legacy cognitive-loop ветки
- `execution/`
  официальный execution layer: execution contracts, operation runtime, failure policy, compensation metadata, recovery observability и operation ledger с delta/branch/lineage model
- `memory/`
  ingestion pipeline, corpus parsing, knowledge graph, vector memory
- `agents/`
  базовые manager/worker сущности
- `storage/`
  snapshots и runtime state artifacts

### Источники данных

- [`GPTMemory_runtime.yaml`](/D:/Development%20GPTMEAi/GPTMemory_runtime.yaml)
- [`memory/chats`](/D:/Development%20GPTMEAi/memory/chats)
- [`memory/parsed`](/D:/Development%20GPTMEAi/memory/parsed)
- [`memory/knowledge`](/D:/Development%20GPTMEAi/memory/knowledge)
- [`memory/embeddings`](/D:/Development%20GPTMEAi/memory/embeddings)

## Что за что отвечает

### `ai_os/`

- [`config.py`](/D:/Development%20GPTMEAi/ai_os/config.py)
  единые пути и runtime config
- [`manifest.py`](/D:/Development%20GPTMEAi/ai_os/manifest.py)
  официальный срез структуры проекта
- [`runtime.py`](/D:/Development%20GPTMEAi/ai_os/runtime.py)
  bootstrap официального runtime
- [`agent_runtime.py`](/D:/Development%20GPTMEAi/ai_os/agent_runtime.py)
  register/heartbeat/queue/claim/complete/events, persistent agent state, capability-aware role policy и managed dispatch
- [`role_policy.py`](/D:/Development%20GPTMEAi/ai_os/role_policy.py)
  policy engine для выбора исполнителя по role/capabilities/owner hint/load history
- [`cognitive_loop.py`](/D:/Development%20GPTMEAi/ai_os/cognitive_loop.py)
  официальный cognitive loop
- [`stabilization_playbook.py`](/D:/Development%20GPTMEAi/ai_os/stabilization_playbook.py)
  reusable branch stabilization playbooks, собранные из procedural stabilization learning
- [`memory_pipeline.py`](/D:/Development%20GPTMEAi/ai_os/memory_pipeline.py)
  мост между runtime и chat-corpus artifacts

### `planning/`

- [`runtime.py`](/D:/Development%20GPTMEAi/planning/runtime.py)
  официальный planner runtime: persistent планы, dependency-aware шаги, branch health / recovery policy / stabilization playbook snapshots и executor bridge к `agent_runtime`

### `core/`

- [`memory_engine.py`](/D:/Development%20GPTMEAi/core/memory_engine.py)
  базовые memory blocks
- [`retrieval_engine.py`](/D:/Development%20GPTMEAi/core/retrieval_engine.py)
  текстовый и tag-based retrieval
- [`temporal_engine.py`](/D:/Development%20GPTMEAi/core/temporal_engine.py)
  temporal ordering и recent memory
- [`graph_engine.py`](/D:/Development%20GPTMEAi/core/graph_engine.py)
  graph relations между блоками памяти

### `scripts/`

- [`api_server.py`](/D:/Development%20GPTMEAi/scripts/api_server.py)
  основной локальный API
- [`runtime_store.py`](/D:/Development%20GPTMEAi/scripts/runtime_store.py)
  чтение/запись runtime store

## Какая файловая система считается нормальной

### Чистый корень проекта

В корне должны жить только:

- официальные entrypoints
- основные каталоги системы
- постоянная архитектурная документация
- ключевые runtime/data файлы

### Developer docs

Вся документация для разработчика должна жить в:

- [`docs/developer/`](/D:/Development%20GPTMEAi/docs/developer)

Главный файл для быстрого входа в проект:

- [`docs/developer/DEVELOPER_CONTEXT.md`](/D:/Development%20GPTMEAi/docs/developer/DEVELOPER_CONTEXT.md)

Active current-state overlay for the historical canonical 100-step plan:

- [`docs/developer/GPTMEAI_100_STEP_CURRENT_STATE_OVERLAY.md`](/D:/Development%20GPTMEAi/docs/developer/GPTMEAI_100_STEP_CURRENT_STATE_OVERLAY.md)

### Рабочая папка разработки

Вся временная активность разработки должна постепенно уходить в:

- [`development/`](/D:/Development%20GPTMEAi/development)

Там должны жить:

- change notes
- временные скрипты
- промежуточные отчёты
- рабочие логи
- экспериментальные артефакты

Для служебных dev-операций по умолчанию следует предпочитать Python-скрипты в [`development/scripts/`](/D:/Development%20GPTMEAi/development/scripts), а не одноразовые PowerShell-команды. Это снижает количество shell-specific действий и делает служебные workflow воспроизводимее.

## Правило серьёзных изменений

После каждого серьёзного изменения разработчик должен сделать 2 вещи:

1. Обновить этот файл, если изменился смысл, структура, стадии готовности или правила проекта.
2. Добавить отдельную запись в [`development/changes/`](/D:/Development%20GPTMEAi/development/changes) с кратким описанием:
   дата, что изменено, зачем, какие файлы затронуты, что делать дальше.

Серьёзным изменением считается:

- новый официальный слой архитектуры
- смена официального runtime
- изменение структуры каталогов
- важный рефакторинг memory/agent/control-plane подсистем
- изменение инвариантов или roadmap

## Стадия готовности проекта

### Уже оформлено

- один официальный runtime
- control plane через локальный API и dashboard
- memory core
- memory pipeline bridge
- базовый agent runtime
- persistent agent runtime state
- официальный cognitive loop
- официальный planner runtime с plan steps, plan kinds и dependency-aware manager/worker dispatch
- recovery preview и replay-aware recovery plans поверх snapshot lineage
- phase-aware recovery workflow с `coordination -> anchor_review -> replay_execution -> validation`
- targeted recovery advance flow с point-to-point queue + dispatch только для выбранного recovery plan
- compensation-aware recovery advance, который может закрыть failed recovery step через execution compensation и продолжить workflow
- completion-driven planner handoff: завершение recovery task может сразу продвинуть workflow к следующей фазе
- recovery workflow теперь может доходить до `validation` и `workflow_complete` через официальный planner handoff
- remediation policy для repeated recovery failures: recovery может автоматически ставиться на паузу, поднимать child remediation plan и возвращаться в recovery после remediation completion
- post-validation branch health / confidence / quality signals для recovery workflow
- history-aware branch health trends, отдельный branch health snapshot и planner-side gating для branch-aware execution
- long-horizon branch quality drift / pressure layer, который эскалирует branch gate по накопленной recovery history
- pressure-aware dispatch/remediation policy layer: planner вкладывает `dispatch_policy` в queued tasks, agent runtime уважает branch caps даже при manual claim/dispatch, а remediation policy адаптируется к критическому branch pressure
- cognitive-loop pressure awareness: loop видит planner branch health и сам поднимает `branch_stabilization` plans для веток с `restricted/blocked dispatch` или `high/critical pressure`
- branch stabilization learning memory: completed stabilization plans сохраняются как procedural memory, perception читает их как stabilization memory, а новые stabilization plans могут ссылаться на prior branch lessons
- branch stabilization playbooks: repeated stabilization lessons сворачиваются в reusable procedural playbooks, planner и branch health snapshots отдают `support_level / reuse_ready / recommended_actions`, а cognitive loop умеет строить `review/apply stabilization playbook` шаги для pressure-heavy веток
- planner-visible branch stabilization outcomes: terminal `branch_stabilization` plans теперь сами создают branch health observations для planner policy (`completed -> observe / heightened_monitoring`, `failed -> degraded / manual_review`), поэтому branch health, planner gate и dispatch policy обновляются без ручного history seeding, а recovery-путь остаётся без изменения
- replay advisory continuity bridge: `preview_recovery_plan_from_replay()` теперь возвращает stabilization-derived `branch_recovery_signal` и кладёт его и в top-level preview, и в `context`; `completed` stabilization даёт `observe / heightened_monitoring / heightened_monitoring_during_replay`, `failed` даёт `degraded / manual_review / manual_review_before_replay`, а ветки без сигнала сохраняют прежнее replay preview поведение без изменения snapshot lineage schema, snapshot creation, replay ordering или recovery orchestration
- failed stabilization policy scope clarification: `branch` summary `planner_gate` и `dispatch_policy` считаются branch-wide operational control surfaces, тогда как `branch_recovery_signal` и replay preview `dispatch_policy_mode` считаются recovery-scoped advisory surfaces; поэтому failed `branch_stabilization` намеренно замораживает ordinary operational work строже, чем ограничивает recovery/replay preview, operational dispatch может стать `blocked` для остановки новой normal branch work, а replay preview может оставаться `restricted` / `manual_review_before_replay`, потому что `recovery`, `remediation` и `branch_stabilization` paths всё ещё допустимы как controlled review-first flows; это accepted behavior, а не verified runtime bug, optional future clarity slice может добавить scoped field names или раздельные operational/recovery labels, а existing consolidated smoke уже покрывает текущее поведение
- scoped recovery-preview policy labels: `branch_recovery_signal` теперь additive-only включает `policy_scope="recovery_preview"`, `planner_gate_scope="recovery"` и `dispatch_policy_scope="recovery"`, чтобы явно отделить recovery-scoped advisory preview fields от branch-wide operational control surfaces; runtime behavior не менялся, existing fields не переименованы и не удалены, failed operational dispatch может оставаться строже while recovery preview remains `restricted` / advisory, `snapshot_id` остаётся authoritative, no-signal поведение и `anchor_bias` не изменились, а `/snapshots/replay`, snapshot schema, recovery graph, API routes, dashboard, role policy, agent runtime и cognitive loop не менялись
- recovery task continuity metadata: recovery preview `task_specs` теперь получают additive metadata-only `recovery_continuity`, собранный только из уже вычисленных `branch_recovery_signal` и `anchor_bias`; metadata прикрепляется только к recovery task metadata, не к plan context, при этом created recovery plan context сохраняет `branch_recovery_signal` и `anchor_bias` unchanged from preview, no-signal ветки не получают meaningful `recovery_continuity`, task graph не меняется (`task count`, `step_key`, `depends_on`, `recovery_phase`, `preferred_role` unchanged), `snapshot_id` остаётся authoritative, `anchor_bias` behavior unchanged, а `/snapshots/replay`, snapshot schema, replay ordering, recovery graph, API route code, dashboard, role policy, agent runtime и cognitive loop не менялись; prior focused smoke failure был из-за incorrect assertion expecting top-level created_plan `branch_recovery_signal` / `anchor_bias`, correct location is `created_plan["context"]`
- raw snapshot replay metadata: `SnapshotLineageRegistry.replay_plan()` теперь добавляет response-only `replay_metadata` в raw `/snapshots/replay` responses с `source="raw_snapshot_lineage"`, `planner_context_included=false`, `planner_context_endpoint="/planner/recovery/preview"`, `anchor_selection_model="explicit_snapshot_id -> operation_id -> branch_latest -> global_latest"`, `replay_order="logical_time_ascending_after_anchor"` и raw anchor/count fields (`anchor_snapshot_id`, `effective_branch_id`, `anchor_entry_logical_time`, `replay_entry_count`, `replay_step_count`); planner-only поля (`branch_recovery_signal`, `anchor_bias`, `recovery_continuity`, `policy_scope`, `planner_gate_scope`, `dispatch_policy_scope`) намеренно отсутствуют в `/snapshots/replay`, `/planner/recovery/preview` остаётся planner-aware endpoint, anchor priority и replay ordering не изменились, а snapshot schema, snapshot export flow, recovery task graph, planner preview behavior, API route code и dashboard не менялись; durable focused verification теперь закреплена в `development/scripts/smoke_snapshots_replay_metadata.py`, production code не менялся, проверки `py_compile`, `smoke_snapshots_replay_metadata.py --json --cleanup` и `smoke_stabilization_replay_continuity.py --json --cleanup` прошли, при этом initial `py_compile` потребовал elevated rerun из-за Windows `__pycache__` access denial, поэтому в будущих проверках предпочтителен `pycache_prefix`, когда применимо
- Concept Core MVP foundation: добавлен additive-only модуль [`ai_os/concept_core.py`](/D:/Development%20GPTMEAi/ai_os/concept_core.py) с typed reasoning/safety primitives для `KnowledgeStatus`, `EvidenceItem`, `IdentityCore`, `RiskProfile`, `DecisionCommit`, `ForeignnessLevel`, `InterventionLevel`, `SafetyGuard`, `DecisionEngine`, `MemoryNode` и `MemoryCommitValidator`; модуль различает `confirmed/inference/hypothesis/unknown/contradiction`, блокирует red-button decisions без безопасной review/verification/rollback posture, блокирует destructive actions на unknown objects, повышает contradiction до `risky/verify`, отклоняет memory nodes без `source/status/context/confidence`, и пока не меняет API routes, dashboard, planner behavior, cognitive loop behavior, memory storage schema, snapshot schema, execution ledger schema или runtime storage
- Concept Core decision advisory in Cognitive Loop: direct `CognitiveLoop.plan()` output возвращает top-level `concept_core_advisory`, построенный через existing Concept Core `DecisionEngine` / `SafetyGuard` primitives; поле строго advisory-only (`runtime_enforcement=False`), `would_block_if_enforced` описательное, red-button-like task titles только reported and not enforced, `act()` behavior, planner calls, task generation, `plan_groups` и `recovery_requests` unchanged, advisory не передаётся через task metadata, planner context или recovery request args; persisted/status/run-shaped serialization теперь фильтрует только top-level `concept_core_advisory` из copied plan payloads через `_sanitize_plan_for_serialization()`, `_sanitize_cycle_for_serialization()` и `_state_for_serialization()`, `_record_cycle()` stores sanitized `last_cycle`, `_save_state()` writes sanitized state, а `status_snapshot()` returns sanitized `last_cycle`; planner/runtime/dispatch/API/schema/storage behavior не менялся, live runtime/API smoke не запускался, а проверки `py_compile`, `smoke_concept_core_advisory_consumers.py --json --cleanup`, `smoke_concept_core_decision_advisory.py --json --cleanup`, `smoke_concept_core.py`, `smoke_concept_core_memory.py --json --cleanup`, `smoke_memory_add_concept_route.py --json --cleanup`, `smoke_memory_concept_read_visibility.py --json --cleanup`, `smoke_snapshots_replay_metadata.py --json --cleanup` и `smoke_stabilization_replay_continuity.py --json --cleanup` прошли
- Concept Core public status surface: `GET /concept-core/status` теперь является первым deliberate public Concept Core status surface; endpoint static/read-only/capability-level, возвращает `status="ok"`, `service="AI OS Concept Core"`, `mode="advisory_only"`, `runtime_enforcement=false`, `storage_schema_mutation=false`, `public_api_behavior_mutation=false`, capabilities (`typed_primitives`, `strict_memory_add`, `memory_metadata_visibility`, `direct_cognitive_plan_advisory`, `public_decision_preview=false`, `global_enforcement=false`), visibility для `/memory/all`, `/memory/search`, `/memory/tag`, `/memory/recent` и non-exposure flags для `/memory/related`, cognitive status/run, planner status и dispatch, плюс `safety_contract` с `advisory_non_enforcing`, `internal_plan_payload_exposed=false` и `text_heuristic_mvp_not_authoritative_policy`; endpoint не вызывает `CognitiveLoop.plan()`, `run_cycle()`, `status_snapshot()`, planner preview или memory read/write methods, не раскрывает `concept_core_advisory`, internal plan payload, task titles, `plan_groups`, `recovery_requests`, evidence lists, decision dumps, memory content, `metadata.concept_core` values или red-button term list; `/health`, `/cognitive/status`, `/cognitive/run`, `/planner/status`, `/planner/recovery/preview`, все `/memory` routes, dashboard, schemas, storage/runtime behavior и global enforcement unchanged; verification прошла через TDD RED, `py_compile`, `smoke_concept_core_status_route.py --json --cleanup` и существующие Concept Core/replay smokes, live runtime startup не выполнялся
- optional strict Concept Core memory commit path: `MemoryEngine.add_concept_node(payload: dict, *, tags=None, importance=None)` теперь даёт explicit strict path для Concept Core memory commits, валидирует payload через `MemoryCommitValidator`, сохраняет `MemoryNode.content` как legacy block `text` и кладёт validated Concept Core payload в `metadata["concept_core"] = MemoryNode.to_dict()`; existing `MemoryEngine.add(text, ...)` и `/memory/add` остаются unchanged, strict validation не включена глобально, invalid strict payloads rejected before writing, legacy memory block shape compatible, project `GPTMemory_runtime.yaml` был untouched in verification, а API routes, schemas, cognitive loop, runtime behavior и storage schema не менялись
- optional strict `/memory/add` Concept Core mode: `POST /memory/add` теперь поддерживает explicit strict mode только при `payload["strict"] is True`; legacy request `{"text": "..."}` по-прежнему вызывает `MemoryEngine.add(text)`, возвращает status code `201` и сохраняет outer response shape `status/message/memory_count/item`, strict request требует `payload["concept_core"]` как dict, вызывает `MemoryEngine.add_concept_node(...)`, сохраняет `MemoryNode.content` как `item.text` и validated payload под `metadata["concept_core"]`; strict validation errors возвращают `400 {"error": "..."}`, invalid strict requests не пишут memory blocks, project `GPTMemory_runtime.yaml` был unchanged during verification, global strict validation не включалась, memory schema migration, cognitive loop/runtime behavior changes и live runtime server startup не выполнялись
- Concept Core memory read-path visibility smoke: добавлен smoke-only script `development/scripts/smoke_memory_concept_read_visibility.py`; production code не менялся, потому что existing full-block read routes уже возвращают `metadata["concept_core"]` для strict Concept Core memory blocks через `/memory/all`, `/memory/search`, `/memory/tag` и `/memory/recent`, legacy memory blocks не получают `metadata.concept_core` по умолчанию, `/memory/related` остаётся graph-summary shaped и не выдаёт full Concept Core memory records, project `GPTMemory_runtime.yaml` был unchanged before/after verification, а проверки `py_compile`, `smoke_concept_core.py`, `smoke_concept_core_memory.py --json --cleanup`, `smoke_memory_add_concept_route.py --json --cleanup`, `smoke_memory_concept_read_visibility.py --json --cleanup` и `smoke_stabilization_replay_continuity.py --json --cleanup` прошли
- Semantic Mesh library-only model: добавлен additive/read-only модуль [`ai_os/semantic_mesh.py`](/D:/Development%20GPTMEAi/ai_os/semantic_mesh.py) с dataclasses `SemanticMeshNode`, `SemanticMeshRelation`, `SemanticMeshEvidenceRef`, `SemanticMeshIndex` и builder `build_semantic_mesh(...)` для уже загруженных memory blocks; слой считает coverage diagnostics, индексирует strict Concept Core nodes, оставляет legacy blocks валидными, сообщает malformed Concept Core metadata, dangling targets и unknown relation types как diagnostics, маркирует weak tag/word similarity как `weak_derived`, не читает и не пишет runtime/storage, не добавляет API route, не меняет planner/dispatch/replay behavior и не выполняет migration/backfill
- Semantic Mesh API preview: добавлен bounded read-only endpoint `GET /semantic-mesh/preview`, который строит response через `build_semantic_mesh(memory_engine.get_all())` и возвращает `status/service/mode/runtime_enforcement/storage_schema_mutation/public_api_behavior_mutation/source/mesh`; endpoint additive-only, не принимает query semantics, не пишет runtime/storage, не вызывает graph save/build, pipeline rebuild, snapshot export, planner/dispatch/replay paths или dashboard integration, а handler-level smoke с temp runtime подтвердил strict/legacy/malformed/dangling/unknown/weak-derived visibility и unchanged project `GPTMemory_runtime.yaml` metadata
- Semantic Mesh Stage E1 advisory adapter: добавлен pure/library-only модуль `ai_os/semantic_mesh_advisory.py`, который принимает уже построенный `SemanticMeshIndex` и optional plan mapping, возвращает только aggregate coverage state (`empty`, `strict_only`, `legacy_only`, `malformed_only`, `mixed`), required diagnostics, explicit/weak/diagnostic relation counts, aggregate plan summary с bounded `focus_area` и count-only collections, а также deterministic attention signals; payload не содержит mesh nodes, relation payloads, evidence refs, malformed record details или planned task titles, adapter имеет exact import allowlist, не импортирует storage/planner/execution/snapshot/network dependencies и декларирует `runtime_enforcement=false`, `planner_input_applied=false`, `dispatch_input_applied=false`, `planner_context_persistence=false`, `storage_schema_mutation=false`, `public_api_behavior_mutation=false`; в рамках E1 `CognitiveLoop`, `PlannerRuntime`, API, task metadata, recovery requests, persistence/status, runtime/storage schemas и dispatch behavior не менялись, focused smoke `smoke_semantic_mesh_advisory.py --json --cleanup` прошёл, а automatic mesh construction и planner/dispatch use остаются отдельно approval-gated
- Semantic Mesh Stage E2A exact opt-in direct-plan wiring: `CognitiveLoop.plan(...)` принимает keyword-only `semantic_mesh_index: SemanticMeshIndex | None = None` и добавляет top-level aggregate-only `semantic_mesh_advisory` только при явной передаче уже построенного индекса; default `plan(...)` и `run_cycle()` не строят и не читают Semantic Mesh и не получают новое поле, `act()`/planner calls/task metadata/recovery args unchanged, а `_sanitize_plan_for_serialization()` фильтрует Semantic Mesh advisory вместе с `concept_core_advisory` из persisted/status/run-shaped outputs; planner/dispatch decisions, API routes, schemas, storage, replay и default runtime behavior не менялись, focused RED/GREEN smoke подтверждает идентичные planner calls, отсутствие automatic mesh build и unchanged project runtime state
- Semantic Mesh Stage F2A direct-library exact opt-in writer wiring: `MemoryCommitValidator.validate(...)` и `MemoryEngine.add_concept_node(...)` принимают keyword-only `relation_contract_version: str | None = None`; default `None` сохраняет прежний permissive Concept Core relation path, а любой explicit non-`None` opt-in до записи вызывает pure F1 validator и принимает только exact `semantic_relation.v1`, missing `relations` трактуется как `[]`, explicit non-list и malformed relation payloads отклоняются typed `SemanticRelationContractError` без записи, canonical copy сохраняется в existing `metadata.concept_core.relations`; `MemoryEngine.add(...)`, `/memory/add`, API schemas, storage schema, migration/backfill, target lookup, reverse edges, Semantic Mesh read semantics, planner/dispatch/replay и default runtime behavior не менялись
- snapshot coverage freshness bridge: Cognitive Loop теперь флагует stale/missing snapshot coverage для веток с stabilization-derived planner branch health signal, если `status` равен `observe/degraded` или `recommendation` равен `heightened_monitoring/manual_review`, а latest branch snapshot отсутствует или старше `branch health last_updated`; при этом `completed stale`, `failed stale` и `completed missing` флагуются, `completed fresh` и `no-signal` не флагуются, используется уже существующий `capture_snapshot_coverage` шаг, и не меняются snapshot creation, snapshot schema, replay ordering, replay anchor selection, recovery graph, API routes или dashboard
- planner-level recovery anchor bias: `preview_recovery_plan_from_replay()` теперь может предпочесть fresh same-branch post-stabilization snapshot для meaningful stabilization-derived `branch_recovery_signal`, если текущий anchor старше `branch health last_updated`; bridge работает для `completed` и `failed` stabilization paths, возвращает `anchor_bias` и в top-level preview, и в `context`, виден через `/planner/recovery/preview`, не меняет `/snapshots/replay`, сохраняет authoritative `snapshot_id`, не трогает no-signal ветки и при отсутствии fresh post-stabilization snapshot оставляет исходный anchor без выбора unrelated snapshot
- consolidated stabilization/replay continuity smoke: `development/scripts/smoke_stabilization_replay_continuity.py` теперь даёт reusable isolated `%TEMP%`-only verification для branch health outcomes, planner gate/dispatch continuity, planner/API visibility для `branch_recovery_signal` и `anchor_bias`, snapshot coverage freshness, planner-level anchor bias, authoritative `snapshot_id`, no-signal compatibility, safe no-fresh fallback и `operation_id` visibility; script поддерживает `--json` и `--cleanup`, последний прогон прошёл с `py_compile` через `pycache_prefix`, `smoke --json --cleanup`, `cleanup_succeeded=true` и `temp_root_exists_after_cleanup=false`, а различие между более строгим failed execution dispatch и advisory/restricted replay preview оставлено как follow-up semantic consistency check
- demo recovery seed для dashboard/API: безопасное наполнение `Recovery workflows` и `Branch health` живыми demo-only workflow на ветках `demo/*`
- официальный execution layer с failure policy и compensation metadata
- execution feedback loop между execution runtime и cognitive loop
- operation ledger foundation для переходов и компенсаций
- delta/branch/lineage foundation для operation ledger
- agent role policy foundation с capability-aware preview и dispatch
- recovery observability в `planner/status`, `planner/recovery/workflows`, `execution/status` и `health`
- recovery `next_actions` для inspectable workflow steering
- recovery compensation observability в execution snapshot
- project-local smoke helper для recovery workflow
- project-local smoke helper для remediation-aware recovery workflow
- архитектурные инварианты
- техническая спецификация слоёв

### Ещё не доведено

- полноразмерная branch/time model поверх текущего lineage foundation
- окончательное разделение official и legacy путей
- очистка корня проекта от исторического временного инструментария

## Текущий вектор развития

Ближайший правильный порядок работ:

1. Развивать branch health layer дальше: от history-aware trend/gating к branch quality drift, longer-term health memory и более строгим planner policies.
2. Развивать role policy от foundation к richer capability/load/history governance.
3. Постепенно расширять branch/time model и snapshot lineage.
4. Завершить очистку корня проекта без разрушения старых путей.

## Визуальная демонстрация recovery слоя

Чтобы визуально проверить recovery/branch-health логику в живом control plane, не нужно ждать реального сбоя в основном runtime.

Для этого теперь есть 2 штатных пути:

- кнопка `Seed recovery demo` в [`dashboard/index.html`](/D:/Development%20GPTMEAi/dashboard/index.html)
- helper [`development/scripts/seed_recovery_demo.py`](/D:/Development%20GPTMEAi/development/scripts/seed_recovery_demo.py)

Они создают только demo-only workflow на ветках:

- `demo/recovery-observe`
- `demo/recovery-remediation`

Эти данные не должны вмешиваться в `main` branch и не предназначены для реальной orchestration-нагрузки. Их цель: дать разработчику живую, визуально понятную картину `Recovery workflows`, `Branch health` и remediation-aware recovery quality прямо в dashboard.

## Связанные документы

- [`AI_OS_PROJECT_AUDIT.md`](/D:/Development%20GPTMEAi/AI_OS_PROJECT_AUDIT.md)
- [`AI_OS_DEVELOPMENT_INVARIANTS.md`](/D:/Development%20GPTMEAi/AI_OS_DEVELOPMENT_INVARIANTS.md)
- [`CHAT_CORPUS_ARCHITECTURE_ANALYSIS.md`](/D:/Development%20GPTMEAi/CHAT_CORPUS_ARCHITECTURE_ANALYSIS.md)
- [`AI_OS_LAYER_TECHNICAL_SPEC.md`](/D:/Development%20GPTMEAi/AI_OS_LAYER_TECHNICAL_SPEC.md)
- [`AI_OS_META_PRINCIPLES_ENGINEERING_SPEC.md`](/D:/Development%20GPTMEAi/docs/developer/AI_OS_META_PRINCIPLES_ENGINEERING_SPEC.md)
