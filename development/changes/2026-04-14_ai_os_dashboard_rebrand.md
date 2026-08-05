# 2026-04-14 - AI OS dashboard rebrand and shell refresh

## Что изменено

- В [`dashboard/index.html`](/D:/Development%20GPTMEAi/dashboard/index.html) обновлён visual shell dashboard:
  - `GPTMemory Dashboard` переименован в `AI OS Control Plane`
  - sidebar получила identity-блок `Persistent AI Mind System`
  - добавлена правая workspace-area с явной операторской зоной
  - улучшены фон, типографика, spacing, hover-depth и mobile layout
- В [`scripts/api_server.py`](/D:/Development%20GPTMEAi/scripts/api_server.py) health service теперь возвращает `AI OS API` вместо legacy-названия.

## Зачем

После появления recovery demo и branch-health визуализации интерфейс уже перестал быть чисто технической заглушкой. Было важно привести branding и shell dashboard в соответствие реальной архитектуре AI OS, чтобы control plane воспринимался как часть системы, а не как старый `GPTMemory` экран.

## Результат

- интерфейс теперь визуально соответствует AI OS
- recovery / planner / execution смотрятся как части одной операционной панели
- legacy-branding уменьшен без изменения runtime-логики
