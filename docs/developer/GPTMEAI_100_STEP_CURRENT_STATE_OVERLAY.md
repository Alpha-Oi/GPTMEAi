# GPTMEAi 100-Step Current State Overlay

Last updated: `2026-05-01`

Status: `active current-state overlay`

## Purpose

This document is a current-state overlay for the original canonical `GPTMemoryEngine` 100-step conceptual plan.

It does not replace the original 100-step plan, does not create a new roadmap, and does not make archived legacy execution scripts active again.

The purpose is to preserve the original canonical numbering while mapping the accepted current `GPTMEAi / AI OS Control Plane` state onto the canonical step ranges. Future work should use this overlay as a status and safety layer, while execution remains governed by `AGENTS.md`.

## Source Of Truth

Project root:

- `D:\Development GPTMEAi`

Active execution contract:

- `D:\Development GPTMEAi\AGENTS.md`

Official interpreter:

- `D:\GPTMEAi_venv_candidate\Scripts\python.exe`

Protected damaged local environment:

- `D:\Development GPTMEAi\venv`

Canonical historical 100-step source:

- `D:\Development GPTMEAi\smart_trash\memory_data\DocumentsGPTMemory_20260308_200556\GPTMemoryEngine\memory\разработка GPTMemory Ai+100steps.yaml`

Accepted comparison report:

- `D:\Codex_Review_Reports\GPTMEAi\2026-05-01_215306_compare_against_100_steps_CHATGPT_REVIEW_REPORT.md`

Current interpretation:

- The archived source is historical/conceptual.
- This overlay is the active status mapping.
- `AGENTS.md` remains the active operational contract.
- Old `venv`, `pip`, package-update, auto-repair, broad cleanup, and storage mutation assumptions are not executable current instructions.

## Canonical 10-Level Structure

| canonical range | original level | original theme |
|---|---|---|
| `001-010` | Level 1 | Initialization: boot, environment, config, runtime context, logging, error handling, ready flag |
| `011-020` | Level 2 | Chat data collection: session detection, branch scan, message extraction, normalization, archive save |
| `021-030` | Level 3 | Memory structuring: segmentation, topic/intent/project detection, memory blocks, metadata, tags, relationships |
| `031-040` | Level 4 | Indexing: vector embeddings, semantic/keyword/project/chronology indexes, knowledge graph, validation |
| `041-050` | Level 5 | Storage: local/vector DB writes, archive, backup, compression, versioning, integrity, storage log |
| `051-060` | Level 6 | Search/retrieval: query handling, semantic/keyword/project/chronology search, ranking, context selection |
| `061-070` | Level 7 | GPT context formation: context buffer, memory/project/preference/history injection, token optimization, validation |
| `071-080` | Level 8 | GPT work: prompt assembly, system/memory/user injection, model processing, response generation, safety/formatting |
| `081-090` | Level 9 | Memory update: conversation capture, candidate detection, fact/preference extraction, update, merge, conflict resolution |
| `091-100` | Level 10 | Autonomous AI layer: background scan, optimization, graph update, context prediction, autoload, learning, monitoring, self-repair |

## Current-State Status Table

