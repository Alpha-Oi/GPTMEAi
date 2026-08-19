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

### Read-model relation behavior

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

These rules describe tolerant interpretation of existing Concept Core metadata.
They do not define a write contract.

### Authored relation contract `semantic_relation.v1`

Stage F1 adds a pure validator for future exact opt-in authored relations. Each
authored relation has exactly these fields:

```json
{
  "contract_version": "semantic_relation.v1",
  "type": "supports",
  "target": "concept:beta",
  "evidence_ref": "memory:source-alpha"
}
```

Validation rules:

- `contract_version` must equal `semantic_relation.v1`;
- `type` must be one of the seven allowed relation types listed above;
- `target` must be a non-empty, trimmed string no longer than 256 characters;
- `evidence_ref` must be a non-empty, trimmed opaque string no longer than 512 characters;
- a node may author at most 64 relations;
- additional or generated read-model fields are rejected;
- duplicate `(type, target, evidence_ref)` tuples are rejected;
- a relation cannot target its own `source_concept_id`;
- dangling or forward targets are accepted without lookup;
- validation does not normalize input, perform I/O, or mutate the input payload.

Authored relations are explicit outbound declarations. Generated relation IDs,
resolved node IDs, direction, status, confidence, evidence-ref collections,
relation source, metadata, and weak derived relations belong to the read model
and are not accepted authored fields.

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

Stage E1 is implemented by `ai_os/semantic_mesh_advisory.py` and verified by
`development/scripts/smoke_semantic_mesh_advisory.py`.

The adapter is pure and library-only. It accepts an already-built
`SemanticMeshIndex` plus an optional plan mapping and returns aggregate coverage,
diagnostic counts, relation evidence-source counts, an aggregate plan summary,
and deterministic attention signals. The plan summary may include the bounded
scalar `focus_area`; plan groups, tasks, recovery requests, and planned task
titles are represented only as counts. It does not expose mesh nodes, relation
payloads, evidence refs, malformed record details, or planned task titles.

Coverage states are `empty`, `strict_only`, `legacy_only`, `malformed_only`, and
`mixed`. `legacy_only` requires legacy blocks with no strict or malformed blocks;
`malformed_only` requires malformed blocks with no strict or legacy blocks. Any
other non-empty combination is `mixed`.

The adapter declares `runtime_enforcement=false`, `planner_input_applied=false`,
`dispatch_input_applied=false`, `planner_context_persistence=false`,
`storage_schema_mutation=false`, and `public_api_behavior_mutation=false`. It does
not import storage, planner, execution, snapshot, or network dependencies. The
focused smoke enforces an exact allowlist for the adapter imports.

Stage E2A adds exact opt-in direct-plan wiring in `CognitiveLoop.plan(...)`.
Callers may pass an already-built `SemanticMeshIndex` through the keyword-only
`semantic_mesh_index` parameter. Only then does the returned direct plan include
top-level `semantic_mesh_advisory`. Default `plan(...)` calls and `run_cycle()` do
not build or read a Semantic Mesh and do not include that field.

The E2A advisory is filtered from persisted, status, and run-shaped plan
serialization alongside `concept_core_advisory`. It is not copied into task
metadata, planner context, recovery requests, or dispatch input. E2A does not
change `PlannerRuntime`, API routes, storage/schema behavior, replay, or default
runtime execution. Automatic mesh construction and any planner decision use
remain separately approval-gated.

### Stage F - Versioned relation authoring contract

Stage F1 is implemented by `ai_os/semantic_relation_contract.py` and verified by
`development/scripts/smoke_semantic_relation_contract.py`.

F1 validates and returns a fresh canonical copy of an in-memory
`semantic_relation.v1` relation list without target lookup, I/O, or input
mutation.

Stage F2A adds direct-library exact opt-in writer wiring through the keyword-only
`relation_contract_version` parameter on `MemoryCommitValidator.validate(...)`
and `MemoryEngine.add_concept_node(...)`. The default `None` preserves existing
permissive Concept Core relation handling. Any explicit non-`None` value invokes
the F1 validator before `MemoryEngine.add(...)`; only exact
`semantic_relation.v1` is accepted, missing `relations` defaults to `[]`, and an
explicit non-list value is rejected with a typed contract error before writing.
The canonical relation copy is stored in the existing
`metadata.concept_core.relations` field.

