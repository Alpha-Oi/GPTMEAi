# 2026-04-14 - AI OS overview dashboard

## Что изменено

- В [`dashboard/index.html`](/D:/Development%20GPTMEAi/dashboard/index.html) добавлен новый стартовый экран `AI OS Overview`.
- Dashboard теперь по умолчанию загружает агрегированный операторский срез через `loadOverview()`, а не просто raw `/health`.
- Overview собирает данные из:
  - `/health`
  - `/planner/status`
  - `/planner/branch-health`
  - `/planner/recovery/workflows`
  - `/execution/status`
  - `/agents/status`
  - `/memory/corpus/status`
- В sidebar добавлена отдельная кнопка `Overview`.

## Зачем

После появления recovery demo и rebrand dashboard уже показывал отдельные detail-экраны, но не давал одного ясного операторского входа в систему. Новый overview делает control plane более пригодным для повседневой работы: оператор сразу видит planner pressure, branch state, recovery focus, memory corpus и recent execution.

## Результат

- dashboard теперь открывается как полноценный operator-home
- основные сигналы AI OS видны без перехода по отдельным кнопкам
- detail-экраны при этом сохранены как drill-down режимы
