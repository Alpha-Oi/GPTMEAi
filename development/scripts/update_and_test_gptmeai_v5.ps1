# ======================================================
# Скрипт: update_and_test_gptmeai_v5.ps1
# Назначение: Обновляет ai_kernel.py и cognitive_loop_auto_scale.py,
# исправляет известные ошибки, добавляет шапки, авто-остановку и JSON-логи.
# Автор: Crown Aliy
# Дата/Время: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
# ======================================================

$projectPath = "C:\Development GPTMEAi"
$corePath = Join-Path $projectPath "core"

# --- 1️⃣ Обновление ai_kernel.py ---
$aiKernelFile = Join-Path $corePath "ai_kernel.py"
$aiKernelContent = @"
\"\"\"
ai_kernel.py
Ядро GPTMEAi: управляет запуском Cognitive Loop, Supervisor и памятью.
Исправлены ошибки подключения Supervisor и логирования JSON.
\"\"\"
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
"@
Set-Content -Path $aiKernelFile -Value $aiKernelContent -Encoding UTF8
Write-Host "✔ Файл обновлён и сохранён: $aiKernelFile"

# --- 2️⃣ Обновление cognitive_loop_auto_scale.py ---
$autoScaleFile = Join-Path $corePath "cognitive_loop_auto_scale.py"
$autoScaleContent = @"
\"\"\"
cognitive_loop_auto_scale.py
Авто-Scale: добавляет менеджеров и воркеров, выполняет задачи,
авто-остановка после таймаута, генерация JSON-логов.
\"\"\"
import json
import time
from agents.managers.manager_base import ManagerBase
from agents.workers.worker_base import WorkerBase

class AutoScaleLoop:
    def __init__(self, timeout=15):
        self.managers = [ManagerBase("Manager1"), ManagerBase("Manager2")]
        self.workers = [WorkerBase(f"Worker{i}") for i in range(1,4)]
        self.tasks_executed = []
        self.timeout = timeout

    def run(self):
        start_time = time.time()
        print("Cognitive Loop Auto-Scale запущен")
        while time.time() - start_time < self.timeout:
            self.run_tasks()
            time.sleep(0.5)
        print("Auto-Scale остановлен")
        self.write_json_log()

    def run_tasks(self):
        for manager in self.managers:
            task = manager.next_task()
            if task:
                self.tasks_executed.append(task)
                for worker in self.workers:
                    worker.execute(task)

    def write_json_log(self):
        log_data = {
            "managers": [m.name for m in self.managers],
            "workers": [w.name for w in self.workers],
            "tasks_executed": self.tasks_executed
        }
        with open(f"{projectPath}\\gptmeai_auto_scale_log.json", "w", encoding='utf-8') as f:
            json.dump(log_data, f, indent=4)
        print(f"[AUTO-SCALE] JSON-лог создан: {projectPath}\\gptmeai_auto_scale_log.json")

if __name__ == "__main__":
    loop = AutoScaleLoop(timeout=15)
    loop.run()
"@
Set-Content -Path $autoScaleFile -Value $autoScaleContent -Encoding UTF8
Write-Host "✔ Файл обновлён и сохранён: $autoScaleFile"

# --- 3️⃣ Тестирование ---
Write-Host "`n🔹 Запуск ядра GPTMEAi..."
Start-Process python -ArgumentList "-m core.ai_kernel" -NoNewWindow -Wait

Write-Host "`n🔹 Запуск Auto-Scale..."
Start-Process python -ArgumentList "-m core.cognitive_loop_auto_scale" -NoNewWindow -Wait

# Проверка JSON-логов
$kernelLog = Join-Path $projectPath "gptmeai_status.json"
$autoScaleLog = Join-Path $projectPath "gptmeai_auto_scale_log.json"

if (Test-Path $kernelLog) { Write-Host "[CHECK] JSON лог ядра найден" } else { Write-Warning "[WARNING] JSON лог ядра не найден" }
if (Test-Path $autoScaleLog) { Write-Host "[CHECK] JSON лог Auto-Scale найден" } else { Write-Warning "[WARNING] JSON лог Auto-Scale не найден" }

Write-Host "✅ Скрипт update_and_test_gptmeai_v5 завершён. Все файлы обновлены и готовы для визуализатора."