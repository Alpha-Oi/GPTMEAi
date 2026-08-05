# Semantic Mesh Stage F1 Relation Contract

Date: 2026-08-05

## Summary

Implemented `semantic_relation.v1` as a pure, versioned validator for future
exact opt-in authored relations:

- `ai_os/semantic_relation_contract.py`
- `development/scripts/smoke_semantic_relation_contract.py`

The validator accepts an in-memory relation list plus `source_concept_id`,
validates the complete list atomically, and returns a fresh canonical copy.

## Contract

Each authored relation has exactly four fields:

```json
{
  "contract_version": "semantic_relation.v1",
  "type": "supports",
  "target": "concept:beta",
  "evidence_ref": "memory:source-alpha"
}
```

The contract limits a node to 64 relations, uses the existing seven Semantic
Mesh relation types, rejects unknown fields, non-canonical strings, duplicate
tuples, and self-references, and accepts dangling targets without lookup.
Validation failures use `SemanticRelationContractError` with stable error codes
and do not include rejected input values.

## Scope

This slice does not integrate with `MemoryNode`, `MemoryCommitValidator`,
`MemoryEngine`, `POST /memory/add`, the Semantic Mesh read builder, planner,
dispatch, replay, runtime, storage, or schemas. It adds no writer, migration,
backfill, reverse edges, target lookup, package, environment, or live runtime
behavior. Existing strict Concept Core and legacy memory paths remain unchanged.

Future Stage F2 writer integration remains separately approval-gated.

## Verification

Use the official adopted interpreter:

```powershell
Set-Location 'D:\Development GPTMEAi'
& 'D:\GPTMEAi_venv_candidate\Scripts\python.exe' -B '.\development\scripts\smoke_semantic_relation_contract.py' --json --cleanup
& 'D:\GPTMEAi_venv_candidate\Scripts\python.exe' -B '.\development\scripts\smoke_semantic_mesh_library.py' --json --cleanup
& 'D:\GPTMEAi_venv_candidate\Scripts\python.exe' -B '.\development\scripts\smoke_semantic_mesh_inventory.py' --json --cleanup
& 'D:\GPTMEAi_venv_candidate\Scripts\python.exe' -B '.\development\scripts\smoke_semantic_mesh_advisory.py' --json --cleanup
& 'D:\GPTMEAi_venv_candidate\Scripts\python.exe' -B '.\development\scripts\smoke_concept_core_memory.py' --json --cleanup
& 'D:\GPTMEAi_venv_candidate\Scripts\python.exe' -B '.\development\scripts\smoke_memory_add_concept_route.py' --json --cleanup
```

Expected smoke status: `ok`.

## Rollback

Remove the pure validator and focused smoke, then revert the Semantic Mesh
contract documentation update. No data rollback is required because Stage F1
does not write or migrate data.
