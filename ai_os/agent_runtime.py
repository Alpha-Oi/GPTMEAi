"""Minimal agent runtime for the official AI OS control plane."""

from __future__ import annotations

import json
from collections import Counter, deque
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, UTC
from pathlib import Path
from threading import RLock

from ai_os.config import get_project_paths
from ai_os.role_policy import build_dispatch_plan, dispatch_policy_for_task, evaluate_task_dispatch, rank_tasks_for_agent
from execution.contracts import build_execution_fields
from execution.runtime import EXECUTION_RUNTIME


VALID_AGENT_ROLES = {"manager", "worker"}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def normalize_agent_id(role: str, name: str) -> str:
    safe_name = "".join(ch.lower() if ch.isalnum() else "-" for ch in name.strip())
    while "--" in safe_name:
        safe_name = safe_name.replace("--", "-")
    safe_name = safe_name.strip("-") or "agent"
    return f"{role}:{safe_name}"


@dataclass
class AgentRecord:
    id: str
    name: str
    role: str
    status: str = "idle"
    capabilities: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    current_task_id: int | None = None
    tasks_completed: int = 0
    tasks_failed: int = 0
    tasks_claimed: int = 0
    last_assigned_at: str | None = None
    last_heartbeat: str = field(default_factory=utc_now)


@dataclass
class TaskRecord:
    id: int
    title: str
    preferred_role: str | None = None
    metadata: dict = field(default_factory=dict)
    operation_id: str | None = None
    execution_mode: str = "commit"
    branch_id: str = "main"
    parent_branch_id: str | None = None
    parent_operation_id: str | None = None
    failure_policy: dict = field(default_factory=dict)
    compensation_plan: list[dict] = field(default_factory=list)
    delta: dict = field(default_factory=dict)
    status: str = "queued"
    created_at: str = field(default_factory=utc_now)
    assigned_agent_id: str | None = None
    assigned_agent_name: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    result: str | None = None
    attempts: int = 0
    last_error: str | None = None


