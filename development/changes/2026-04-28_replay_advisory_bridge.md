# 2026-04-28 - Replay advisory bridge

## Что сделано

- `preview_recovery_plan_from_replay()` теперь возвращает stabilization-derived `branch_recovery_signal`
- сигнал добавляется и в `preview["branch_recovery_signal"]`, и в `preview["context"]["branch_recovery_signal"]`
- terminal `branch_stabilization completed` теперь даёт replay advisory `observe / heightened_monitoring / heightened_monitoring_during_replay`
- terminal `branch_stabilization failed` теперь даёт replay advisory `degraded / manual_review / manual_review_before_replay`
- ветки без branch health / stabilization signal сохраняют прежнее replay preview поведение и не получают meaningful `branch_recovery_signal`

## Что намеренно не менялось

- schema `snapshot lineage`
- snapshot creation flow
- replay ordering
- recovery orchestration
- API routes
- dashboard

## Инженерный смысл

Это advisory bridge только для replay preview continuity между planner branch health и recovery preview. Он не мутирует snapshot coverage и не меняет snapshot lineage runtime model.