F2A itself adds no API opt-in. Stage F2B adds a deliberate top-level
`relation_contract_version` transport control to `POST /memory/add`. It is active
only when `strict` is exactly `True` and accepts only exact
`semantic_relation.v1`. When the field is absent, the route preserves its
existing permissive strict call and does not pass the new writer keyword. The
transport field is not persisted and the success response shape is unchanged.

An explicit unsupported, non-string, or `null` version returns
`400 {"error": "unsupported_contract_version;field=contract_version"}` before
the writer is called. Supplying the transport field outside strict mode returns
`400 {"error": "relation_contract_requires_strict_mode;field=relation_contract_version"}`
before the legacy text writer can run. Relation validation failures retain the
typed F1 error strings through the existing API `ValueError` boundary.

F2B does not change storage schemas, migrations, backfills, target lookup,
reverse-edge creation, `/concept-core/status`, Semantic Mesh read semantics,
planner, dispatch, replay, or default requests that omit the transport opt-in.

Stage F3A adds the standalone pure classifier
`ai_os.semantic_relation_compatibility.classify_semantic_relation_compatibility(...)`
for already loaded stored relation lists. It reports one aggregate status:
`empty`, `compatible_v1_shape`, `legacy_unversioned`, `mixed_versioning`,
`unsupported_version`, `invalid_v1`, or `malformed_relations`. Exact fully
versioned lists reuse the F1 validator so list limits, duplicate detection,
self-reference rejection, and stable `code/index/field` diagnostics do not
drift into a second validation implementation.

`compatible_v1_shape` means only that the stored list has the exact
`semantic_relation.v1` shape for the supplied source concept ID. It does not
prove that the F2A/F2B writer validated the stored payload because the API
transport opt-in is intentionally not persisted and the permissive path may
store the same shape. Every report therefore returns
`writer_validation_provenance=not_available` and
`target_lookup_performed=false`.

F3A is not integrated into `SemanticMeshIndex`, `build_semantic_mesh(...)`,
`GET /semantic-mesh/preview`, Concept Core, memory writers, planner, runtime, or
storage. It adds no target lookup, reverse edges, migration, backfill, schema
change, API behavior change, or persistence metadata.

Stage F3B adds the standalone pure aggregate builder
`ai_os.semantic_relation_compatibility_inventory.build_semantic_relation_compatibility_inventory(...)`
over caller-supplied `SemanticRelationCompatibilityReport` objects. It accepts
an exact list, validates report type, status, non-negative counts, aggregate and
status-specific count consistency, and issue invariants, then returns deterministic fixed-taxonomy
status counts plus aggregate relation and issue-report counts. Exact report
generation provenance cannot be established from these public value objects.

The F3B inventory is aggregate-only. It does not accept or expose memory blocks,
Concept Core metadata, source concept IDs, relation payloads, targets, or
evidence refs. It reports `report_generation_provenance=not_available`,
`writer_validation_provenance=not_available`, and
`target_lookup_performed=false`; it does not derive an overall readiness,
migration, planner, or enforcement decision from the counts.

F3B does not import or call `MemoryEngine`, storage, Semantic Mesh, API, planner,
runtime, or network surfaces. It adds no target lookup, reverse edges,
migration, backfill, schema change, persistence metadata, or API behavior.

Stage F3C adds the standalone pure direct-input batch builder
`ai_os.semantic_relation_compatibility_batch.build_direct_semantic_relation_compatibility_inventory(...)`.
It accepts an exact list of exact frozen `SemanticRelationCompatibilityInput`
objects containing only a caller-supplied `source_concept_id` and already loaded
`relations`. Each input is classified directly through F3A, and the resulting
reports are aggregated through the existing F3B builder. F3C does not duplicate
classification or aggregation rules.

