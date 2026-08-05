# 2026-04-30 - Concept Core advisory persistence filter

## Summary

The accepted Concept Core decision advisory behavior now distinguishes direct planning output from serialized cognitive cycle state.

Direct `CognitiveLoop.plan()` output still includes top-level `concept_core_advisory`.

Serialized cognitive cycle payloads now filter only top-level `concept_core_advisory` from plan payload copies before persistence/status/run-shaped output:

- `_sanitize_plan_for_serialization()` removes only top-level `concept_core_advisory`.
- `_sanitize_cycle_for_serialization()` applies that filter to cycle plan payloads.
- `_state_for_serialization()` prepares sanitized state before JSON persistence.
- `_record_cycle()` stores sanitized `last_cycle`.
- `_save_state()` writes sanitized state.
- `status_snapshot()` returns sanitized `last_cycle`.

## Boundaries

- `concept_core_advisory` remains advisory-only.
- `runtime_enforcement` remains `False`.
- `act()` behavior is unchanged.
- planner calls are unchanged.
- advisory is not passed through task metadata, planner context, or recovery request args.
- task generation, `plan_groups`, `recovery_requests`, and planned task titles are unchanged.
- no planner/runtime/dispatch/API/schema/storage behavior changed.
- no live runtime/API smoke was run.

## Verification

Passed:

- `py_compile`
- `smoke_concept_core_advisory_consumers.py --json --cleanup`
- `smoke_concept_core_decision_advisory.py --json --cleanup`
- `smoke_concept_core.py`
- `smoke_concept_core_memory.py --json --cleanup`
- `smoke_memory_add_concept_route.py --json --cleanup`
- `smoke_memory_concept_read_visibility.py --json --cleanup`
- `smoke_snapshots_replay_metadata.py --json --cleanup`
- `smoke_stabilization_replay_continuity.py --json --cleanup`

## Next

Keep the advisory as direct-plan metadata only unless a future scoped design explicitly defines API or enforcement behavior.