class AgentRuntime:
    def __init__(self, state_path: Path | None = None) -> None:
        paths = get_project_paths()
        self.state_path = state_path or paths.agent_runtime_file
        self._lock = RLock()
        self._next_task_id = 1
        self._agents: dict[str, AgentRecord] = {}
        self._tasks: list[TaskRecord] = []
        self._events: deque[dict] = deque(maxlen=100)
        self._load_state()

    def _default_state(self) -> dict:
        return {
            "agents": [],
            "tasks": [],
            "events": [],
            "next_task_id": 1,
            "last_updated": None,
        }

    def _record_fields(self, record_type) -> set[str]:
        return {item.name for item in fields(record_type)}

    def _restore_agent_record(self, payload: dict) -> AgentRecord:
        allowed = self._record_fields(AgentRecord)
        data = {key: payload[key] for key in allowed if key in payload}
        return AgentRecord(**data)

    def _restore_task_record(self, payload: dict) -> TaskRecord:
        allowed = self._record_fields(TaskRecord)
        data = {key: payload[key] for key in allowed if key in payload}
        return TaskRecord(**data)

    def _load_state(self) -> None:
        if not self.state_path.exists():
            state = self._default_state()
        else:
            try:
                state = json.loads(self.state_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                state = self._default_state()

        if not isinstance(state, dict):
            state = self._default_state()

        agents: dict[str, AgentRecord] = {}
        for payload in state.get("agents", []):
            if not isinstance(payload, dict):
                continue
            try:
                record = self._restore_agent_record(payload)
            except TypeError:
                continue
            agents[record.id] = record

        tasks: list[TaskRecord] = []
        for payload in state.get("tasks", []):
            if not isinstance(payload, dict):
                continue
            try:
                tasks.append(self._restore_task_record(payload))
            except TypeError:
                continue

        events = [item for item in state.get("events", []) if isinstance(item, dict)]

        self._agents = agents
        self._tasks = tasks
        self._events = deque(events[:100], maxlen=100)

        next_task_id = 1
        try:
            next_task_id = int(state.get("next_task_id", 1))
        except (TypeError, ValueError):
            next_task_id = 1

        max_existing = max((task.id for task in self._tasks), default=0)
        self._next_task_id = max(next_task_id, max_existing + 1, 1)

        if self._recover_after_restart():
            self._save_state()

    def _save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        body = {
            "agents": [asdict(agent) for agent in sorted(self._agents.values(), key=lambda item: (item.role, item.name.lower()))],
            "tasks": [asdict(task) for task in self._tasks],
            "events": list(self._events),
            "next_task_id": self._next_task_id,
            "last_updated": utc_now(),
        }
        self.state_path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")

    def _recover_after_restart(self) -> bool:
        recovered_task_ids: list[int] = []
        affected_agents: set[str] = set()

        for task in self._tasks:
            if task.status == "in_progress":
                recovered_task_ids.append(task.id)
                if task.assigned_agent_id:
                    affected_agents.add(task.assigned_agent_id)
                task.status = "queued"
                task.assigned_agent_id = None
                task.assigned_agent_name = None
                task.started_at = None
                task.last_error = task.last_error or "task requeued after runtime restart"

        for agent in self._agents.values():
            if agent.status == "busy" or agent.current_task_id in recovered_task_ids or agent.id in affected_agents:
                agent.status = "idle"
                agent.current_task_id = None

        if recovered_task_ids:
            for task_id in recovered_task_ids:
                try:
                    EXECUTION_RUNTIME.release_task(task_id, reason="agent runtime restarted")
                except ValueError:
                    continue
                except Exception as exc:
                    self._log_event(
                        "runtime_recovery_warning",
                        f"execution runtime release failed for recovered task {task_id}",
                        task_id=task_id,
                        reason=str(exc),
                    )
            self._log_event(
                "runtime_recovered",
                "agent runtime restored queued tasks after restart",
                recovered_task_ids=recovered_task_ids,
            )
            return True

        return False

    def _allocate_task_id(self) -> int:
        task_id = self._next_task_id
        self._next_task_id += 1
        return task_id

    def _log_event(self, event_type: str, summary: str, **data) -> None:
        self._events.appendleft(
            {
                "timestamp": utc_now(),
                "type": event_type,
                "summary": summary,
                "data": data,
            }
        )

    def _validate_role(self, role: str | None) -> str | None:
        if role is None:
            return None

        role = str(role).strip().lower()
        if role not in VALID_AGENT_ROLES:
            raise ValueError("role must be either 'manager' or 'worker'")
        return role

    def _get_task_by_id(self, task_id: int) -> TaskRecord | None:
        for task in self._tasks:
            if task.id == task_id:
                return task
        return None

    def _normalize_task_filters(
        self,
        *,
        task_ids: list[int] | None = None,
        plan_id: str | None = None,
    ) -> tuple[set[int] | None, str | None]:
        normalized_task_ids: set[int] | None = None
        if task_ids is not None:
            normalized_task_ids = set()
            for task_id in list(task_ids or []):
                try:
                    normalized_task_id = int(task_id)
                except (TypeError, ValueError):
                    continue
                normalized_task_ids.add(normalized_task_id)
        normalized_plan_id = str(plan_id or "").strip() or None
        return normalized_task_ids, normalized_plan_id

    def _task_matches_filters(
        self,
        task: TaskRecord,
        *,
        task_ids: set[int] | None = None,
        plan_id: str | None = None,
    ) -> bool:
        if task_ids is not None and int(task.id) not in task_ids:
            return False

        if plan_id is not None:
            task_plan_id = str((task.metadata or {}).get("plan_id", "")).strip() or None
            if task_plan_id != plan_id:
                return False

        return True

    def _execution_operation_index(self) -> dict[int, dict]:
        try:
            operations = EXECUTION_RUNTIME.list_operations()
        except Exception:
            return {}

        return {
            int(operation.get("task_id", 0) or 0): dict(operation)
            for operation in operations
            if int(operation.get("task_id", 0) or 0) > 0
        }

    def _task_payload(self, task: TaskRecord, *, operation: dict | None = None) -> dict:
        payload = asdict(task)
        operation = dict(operation or {})
        if operation:
            payload["execution_status"] = operation.get("status")
            payload["compensation_status"] = operation.get("compensation_status")
            payload["execution_completed_at"] = operation.get("completed_at")
            payload["compensated_at"] = operation.get("compensated_at")
            payload["execution_last_error"] = operation.get("last_error")
        payload["dispatch_policy"] = dispatch_policy_for_task(payload)
        return payload

    def _active_branch_assignment_counts(self, *, exclude_task_id: int | None = None) -> Counter[str]:
        counts: Counter[str] = Counter()
        for task in self._tasks:
            if exclude_task_id is not None and int(task.id) == int(exclude_task_id):
                continue
            if task.status != "in_progress" or not task.assigned_agent_id:
                continue
            branch_id = str(task.branch_id or "main").strip() or "main"
            counts[branch_id] += 1
        return counts

    def _claim_task_locked(self, agent: AgentRecord, task: TaskRecord) -> tuple[dict, dict, dict]:
        previous_task_state = asdict(task)
        previous_agent_state = asdict(agent)

        task.status = "in_progress"
        task.assigned_agent_id = agent.id
        task.assigned_agent_name = agent.name
        task.started_at = utc_now()
        task.attempts += 1

        agent.status = "busy"
        agent.current_task_id = task.id
        agent.tasks_claimed += 1
        agent.last_assigned_at = task.started_at
        agent.last_heartbeat = utc_now()
        agent.metadata["last_branch_id"] = task.branch_id
        if task.operation_id:
            agent.metadata["last_operation_id"] = task.operation_id

        self._log_event("task_claimed", f"{agent.name} claimed task {task.id}", task_id=task.id, agent_id=agent.id)
        task_data = asdict(task)
        self._save_state()
        return task_data, previous_task_state, previous_agent_state

    def _rollback_claim(self, previous_task_state: dict, previous_agent_state: dict, reason: str) -> None:
        with self._lock:
            task = self._get_task_by_id(previous_task_state["id"])
            if task is not None:
                restored_task = self._restore_task_record(previous_task_state)
                task.__dict__.update(restored_task.__dict__)

            restored_agent = self._restore_agent_record(previous_agent_state)
            self._agents[restored_agent.id] = restored_agent
            self._log_event(
                "task_claim_rollback",
                f"rollback claim for task {previous_task_state['id']}",
                task_id=previous_task_state["id"],
                agent_id=previous_agent_state["id"],
                reason=str(reason),
            )
            self._save_state()

    def register_agent(
        self,
        name: str,
        role: str,
        capabilities: list[str] | None = None,
        metadata: dict | None = None,
    ) -> dict:
        name = str(name).strip()
        if not name:
            raise ValueError("agent name is required")

        role = self._validate_role(role)
        capabilities = list(capabilities or [])
        metadata = dict(metadata or {})
        agent_id = normalize_agent_id(role, name)

        with self._lock:
            agent = self._agents.get(agent_id)
            if agent is None:
                agent = AgentRecord(
                    id=agent_id,
                    name=name,
                    role=role,
                    capabilities=capabilities,
                    metadata=metadata,
                )
                self._agents[agent_id] = agent
                self._log_event("agent_registered", f"{role} {name} registered", agent_id=agent.id)
            else:
                if capabilities:
                    agent.capabilities = capabilities
                if metadata:
                    agent.metadata.update(metadata)
                agent.last_heartbeat = utc_now()
                self._log_event("agent_updated", f"{role} {name} updated", agent_id=agent.id)

            self._save_state()
            return asdict(agent)

    def heartbeat(self, agent_id: str, status: str | None = None) -> dict:
        with self._lock:
            agent = self._agents.get(agent_id)
            if agent is None:
                raise ValueError("agent_id not found")

            if status:
                agent.status = str(status).strip().lower()
            agent.last_heartbeat = utc_now()
            self._log_event("heartbeat", f"heartbeat from {agent.name}", agent_id=agent.id)
            self._save_state()
            return asdict(agent)

    def deregister_agent(self, agent_id: str) -> dict:
        pending_release_task_id = None
        with self._lock:
            agent = self._agents.pop(agent_id, None)
            if agent is None:
                raise ValueError("agent_id not found")

            removed_agent = asdict(agent)
            previous_task_state = None
            if agent.current_task_id is not None:
                task = self._get_task_by_id(agent.current_task_id)
                if task and task.assigned_agent_id == agent_id and task.status == "in_progress":
                    previous_task_state = asdict(task)
                    pending_release_task_id = task.id
                    task.status = "queued"
                    task.assigned_agent_id = None
                    task.assigned_agent_name = None
                    task.started_at = None
                    task.last_error = "task requeued after agent deregistration"

            self._log_event("agent_removed", f"{agent.role} {agent.name} removed", agent_id=agent.id)
            self._save_state()

        if pending_release_task_id is not None:
            try:
                EXECUTION_RUNTIME.release_task(pending_release_task_id, reason="agent deregistered")
            except Exception as exc:
                with self._lock:
                    self._agents[removed_agent["id"]] = self._restore_agent_record(removed_agent)
                    if previous_task_state is not None:
                        task = self._get_task_by_id(previous_task_state["id"])
                        if task is not None:
                            restored = self._restore_task_record(previous_task_state)
                            task.__dict__.update(restored.__dict__)
                    self._log_event(
                        "agent_remove_rollback",
                        f"rollback agent removal for {removed_agent['name']}",
                        agent_id=removed_agent["id"],
                        reason=str(exc),
                    )
                    self._save_state()
                raise

        return removed_agent

    def queue_task(
        self,
        title: str,
        preferred_role: str | None = None,
        metadata: dict | None = None,
        *,
        operation_id: str | None = None,
        execution_mode: str | None = None,
        branch_id: str | None = None,
        parent_branch_id: str | None = None,
        parent_operation_id: str | None = None,
        failure_policy: dict | None = None,
        compensation_plan=None,
        delta=None,
    ) -> dict:
        title = str(title).strip()
        if not title:
            raise ValueError("task title is required")

        preferred_role = self._validate_role(preferred_role)
        execution = build_execution_fields(
            title,
            metadata=metadata,
            operation_id=operation_id,
            execution_mode=execution_mode,
            branch_id=branch_id,
            parent_branch_id=parent_branch_id,
            parent_operation_id=parent_operation_id,
            failure_policy=failure_policy,
            compensation_plan=compensation_plan,
            delta=delta,
        )

        with self._lock:
            task = TaskRecord(
                id=self._allocate_task_id(),
                title=title,
                preferred_role=preferred_role,
                metadata=execution["metadata"],
                operation_id=execution["operation_id"],
                execution_mode=execution["execution_mode"],
                branch_id=execution["branch_id"],
                parent_branch_id=execution["parent_branch_id"],
                parent_operation_id=execution["parent_operation_id"],
                failure_policy=execution["failure_policy"],
                compensation_plan=execution["compensation_plan"],
                delta=execution["delta"],
            )
            self._tasks.append(task)
            self._log_event("task_queued", f"task queued: {task.title}", task_id=task.id)
            task_data = asdict(task)
            self._save_state()

        try:
            operation = EXECUTION_RUNTIME.register_task(task_data)
        except Exception:
            with self._lock:
                self._tasks = [item for item in self._tasks if item.id != task.id]
                self._log_event("task_queue_rollback", f"rollback queued task {task.id}", task_id=task.id)
                self._save_state()
            raise
        with self._lock:
            current_task = self._get_task_by_id(int(task_data["id"]))
            if current_task is None:
                return dict(task_data)
            return self._task_payload(current_task, operation=operation)

    def recommend_task_for_agent(self, agent_id: str, *, limit: int = 5) -> dict:
        with self._lock:
            agent = self._agents.get(agent_id)
            if agent is None:
                raise ValueError("agent_id not found")

            operation_index = self._execution_operation_index()
            current_task = self._get_task_by_id(agent.current_task_id) if agent.current_task_id is not None else None
            branch_assignment_counts = self._active_branch_assignment_counts()
            queued_tasks = [
                self._task_payload(task, operation=operation_index.get(task.id))
                for task in self._tasks
                if task.status == "queued"
            ]
            ranked = rank_tasks_for_agent(
                asdict(agent),
                queued_tasks,
                limit=limit,
                branch_assignment_counts=branch_assignment_counts,
            )

            return {
                "status": "ok",
                "service": "AI OS Agent Role Policy",
                "agent": asdict(agent),
                "current_task": self._task_payload(current_task, operation=operation_index.get(current_task.id)) if current_task is not None else None,
                "recommended_task": ranked[0] if ranked else None,
                "candidates": ranked,
                "queued_task_count": len(queued_tasks),
                "active_branch_assignments": dict(branch_assignment_counts),
            }

    def claim_task(self, agent_id: str, task_id: int) -> dict:
        with self._lock:
            agent = self._agents.get(agent_id)
            if agent is None:
                raise ValueError("agent_id not found")

            if agent.current_task_id is not None:
                current = self._get_task_by_id(agent.current_task_id)
                if current is None:
                    return None
                return self._task_payload(current, operation=self._execution_operation_index().get(current.id))

            task = self._get_task_by_id(int(task_id))
            if task is None:
                raise ValueError("task_id not found")
            if task.status != "queued":
                raise ValueError("task is not queued")
            if task.preferred_role and task.preferred_role != agent.role:
                raise ValueError("task role does not match agent role")
            dispatch = evaluate_task_dispatch(asdict(task), self._active_branch_assignment_counts(exclude_task_id=task.id))
            if not dispatch.get("eligible"):
                raise ValueError(str(dispatch.get("reason") or "task is blocked by branch dispatch policy"))

            task_data, previous_task_state, previous_agent_state = self._claim_task_locked(agent, task)

        try:
            operation = EXECUTION_RUNTIME.claim_task(task_data["id"], agent.id, agent.name)
        except Exception as exc:
            self._rollback_claim(previous_task_state, previous_agent_state, str(exc))
            raise
        with self._lock:
            current_task = self._get_task_by_id(int(task_data["id"]))
            if current_task is None:
                return dict(task_data)
            return self._task_payload(current_task, operation=operation)

    def claim_next_task(self, agent_id: str) -> dict | None:
        recommendation = self.recommend_task_for_agent(agent_id, limit=1)
        candidate = recommendation.get("recommended_task")
        if not candidate or not candidate.get("eligible"):
            return recommendation.get("current_task")
        return self.claim_task(agent_id, int(candidate["task_id"]))

    def dispatch_preview(
        self,
        *,
        limit: int = 10,
        task_ids: list[int] | None = None,
        plan_id: str | None = None,
    ) -> dict:
        normalized_task_ids, normalized_plan_id = self._normalize_task_filters(
            task_ids=task_ids,
            plan_id=plan_id,
        )
        with self._lock:
            agents = [asdict(agent) for agent in sorted(self._agents.values(), key=lambda item: (item.role, item.name.lower()))]
            tasks = [
                asdict(task)
                for task in self._tasks
                if self._task_matches_filters(task, task_ids=normalized_task_ids, plan_id=normalized_plan_id)
            ]

        preview = build_dispatch_plan(tasks, agents, limit=limit)
        preview.update(
            {
                "status": "ok",
                "service": "AI OS Agent Role Policy",
                "filters": {
                    "task_ids": sorted(normalized_task_ids) if normalized_task_ids is not None else None,
                    "plan_id": normalized_plan_id,
                },
                "agent_counts": {
                    "total": len(agents),
                    "idle": sum(
                        1
                        for agent in agents
                        if agent["status"] == "idle" and agent.get("current_task_id") is None
                    ),
                    "busy": sum(1 for agent in agents if agent["status"] == "busy"),
                },
                "task_counts": {
                    "total": len(tasks),
                    "queued": sum(1 for task in tasks if task["status"] == "queued"),
                    "in_progress": sum(1 for task in tasks if task["status"] == "in_progress"),
                },
            }
        )
        return preview

    def dispatch_ready_tasks(
        self,
        *,
        limit: int = 10,
        task_ids: list[int] | None = None,
        plan_id: str | None = None,
    ) -> dict:
        preview = self.dispatch_preview(limit=limit, task_ids=task_ids, plan_id=plan_id)
        assignments: list[dict] = []
        errors: list[dict] = []

        for assignment in preview.get("assignments", []):
            try:
                task = self.claim_task(
                    str(assignment.get("agent_id", "")).strip(),
                    int(assignment.get("task_id")),
                )
            except Exception as exc:
                errors.append(
                    {
                        "task_id": assignment.get("task_id"),
                        "agent_id": assignment.get("agent_id"),
                        "reason": str(exc),
                    }
                )
                continue

            assignments.append(
                {
                    **assignment,
                    "task": task,
                }
            )

        return {
            "status": "ok",
            "service": "AI OS Agent Dispatch",
            "filters": preview.get("filters", {}),
            "dispatch_count": len(assignments),
            "assignments": assignments,
            "errors": errors,
            "policy_preview": preview,
            "snapshot": self.snapshot(),
        }

    def complete_task(self, agent_id: str, task_id: int, result: str = "", success: bool = True) -> dict:
        with self._lock:
            agent = self._agents.get(agent_id)
            if agent is None:
                raise ValueError("agent_id not found")

            task = self._get_task_by_id(task_id)
            if task is None:
                raise ValueError("task_id not found")
            if task.assigned_agent_id != agent.id:
                raise ValueError("task is not assigned to this agent")

            previous_task_state = asdict(task)
            previous_agent_state = asdict(agent)
            task.status = "done" if success else "failed"
            task.result = str(result).strip() or None
            task.completed_at = utc_now()
            task.last_error = None if success else (task.result or "task execution failed")

            agent.status = "idle"
            agent.current_task_id = None
            agent.tasks_completed += 1
            if not success:
                agent.tasks_failed += 1
            agent.last_heartbeat = utc_now()
            agent.metadata["last_branch_id"] = task.branch_id
            if task.operation_id:
                agent.metadata["last_operation_id"] = task.operation_id

            event_type = "task_completed" if success else "task_failed"
            self._log_event(event_type, f"{agent.name} finished task {task.id}", task_id=task.id, agent_id=agent.id)
            task_data = asdict(task)
            self._save_state()

        try:
            operation = EXECUTION_RUNTIME.complete_task(task_id, success=success, result=result, agent_id=agent_id)
        except Exception as exc:
            with self._lock:
                task = self._get_task_by_id(previous_task_state["id"])
                if task is not None:
                    restored_task = self._restore_task_record(previous_task_state)
                    task.__dict__.update(restored_task.__dict__)

                restored_agent = self._restore_agent_record(previous_agent_state)
                self._agents[restored_agent.id] = restored_agent
                self._log_event(
                    "task_complete_rollback",
                    f"rollback completion for task {previous_task_state['id']}",
                    task_id=previous_task_state["id"],
                    agent_id=previous_agent_state["id"],
                    reason=str(exc),
                )
                self._save_state()
            raise
        with self._lock:
            current_task = self._get_task_by_id(task_id)
            if current_task is None:
                return dict(task_data)
            return self._task_payload(current_task, operation=operation)

    def list_agents(self) -> list[dict]:
        with self._lock:
            agents = sorted(self._agents.values(), key=lambda item: (item.role, item.name.lower()))
            return [asdict(agent) for agent in agents]

    def list_tasks(self) -> list[dict]:
        operation_index = self._execution_operation_index()
        with self._lock:
            return [self._task_payload(task, operation=operation_index.get(task.id)) for task in self._tasks]

    def recent_events(self) -> list[dict]:
        with self._lock:
            return list(self._events)

    def snapshot(self) -> dict:
        operation_index = self._execution_operation_index()
        with self._lock:
            agents = [asdict(agent) for agent in sorted(self._agents.values(), key=lambda item: (item.role, item.name.lower()))]
            tasks = [self._task_payload(task, operation=operation_index.get(task.id)) for task in self._tasks]

            return {
                "status": "ok",
                "service": "AI OS Agent Runtime",
                "state_file": str(self.state_path),
                "agent_counts": {
                    "total": len(agents),
                    "managers": sum(1 for agent in agents if agent["role"] == "manager"),
                    "workers": sum(1 for agent in agents if agent["role"] == "worker"),
                    "busy": sum(1 for agent in agents if agent["status"] == "busy"),
                    "idle": sum(1 for agent in agents if agent["status"] == "idle"),
                },
                "task_counts": {
                    "total": len(tasks),
                    "queued": sum(1 for task in tasks if task["status"] == "queued"),
                    "in_progress": sum(1 for task in tasks if task["status"] == "in_progress"),
                    "done": sum(1 for task in tasks if task["status"] == "done"),
                    "failed": sum(1 for task in tasks if task["status"] == "failed"),
                },
                "agents": agents,
                "tasks": tasks,
                "events": list(self._events),
            }


AGENT_RUNTIME = AgentRuntime()