The F3C output remains aggregate-only and deterministic. It reports
`report_generation_provenance=direct_f3a_classifier` only to describe the
in-process F3C-to-F3A call path. This marker does not establish the origin,
authenticity, freshness, completeness, uniqueness, storage ownership, or writer
validation of caller-supplied relation inputs. F3C therefore retains
`writer_validation_provenance=not_available` and
`target_lookup_performed=false`, derives no readiness or migration decision,
and counts repeated input items independently without source-ID deduplication.

F3C does not accept storage handles, paths, memory blocks, Concept Core
metadata, iterators, generators, or caller-supplied compatibility reports. It
does not expose source concept IDs, relation payloads, individual reports,
targets, or evidence refs. It does not import or call `MemoryEngine`, storage,
Semantic Mesh, API, writers, planner, runtime, or network surfaces and adds no
target lookup, reverse edges, migration, backfill, schema change, persistence
metadata, input mutation, or API behavior.

Stage F3D adds the standalone pure direct-batch comparison function
`ai_os.semantic_relation_compatibility_comparison.compare_direct_semantic_relation_compatibility_batches(...)`.
It accepts exact caller-supplied `baseline_inputs` and `candidate_inputs`, calls
the existing F3C builder exactly once for each batch, retains the exact returned
inventories, and computes signed `candidate_minus_baseline` deltas for every
fixed-taxonomy status and aggregate count. F3D does not duplicate F3A
classification, F3B aggregation, or F3C batch-validation rules.

The F3D output contains only the baseline aggregate, candidate aggregate, and
descriptive signed deltas. `inventory_generation_provenance` describes only the
direct in-process F3D-to-F3C call path; `writer_validation_provenance` remains
`not_available`. The comparison performs no source-identity matching,
deduplication, pairing, relation alignment, trend interpretation, readiness,
migration, enforcement, or policy decision. Duplicate inputs remain independent
F3C count entries.

F3D does not expose or retain source IDs, relation payloads, individual reports,
targets, or evidence refs. It does not import or call `MemoryEngine`, storage,
Semantic Mesh, API, writers, planner, runtime, or network surfaces and adds no
storage read, target lookup, reverse edges, migration, backfill, schema change,
persistence metadata, file I/O, input mutation, or API behavior.

Stage F3E adds the standalone pure aggregate comparison-inventory builder
`ai_os.semantic_relation_compatibility_comparison_inventory.build_semantic_relation_compatibility_comparison_inventory(...)`.
It accepts an exact list of exact caller-supplied F3D
`SemanticRelationCompatibilityComparison` objects, validates their nested F3C
inventory types, fixed taxonomy, aggregate count consistency, status-derived
issue/minimum relation counts, and every signed `candidate_minus_baseline`
delta, then returns deterministic summed baseline, candidate, and delta counts.
F3E does not call F3D or regenerate comparisons.

Public F3D value objects can be constructed without the F3D builder, so F3E
reports `comparison_generation_provenance=not_available` and does not propagate
F3D direct-call provenance as evidence. Repeated comparison objects are counted
independently, input order is irrelevant, and positive and negative deltas may
cancel arithmetically without implying improvement, regression, trend,
readiness, migration, enforcement, or policy meaning.

F3E does not retain or expose individual comparisons, nested inventories,
source IDs, relation payloads, reports, targets, or evidence refs. It does not
import or call `MemoryEngine`, storage, Semantic Mesh, API, writers, planner,
runtime, or network surfaces and adds no storage read, source matching,
deduplication, pairing, relation alignment, target lookup, reverse edges,
migration, backfill, schema change, persistence metadata, file I/O, input
mutation, or API behavior.

Stage F3F adds the standalone pure direct comparison-batch composer
`ai_os.semantic_relation_compatibility_comparison_batch.build_direct_semantic_relation_compatibility_comparison_inventory(...)`.
It accepts an exact list of exact frozen
`SemanticRelationCompatibilityComparisonBatchInput` value objects. Each object
is one explicit caller-supplied `baseline_inputs` / `candidate_inputs` pair;
F3F does not infer, discover, match, deduplicate, or align comparison units.

