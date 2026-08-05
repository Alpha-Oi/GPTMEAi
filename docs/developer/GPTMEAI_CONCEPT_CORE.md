# GPTMEAi Concept Core

Status: MVP foundation, additive-only.

`Concept Core` is the typed reasoning safety layer for GPTMEAi. It does not replace the existing cognitive loop, planner, execution ledger, memory engine, or recovery flows. Current slices add reusable data contracts, advisory-only cognitive planning metadata, explicit strict memory commit support, and one static public status surface without enabling runtime enforcement.

## Runtime Pipeline

Target reasoning pipeline:

```text
User Request
-> Intake
-> Identity
-> Evidence
-> Risk
-> Decision
-> Safety
-> Output
-> Verification
-> Memory Commit
```

The current MVP implements the typed core for `Identity`, `Evidence`, `Risk`, `Decision`, `Safety`, and `Memory Commit` validation. Runtime enforcement remains disabled. The only deliberate public Concept Core status surface is `GET /concept-core/status`, which is static, read-only, and capability-level.

## Knowledge Status

`KnowledgeStatus` distinguishes:

- `confirmed`
- `inference`
- `hypothesis`
- `unknown`
- `contradiction`

`EvidenceItem` requires `content`, `source`, `status`, `confidence`, and optional `metadata`.

## Foreignness

`ForeignnessLevel` classifies understanding and risk:

- `known`
- `familiar`
- `partially_understood`
- `unknown`
- `risky`
- `quarantined`
- `irreversible_threat`

Contradictory evidence escalates foreignness to `risky`. Unknown identity plus destructive action is blocked.

## Intervention

`InterventionLevel` is the safe action envelope:

- `observe`
- `ask`
- `verify`
- `patch`
- `refactor`
- `rebuild_file`
- `rebuild_module`
- `redesign`
- `block`

`DecisionEngine` produces a coherent `DecisionCommit` with one selected intervention. If there is contradiction or insufficient understanding, the decision is downgraded to `verify` or blocked.

## Safety Protocol

`SafetyGuard` blocks unsafe decisions before execution. Red-button actions require explicit review, verification, rollback, reversibility, and a bounded risk profile.

Red-button action categories include:

- deleting data
- changing schemas
- changing public APIs
- overwriting memory or storage
- modifying project contracts
- removing rollback
- irreversible external actions
- environment promotion or repair outside explicit repair scope

This MVP is a local decision validator only. It does not yet enforce every existing runtime route.

## Cognitive Loop Decision Advisory

Current optional integration:

- `CognitiveLoop.plan()` returns a top-level `concept_core_advisory` payload.
- The advisory is built with existing Concept Core decision/safety primitives.
- `mode` is `advisory_only`.
- `runtime_enforcement` is `False`.
- `would_block_if_enforced` is descriptive only.
- Red-button-like task titles are reported but not enforced.
- `act()` behavior is unchanged.
- Planner calls are unchanged.
- The advisory is not passed through task metadata.
- The advisory is not passed through planner context.
- The advisory is not passed through recovery request args.
- Task generation is unchanged.
- `plan_groups` are unchanged.
- `recovery_requests` are unchanged.
- Persisted/status/run-shaped serialization filters top-level `concept_core_advisory` from copied plan payloads.
- `_sanitize_plan_for_serialization()` removes only top-level `concept_core_advisory` from serialized plan payload copies.
- `_sanitize_cycle_for_serialization()` applies that plan filter to cycle payload copies.
- `_state_for_serialization()` prepares sanitized state before JSON persistence.
- `_record_cycle()` stores sanitized `last_cycle`.
- `_save_state()` writes sanitized state.
- `status_snapshot()` returns sanitized `last_cycle`.

No planner/runtime/dispatch/API/schema/storage behavior changed in this slice.
No live runtime/API smoke was run for this slice.

## Public Status Surface

`GET /concept-core/status` is the first deliberate public Concept Core status surface.

It is static, read-only, capability-level, advisory-only, and non-enforcing. It does not run a cognitive cycle, inspect planner state, or read/write memory.

Response contract:

- `status`: `"ok"`
- `service`: `"AI OS Concept Core"`
- `mode`: `"advisory_only"`
- `runtime_enforcement`: `False`
- `storage_schema_mutation`: `False`
- `public_api_behavior_mutation`: `False`
- `capabilities.typed_primitives`: `True`
- `capabilities.strict_memory_add`: `True`
- `capabilities.memory_metadata_visibility`: `True`
- `capabilities.direct_cognitive_plan_advisory`: `True`
- `capabilities.public_decision_preview`: `False`
- `capabilities.global_enforcement`: `False`
- `visibility.memory_metadata_routes`: `/memory/all`, `/memory/search`, `/memory/tag`, `/memory/recent`
- `visibility.memory_related_exposes_metadata`: `False`
- `visibility.cognitive_status_exposes_plan_advisory`: `False`
- `visibility.cognitive_run_exposes_plan_advisory`: `False`
- `visibility.planner_status_uses_concept_core`: `False`
- `visibility.dispatch_uses_concept_core`: `False`
- `safety_contract.label`: `"advisory_non_enforcing"`
- `safety_contract.internal_plan_payload_exposed`: `False`
- `safety_contract.red_button_detection`: `"text_heuristic_mvp_not_authoritative_policy"`

