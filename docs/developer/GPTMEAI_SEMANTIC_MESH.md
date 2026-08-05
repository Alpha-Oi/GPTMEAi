# GPTMEAi Semantic Mesh Architecture Contract

## 1. Purpose

Semantic Mesh is an additive, read-first semantic layer for GPTMEAi.

Its purpose is to connect Concept Core memory nodes, evidence, context, and explicit or derived relations without replacing the existing memory engine, graph engine, planner, cognitive loop, recovery flow, replay flow, API, or storage model.

The initial contract treats Semantic Mesh as an advisory interpretation layer over existing memory records, especially strict Concept Core memory blocks stored under `metadata.concept_core`.

## 2. Non-goals

Stage A of this contract did not implement:

- production code;
- API routes;
- schema migration;
- storage writes;
- global strict memory enforcement;
- planner, dispatch, or recovery enforcement;
- replay or snapshot contract changes.

Current stage status is tracked in section 8. Semantic Mesh still does not create runtime state, storage indexes, generated artifacts, migration tools, planner enforcement, or relation writers.

## 3. Current accepted foundation

The accepted foundation is:

- `ai_os/concept_core.py` is an additive typed Concept Core layer.
- `MemoryNode` already includes `id`, `type`, `title`, `content`, `status`, `source`, `confidence`, `context`, `relations`, `created_at`, and `updated_at`.
- `MemoryCommitValidator` validates source-backed Concept Core memory payloads before strict memory commits.
- `MemoryEngine.add(text, ...)` remains the legacy memory write path.
- `MemoryEngine.add_concept_node(payload, ...)` is the optional strict Concept Core path. It validates the payload, stores `MemoryNode.content` as legacy block `text`, and stores the validated node under `metadata["concept_core"]`.
- `POST /memory/add` uses strict Concept Core mode only when `strict` is exactly `True`.
- Legacy `POST /memory/add {"text": "..."}` behavior remains unchanged.
- Full-block memory read routes (`/memory/all`, `/memory/search`, `/memory/tag`, `/memory/recent`) can expose `metadata.concept_core` when it exists.
- `/memory/related` remains graph-summary shaped and does not expose full Concept Core records.
- `GraphMemory` derives similarity relations from shared tags and words. It is not a typed semantic graph.
- `GET /concept-core/status` is static, read-only, advisory-only, and declares no global enforcement.
- `CognitiveLoop.plan()` direct output can include `concept_core_advisory`, but persisted/status/run-shaped output filters it and planner/dispatch do not enforce Concept Core.
- `/snapshots/replay` remains raw replay output; planner-only replay context belongs to `/planner/recovery/preview`.

## 4. Semantic Mesh MVP boundaries

The safe MVP boundary is:

- read-only;
- ephemeral and in-memory first;
- derived primarily from existing `metadata.concept_core`;
- no storage schema migration;
- no automatic backfill of legacy memory;
- no global strict enforcement;
- no planner or dispatch enforcement;
- no API exposure in the first implementation slice unless separately scoped.

The MVP may classify and report coverage, malformed metadata, relation candidates, dangling targets, and weak derived signals. It must not mutate source records.

## 5. Proposed model contracts

These are documentation-level contracts for future implementation. They are not code in this task.

### SemanticMeshNode

Required conceptual fields:

- `mesh_node_id`
- `concept_id`
- `memory_block_id`
- `concept_type`
- `title`
- `status`
- `source`
- `confidence`
- `context`
- `tags`
- `created_at`
- `updated_at`
- `content_ref`
- `raw_concept_core_ref`

`content_ref` should point to the original memory block content, typically `{ memory_block_id, field_path: "text" }`.

`raw_concept_core_ref` should point to the original Concept Core metadata, typically `{ memory_block_id, field_path: "metadata.concept_core" }`.

### SemanticMeshRelation

Required conceptual fields:

- `relation_id`
- `source_node_id`
- `target_node_id` or `target_concept_id`
- `relation_type`
- `direction`
- `status`
- `confidence`
- `evidence_refs`
- `relation_source`
- `metadata`

`relation_source` must distinguish explicit Concept Core relations from weak derived signals such as shared tags or shared words.

### SemanticMeshEvidenceRef

Required conceptual fields:

- `memory_block_id`
- `field_path`
- `source`
- `status`
- `confidence`
- `context_keys`

Evidence refs should point back to original memory data instead of duplicating large record content.