For each explicit pair, F3F calls the existing F3D comparison exactly once with
the exact supplied batch objects. It passes only the exact generated comparison
objects, in a new list, to the existing F3E builder exactly once. The returned
aggregate-only inventory preserves the exact F3E baseline, candidate, and delta
objects and marks the bounded in-process call path with
`comparison_generation_provenance=direct_f3d_comparison_for_each_input` and
`comparison_inventory_generation_provenance=direct_f3e_comparison_inventory_builder`.
These markers do not prove input origin, authenticity, freshness, completeness,
uniqueness, storage ownership, source identity, or writer validation.

Duplicate explicit pairs are counted independently and aggregate order is
irrelevant, while input order remains relevant only for safe
`comparison_index/batch/index/field` error context. F3F does not retain or expose
input pairs, individual comparisons, nested inventories, source IDs, relation
payloads, reports, targets, or evidence refs. It does not import or call
`MemoryEngine`, storage, Semantic Mesh, API, writers, planner, runtime, or
network surfaces and adds no storage read, source matching, target lookup,
reverse edges, migration, backfill, schema change, persistence metadata, file
I/O, input mutation, policy interpretation, or API behavior.

## 9. Safety invariants

- Legacy `MemoryEngine.add` remains unchanged.
- Legacy `POST /memory/add {"text": "..."}` remains unchanged.
- No automatic backfill or migration of legacy memory is allowed.
- Authored relation validation is never activated from relation content alone.
- No planner, dispatch, or recovery decision is enforced from Semantic Mesh.
- `/snapshots/replay` remains raw replay output.
- Semantic Mesh is advisory-only until explicitly promoted by a later accepted contract.
- Protected zones remain no-edit unless a later task explicitly scopes them.
- No package, interpreter, or environment mutation is part of Semantic Mesh MVP work.

## 10. Verification expectations

Future verification expectations:

