# 2026-04-28 - Scoped recovery preview policy labels

`branch_recovery_signal` now includes additive scoped policy metadata: `policy_scope="recovery_preview"`, `planner_gate_scope="recovery"`, and `dispatch_policy_scope="recovery"`. This clarifies that replay/recovery preview policy fields are recovery-scoped advisory surfaces, separate from branch-wide operational control surfaces.

This is metadata-only. Runtime behavior did not change, existing fields were not renamed or removed, failed operational dispatch may remain stricter while recovery preview remains `restricted` / advisory, explicit `snapshot_id` still wins, no-signal behavior is unchanged, and `anchor_bias` behavior is unchanged.

No changes were made to `/snapshots/replay`, snapshot schema, recovery graph, API routes, dashboard, role policy, agent runtime, or cognitive loop. Verification passed with `py_compile`, consolidated smoke, and a focused isolated scoped-label check.