| canonical range | original theme | current GPTMEAi equivalent | status | evidence files | accepted verification | notes / current constraints |
|---|---|---|---|---|---|---|
| `001-010` | Initialization | Official external runtime adoption; `run_ai_os.ps1` defaults to `D:\GPTMEAi_venv_candidate\Scripts\python.exe`; API status surfaces exist | partial | `AGENTS.md`; `run_ai_os.ps1`; `scripts/api_server.py`; `docs/developer/DEVELOPER_CONTEXT.md` | external interpreter adoption checks; prior accepted runtime smoke; supervised controller dry-run | damaged `.\venv` remains no-use/no-edit; no fallback to damaged env |
| `011-020` | Chat data collection | Historical chat/archive collector artifacts exist, but current GPTMEAi control plane does not treat old archived ingestion as active execution scope | partial | `.gptcollector/` references; archived canonical source; `memory/` paths in developer docs | no current smoke in this slice | storage/memory/chat data are protected; do not mutate without explicit scope |
| `021-030` | Memory structuring | Concept Core MVP, `MemoryEngine.add_concept_node(...)`, strict Concept Core memory payload validation, memory metadata visibility | partial | `ai_os/concept_core.py`; `core/memory_engine.py`; `scripts/api_server.py`; `docs/developer/GPTMEAI_CONCEPT_CORE.md` | `smoke_concept_core.py`; `smoke_concept_core_memory.py --json --cleanup`; `smoke_memory_add_concept_route.py --json --cleanup`; `smoke_memory_concept_read_visibility.py --json --cleanup` | no memory schema migration; strict mode is opt-in only |
| `031-040` | Indexing | Existing keyword/tag/recent/search surfaces, graph-summary related memory route, and read-only Semantic Mesh library/API preview | partial | `scripts/api_server.py`; `core/retrieval_engine.py`; `core/graph_engine.py`; `ai_os/semantic_mesh.py`; `development/scripts/smoke_memory_concept_read_visibility.py`; `development/scripts/smoke_semantic_mesh_library.py` | accepted memory visibility smoke; `smoke_semantic_mesh_library.py --json --cleanup` | persistent semantic/vector retrieval index remains future design work; no migration or storage index |
| `041-050` | Storage | Runtime state, operation ledger, snapshot lineage, replay metadata, Concept Core strict payload metadata storage | partial | `execution/`; `planning/`; `development/changes/2026-04-28_raw_snapshot_replay_metadata.md`; `development/changes/2026-04-30_snapshots_replay_metadata_smoke.md` | `smoke_snapshots_replay_metadata.py --json --cleanup`; `smoke_stabilization_replay_continuity.py --json --cleanup` | backups/storage are no-edit zones; no storage shape mutation without approval |
| `051-060` | Search/retrieval | `/memory/all`, `/memory/search`, `/memory/tag`, `/memory/recent`; `/memory/related` remains graph-summary only | partial | `scripts/api_server.py`; `development/scripts/smoke_memory_concept_read_visibility.py`; `docs/developer/GPTMEAI_CONCEPT_CORE.md` | `smoke_memory_concept_read_visibility.py --json --cleanup` | not a full semantic retrieval/ranking implementation |
| `061-070` | GPT context formation | `CognitiveLoop.plan()` produces top-level `concept_core_advisory` and can opt in to top-level aggregate `semantic_mesh_advisory` with an already-built `SemanticMeshIndex`; persisted/status/run-shaped serialization filters both advisories | partial | `ai_os/cognitive_loop.py`; `ai_os/semantic_mesh_advisory.py`; `development/scripts/smoke_concept_core_advisory_consumers.py`; `development/scripts/smoke_semantic_mesh_cognitive_advisory.py`; `docs/developer/GPTMEAI_CONCEPT_CORE.md`; `docs/developer/GPTMEAI_SEMANTIC_MESH.md` | `smoke_concept_core_advisory_consumers.py --json --cleanup`; `smoke_semantic_mesh_cognitive_advisory.py --json --cleanup` | default `run_cycle()` does not build/read Semantic Mesh; advisories are not injected into planner context, task metadata, recovery args, or dispatch input |
| `071-080` | GPT work | Concept Core decision advisory and public static `/concept-core/status` capability surface | partial / superseded | `ai_os/concept_core.py`; `ai_os/cognitive_loop.py`; `scripts/api_server.py`; `development/scripts/smoke_concept_core_decision_advisory.py`; `development/scripts/smoke_concept_core_status_route.py` | `smoke_concept_core_decision_advisory.py --json --cleanup`; `smoke_concept_core_status_route.py --json --cleanup` | no direct model-response pipeline confirmed here; no global Concept Core hard enforcement |
| `081-090` | Memory update | Strict `/memory/add` Concept Core mode and validated memory commit path | partial | `scripts/api_server.py`; `core/memory_engine.py`; `development/scripts/smoke_memory_add_concept_route.py`; `development/changes/2026-04-28_memory_add_concept_core_strict_mode.md` | `smoke_memory_add_concept_route.py --json --cleanup` | no automatic conversation capture; no memory schema migration |
| `091-100` | Autonomous AI layer | Recovery/replay continuity, branch stabilization planner policy bridge, scoped recovery-preview labels, `branch_recovery_signal`, `anchor_bias`, recovery continuity task metadata, supervised live smoke controller dry-run | partial / approval-gated | `planning/`; `execution/`; `ai_os/cognitive_loop.py`; `development/scripts/smoke_stabilization_replay_continuity.py`; `development/scripts/smoke_concept_core_status_live_supervised.py`; `development/changes/2026-04-28_branch_stabilization_planner_policy_bridge.md` | `smoke_stabilization_replay_continuity.py --json --cleanup`; supervised live controller `--dry-run --json --timeout-seconds 10` | self-repair, broad cleanup, hard blocking, package mutation, and live runtime starts are approval-gated |

## Unsafe Or Superseded Legacy Assumptions

These historical assumptions are not active execution instructions:

