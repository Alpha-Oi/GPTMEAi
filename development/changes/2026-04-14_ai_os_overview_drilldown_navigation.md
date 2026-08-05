# 2026-04-14 - AI OS overview drill-down navigation

## Что изменено

- В [`dashboard/index.html`](/D:/Development%20GPTMEAi/dashboard/index.html) добавлены quick actions в верхней части `AI OS Overview`.
- Внутри overview-панелей добавлены action-кнопки:
  - `Open health`
  - `Open planner`
  - `Open recovery`
  - `Open branches`
  - `Open execution`
- Добавлены стили `panelHeader`, `panelHeaderActions`, `miniButton`, чтобы overview стал полноценным навигационным слоем, а не только read-only summary.

## Зачем

После появления overview dashboard уже давал хороший операторский срез, но переход к detail-экранам всё ещё требовал лишнего движения по sidebar. Drill-down navigation делает workspace более быстрым и естественным для повседневной работы оператора.

## Результат

- overview теперь служит реальным входом в control plane
- detail views открываются напрямую из summary-контекста
- navigation pressure на sidebar уменьшена
