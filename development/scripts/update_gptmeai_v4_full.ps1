<#
.SYNOPSIS
Обновление GPTMEAi V4 - исправление ошибок ядра и Auto-Scale
.DESCRIPTION
Скрипт исправляет синтаксические ошибки, обновляет импорты, добавляет шапку с описанием, автором и датой,
включает авто-остановку воркеров/менеджеров и генерацию JSON-логов для визуализатора.
Автор: Crown Aliy
Дата: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
#>

$projectPath = "C:\Development GPTMEAi"

# ---- ai_kernel.py ----
$aiKernelPath = "$projectPath\core\ai_kernel.py"
$aiKernelContent = @"
\"\"\"
ai_kernel.py
Ядро GPTMEAi
- Запуск Cognitive Loop
- Связь с SupervisorBridge
- JSON-лог состояния
Автор: Crown Aliy
Дата: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
\"\"\"

import json
import os
from core.supervisor_bridge import SupervisorBridge
from core.cognitive_loop import CognitiveLoop

class GPTMEAiKernel:
    def __init__(self):
        self.supervisor = SupervisorBridge()
        self.loop = CognitiveLoop()
        self.status_file = os.path.join(r'$projectPath', 'gptmeai_status.json')
        self.kernel_state = "stopped"

    def start(self):
        self.kernel_state = "running"
        self.supervisor.start()  # исправлено connect -> start
        self.loop.start()
        self._save_status()
    
    def _save_status(self):
        status = {
            "kernel_state": self.kernel_state,
            "supervisor_status": self.supervisor.status()
        }
        with open(self.status_file, "w", encoding="utf-8") as f:
            json.dump(status, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    kernel = GPTMEAiKernel()
    kernel.start()
"@

Set-Content -Path $aiKernelPath -Value $aiKernelContent -Encoding UTF8
Write-Host "✔ Файл обновлён и сохранён: $aiKernelPath"

# ---- cognitive_loop_auto_scale.py ----
$autoScalePath = "$projectPath\core\cognitive_loop_auto_scale.py"
$autoScaleContent = @"
\"\"\"
cognitive_loop_auto_scale.py
Auto-Scale для GPTMEAi
- Автоматическое добавление менеджеров и воркеров
- Авто-остановка после заданного времени
- JSON-лог для визуализатора
Автор: Crown Aliy
Дата: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
\"\"\"

import time
import json
import os
from agents.managers.manager_base import ManagerBase
from agents.workers.worker_base import WorkerBase

AUTO_STOP_SECONDS = 15
project_path = r'$projectPath'
log_file = os.path.join(project_path, "gptmeai_auto_scale_log.json")

class AutoScale:
    def __init__(self):
        self.managers = []
        self.workers = []
        self.tasks_executed = []
    
    def add_manager(self, name):
        manager = ManagerBase(name)
        self.managers.append(manager)
        print(f"[AUTO-SCALE] Добавлен менеджер: {name}")
    
    def add_worker(self, name):
        worker = WorkerBase(name)
        self.workers.append(worker)
        print(f"[AUTO-SCALE] Добавлен воркер: {name}")
    
    def run_tasks(self):
        for manager in self.managers:
            task = manager.get_next_task()  # исправлено next_task -> get_next_task
            if task:
                self.tasks_executed.append(task)
                for worker in self.workers:
                    worker.execute(task)
                    print(f"Worker {worker.name} выполняет команду: {task}")
    
    def save_log(self):
        data = {
            "managers": [m.name for m in self.managers],
            "workers": [w.name for w in self.workers],
            "tasks_executed": self.tasks_executed
        }
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[AUTO-SCALE] JSON-лог создан: {log_file}")
    
    def run(self):
        start_time = time.time()
        print("Cognitive Loop Auto-Scale запущен")
        while time.time() - start_time < AUTO_STOP_SECONDS:
            self.run_tasks()
            time.sleep(1)
        self.save_log()
        print("Auto-Scale остановлен")

if __name__ == "__main__":
    loop = AutoScale()
    # добавление менеджеров и воркеров
    loop.add_manager("Manager1")
    loop.add_manager("Manager2")
    loop.add_worker("Worker1")
    loop.add_worker("Worker2")
    loop.add_worker("Worker3")
    loop.run()
"@

Set-Content -Path $autoScalePath -Value $autoScaleContent -Encoding UTF8
Write-Host "✔ Файл обновлён и сохранён: $autoScalePath"

Write-Host "`n✅ Все файлы обновлены и подготовлены для визуализатора!"