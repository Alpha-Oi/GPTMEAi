# ====================================================
# Скрипт: update_gptmeai_v2_full.ps1
# Описание: Обновляет ядро AIKernel и Cognitive Loop Auto-Scale.
#            Добавляет JSON-логи для визуализатора.
# Дата обновления: 11.03.2026
# Автор: Crown Aliy
# ====================================================

$projectPath = "C:\Development GPTMEAi"

# ----------------------------
# Обновление ai_kernel.py
# ----------------------------
$aiKernelPath = Join-Path $projectPath "core\ai_kernel.py"

$aiKernelContent = @'
"""
Файл: ai_kernel.py
Описание: Основное ядро GPTMEAi. Инициализирует память, подключает супервайзер и запускает Cognitive Loop.
Дата обновления: 11.03.2026
Автор: Crown Aliy
"""

import os
import json
from core.supervisor_bridge import SupervisorBridge
from memory.vector_store import VectorStore

class AIKernel:
    def __init__(self):
        self.state = "initializing"
        self.memory = VectorStore()
        self.supervisor = SupervisorBridge()
        self.json_log_path = "gptmeai_status.json"

    def start(self):
        print("GPTMEAi Kernel starting...")
        print(self.supervisor.status())
        self.state = "running"
        self._save_memory()
        self._write_json_log()
        print("Memory saved:", self.memory.load("system_status"))

    def _save_memory(self):
        try:
            self.memory.save("system_status", self.state)
        except Exception as e:
            print(f"[ERROR] Ошибка при сохранении памяти: {e}")

    def _write_json_log(self):
        log_data = {
            "kernel_state": self.state,
            "supervisor_status": self.supervisor.status()
        }
        try:
            with open(self.json_log_path, "w", encoding="utf-8") as f:
                json.dump(log_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ERROR] Не удалось записать JSON-лог: {e}")

    def status(self):
        return self.state

if __name__ == "__main__":
    kernel = AIKernel()
    kernel.start()
'@

Set-Content -Path $aiKernelPath -Value $aiKernelContent -Encoding UTF8
Write-Host "✔ ai_kernel.py обновлён и сохранён"

# ----------------------------
# Обновление cognitive_loop_auto_scale.py
# ----------------------------
$autoScalePath = Join-Path $projectPath "core\cognitive_loop_auto_scale.py"

$autoScaleContent = @'
"""
Файл: cognitive_loop_auto_scale.py
Описание: Cognitive Loop Auto-Scale. Автоматически добавляет менеджеров и воркеров, логирует задачи в JSON.
Дата обновления: 11.03.2026
Автор: Crown Aliy
"""

import json
import time
from agents.managers.manager_base import ManagerBase
from agents.workers.worker_base import WorkerBase

class AutoScale:
    def __init__(self, max_runtime_sec=60):
        self.managers = []
        self.workers = []
        self.json_log_path = "gptmeai_auto_scale_log.json"
        self.start_time = time.time()
        self.max_runtime_sec = max_runtime_sec

    def add_manager(self, name):
        try:
            manager = ManagerBase(name)
            self.managers.append(manager)
            print(f"[AUTO-SCALE] Менеджер добавлен: {name}")
        except Exception as e:
            print(f"[ERROR] Не удалось добавить менеджера {name}: {e}")

    def add_worker(self, name):
        try:
            worker = WorkerBase(name)
            self.workers.append(worker)
            print(f"[AUTO-SCALE] Воркeр добавлен: {name}")
        except Exception as e:
            print(f"[ERROR] Не удалось добавить воркера {name}: {e}")

    def run(self):
        print("Cognitive Loop Auto-Scale запущен")
        while time.time() - self.start_time < self.max_runtime_sec:
            for manager in self.managers:
                for task in manager.get_tasks():
                    print(f"Manager {manager.name} выполняет задачу: {task}")
                    for worker in self.workers:
                        print(f"Worker {worker.name} выполняет команду: {task}")
            time.sleep(1)
        self._write_json_log()
        print("Auto-Scale завершён после max_runtime_sec")

    def _write_json_log(self):
        data = {
            "managers": [m.name for m in self.managers],
            "workers": [w.name for w in self.workers],
            "runtime_sec": int(time.time() - self.start_time)
        }
        try:
            with open(self.json_log_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ERROR] Не удалось записать JSON-лог: {e}")

if __name__ == "__main__":
    loop = AutoScale(max_runtime_sec=30)
    loop.add_manager("Manager1")
    loop.add_manager("Manager2")
    loop.add_worker("Worker1")
    loop.add_worker("Worker2")
    loop.add_worker("Worker3")
    loop.run()
'@

Set-Content -Path $autoScalePath -Value $autoScaleContent -Encoding UTF8
Write-Host "✔ cognitive_loop_auto_scale.py обновлён и сохранён"

# ----------------------------
# Проверка JSON-логов
# ----------------------------
Write-Host "🔹 Проверка работы Auto-Scale и JSON-логов"
if (!(Test-Path "$projectPath\gptmeai_status.json")) { Write-Host "[WARNING] JSON лог ядра не найден" } else { Write-Host "[OK] JSON лог ядра найден" }
if (!(Test-Path "$projectPath\gptmeai_auto_scale_log.json")) { Write-Host "[WARNING] JSON лог Auto-Scale не найден" } else { Write-Host "[OK] JSON лог Auto-Scale найден" }

Write-Host "✅ Скрипты обновлены и проверка завершена"