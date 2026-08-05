# 2026-04-30 - Concept Core decision advisory in CognitiveLoop.plan()

## Summary

`CognitiveLoop.plan()` now includes a top-level `concept_core_advisory` payload built from existing Concept Core decision and safety primitives.

The advisory is additive and non-enforcing:

- `mode` is `advisory_only`.
- `runtime_enforcement` is `False`.
- `would_block_if_enforced` is descriptive only.
- red-button-like task titles are reported in advisory metadata but are not blocked.
- `act()` behavior is unchanged.
- planner calls are unchanged.
- task generation is unchanged.
- `plan_groups` are unchanged.
- `recovery_requests` are unchanged.
- advisory data is not attached to task metadata.
- advisory data is not attached to planner context.
- advisory data is not persisted into runtime state by this slice.

## Files

- `ai_os/cognitive_loop.py`
- `development/scripts/smoke_concept_core_decision_advisory.py`

## Not Changed

- planner runtime
- dispatch policy
- agent runtime
- execution runtime
- API routes
- dashboard
- public API behavior
- schemas
- storage behavior

## Verification

The implementation slice passed:

- `py_compile`
- `smoke_concept_core.py`
- `smoke_concept_core_memory.py --json --cleanup`
- `smoke_memory_add_concept_route.py --json --cleanup`
- `smoke_memory_concept_read_visibility.py --json --cleanup`
- `smoke_snapshots_replay_metadata.py --json --cleanup`
- `smoke_stabilization_replay_continuity.py --json --cleanup`
- `smoke_concept_core_decision_advisory.py --json --cleanup`

## Next

Keep the advisory non-enforcing until a separate scoped slice explicitly defines planner/runtime behavior, public API expectations, and verification coverage for any enforcement path.
