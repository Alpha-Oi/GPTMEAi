# -*- coding: utf-8 -*-
# --------------------------------------------
# Скрипт: supervisor_bridge.py
# Назначение: [КОРОТКОЕ ОПИСАНИЕ ФАЙЛА, УКАЖИ ЧТО ДЕЛАЕТ]
# Автор: Crown Aliy
# Дата создания/обновления: 2026-03-12 18:32:23
# --------------------------------------------
import subprocess

class SupervisorBridge:

    def __init__(self):
        self.supervisor_script = 'gptmeai_supervisor.ps1'

    def restart_supervisor(self):
        subprocess.run(
            ['powershell', '-ExecutionPolicy', 'Bypass', '-File', self.supervisor_script]
        )

    def status(self):
        return 'Supervisor connected'






