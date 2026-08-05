# Semantic Mesh Stage E2A Cognitive Advisory Wiring

Date: 2026-08-05

## Summary

Implemented exact opt-in direct-plan wiring for the existing Stage E1 Semantic
Mesh advisory adapter.

`CognitiveLoop.plan(...)` now accepts the keyword-only parameter
`semantic_mesh_index: SemanticMeshIndex | None = None`. When a caller explicitly
supplies an already-built index, the direct plan includes top-level aggregate-only
`semantic_mesh_advisory`. With the default `None`, the plan remains unchanged and
no Semantic Mesh is built or read.

## Scope

- `run_cycle()` remains on the default path and does not opt in;
- `act()` and planner calls do not consume the advisory;
- task metadata, planner context, recovery request args, and dispatch input are unchanged;
- persisted, status, and run-shaped serialization filters both
  `concept_core_advisory` and `semantic_mesh_advisory`;
- no API route, schema, storage, replay, package, environment, or live runtime
  behavior changed.

## Verification

Use the official adopted interpreter:

```powershell
Set-Location 'D:\Development GPTMEAi'
& 'D:\GPTMEAi_venv_candidate\Scripts\python.exe' -B '.\development\scripts\smoke_semantic_mesh_cognitive_advisory.py' --json --cleanup
& 'D:\GPTMEAi_venv_candidate\Scripts\python.exe' -B '.\development\scripts\smoke_semantic_mesh_advisory.py' --json --cleanup
& 'D:\GPTMEAi_venv_candidate\Scripts\python.exe' -B '.\development\scripts\smoke_concept_core_advisory_consumers.py' --json --cleanup
& 'D:\GPTMEAi_venv_candidate\Scripts\python.exe' -B '.\development\scripts\smoke_concept_core_decision_advisory.py' --json --cleanup
& 'D:\GPTMEAi_venv_candidate\Scripts\python.exe' -B '.\development\scripts\smoke_branch_playbook.py' --json --cleanup
& 'D:\GPTMEAi_venv_candidate\Scripts\python.exe' -B '.\development\scripts\smoke_stabilization_replay_continuity.py' --json --cleanup
```

Expected smoke status: `ok`.

## Rollback

Remove the keyword-only parameter and conditional advisory attachment from
`CognitiveLoop.plan(...)`, remove the Semantic Mesh serialization filter and
focused smoke, and revert these documentation updates. No data rollback is
required because this slice does not mutate storage or schemas.
