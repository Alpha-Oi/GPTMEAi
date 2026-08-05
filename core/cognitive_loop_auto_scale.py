# -*- coding: utf-8 -*-
import time

from ai_os.cognitive_loop_compat import LegacyCognitiveLoopCompat


class AutoScaleLoop(LegacyCognitiveLoopCompat):
    def __init__(self, timeout=15):
        super().__init__(label="Cognitive Loop Auto-Scale", loop_delay=0.5)
        self.timeout = timeout

    def run(self):
        thread = self.start()
        start_time = time.time()
        print("Cognitive Loop Auto-Scale запущен")
        while time.time() - start_time < self.timeout:
            time.sleep(0.5)
        self.stop()
        thread.join(timeout=2)
        print("Auto-Scale остановлен")


if __name__ == "__main__":
    loop = AutoScaleLoop(timeout=15)
    loop.run()






