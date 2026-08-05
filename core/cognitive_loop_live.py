# -*- coding: utf-8 -*-
from ai_os.cognitive_loop_compat import LegacyCognitiveLoopCompat


class CognitiveLoopLive(LegacyCognitiveLoopCompat):
    def __init__(self):
        super().__init__(label="Cognitive Loop Live", loop_delay=0.2)


def live_input(loop: CognitiveLoopLive):
    while loop.running:
        command = input("Введите команду (add_task/add_manager/add_worker/remove_manager/remove_worker/stop): ")
        if command.startswith("add_task "):
            _, task = command.split(" ", 1)
            loop.add_task(task)
        elif command.startswith("add_manager "):
            _, name = command.split(" ", 1)
            loop.add_manager(name)
        elif command.startswith("add_worker "):
            _, name = command.split(" ", 1)
            loop.add_worker(name)
        elif command.startswith("remove_manager "):
            _, name = command.split(" ", 1)
            loop.remove_manager(name)
        elif command.startswith("remove_worker "):
            _, name = command.split(" ", 1)
            loop.remove_worker(name)
        elif command == "stop":
            loop.stop()
            break
        else:
            print("Неизвестная команда")


if __name__ == "__main__":
    loop = CognitiveLoopLive()
    thread = loop.start()
    live_input(loop)
    thread.join(timeout=2)
    print("Cognitive Loop Live завершён")





