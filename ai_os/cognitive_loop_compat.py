"""Compatibility bridge from legacy cognitive-loop modules to the official agent runtime."""

from __future__ import annotations

import time
from queue import Queue
from threading import Thread

from agents.managers.manager_base import ManagerBase
from agents.workers.worker_base import WorkerBase
from ai_os.agent_runtime import AGENT_RUNTIME, AgentRuntime


DEFAULT_MANAGERS = ["Manager1", "Manager2"]
DEFAULT_WORKERS = ["Worker1", "Worker2", "Worker3"]
DEFAULT_TASKS = [
    "Проверка системы",
    "Анализ данных ядра",
    "Мониторинг состояния памяти",
    "Оптимизация алгоритмов",
    "Отчёт о работе агентов",
]


class LegacyCognitiveLoopCompat:
    def __init__(
        self,
        *,
        runtime: AgentRuntime | None = None,
        label: str = "Cognitive Loop",
        loop_delay: float = 0.2,
        bootstrap_defaults: bool = True,
    ) -> None:
        self.runtime = runtime or AGENT_RUNTIME
        self.label = label
        self.loop_delay = loop_delay
        self.running = True
        self.task_queue: Queue[str] = Queue()
        self.managers: list[ManagerBase] = []
        self.workers: list[WorkerBase] = []
        self._manager_index = 0
        self._worker_index = 0
        self._thread: Thread | None = None

        if bootstrap_defaults:
            for name in DEFAULT_MANAGERS:
                self.add_manager(name)
            for name in DEFAULT_WORKERS:
                self.add_worker(name)
            self._populate_tasks()
        else:
            self._sync_task_queue()

    def _populate_tasks(self) -> None:
        existing_titles = {task["title"] for task in self.runtime.list_tasks()}
        for task in DEFAULT_TASKS:
            if task not in existing_titles:
                self.add_task(task)
        self._sync_task_queue()

    def _sync_task_queue(self) -> None:
        queue = Queue()
        for title in self.get_tasks():
            queue.put(title)
        self.task_queue = queue

    def _next_manager(self) -> ManagerBase | None:
        if not self.managers:
            return None
        manager = self.managers[self._manager_index % len(self.managers)]
        self._manager_index += 1
        return manager

    def _next_worker(self) -> WorkerBase | None:
        if not self.workers:
            return None
        worker = self.workers[self._worker_index % len(self.workers)]
        self._worker_index += 1
        return worker

    def add_manager(self, name: str) -> ManagerBase:
        name = str(name).strip()
        if not name:
            raise ValueError("manager name is required")

        for manager in self.managers:
            if manager.name == name:
                return manager

        manager = ManagerBase(name)
        record = self.runtime.register_agent(
            name=name,
            role="manager",
            metadata={"source": "legacy_cognitive_loop", "label": self.label},
        )
        manager.agent_id = record["id"]
        self.runtime.heartbeat(manager.agent_id, "idle")
        self.managers.append(manager)
        print(f"[AGENT] Менеджер добавлен: {name}")
        return manager

    def remove_manager(self, name: str) -> None:
        removed = None
        keep = []
        for manager in self.managers:
            if manager.name == name and removed is None:
                removed = manager
            else:
                keep.append(manager)
        self.managers = keep

        if removed is not None:
            try:
                self.runtime.deregister_agent(removed.agent_id)
            except Exception:
                pass
            print(f"[AGENT] Менеджер удалён: {name}")

    def add_worker(self, name: str) -> WorkerBase:
        name = str(name).strip()
        if not name:
            raise ValueError("worker name is required")

        for worker in self.workers:
            if worker.name == name:
                return worker

        worker = WorkerBase(name)
        record = self.runtime.register_agent(
            name=name,
            role="worker",
            metadata={"source": "legacy_cognitive_loop", "label": self.label},
        )
        worker.agent_id = record["id"]
        self.runtime.heartbeat(worker.agent_id, "idle")
        self.workers.append(worker)
        print(f"[AGENT] Воркeр добавлен: {name}")
        return worker

    def remove_worker(self, name: str) -> None:
        removed = None
        keep = []
        for worker in self.workers:
            if worker.name == name and removed is None:
                removed = worker
            else:
                keep.append(worker)
        self.workers = keep

        if removed is not None:
            try:
                self.runtime.deregister_agent(removed.agent_id)
            except Exception:
                pass
            print(f"[AGENT] Воркeр удалён: {name}")

    def add_task(self, task: str) -> dict:
        task = str(task).strip()
        if not task:
            raise ValueError("task is required")

        record = self.runtime.queue_task(
            title=task,
            preferred_role="worker",
            metadata={"source": "legacy_cognitive_loop", "label": self.label},
        )
        self._sync_task_queue()
        print(f"[TASK] Новая задача добавлена: {task}")
        return record

    def get_tasks(self) -> list[str]:
        items = []
        for task in self.runtime.list_tasks():
            if task["status"] in {"queued", "in_progress"}:
                items.append(task["title"])
        return items

    @property
    def tasks(self) -> list[str]:
        return self.get_tasks()

    def status_snapshot(self) -> dict:
        return {
            "label": self.label,
            "running": self.running,
            "managers": [manager.name for manager in self.managers],
            "workers": [worker.name for worker in self.workers],
            "tasks_queue": self.get_tasks(),
        }

    def run_cycle(self) -> None:
        print(f"{self.label} запущен")
        self.running = True

        while self.running:
            manager = self._next_manager()
            worker = self._next_worker()
            if manager is None or worker is None:
                time.sleep(self.loop_delay)
                continue

            task = self.runtime.claim_next_task(worker.agent_id)
            self._sync_task_queue()
            if task is None:
                time.sleep(self.loop_delay)
                continue

            self.runtime.heartbeat(manager.agent_id, "busy")
            manager.run_task(task["title"])
            worker.execute(task["title"])
            self.runtime.complete_task(
                worker.agent_id,
                task["id"],
                result=f"Legacy loop '{self.label}' executed task via {worker.name} under {manager.name}",
            )
            self.runtime.heartbeat(manager.agent_id, "idle")
            self._sync_task_queue()
            time.sleep(self.loop_delay)

    def start(self) -> Thread:
        if self._thread and self._thread.is_alive():
            return self._thread

        self.running = True
        self._thread = Thread(target=self.run_cycle, daemon=True)
        self._thread.start()
        return self._thread

    def stop(self) -> None:
        self.running = False
        print(f"{self.label} остановлен")
