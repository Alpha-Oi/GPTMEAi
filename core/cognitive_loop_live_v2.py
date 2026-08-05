# -*- coding: utf-8 -*-
from ai_os.cognitive_loop_compat import LegacyCognitiveLoopCompat


class CognitiveLoopLiveV2(LegacyCognitiveLoopCompat):
    def __init__(self):
        super().__init__(label="Cognitive Loop Live V2", loop_delay=0.5)


if __name__ == "__main__":
    loop = CognitiveLoopLiveV2()
    loop.add_task("Проверка системы")
    loop.add_task("Анализ данных ядра")
    loop.add_task("Мониторинг состояния памяти")
    loop.add_task("Оптимизация алгоритмов")
    loop.add_task("Отчёт о работе агентов")
    loop.start().join(timeout=10)





