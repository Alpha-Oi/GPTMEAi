# 2026-04-28 - /memory/add Concept Core strict mode

- Added optional explicit strict Concept Core mode to `POST /memory/add`.
- Legacy `/memory/add` behavior remains unchanged: `{"text": "..."}` still calls `MemoryEngine.add(text)`, returns status code `201`, and preserves the `status/message/memory_count/item` response shape.
- Strict mode is used only when `payload["strict"] is True`; `payload["concept_core"]` must be a dict and is committed through `MemoryEngine.add_concept_node(...)`.
- Valid strict payloads store `MemoryNode.content` as `item.text` and the validated node under `metadata["concept_core"]`.
- Strict validation errors return `400 {"error": "..."}` and invalid strict requests do not write memory blocks.
- No global strict validation, memory schema migration, cognitive loop/runtime behavior change, or live runtime startup was introduced.
- Verification passed: expected RED route smoke before patch, `py_compile`, `smoke_concept_core.py`, `smoke_concept_core_memory.py --json --cleanup`, `smoke_memory_add_concept_route.py --json --cleanup`, and `smoke_stabilization_replay_continuity.py --json --cleanup`; project `GPTMemory_runtime.yaml` was unchanged during route smoke verification.