### SemanticMeshIndex

Required conceptual fields:

- `nodes`
- `relations`
- `diagnostics`
- coverage counts

Coverage counts should include at least the diagnostics listed in section 7.

## 6. Relation contract

Initial allowed relation types:

- `supports`
- `contradicts`
- `refines`
- `depends_on`
- `derived_from`
- `evidences`
- `related_to`

Rules:

- Explicit Concept Core relations are advisory.
- Derived tag or word relations are weak signals and must be labeled.
- Relation IDs should be deterministic.
- Dangling targets create diagnostics, not hard failures.
- Unknown relation types should be diagnostics in the read-only MVP, not fatal errors.
- Weak similarity must not be silently promoted to authoritative semantics.

## 7. Evidence and diagnostics contract

Required diagnostics:

- `total_blocks`
- `strict_concept_blocks`
- `legacy_blocks`
- `malformed_concept_blocks`
- `relation_count`
- `dangling_relation_count`
- `weak_derived_relation_count`
- `unknown_relation_type_count`

Evidence rules:

- Every mesh node must point back to the original memory block.
- Every relation should have an evidence ref where possible.
- A malformed `metadata.concept_core` payload should be reported as diagnostic data, not repaired in place.
- Legacy blocks without Concept Core metadata remain valid memory blocks.
- Weak tag/word similarity must stay labeled as weak derived evidence.

## 8. Implementation staging

### Stage A - Docs-only contract

This current task. It creates this architecture contract and a change note only.

### Stage B - Read-only inventory smoke

Implemented by `development/scripts/smoke_semantic_mesh_inventory.py`.

The smoke inspects fixture memory blocks and reports Semantic Mesh coverage without changing storage.

### Stage C - Isolated library-only model

Implemented by `ai_os/semantic_mesh.py` and verified by `development/scripts/smoke_semantic_mesh_library.py`.

This layer adds dataclasses and a read-only `build_semantic_mesh(...)` builder over already-loaded memory blocks. It does not add API routes, runtime writes, storage indexes, planner enforcement, replay changes, or migration behavior.

### Stage D - Optional read-only API preview

Implemented by `GET /semantic-mesh/preview` in `scripts/api_server.py` and verified by `development/scripts/smoke_semantic_mesh_api_preview.py`.

The endpoint is additive, read-only, and advisory. It builds the response from `build_semantic_mesh(memory_engine.get_all())`, exposes `mesh.nodes`, `mesh.relations`, `mesh.diagnostics`, and `mesh.malformed_blocks`, and declares `runtime_enforcement=false` plus `storage_schema_mutation=false`. It does not add query semantics, POST/write routes, storage indexes, backfill, planner/dispatch/replay integration, or dashboard integration.

### Stage E - Planner/Cognitive advisory adapter

Only after separate design. It must remain advisory-only and non-enforcing.

### Stage F - Strict relation writer

Only after relation schema contract and RED/GREEN smokes. It must preserve legacy `/memory/add` behavior.

## 9. Safety invariants

- Legacy `MemoryEngine.add` remains unchanged.
- Legacy `POST /memory/add {"text": "..."}` remains unchanged.
- No automatic backfill or migration of legacy memory is allowed.
- No planner, dispatch, or recovery decision is enforced from Semantic Mesh.
- `/snapshots/replay` remains raw replay output.
- Semantic Mesh is advisory-only until explicitly promoted by a later accepted contract.
- Protected zones remain no-edit unless a later task explicitly scopes them.
- No package, interpreter, or environment mutation is part of Semantic Mesh MVP work.

## 10. Verification expectations

Future verification expectations:

- run `py_compile` for new code when code exists;
- use fixture-based smoke for any read-only index implementation;
- keep existing Concept Core smokes green;
- keep existing memory route/read visibility smokes green if routes are touched;
- keep replay/stabilization continuity smokes green if planner or replay boundaries are touched;
- use docs read-back for docs-only tasks.

Docs-only tasks do not require live runtime startup.

## 11. Rollback expectations

Rollback by stage:

- Docs-only: remove or revert this contract and its change note.
- Library-only: remove the new module and smoke, then rerun targeted verification.
- API preview: remove the route and smoke, then verify legacy routes and status surfaces.
- Planner/Cognitive adapter: remove the advisory adapter and verify continuity smokes.

No stage may require data rollback unless a later approved task explicitly introduces storage mutation.
