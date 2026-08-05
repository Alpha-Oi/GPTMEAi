# 2026-04-30 - Concept Core public status endpoint checkpoint

## Summary

`GET /concept-core/status` is the first deliberate public Concept Core status surface.

The endpoint is static, read-only, capability-level, advisory-only, and non-enforcing. It does not expose internal `CognitiveLoop.plan()` payloads, does not imply runtime enforcement, and does not mutate schema, storage, memory, planner, dispatch, cognitive act, or runtime behavior.

## Accepted endpoint behavior

The endpoint returns:

- `status="ok"`
- `service="AI OS Concept Core"`
- `mode="advisory_only"`
- `runtime_enforcement=false`
- `storage_schema_mutation=false`
- `public_api_behavior_mutation=false`
- capabilities for:
  - `typed_primitives=true`
  - `strict_memory_add=true`
  - `memory_metadata_visibility=true`
  - `direct_cognitive_plan_advisory=true`
  - `public_decision_preview=false`
  - `global_enforcement=false`
- visibility fields for:
  - memory metadata routes: `/memory/all`, `/memory/search`, `/memory/tag`, `/memory/recent`
  - `/memory/related` not exposing metadata
  - `/cognitive/status` and `/cognitive/run` not exposing plan advisory
  - planner status not using Concept Core
  - dispatch not using Concept Core
- `safety_contract.label="advisory_non_enforcing"`
- `safety_contract.internal_plan_payload_exposed=false`
- `safety_contract.red_button_detection="text_heuristic_mvp_not_authoritative_policy"`

The endpoint does not call:

- `CognitiveLoop.plan()`
- `CognitiveLoop.run_cycle()`
- `CognitiveLoop.status_snapshot()`
- planner preview
- memory read/write methods

The endpoint does not expose:

- internal `CognitiveLoop.plan()` payload
- `concept_core_advisory`
- task titles
- `plan_groups`
- `recovery_requests`
- evidence lists
- decision object dumps
- memory content
- `metadata.concept_core` values
- red-button term list

## Files changed in this slice

Implementation slice:

- `scripts/api_server.py`
- `development/scripts/smoke_concept_core_status_route.py`

Docs/checkpoint capture:

- `docs/developer/DEVELOPER_CONTEXT.md`
- `docs/developer/GPTMEAI_CONCEPT_CORE.md`
- `development/changes/2026-04-30_concept_core_status_endpoint_checkpoint.md`

## Verified green checks

Implementation verification passed before this docs checkpoint:

- TDD RED before implementation proved the missing route and old dispatch order.
- `py_compile`
- `smoke_concept_core_status_route.py --json --cleanup`
- `smoke_concept_core.py`
- `smoke_concept_core_memory.py --json --cleanup`
- `smoke_memory_add_concept_route.py --json --cleanup`
- `smoke_memory_concept_read_visibility.py --json --cleanup`
- `smoke_concept_core_decision_advisory.py --json --cleanup`
- `smoke_concept_core_advisory_consumers.py --json --cleanup`
- `smoke_snapshots_replay_metadata.py --json --cleanup`
- `smoke_stabilization_replay_continuity.py --json --cleanup`

Docs-only verification for this checkpoint is read-back only. No code smokes or live runtime startup are part of this docs task.

## Active invariants

- `GET /concept-core/status` remains static/read-only/capability-level.
- Concept Core remains advisory-only and non-enforcing.
- Direct `CognitiveLoop.plan()` advisory remains internal/direct-caller level.
- Persisted/status/run-shaped cognitive serialization keeps filtering top-level `concept_core_advisory`.
- Existing memory metadata visibility remains through full-block memory routes.
- Existing public route contracts stay preserved.
- Global Concept Core hard enforcement stays disabled.
- Damaged project-local `venv/` remains protected and unused.
- Official verification interpreter remains `D:\GPTMEAi_venv_candidate\Scripts\python.exe`.

## What remains unchanged

- `/health`
- `/cognitive/status`
- `/cognitive/run`
- `/planner/status`
- `/planner/recovery/preview`
- all `/memory` routes
- dashboard
- planner behavior
- dispatch behavior
- cognitive-loop `act()` behavior
- recovery graph behavior
- schemas
- storage, memory, and runtime data
- package/environment state

## Remaining risks / debt

- Red-button detection remains a text/heuristic MVP and is not authoritative policy.
- No public Concept Core decision preview endpoint exists.
- No dashboard visualization exists for `GET /concept-core/status`.
- Live runtime/API confirmation is optional and separate because the accepted implementation was handler/smoke verified without starting runtime.

## Next safe options

1. Read-only API/status design for a future explicit Concept Core decision preview endpoint.
2. Smoke-only live runtime/API confirmation for `http://127.0.0.1:8010/concept-core/status`, only after explicit approval to start runtime.
3. Read-only dashboard visibility design for displaying the static status surface without exposing internal plan payloads.

## Copy-paste handoff block

Project root: `D:\Development GPTMEAi`

Active contract: `D:\Development GPTMEAi\AGENTS.md`

Official interpreter: `D:\GPTMEAi_venv_candidate\Scripts\python.exe`

Accepted Concept Core API/status visibility phase:

- `GET /concept-core/status` is implemented as the first deliberate public Concept Core status surface.
- It is static, read-only, capability-level, advisory-only, and non-enforcing.
- It does not expose internal `CognitiveLoop.plan()` payloads.
- It does not expose `concept_core_advisory`, task titles, `plan_groups`, `recovery_requests`, evidence lists, decision dumps, memory content, `metadata.concept_core` values, or red-button terms.
- It does not call `CognitiveLoop.plan()`, `run_cycle()`, `status_snapshot()`, planner preview, or memory read/write methods.
- Direct `CognitiveLoop.plan()` advisory remains internal/direct-caller level.
- Existing memory metadata visibility remains through `/memory/all`, `/memory/search`, `/memory/tag`, and `/memory/recent`.
- Existing route contracts were preserved.
- No dashboard, schema, storage, runtime, planner, dispatch, cognitive act, recovery graph, package, or environment behavior changed.
- Optional live runtime/API smoke is a separate approved task if runtime-level confirmation is desired.

Verified green before docs capture:

- TDD RED
- `py_compile`
- new route smoke
- accepted Concept Core, memory, advisory, replay metadata, and stabilization replay continuity smokes
