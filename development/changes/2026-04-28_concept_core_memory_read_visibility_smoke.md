# 2026-04-28 - Concept Core memory read visibility smoke

- Added smoke-only verification script `development/scripts/smoke_memory_concept_read_visibility.py`.
- No production code changes were needed: existing full-block memory read routes already expose `metadata["concept_core"]` for strict Concept Core memory blocks.
- Verified existing visibility through `/memory/all`, `/memory/search`, `/memory/tag`, and `/memory/recent`.
- Verified `/memory/related` remains graph-summary shaped and does not expose full Concept Core memory records.
- Legacy memory blocks do not get `metadata.concept_core` by default, while strict Concept Core memory blocks include `metadata["concept_core"]`.
- Project `GPTMemory_runtime.yaml` was unchanged before and after verification.
- Verification passed: `py_compile`, `smoke_concept_core.py`, `smoke_concept_core_memory.py --json --cleanup`, `smoke_memory_add_concept_route.py --json --cleanup`, `smoke_memory_concept_read_visibility.py --json --cleanup`, and `smoke_stabilization_replay_continuity.py --json --cleanup`.
