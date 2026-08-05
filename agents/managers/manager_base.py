# -*- coding: utf-8 -*-
class ManagerBase:
    def __init__(self, name):
        self.name = name

    def perform_task(self, task):
        print(f"Manager {self.name} выполняет задачу: {task}")

    def run_task(self, task):
        # Backward-compatible alias used by the cognitive loop modules.
        self.perform_task(task)



