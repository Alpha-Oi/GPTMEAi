# 2026-04-28 - Recovery continuity task metadata

Recovery preview `task_specs` now receive additive metadata-only `recovery_continuity`, built from already-computed `branch_recovery_signal` and `anchor_bias`. The metadata is attached only to recovery task metadata, not to plan context.

Created recovery plan context still preserves `branch_recovery_signal` and `anchor_bias` unchanged from preview. No-signal branch behavior is unchanged, explicit `snapshot_id` still wins, and `anchor_bias` behavior is unchanged. The recovery task graph is unchanged: task count, `step_key`, `depends_on`, `recovery_phase`, and `preferred_role` remain stable.

No changes were made to `/snapshots/replay`, snapshot schema, replay ordering, recovery graph, API route code, dashboard, role policy, agent runtime, or cognitive loop. Verification passed with the corrected focused isolated smoke and consolidated smoke; both used cleanup with `cleanup_succeeded=true` and `temp_root_exists_after_cleanup=false`.

The prior failed focused smoke was caused by an incorrect assertion expecting top-level created plan `branch_recovery_signal` / `anchor_bias` fields. The correct location is `created_plan["context"]`.
