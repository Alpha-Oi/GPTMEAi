# 2026-04-28 - Failed stabilization policy scope clarification

## Что уточнено

- `branch` summary `planner_gate` и `dispatch_policy` следует читать как branch-wide operational control surfaces
- `branch_recovery_signal` и replay preview `dispatch_policy_mode` следует читать как recovery-scoped advisory surfaces
- failed `branch_stabilization` намеренно замораживает ordinary operational work строже, чем ограничивает recovery/replay preview
- operational dispatch может перейти в `blocked`, чтобы не пускать новую normal branch work
- recovery preview при этом может оставаться `restricted` / `manual_review_before_replay`, потому что `recovery`, `remediation` и `branch_stabilization` пути всё ещё допустимы как controlled review-first flows

## Статус

- это accepted behavior, а не подтверждённый runtime bug
- optional future clarity slice может добавить явные scoped field names вроде `policy_scope="recovery"` или отдельные operational/recovery policy labels, но сейчас code change не нужен
- existing consolidated smoke уже покрывает текущее поведение
