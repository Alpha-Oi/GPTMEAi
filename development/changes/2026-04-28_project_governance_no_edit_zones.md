# 2026-04-28 - Project governance no-edit zones

Read-only governance check confirmed `D:\Development GPTMEAi` as the active project root, with no confirmed `.git` root and no root `.gitignore` found. Until VCS/source-of-truth cleanup is explicitly approved, `development/changes/` remains the manual change ledger.

`venv_new/` is a failed partial environment candidate and must not be promoted. `D:\GPTMEAi_venv_candidate` is the adopted external runtime environment and must not be casually edited, formatted, lint-fixed, header-injected, deleted, moved, or repaired unless the task explicitly targets environment repair.

`.gitignore` design is intentionally postponed to a separate source-of-truth/VCS slice. Root script classification is also intentionally postponed.
