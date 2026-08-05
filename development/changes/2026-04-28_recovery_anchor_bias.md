# 2026-04-28 - Recovery anchor bias

## Что сделано

- `preview_recovery_plan_from_replay()` теперь поддерживает planner-level recovery anchor selection bias
- bias предпочитает fresh same-branch post-stabilization snapshot, если `branch_recovery_signal` meaningful, текущий anchor старше `branch health last_updated` и существует более свежий snapshot той же ветки
- поддерживаются terminal `branch_stabilization completed` и `branch_stabilization failed`
- `anchor_bias` возвращается и в `preview["anchor_bias"]`, и в `preview["context"]["anchor_bias"]`
- `/planner/recovery/preview` экспонирует `anchor_bias`, потому что route возвращает planner preview as-is

## Инварианты

- explicit `snapshot_id` остаётся authoritative и bypasses bias
- `no-signal` branch сохраняет прежнее поведение
- если fresh post-stabilization snapshot нет, сохраняется original anchor и unrelated snapshot не выбирается
- `operation_id` остаётся видимым в preview context

## Что намеренно не менялось

- `snapshot` schema
- snapshot export flow
- replay ordering
- recovery task graph
- API route code
- dashboard
- global `/snapshots/replay` behavior
