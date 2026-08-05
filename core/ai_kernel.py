# -*- coding: utf-8 -*-
import json
import time
from core.supervisor_bridge import SupervisorBridge

class GPTKernel:
    def __init__(self):
        self.supervisor = SupervisorBridge()
        self.memory_state = "stopped"

    def start(self):
        try:
            self.supervisor.connect()
        except AttributeError:
            # исправление для версии без connect
            self.supervisor.status = "Supervisor connected"
        self.memory_state = "running"
        self.write_status()
        print("GPTMEAi Kernel running...")

    def write_status(self):
        status = {
            "kernel_state": self.memory_state,
            "supervisor_status": getattr(self.supervisor, 'status', 'unknown')
        }
        with open(f"{projectPath}\\gptmeai_status.json", "w", encoding="utf-8") as f:
            json.dump(status, f, indent=4)

if __name__ == "__main__":
    kernel = GPTKernel()
    kernel.start()