- Old local `venv` activation is superseded. Current official interpreter is `D:\GPTMEAi_venv_candidate\Scripts\python.exe`.
- Old `pip install`, `pip install --upgrade`, dependency repair, and package auto-update actions are unsafe unless an explicit environment-repair scope is approved.
- Archived setup scripts under `smart_trash` are not canonical execution for the current project.
- `smart_trash` content is read-only historical source unless the task explicitly targets migration or archival recovery.
- Broad auto-repair, auto-cleanup, duplicate deletion, backup mutation, storage mutation, and self-repair loops are approval-gated and must not run by default.
- `storage/`, `memory/`, `backups/`, `legacy/`, `runtime/`, and `development/tmp/` remain protected no-edit zones without explicit task scope.
- Global Concept Core enforcement is not enabled.
- Concept Core is currently advisory-only.
- No memory schema migration is accepted.
- No confirmed `.git` root should be assumed.
- The `eventlet` deprecation warning remains a future dependency risk, not a current mutation trigger.

## Next Safe Batch

| item | derived canonical range | type | approval required | allowed files | verification | stop conditions |
|---|---|---|---|---|---|---|
| Run supervised live smoke controller for `/concept-core/status` | `001-010`, `071-080`, `091-100` | approval-gated smoke-only | yes, because it starts runtime | no project edits | `D:\GPTMEAi_venv_candidate\Scripts\python.exe .\development\scripts\smoke_concept_core_status_live_supervised.py --timeout-seconds 90` | stop if port `8010` is occupied, `/health` times out, any endpoint assertion fails, cleanup cannot confirm stop/release |
| Capture docs/checkpoint after live smoke if green | `001-010`, `071-080` | docs-only | no after accepted green live smoke; yes if scope changes | `docs/developer/`; `development/changes/` | read-back only | stop if live smoke was not actually green |
| Design Concept Core decision preview endpoint | `071-080`, `091-100` | read-only design | no for design; yes before implementation | external report only unless later docs approved | design review only | stop before changing API behavior, schemas, planner/dispatch/runtime behavior, or global enforcement |
| Improve smoke check reporting inventory | all ranges | smoke-maintenance / read-only design first | yes before script edits | `development/scripts/` only if approved | `py_compile`; dry-run or focused smoke only | stop on first smoke failure; do not broaden into formatter/lint cleanup |
| Semantic mesh MVP design | `031-040`, `051-060`, `061-070` | read-only design | no for design; yes before implementation | external report only | audit existing `core/`, `memory/`, `ai_os/` contracts | stop before storage/memory schema writes or embedding dependency changes |
| Long-term environment/package manifest design | `001-010`, `098` | read-only design | no for design; yes before environment repair | external report only | inspect current manifest/docs only | stop before `pip`, install/update/repair, or modifying `D:\GPTMEAi_venv_candidate` |
| 100-step evidence index | all ranges | read-only | no | external report only | file/metadata search only | stop before reading sensitive data contents or entering protected runtime data |
| 100-step overlay maintenance after accepted implementation slices | all ranges | docs-only | no after accepted verified slice; yes if scope expands | this overlay; `development/changes/`; optionally `DEVELOPER_CONTEXT.md` | read-back only | stop if implementation verification did not pass |

## Current Invariants

- `AGENTS.md` governs execution.
- Use the official interpreter: `D:\GPTMEAi_venv_candidate\Scripts\python.exe`.
- Do not use or edit damaged `D:\Development GPTMEAi\venv`.
- Do not edit, repair, or casually modify `D:\GPTMEAi_venv_candidate`.
- Do not touch `storage/`, `memory/`, `backups/`, `legacy/`, `runtime/`, or `development/tmp/` without explicit scope.
- Do not change production code, public API behavior, schemas, persisted storage shape, planner/dispatch/runtime behavior, cognitive-loop act behavior, recovery graph behavior, or global Concept Core enforcement without explicit approval.
- Concept Core remains advisory-only.
- Use focused smokes and external review reports for evidence.
- Do not claim verification success unless the command actually ran and passed.
- Do not treat archived `smart_trash` scripts as active execution guidance.

## Handoff Summary

```text
Project root: D:\Development GPTMEAi
Active contract: D:\Development GPTMEAi\AGENTS.md
Official interpreter: D:\GPTMEAi_venv_candidate\Scripts\python.exe
Damaged local venv: D:\Development GPTMEAi\venv (no-use/no-edit)

Canonical 100-step source:
D:\Development GPTMEAi\smart_trash\memory_data\DocumentsGPTMemory_20260308_200556\GPTMemoryEngine\memory\разработка GPTMemory Ai+100steps.yaml

Active overlay:
docs/developer/GPTMEAI_100_STEP_CURRENT_STATE_OVERLAY.md

Interpretation:
- Original 100-step numbering is preserved as historical/conceptual roadmap.
- This overlay maps current GPTMEAi / AI OS Control Plane state to the canonical ranges.
- AGENTS.md overrides old local venv/pip/auto-repair/storage mutation assumptions.
- Concept Core is advisory-only.
- No global hard enforcement and no memory schema migration are accepted.
- Live runtime starts remain approval-gated.

Next safest step:
Run the supervised live smoke controller only after explicit approval and only if port preflight is clean.
```
