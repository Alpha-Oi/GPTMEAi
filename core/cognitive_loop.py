# -*- coding: utf-8 -*-
from threading import Thread
import time

from ai_os.cognitive_loop_compat import LegacyCognitiveLoopCompat


class CognitiveLoop(LegacyCognitiveLoopCompat):
    def __init__(self):
        super().__init__(label="Cognitive Loop", loop_delay=0.5)


if __name__ == "__main__":
    loop = CognitiveLoop()
    thread = Thread(target=loop.run_cycle, daemon=True)
    thread.start()

    time.sleep(2)
    loop.add_task("Обновление базы данных")
    loop.add_task("Анализ логов")
    loop.add_manager("Manager3")
    loop.add_worker("Worker4")

    time.sleep(5)
    loop.stop()
    thread.join(timeout=2)





