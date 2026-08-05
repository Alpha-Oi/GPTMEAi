# 2026-04-28 - External runtime adoption

## What changed

- adopted `D:\GPTMEAi_venv_candidate\Scripts\python.exe` as the current official healthy interpreter path
- updated `AGENTS.md`, `README.md`, and `docs/developer/DEVELOPER_CONTEXT.md` to point at the external interpreter
- updated `run_ai_os.ps1` to use the external interpreter by default
- `run_ai_os.ps1` now allows explicit override through `GPTMEAI_PYTHON`
- `run_ai_os.ps1` fails clearly if the selected interpreter does not exist

## Safety posture

- current damaged `D:\Development GPTMEAi\venv` was not modified
- `D:\GPTMEAi_venv_candidate` was not moved, copied, deleted, or modified
- project-root `venv_new` remains a failed partial candidate and must not be promoted
- dependency mutation still requires explicit environment-repair scope

## Verification target

- external interpreter path exists
- external Python version is `3.14.x`
- external `pip --version` works
- third-party imports pass
- project imports pass
- `development/scripts/smoke_stabilization_replay_continuity.py --json --cleanup` passes
- `run_ai_os.ps1` parse-check passes without starting the runtime server
