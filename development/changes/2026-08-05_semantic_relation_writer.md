# Semantic Mesh Stage F2A Relation Writer Wiring

Date: 2026-08-05

## Summary

Implemented direct-library exact opt-in writer validation for authored
`semantic_relation.v1` relations.

`MemoryCommitValidator.validate(...)` and `MemoryEngine.add_concept_node(...)`
now accept the keyword-only parameter
`relation_contract_version: str | None = None`. The default `None` keeps the
existing permissive behavior. An explicit non-`None` value validates the raw
relation list through the Stage F1 contract before any memory write.

## Contract

- only exact `semantic_relation.v1` opt-in is accepted;
- a missing `relations` key is treated as an empty list;
- an explicit non-list `relations` value is rejected;
- F1 `SemanticRelationContractError` types and stable codes propagate unchanged;
- successful validation stores a fresh canonical copy under the existing
  `metadata.concept_core.relations` field;
- invalid opt-in payloads do not create memory blocks;
- input payloads are not mutated.

## Scope

This slice changes only direct-library calls. Existing `MemoryEngine.add(...)`
and default `MemoryEngine.add_concept_node(...)` behavior remain unchanged.
`POST /memory/add` does not pass the new opt-in and has no API or response change.
There is no storage schema change, migration, backfill, target lookup,
reverse-edge creation, Semantic Mesh read-model change, planner/dispatch/replay
change, package/environment mutation, or live runtime startup.

## Verification

Use the official adopted interpreter:

```powershell
Set-Location 'D:\Development GPTMEAi'
& 'D:\GPTMEAi_venv_candidate\Scripts\python.exe' -B '.\development\scripts\smoke_semantic_relation_writer.py' --json --cleanup
& 'D:\GPTMEAi_venv_candidate\Scripts\python.exe' -B '.\development\scripts\smoke_semantic_relation_contract.py' --json --cleanup
& 'D:\GPTMEAi_venv_candidate\Scripts\python.exe' -B '.\development\scripts\smoke_concept_core.py'
& 'D:\GPTMEAi_venv_candidate\Scripts\python.exe' -B '.\development\scripts\smoke_concept_core_memory.py' --json --cleanup
& 'D:\GPTMEAi_venv_candidate\Scripts\python.exe' -B '.\development\scripts\smoke_memory_add_concept_route.py' --json --cleanup
& 'D:\GPTMEAi_venv_candidate\Scripts\python.exe' -B '.\development\scripts\smoke_memory_concept_read_visibility.py' --json --cleanup
& 'D:\GPTMEAi_venv_candidate\Scripts\python.exe' -B '.\development\scripts\smoke_semantic_mesh_library.py' --json --cleanup
& 'D:\GPTMEAi_venv_candidate\Scripts\python.exe' -B '.\development\scripts\smoke_semantic_mesh_api_preview.py' --json --cleanup
```

Expected smoke status: `ok`.

## Rollback

Remove the keyword-only relation contract parameter and forwarding from
`MemoryCommitValidator` and `MemoryEngine`, remove the focused writer smoke, and
revert these documentation updates. No data rollback is required because this
slice adds no schema or migration.
