# 2026-04-13 Recovery Plan Preview And Replay Steps

## Что изменено

Углублена official recovery-ветка planner runtime:

- [`planning/runtime.py`](/D:/Development%20GPTMEAi/planning/runtime.py)
- [`scripts/api_server.py`](/D:/Development%20GPTMEAi/scripts/api_server.py)
- [`dashboard/index.html`](/D:/Development%20GPTMEAi/dashboard/index.html)

Также обновлены:

- [`README.md`](/D:/Development%20GPTMEAi/README.md)
- [`docs/developer/DEVELOPER_CONTEXT.md`](/D:/Development%20GPTMEAi/docs/developer/DEVELOPER_CONTEXT.md)
- [`AI_OS_LAYER_TECHNICAL_SPEC.md`](/D:/Development%20GPTMEAi/AI_OS_LAYER_TECHNICAL_SPEC.md)

## Что теперь умеет система

- строить `recovery preview` без создания persistent плана
- отдавать preview через `GET /planner/recovery/preview`
- разворачивать replay-gap не в один общий шаг, а в последовательные replay steps по конкретным `snapshot lineage / operation ledger` entries
- ограничивать detail recovery через `max_replay_steps`
- сохранять в recovery plan контекст:
  - `recovery_mode`
  - `planned_replay_step_count`
  - `replay_entries_preview`
  - `recovery_alignment_only`

## Почему это важно

Это делает recovery layer более инженерным и менее абстрактным:

- recovery можно сначала inspect-ить, а потом создавать
- replay идёт по трассе состояний, а не по общей формулировке
- planner получает более конкретную branch/time основу для будущего nonlinear recovery workflow

## Проверка

- AST и import-check прошли для:
  - [`planning/runtime.py`](/D:/Development%20GPTMEAi/planning/runtime.py)
  - [`scripts/api_server.py`](/D:/Development%20GPTMEAi/scripts/api_server.py)
- isolated smoke test подтвердил:
  - preview service возвращает `AI OS Recovery Plan Preview`
  - replay-gap из 3 записей режется до `planned_replay_step_count = 2` при `max_replay_steps=2`
  - created recovery plan содержит 5 шагов:
    - coordination
    - anchor review
    - replay step 1
    - replay step 2
    - validation
  - первый dispatch по плану ставит в очередь только coordination step

## Что дальше

1. Развивать recovery workflow от replay-aware planning к более формальному replay execution.
2. Связать replay steps с richer capability semantics и recovery policies.
3. Расширять branch/time model без потери inspectable control plane.