The endpoint does not call:

- `CognitiveLoop.plan()`
- `CognitiveLoop.run_cycle()`
- `CognitiveLoop.status_snapshot()`
- planner recovery preview
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

Existing route contracts remain unchanged:

- `/health`
- `/cognitive/status`
- `/cognitive/run`
- `/planner/status`
- `/planner/recovery/preview`
- all `/memory` routes

No dashboard change, global Concept Core enforcement, schema/storage mutation, runtime behavior change, or live runtime startup was part of this slice.

Verification passed:

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

## Memory Commit Protocol

`MemoryCommitValidator` validates `MemoryNode` payloads before future memory commits.

Required fields:

- `id`
- `type`
- `title`
- `content`
- `status`
- `source`
- `confidence`
- `context`
- `relations`
- `created_at`
- `updated_at`

Memory nodes without `source`, `status`, `context`, or valid `confidence` are rejected. This protects future memory writes from untraceable or context-free entries.

Current optional integration:

- `MemoryEngine.add_concept_node(payload: dict, *, tags=None, importance=None)` is the explicit strict Concept Core memory commit path.
- Existing `MemoryEngine.add(text, ...)` behavior remains unchanged.
- Legacy `POST /memory/add` behavior remains unchanged: `{"text": "..."}` still calls `MemoryEngine.add(text)`, returns status code `201`, and preserves the `status/message/memory_count/item` outer response shape.
- `POST /memory/add` now has explicit strict mode only when `payload["strict"] is True`; strict requests require `payload["concept_core"]` to be a dict and call `MemoryEngine.add_concept_node(...)`.
- `add_concept_node()` validates payloads through `MemoryCommitValidator`.
- Valid `MemoryNode.content` is stored as legacy block `text` and route response `item.text`.
- The validated Concept Core payload is stored under `metadata["concept_core"] = MemoryNode.to_dict()`.
- Strict validation errors return `400 {"error": "..."}` and invalid strict payloads are rejected before writing memory blocks.
- Legacy memory block shape remains compatible.
- No global strict validation is enabled, no memory schema migration was performed, and cognitive loop/runtime behavior remains unchanged.

Read-path visibility:

- No production read-path change was required for Concept Core visibility.
- Existing full-block read routes already return `metadata["concept_core"]` when it is present: `/memory/all`, `/memory/search`, `/memory/tag`, and `/memory/recent`.
- Legacy memory blocks do not get `metadata.concept_core` by default.
- Strict Concept Core memory blocks include `metadata["concept_core"]`.
- `/memory/related` remains graph-summary shaped and does not expose full Concept Core memory records.
- `development/scripts/smoke_memory_concept_read_visibility.py` verifies this behavior with temp runtime state only.

## Current Integration Boundary

Implemented:

- `ai_os.concept_core.KnowledgeStatus`
- `ai_os.concept_core.ForeignnessLevel`
- `ai_os.concept_core.InterventionLevel`
- `ai_os.concept_core.EvidenceItem`
- `ai_os.concept_core.IdentityCore`
- `ai_os.concept_core.RiskProfile`
- `ai_os.concept_core.DecisionCommit`
- `ai_os.concept_core.MemoryNode`
- `ai_os.concept_core.SafetyGuard`
- `ai_os.concept_core.DecisionEngine`
- `ai_os.concept_core.MemoryCommitValidator`
- top-level advisory-only `CognitiveLoop.plan()["concept_core_advisory"]`
- read-only `GET /concept-core/status` static capability/status surface
- `core.memory_engine.MemoryEngine.add_concept_node`
- optional explicit strict mode in `POST /memory/add`
- smoke-only read-path visibility verification for existing Concept Core metadata exposure

Not changed:

- dashboard
- planner behavior
- cognitive loop `act()` behavior
- task generation
- planner calls
- existing `/health`, `/cognitive/status`, `/cognitive/run`, `/planner/status`, `/planner/recovery/preview`, and `/memory` route contracts
- memory storage schema
- snapshot schema
- execution ledger schema

Future slices should wire these validators into runtime paths only with explicit migration and compatibility planning.
