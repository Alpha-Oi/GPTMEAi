# 2026-04-28 - Raw snapshot replay metadata

`SnapshotLineageRegistry.replay_plan()` now adds response-only `replay_metadata` to raw snapshot replay responses, and `/snapshots/replay` exposes that metadata without changing API route code.

`replay_metadata` identifies the response as raw snapshot lineage with `source="raw_snapshot_lineage"`, `planner_context_included=false`, `planner_context_endpoint="/planner/recovery/preview"`, `anchor_selection_model="explicit_snapshot_id -> operation_id -> branch_latest -> global_latest"`, and `replay_order="logical_time_ascending_after_anchor"`. It also includes `anchor_snapshot_id`, `effective_branch_id`, `anchor_entry_logical_time`, `replay_entry_count`, and `replay_step_count`.

Planner-only fields are intentionally absent from `/snapshots/replay`: `branch_recovery_signal`, `anchor_bias`, `recovery_continuity`, `policy_scope`, `planner_gate_scope`, and `dispatch_policy_scope`. `/planner/recovery/preview` remains the planner-aware endpoint and still exposes planner-only fields.

Anchor priority is unchanged: explicit `snapshot_id` wins, `operation_id` anchor behavior is unchanged, branch latest fallback is unchanged, and global latest fallback is unchanged. Replay ordering is unchanged. Snapshot schema, snapshot export flow, recovery task graph, planner preview behavior, API route code, and dashboard were not changed.

Verification passed: `py_compile`, consolidated smoke, and focused `/snapshots/replay` route/handler smoke. Focused smoke cleanup reported `cleanup_succeeded=true` and `temp_root_exists_after_cleanup=false`.
