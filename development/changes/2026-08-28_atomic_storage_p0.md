# Crash-Safe Storage Layer (Storage P0)

Date: 2026-08-28

## Summary

The runtime persistence layer had no atomicity. Every state file is a JSON
document read whole and rewritten whole on each change with a bare
`Path.write_text(...)`. A process killed mid-write (disk full, power loss, OOM)
left a truncated file. The next load caught the `JSONDecodeError` and returned
an **empty** document; the following save then made that data loss permanent.
For `GPTMemory_runtime.yaml` this meant one bad write could silently erase
every memory block.

This change removes that failure mode. It does not migrate any storage format
(that is P1+ -- see below).

## What changed

New module `ai_os/atomic_store.py` (pure standard library, no project imports):

- `atomic_write_text` / `atomic_write_json` -- write a sibling `*.tmp` file,
  `flush()` + `os.fsync()`, rotate the current file into `<name>.bak` /
  `.bak2` / `.bak3`, then `os.replace()` (atomic on Windows and POSIX). A
  best-effort directory `fsync` follows on POSIX.
- `read_json_resilient` -- when the primary file is missing / empty / corrupt /
  wrong-type, walk the `.bak` chain. If nothing is recoverable it **raises**
  `StoreCorruptionError` by default instead of returning an empty document.
  Callers that must stay bootable pass `on_unrecoverable="default"` with
  `preserve_corrupt=True`, which renames the unreadable primary to
  `<name>.corrupt-<timestamp>` before falling back to defaults.
- `ensure_free_space` -- raises `OSError(ENOSPC)` before a large rewrite starts.
- `rotate_dir` -- caps ever-growing snapshot / export directories.

Rewired to use it:

| File | Change |
| --- | --- |
| `scripts/runtime_store.py` | `save_runtime` atomic; `load_runtime` recovers from `.bak` and **raises** rather than returning empty memory |
| `ai_os/agent_runtime.py` | `_save_state` atomic, `_load_state` resilient (`default` + `preserve_corrupt`) |
| `ai_os/cognitive_loop.py` | same |
| `planning/runtime.py` | same |
| `execution/ledger.py` | same |
| `execution/runtime.py` | same |
| `execution/snapshots.py` | same |
| `core/storage_engine.py` | export via atomic write + `rotate_dir` (keep 50) |
| `scripts/export_snapshot.py` | atomic snapshot write + `rotate_dir` (keep 50) |
| `scripts/api_server.py` | `/snapshot/export` atomic write + `rotate_dir` (keep 50) |
| `memory/vector_memory.py` | free-space guard + atomic write for the large embeddings file |
| `.gitignore` | ignore `*.bak[0-9]` and `*.corrupt-*` |

The control-plane stores (`storage/*.json`) use `on_unrecoverable="default"` so a
corrupt operational file does not brick startup -- the bad bytes are preserved
as `*.corrupt-<ts>` and the next (rotating) save starts a clean chain. Only
`GPTMemory_runtime.yaml` (user memory) is treated as raise-on-corruption: losing
it silently is worse than a loud failure that a human resolves.

## Verification

- `python development/scripts/smoke_atomic_store.py` -- 8/8 pass (atomic write +
  rotation, `.bak` recovery, raise-when-unrecoverable, default-on-fresh,
  preserve-corrupt, end-to-end `runtime_store` never-wipes, `rotate_dir`,
  free-space guard).
- Import check across all 13 touched modules -- clean.
- Save/load round-trip + corruption-recovery for all six state stores -- pass.
- `python -m ai_os.manifest` -- unchanged.
- `smoke_branch_playbook.py` -- `ok`. `smoke_stabilization_replay_continuity.py`
  -- runs. `smoke_recovery_workflow.py` / `smoke_recovery_remediation.py` report
  `error`, but they report the same on a clean checkout (pre-existing, unrelated
  to this change).

## Known limitations (out of scope here)

- **Concurrent writers.** `os.replace` makes every *reader* see a complete file,
  but multiple processes writing the same path still race (last writer wins).
  Real multi-process safety needs a lock or a database.
- **Rename window.** Rotation renames `path -> .bak` just before
  `os.replace(tmp, path)`. There is a sub-millisecond window with no primary
  file; `read_json_resilient` covers it via the `.bak` chain.
- After a successful `.bak` recovery the corrupt primary is left in place; the
  next save rotates it into a backup slot. Data is never lost, but one backup
  generation may briefly hold garbage.

## Not done (P1+, tracked for the next storage pass)

- `memory_blocks` + agent / planner / execution / ledger -> SQLite (WAL); stable
  primary keys; stop renumber-on-delete (`core/memory_engine.py`).
- Move `graph_relations` out of `GPTMemory_runtime.yaml` (derived data must not
  be able to clobber source blocks) -- `core/graph_engine.py`.
- Vector store: binary matrix (`.npy` / parquet) + `sqlite-vec` / faiss;
  incremental upsert instead of full re-embed -- `memory/vector_memory.py`.
- `search()` should use `memory/index/memory_index.json` or FTS5 instead of a
  per-query disk re-read + substring scan.
- Rotation for `stable_backup/` (written by non-canonical root scripts).
