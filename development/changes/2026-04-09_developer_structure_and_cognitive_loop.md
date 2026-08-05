# 2026-04-09 Developer Structure And Cognitive Loop

## Что изменено

- добавлен официальный `Cognitive Loop` в [`ai_os/cognitive_loop.py`](/D:/Development%20GPTMEAi/ai_os/cognitive_loop.py)
- добавлены API endpoints для cognitive loop в [`scripts/api_server.py`](/D:/Development%20GPTMEAi/scripts/api_server.py)
- dashboard расширен управлением и статусом cognitive loop в [`dashboard/index.html`](/D:/Development%20GPTMEAi/dashboard/index.html)
- создана developer-документация в [`docs/developer/`](/D:/Development%20GPTMEAi/docs/developer)
- создана рабочая папка разработки [`development/`](/D:/Development%20GPTMEAi/development)
- `README`, `manifest` и `config` обновлены под новую структуру
- инварианты дополнены правилами developer-context и чистого корня

## Зачем

Чтобы проект развивался не только как код, но и как поддерживаемая инженерная система:

- новый разработчик должен быстро понимать идею и структуру
- серьёзные изменения должны оставлять документированный след
- временная активность должна уходить из корня проекта в отдельное рабочее пространство

## Что это даёт

- появляется канонический onboarding-файл для разработчика
- появляется официальный процесс фиксации серьёзных изменений
- появляется структура для постепенной очистки корня проекта
- cognitive loop становится частью официальной AI OS архитектуры

## Затронутые файлы

- [`ai_os/cognitive_loop.py`](/D:/Development%20GPTMEAi/ai_os/cognitive_loop.py)
- [`ai_os/config.py`](/D:/Development%20GPTMEAi/ai_os/config.py)
- [`ai_os/manifest.py`](/D:/Development%20GPTMEAi/ai_os/manifest.py)
- [`scripts/api_server.py`](/D:/Development%20GPTMEAi/scripts/api_server.py)
- [`dashboard/index.html`](/D:/Development%20GPTMEAi/dashboard/index.html)
- [`README.md`](/D:/Development%20GPTMEAi/README.md)
- [`AI_OS_DEVELOPMENT_INVARIANTS.md`](/D:/Development%20GPTMEAi/AI_OS_DEVELOPMENT_INVARIANTS.md)

## Что дальше

1. Выделить официальный execution layer.
2. Начать постепенный вынос временных root-скриптов в `development/scripts/`.
3. Решить, какие root-логи и diagnostic artifacts можно безопасно мигрировать в `development/logs/`.
