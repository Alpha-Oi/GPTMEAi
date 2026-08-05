# 2026-04-28 - Optional strict Concept Core memory commit path

Added optional strict Concept Core memory commit support through `MemoryEngine.add_concept_node(payload: dict, *, tags=None, importance=None)`.

Existing `MemoryEngine.add(text, ...)` behavior remains unchanged, and `/memory/add` remains unchanged and is not globally strict-validated. `add_concept_node()` validates payloads through `MemoryCommitValidator`, maps valid `MemoryNode.content` into the legacy memory block `text`, and stores the validated Concept Core payload under `metadata["concept_core"] = MemoryNode.to_dict()`.

Invalid strict payloads are rejected before writing. Legacy memory block shape remains compatible. Verification used temp runtime state and confirmed project `GPTMemory_runtime.yaml` was untouched. No API routes, schemas, cognitive loop behavior, runtime behavior, or storage schema were changed.

Verification passed: expected RED check before implementation (`MemoryEngine` had no `add_concept_node`), `py_compile`, `smoke_concept_core.py`, `smoke_concept_core_memory.py --json --cleanup`, and `smoke_stabilization_replay_continuity.py --json --cleanup`.

Route-level `/memory/add` integration remains a separate read-only design slice.
