# AGENTS.md

## Project Identity

- Project root: `D:\Development GPTMEAi`
- Project: `GPTMEAi / GPTMemory Ai-OS / AI OS Control Plane`
- This project is not `GPTMemory Studio`.
- This file is the local operational contract for work inside this project root.

## Source-Of-Truth Order

When instructions conflict or the project is ambiguous, use this order:

1. Direct user instruction
2. `AGENTS.md`
3. `ai_os/manifest.py`
4. `README.md`
5. `docs/developer/DEVELOPER_CONTEXT.md`
6. `AI_OS_DEVELOPMENT_INVARIANTS.md`
7. `AI_OS_LAYER_TECHNICAL_SPEC.md`
8. `development/changes/`

## Current Repository Status

- No confirmed `.git` root.
- Do not assume branch, commit, diff, or `git status` workflow.
- Do not assume PR, branch naming, or commit-based recovery workflow exists in this workspace.

## Current Environment Warning

- Current warning: `venv pip` may be broken.
- Current venv damage appears broader than pip: third-party site-packages may also contain corrupted injected headers.
- Current official healthy interpreter: `D:\GPTMEAi_venv_candidate\Scripts\python.exe`.
- The project-local `D:\Development GPTMEAi\venv` is a damaged no-edit artifact, not the current official runtime interpreter.
- The project-local `D:\Development GPTMEAi\venv_new` is a failed partial environment candidate and must not be promoted.
- The external `D:\GPTMEAi_venv_candidate` is the adopted official runtime environment and must not be casually modified.
- Do not run package install/update commands until `pip` health is explicitly verified or repaired.
- Do not edit, format, header-inject, lint-fix, rewrite, or patch files inside `venv/`.
- Do not edit, format, header-inject, lint-fix, rewrite, patch, delete, move, or repair files inside `venv_new/` or `D:\GPTMEAi_venv_candidate\` unless the task explicitly targets environment repair.
- Do not repair `venv/` unless the task explicitly targets environment repair.
- Dependency mutation still requires explicit environment-repair scope.
- Prefer side-by-side replacement venv repair planning over in-place mutation.
- Prefer existing project runtime commands with the official healthy interpreter over environment mutation.

## Official Runtime

Use the adopted external healthy interpreter first:

- `D:\GPTMEAi_venv_candidate\Scripts\python.exe .\run_ai_os.py`
- `D:\GPTMEAi_venv_candidate\Scripts\python.exe -m ai_os`

Fallback only with explicit approval if the external interpreter is unavailable:

- `python .\run_ai_os.py`
- `python -m ai_os`

Useful read-only runtime inspection:

- `D:\GPTMEAi_venv_candidate\Scripts\python.exe -m ai_os.manifest`

Dashboard and primary endpoints:

- `http://127.0.0.1:8010/dashboard`
- `/health`
- `/planner/status`
- `/planner/branch-health`
- `/planner/playbooks`
- `/planner/recovery/workflows`
- `/execution/status`
- `/execution/ledger`
- `/snapshot/latest`
- `/snapshots/lineage`
- `/snapshots/replay`

## Canonical Project Areas

Primary code and control-plane surface:

- `ai_os/`
- `planning/`
- `execution/`
- `core/`
- `scripts/api_server.py`
- `dashboard/`

Primary docs and developer guidance:

- `README.md`
- `docs/developer/DEVELOPER_CONTEXT.md`
- `AI_OS_DEVELOPMENT_INVARIANTS.md`
- `AI_OS_LAYER_TECHNICAL_SPEC.md`
- `development/changes/`

Project-local development workspace:

- `development/scripts/`
- `development/logs/`
- `development/tmp/`

## Editable Zones

Unless the task says otherwise, edits should be limited to:

- `ai_os/`
- `planning/`
- `execution/`
- `core/`
- `scripts/api_server.py`
- `dashboard/`
- `docs/developer/`
- `development/scripts/`
- `development/changes/`
- this root `AGENTS.md`

## No-Edit Zones Without Explicit Task Scope

Do not delete, move, rewrite, or mass-clean these paths unless the task explicitly targets migration, recovery, archival cleanup, or data repair:

- `backups/`
- `backup_python_files/`
- `stable_backup/`
- `smart_trash/`
- `legacy/`
- `venv/`
- `venv/Lib/site-packages/`
- `venv_new/`
- `D:\GPTMEAi_venv_candidate\`
- `GPTMemoryEngine/`
- `.gptcollector/`
- `logs/`
- `runtime/`
- `storage/`
- `GPTMemory_runtime.yaml`
- `memory/chats/`
- `memory/parsed/`
- `memory/knowledge/`
- `memory/embeddings/`
- `development/tmp/`

## Working Rules

- Confirm the active task scope before editing files.
- Do not mix feature work with broad cleanup unless explicitly requested.
- Do not assume archived or legacy code is safe to modernize in passing.
- Prefer PowerShell-compatible commands and explicit Windows paths.
- Prefer the adopted external healthy interpreter over PATH Python.
- Do not assume packaging metadata exists; verify before using any package-manager workflow.
- Do not expose secrets from `.env`.

## Virtual Environment Safety

- Treat `venv/` as generated/runtime environment, not project source.
- Treat `venv_new/` as a failed partial environment candidate, not project source.
- Treat `D:\GPTMEAi_venv_candidate\` as the protected adopted external runtime environment.
- Never include `venv/`, `venv_new/`, or `D:\GPTMEAi_venv_candidate\` in broad code cleanup, formatting, lint, header injection, search-and-replace, or patch scripts.
- Dependency mutation is blocked until an approved environment repair plan exists.

## Verification Rules

After code or config changes:

1. Run the narrowest meaningful verification first.
2. Then run the broader project-local check relevant to the area changed.
3. For runtime or API changes, verify at least the affected endpoint plus relevant status surfaces such as `/health`, `/planner/status`, and `/execution/status`.
4. Prefer project-local smoke scripts when relevant:
   - `development/scripts/smoke_recovery_workflow.py`
   - `development/scripts/smoke_recovery_remediation.py`
   - `development/scripts/smoke_branch_playbook.py`
   - `development/scripts/smoke_stabilization_replay_continuity.py`
   - `development/scripts/seed_recovery_demo.py`
5. If verification cannot run, state exactly why.

## Documentation Rules

- If runtime meaning, architecture, or canonical structure changes, update `docs/developer/DEVELOPER_CONTEXT.md`.
- After serious changes, add a note under `development/changes/`.
- Keep root cleanup deliberate and incremental; do not rewrite history to make the tree look clean.

## Windows And Temp-File Safety

- Do not aggressively delete `development/tmp/`.
- Assume Windows may keep file handles open on temporary artifacts.
- If cleanup is required, prefer targeted and reversible cleanup over bulk deletion.