- run `py_compile` for new code when code exists;
- use fixture-based smoke for any read-only index implementation;
- keep the Stage E1 advisory payload aggregate-only and deterministic;
- prove the advisory adapter has no runtime, planner, storage, or network imports;
- prove Stage E2A changes only explicit direct-plan output and leaves default `run_cycle()` unchanged;
- prove planner calls and serialization remain free of `semantic_mesh_advisory`;
- prove Stage F1 accepts only exact `semantic_relation.v1` authored payloads;
- prove Stage F1 performs no target lookup, file writes, runtime mutation, or input mutation;
- keep the Stage F1 validator import allowlist limited to `__future__`;
- prove Stage F2A validates only explicit direct-library opt-in writes before storage mutation;
- prove Stage F2A preserves the default permissive writer and unchanged `/memory/add` behavior;
- prove invalid Stage F2A payloads preserve typed F1 errors and do not write blocks;
- prove Stage F2B forwards only an explicit exact strict API opt-in;
- prove Stage F2B leaves absent opt-in, legacy text writes, response shape, and status surfaces unchanged;
- prove invalid Stage F2B transport controls and relation payloads do not write blocks;
- prove Stage F2B performs no target lookup or reverse-edge creation;
- prove Stage F3A classifies stored list compatibility without claiming writer provenance;
- prove Stage F3A reuses F1 for exact-v1 list validation and returns only safe `code/index/field` diagnostics;
- prove Stage F3A has no Semantic Mesh, API, writer, storage, planner, runtime, or network integration;
- prove Stage F3A performs no target lookup, file I/O, runtime mutation, or input mutation;
- prove Stage F3B aggregates well-formed caller-supplied compatibility reports with exact fixed-taxonomy counts without claiming report-generation provenance;
- prove Stage F3B rejects malformed reports with safe `code/index/field` errors and no rejected values;
- prove Stage F3B is order-independent and exposes no report, source-ID, or relation payloads;
- prove Stage F3B has no storage read, Semantic Mesh/API integration, target lookup, reverse edges, migration, or mutation;
- prove Stage F3C accepts only an exact list of exact direct-input value objects and returns safe `code/index/field` envelope errors without rejected values;
- prove Stage F3C calls F3A once per input with direct object identity, passes only generated reports to F3B, and does not duplicate either contract;
- prove Stage F3C covers the complete F3A taxonomy, positive malformed-only input, deterministic empty and order-independent output, and explicit count-each duplicate semantics;
- prove Stage F3C exposes only aggregate counts plus bounded call-path provenance and does not retain or mutate source IDs or relation payloads;
- prove Stage F3C has an exact F3A/F3B-only project import allowlist and no storage read, Semantic Mesh/API integration, target lookup, reverse edges, migration, file I/O, or mutation;
- prove Stage F3D calls F3C exactly once for each direct batch with exact batch/list/item identity and retains the exact returned inventories;
- prove Stage F3D computes signed `candidate_minus_baseline` deltas for the complete fixed taxonomy and every aggregate through mixed, swapped, same, empty, malformed-only, and duplicate fixtures;
- prove Stage F3D wraps F3C envelope failures with safe baseline/candidate context and never exposes rejected values;
- prove Stage F3D output is aggregate-only and policy-free, with no source matching, pairing, alignment, readiness, migration, or enforcement interpretation;
- prove Stage F3D has an exact F3C-only project import allowlist and no storage read, Semantic Mesh/API integration, target lookup, reverse edges, migration, file I/O, or mutation;
- prove Stage F3E accepts only an exact list of exact F3D comparison objects and rejects forged nested types, taxonomies, counts, issue/minimum relation invariants, and deltas with safe `code/index/field` errors;
- prove Stage F3E aggregates complete fixed-taxonomy baseline/candidate/delta counts exactly, remains order-independent, and applies explicit count-each duplicate semantics;
- prove Stage F3E accepts positive, negative, zero, cancelling, empty, and malformed-only fixtures without deriving trend, readiness, migration, enforcement, or policy meaning;
- prove Stage F3E exposes only aggregate counts, does not retain input references, and marks caller-supplied comparison provenance as unavailable;
- prove Stage F3E has an exact F3A/F3C/F3D project import allowlist, does not regenerate comparisons, and performs no storage read, Semantic Mesh/API integration, matching, lookup, migration, file I/O, or mutation;
- prove Stage F3F accepts only an exact list of exact direct comparison-batch input objects and preserves safe `comparison_index/batch/index/field` context without rejected values;
- prove Stage F3F calls F3D exactly once per explicit input pair with exact baseline/candidate identities, then calls F3E exactly once with the exact generated comparison identities;
- prove Stage F3F preserves exact F3E aggregate object identities and covers complete taxonomy, positive/negative/zero/cancelling, empty, malformed-only, order-independent, and count-each duplicate behavior;
- prove Stage F3F output is aggregate-only and policy-free, has an exact F3D/F3E project import allowlist, and performs no storage read, Semantic Mesh/API integration, source matching, target lookup, migration, file I/O, or mutation;
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
- Planner/Cognitive adapter: remove the advisory adapter and opt-in `CognitiveLoop.plan(...)` wiring, then verify continuity smokes.
- Relation contract: remove the pure validator and focused smoke, then revert the Stage F1 documentation update.
- Relation writer wiring: remove the keyword-only forwarding from `MemoryCommitValidator` and `MemoryEngine`, remove the writer smoke, then rerun Concept Core and memory route verification.
- Relation API writer wiring: remove the `/memory/add` transport gate/forwarding and focused API smoke, revert the directly related docs, and retain F1/F2A plus existing stored data.
- Relation compatibility classifier: remove the standalone classifier and focused smoke, then revert only the F3A documentation update.
- Relation compatibility inventory: remove the standalone inventory builder and focused smoke, then revert only the F3B documentation update.
- Direct relation compatibility batch inventory: remove the standalone batch builder and focused smoke, then revert only the F3C documentation update.
- Direct-batch aggregate compatibility comparison: remove the standalone comparison module and focused smoke, then revert only the F3D documentation update.
- Aggregate compatibility-comparison inventory: remove the standalone comparison-inventory module and focused smoke, then revert only the F3E documentation update.
- Direct comparison-batch inventory composer: remove the standalone comparison-batch module and focused smoke, then revert only the F3F documentation update.

No stage may require data rollback unless a later approved task explicitly introduces storage mutation.
