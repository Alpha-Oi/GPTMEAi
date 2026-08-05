# 2026-04-28 - Snapshot coverage freshness bridge

## Что сделано

- Cognitive Loop теперь сам выявляет stale или missing snapshot coverage для веток с stabilization-derived planner branch health signal
- ветка требует snapshot coverage, если `status` равен `observe` или `degraded`, либо `recommendation` равен `heightened_monitoring` или `manual_review`, и при этом latest branch snapshot отсутствует или старше `branch health last_updated`
- `completed stabilization + stale snapshot`, `failed stabilization + stale snapshot` и `completed stabilization + missing snapshot` теперь флагуются
- `completed stabilization + fresh snapshot after stabilization` и `no-signal branch` не флагуются
- используется уже существующий шаг `capture_snapshot_coverage`

## Что намеренно не менялось

- snapshot creation flow
- snapshot lineage schema
- replay ordering
- replay anchor selection
- recovery graph
- API routes
- dashboard

## Инженерный смысл

Это bridge только для snapshot coverage freshness между planner branch health и cognitive-loop snapshot coverage behavior. Он не меняет replay anchor selection и не мутирует snapshot runtime model сам по себе.
