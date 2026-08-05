# PowerShell 7.5+
# Файл: update_gptmeai_v3_full.ps1
# Описание: Полное обновление GPTMEAi V3
#           - ai_kernel.py исправлен, шапка добавлена
#           - cognitive_loop_auto_scale.py исправлен, авто-остановка, JSON-лог
#           - проверка работы и наличие логов
# Автор: Crown Aliy
# Дата: 2026-03-11

$projectPath = "C:\Development GPTMEAi"

Write-Host "🔹 Обновление ai_kernel.py"
$aiKernelContent = @"
\"\"\"
Файл: ai_kernel.py
Описание: Основное ядро GPTMEAi. Инициализирует ядро, подключает супервизор и управляет памятью.
Автор: Crown Aliy
Дата: 2026-03-11
\"\"\"

import time
import json
from core.supervisor_bridge import SupervisorBridge

class GPTMEAiKernel:
    def __init__(self):
        self.supervisor = SupervisorBridge()
        self.memory_state = "stopped"

    def start(self):
        print("GPTMEAi Kernel starting...")
        self.supervisor.start()  # заменили connect() на актуальный метод
        self.memory_state = "running"
        print("Supervisor connected")
        self.save_status()
        print("Memory saved:", self.memory_state)

    def save_status(self):
        status = {
            "kernel_state": self.memory_state,
            "supervisor_status": "Supervisor connected",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        with open("gptmeai_status.json", "w", encoding="utf-8") as f:
            json.dump(status, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    kernel = GPTMEAiKernel()
    kernel.start()
"@

Set-Content -Path "$projectPath\core\ai_kernel.py" -Value $aiKernelContent -Encoding UTF8
Write-Host "✔ ai_kernel.py обновлён и сохранён"

Write-Host "🔹 Обновление cognitive_loop_auto_scale.py"
$cognitiveLoopContent = @"
\"\"\"
Файл: cognitive_loop_auto_scale.py
Описание: Auto-Scale Cognitive Loop. Автоматически создает менеджеров и воркеров,
          выполняет задачи и записывает JSON-лог для визуализатора.
          Включена авто-остановка после определенного времени.
Автор: Crown Aliy
Дата: 2026-03-11
\"\"\"

import time
import json
from datetime import datetime
from agents.managers.manager_base import ManagerBase
from agents.workers.worker_base import WorkerBase

AUTO_STOP_SECONDS = 300  # авто-остановка через 5 минут

class CognitiveLoopAutoScale:
    def __init__(self):
        self.managers = {}
        self.workers = {}
        self.tasks_executed = []

    def add_manager(self, name):
        if name not in self.managers:
            self.managers[name] = ManagerBase(name)
            print(f"[AUTO-SCALE] Добавлен менеджер: {name}")
        else:
            print(f"[AUTO-SCALE] Менеджер {name} уже существует")

    def add_worker(self, name):
        if name not in self.workers:
            self.workers[name] = WorkerBase(name)
            print(f"[AUTO-SCALE] Добавлен воркер: {name}")
        else:
            print(f"[AUTO-SCALE] Воркер {name} уже существует")

    def run_tasks(self):
        for manager in self.managers.values():
            task = manager.next_task()
            if task:
                for worker in self.workers.values():
                    worker.execute(task)
                self.tasks_executed.append(task)

    def save_json_log(self):
        log = {
            "timestamp": datetime.now().isoformat(),
            "managers": list(self.managers.keys()),
            "workers": list(self.workers.keys()),
            "tasks_executed": self.tasks_executed
        }
        with open("gptmeai_auto_scale_log.json", "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=4)
        print(f"[AUTO-SCALE] JSON-лог создан: gptmeai_auto_scale_log.json")

    def run(self):
        print("Cognitive Loop Auto-Scale запущен")
        start_time = time.time()
        while True:
            self.run_tasks()
            if time.time() - start_time > AUTO_STOP_SECONDS:
                print("[AUTO-SCALE] Время теста истекло, завершаем работу")
                break
            time.sleep(1)
        self.save_json_log()

if __name__ == "__main__":
    loop = CognitiveLoopAutoScale()
    loop.add_manager("Manager1")
    loop.add_manager("Manager2")
    loop.add_worker("Worker1")
    loop.add_worker("Worker2")
    loop.add_worker("Worker3")
    loop.run()
"@

Set-Content -Path "$projectPath\core\cognitive_loop_auto_scale.py" -Value $cognitiveLoopContent -Encoding UTF8
Write-Host "✔ cognitive_loop_auto_scale.py обновлён и сохранён"

Write-Host "🔹 Проверка работы JSON-логов"

# Проверяем создание логов ядра
if (Test-Path "$projectPath\gptmeai_status.json") {
    Write-Host "[CHECK] JSON лог ядра найден"
} else {
    Write-Warning "[WARNING] JSON лог ядра не найден"
}

# Проверяем создание логов Auto-Scale
if (Test-Path "$projectPath\gptmeai_auto_scale_log.json") {
    Write-Host "[CHECK] JSON лог Auto-Scale найден"
} else {
    Write-Warning "[WARNING] JSON лог Auto-Scale не найден"
}

Write-Host "✅ Скрипты обновлены и проверка завершена"