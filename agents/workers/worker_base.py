# -*- coding: utf-8 -*-
# --------------------------------------------
# Скрипт: worker_base.py
# Назначение: [КОРОТКОЕ ОПИСАНИЕ ФАЙЛА, УКАЖИ ЧТО ДЕЛАЕТ]
# Автор: Crown Aliy
# Дата создания/обновления: 2026-03-12 18:32:21
# --------------------------------------------
class WorkerBase:
    def __init__(self, name):
        self.name = name

    def execute(self, command):
        print(f'Worker {self.name} выполняет команду: {command}')





