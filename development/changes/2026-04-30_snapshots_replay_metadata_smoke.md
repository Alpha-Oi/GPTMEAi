# 2026-04-30 - Durable `/snapshots/replay` replay metadata smoke

Added durable focused smoke `development/scripts/smoke_snapshots_replay_metadata.py` for raw `/snapshots/replay` `replay_metadata` behavior. Production code was not changed.

The smoke verifies that `/snapshots/replay` returns `replay_metadata`, keeps planner-only fields absent from raw replay, preserves explicit `snapshot_id`, `operation_id` anchor behavior, branch latest fallback, global latest fallback, and replay entry/step ordering, and confirms `/planner/recovery/preview` still exposes planner fields separately.

Verification passed with the official interpreter: `py_compile`, `development/scripts/smoke_snapshots_replay_metadata.py --json --cleanup`, and `development/scripts/smoke_stabilization_replay_continuity.py --json --cleanup`. The initial `py_compile` attempt needed an elevated rerun because Windows denied `__pycache__` update access; prefer a `pycache_prefix` approach for future checks when possible.
