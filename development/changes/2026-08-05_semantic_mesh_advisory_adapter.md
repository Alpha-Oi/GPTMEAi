# Semantic Mesh Stage E1 Advisory Adapter

Date: 2026-08-05

## Summary

Implemented Stage E1 as a pure library-only advisory adapter:

- `ai_os/semantic_mesh_advisory.py`
- `development/scripts/smoke_semantic_mesh_advisory.py`

The adapter translates an already-built `SemanticMeshIndex` and an optional plan
mapping into aggregate-only coverage, diagnostic, relation evidence-source,
aggregate plan, and attention-signal data. The bounded scalar `focus_area` is
allowed; plan collections are represented only as counts.

## Corrective review follow-up

- added explicit `malformed_only` coverage so malformed records are not reported
  as `legacy_only`;
- kept `legacy_only` exclusive to legacy blocks without strict or malformed
  blocks and classified other non-empty combinations as `mixed`;
- added a malformed-only smoke fixture;
- replaced the import denylist with an exact allowlist and boundary probes.

## Scope

This slice does not wire Semantic Mesh into `CognitiveLoop`, `PlannerRuntime`,
API routes, task metadata, recovery requests, persistence, status surfaces,
dispatch, replay, storage, or schemas. It does not expose mesh nodes, relation
payloads, evidence refs, malformed record details, or planned task titles.

Stage E2 cognitive integration remains separately approval-gated.

## Verification

Use the official adopted interpreter:

```powershell
Set-Location 'D:\Development GPTMEAi'
& 'D:\GPTMEAi_venv_candidate\Scripts\python.exe' -m py_compile 'ai_os\semantic_mesh.py' 'ai_os\semantic_mesh_advisory.py' 'development\scripts\smoke_semantic_mesh_advisory.py'
& 'D:\GPTMEAi_venv_candidate\Scripts\python.exe' 'development\scripts\smoke_semantic_mesh_advisory.py' --json --cleanup
& 'D:\GPTMEAi_venv_candidate\Scripts\python.exe' 'development\scripts\smoke_semantic_mesh_library.py' --json --cleanup
& 'D:\GPTMEAi_venv_candidate\Scripts\python.exe' 'development\scripts\smoke_semantic_mesh_inventory.py' --json --cleanup
& 'D:\GPTMEAi_venv_candidate\Scripts\python.exe' 'development\scripts\smoke_semantic_mesh_api_preview.py' --json --cleanup
& 'D:\GPTMEAi_venv_candidate\Scripts\python.exe' 'development\scripts\smoke_concept_core_advisory_consumers.py' --json --cleanup
```

Expected smoke status: `ok`.
