"""Official execution runtime for contracts, failure policy and compensation metadata."""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from threading import RLock

from ai_os.config import get_project_paths
from execution.contracts import OperationRecord, build_execution_fields, utc_now
from execution.ledger import OPERATION_LEDGER, OperationLedger


SERVICE_NAME = "AI OS Execution Runtime"


def _optional_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class ExecutionRuntime:
    def __init__(self, state_path: Path | None = None, *, ledger: OperationLedger | None = None) -> None:
        paths = get_project_paths()
        self.state_path = state_path or paths.execution_runtime_file
        self.ledger = ledger or OPERATION_LEDGER
        self._lock = RLock()
        self._operations: list[dict] = []
        self._events: deque[dict] = deque(maxlen=100)
        self._load_state()

    def _default_state(self) -> dict:
        return {
            "operations": [],
            "events": [],
            "last_updated": None,
        }

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

        self._operations = list(state.get("operations", []))
        self._events = deque(list(state.get("events", []))[:100], maxlen=100)

    def _save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        body = {
            "operations": self._operations,
            "events": list(self._events),
            "last_updated": utc_now(),
        }
        self.state_path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")

    def _log_event(self, event_type: str, summary: str, **data) -> None:
        self._events.appendleft(
            {
                "timestamp": utc_now(),
                "type": event_type,
                "summary": summary,
                "data": data,
            }
        )

    def _find_operation_by_task_id(self, task_id: int) -> dict | None:
        for operation in self._operations:
            if int(operation.get("task_id", 0)) == int(task_id):
                return operation
        return None

    def _find_operation_by_id(self, operation_id: str) -> dict | None:
        for operation in self._operations:
            if str(operation.get("operation_id", "")).strip() == str(operation_id).strip():
                return operation
        return None

    def preview_contract(
        self,
        title: str,
        *,
        preferred_role: str | None = None,
        metadata: dict | None = None,
        operation_id: str | None = None,
        execution_mode: str | None = None,
        branch_id: str | None = None,
        parent_branch_id: str | None = None,
        parent_operation_id: str | None = None,
        failure_policy: dict | None = None,
        compensation_plan=None,
        delta=None,
    ) -> dict:
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
        return {
            "status": "ok",
            "service": SERVICE_NAME,
            "preview": {
                "title": str(title).strip(),
                "preferred_role": preferred_role,
                **execution,
            },
        }

    def register_task(self, task: dict) -> dict:
        if not isinstance(task, dict):
            raise ValueError("task must be a dictionary")

        task_id = int(task.get("id", 0))
        title = str(task.get("title", "")).strip()
        if task_id <= 0 or not title:
            raise ValueError("task must include id and title")

        execution = build_execution_fields(
            title,
            metadata=task.get("metadata", {}),
            operation_id=task.get("operation_id"),
            execution_mode=task.get("execution_mode"),
            branch_id=task.get("branch_id"),
            parent_branch_id=task.get("parent_branch_id"),
            parent_operation_id=task.get("parent_operation_id"),
            failure_policy=task.get("failure_policy"),
            compensation_plan=task.get("compensation_plan"),
            delta=task.get("delta"),
        )

        with self._lock:
            existing = self._find_operation_by_task_id(task_id)
            if existing is None:
                record = OperationRecord(
                    operation_id=execution["operation_id"],
                    task_id=task_id,
                    task_title=title,
                    execution_mode=execution["execution_mode"],
                    branch_id=execution["branch_id"],
                    parent_branch_id=execution["parent_branch_id"],
                    parent_operation_id=execution["parent_operation_id"],
                    failure_policy=execution["failure_policy"],
                    compensation_plan=execution["compensation_plan"],
                    delta=execution["delta"],
                    metadata=execution["metadata"],
                )
                existing = record.to_dict()
                self._operations.append(existing)
                self._log_event("operation_registered", f"operation registered for task {task_id}", operation_id=record.operation_id, task_id=task_id)
                self.ledger.record_event(
                    "operation_registered",
                    existing,
                    summary=f"execution contract registered for task {task_id}",
                )
            else:
                existing.update(
                    {
                        "task_title": title,
                        "execution_mode": execution["execution_mode"],
                        "branch_id": execution["branch_id"],
                        "parent_branch_id": execution["parent_branch_id"],
                        "parent_operation_id": execution["parent_operation_id"],
                        "failure_policy": execution["failure_policy"],
                        "compensation_plan": execution["compensation_plan"],
                        "delta": execution["delta"],
                        "metadata": execution["metadata"],
                    }
                )
                self._log_event("operation_updated", f"operation updated for task {task_id}", operation_id=existing["operation_id"], task_id=task_id)
                self.ledger.record_event(
                    "operation_updated",
                    existing,
                    summary=f"execution contract updated for task {task_id}",
                )

            self._save_state()
            return dict(existing)

    def claim_task(self, task_id: int, agent_id: str, agent_name: str | None = None) -> dict:
        with self._lock:
            operation = self._find_operation_by_task_id(task_id)
            if operation is None:
                raise ValueError("execution contract not found for task_id")

            previous_status = operation.get("status")
            previous_attempts = int(operation.get("attempts", 0) or 0)
            operation["status"] = "in_progress"
            operation["claimed_at"] = utc_now()
            operation["assigned_agent_id"] = _optional_text(agent_id)
            operation["assigned_agent_name"] = _optional_text(agent_name)
            operation["attempts"] = previous_attempts + 1

            self._log_event(
                "execution_claimed",
                f"execution claimed for task {task_id}",
                operation_id=operation["operation_id"],
                task_id=task_id,
                agent_id=operation["assigned_agent_id"],
            )
            self.ledger.record_event(
                "execution_claimed",
                operation,
                summary=f"task {task_id} claimed by {operation['assigned_agent_name'] or operation['assigned_agent_id'] or 'agent'}",
                details={
                    "from_status": previous_status,
                    "from_attempts": previous_attempts,
                },
            )
            self._save_state()
            return dict(operation)

    def release_task(self, task_id: int, reason: str = "released") -> dict:
        with self._lock:
            operation = self._find_operation_by_task_id(task_id)
            if operation is None:
                raise ValueError("execution contract not found for task_id")

            previous_status = operation.get("status")
            operation["status"] = "planned"
            operation["assigned_agent_id"] = None
            operation["assigned_agent_name"] = None
            operation["last_error"] = str(reason).strip() or None

            self._log_event(
                "execution_released",
                f"execution released for task {task_id}",
                operation_id=operation["operation_id"],
                task_id=task_id,
                reason=reason,
            )
            self.ledger.record_event(
                "execution_released",
                operation,
                summary=f"task {task_id} released back to execution queue",
                details={
                    "reason": reason,
                    "from_status": previous_status,
                },
            )
            self._save_state()
            return dict(operation)

    def complete_task(self, task_id: int, *, success: bool, result: str = "", agent_id: str | None = None) -> dict:
        with self._lock:
            operation = self._find_operation_by_task_id(task_id)
            if operation is None:
                raise ValueError("execution contract not found for task_id")

            previous_status = operation.get("status")
            previous_compensation_status = operation.get("compensation_status")
            operation["status"] = "committed" if success else "failed"
            operation["completed_at"] = utc_now()
            operation["result"] = _optional_text(result)
            operation["assigned_agent_id"] = _optional_text(agent_id) or operation.get("assigned_agent_id")

            if success:
                operation["compensation_status"] = "not_required"
                operation["last_error"] = None
                event_type = "execution_committed"
                summary = f"execution committed for task {task_id}"
            else:
                operation["last_error"] = _optional_text(result) or "task execution failed"
                rollback_on_error = bool(operation.get("failure_policy", {}).get("rollback_on_error", True))
                operation["compensation_status"] = "pending" if rollback_on_error else "available"
                event_type = "execution_failed"
                summary = f"execution failed for task {task_id}"

            self._log_event(
                event_type,
                summary,
                operation_id=operation["operation_id"],
                task_id=task_id,
                success=success,
            )
            self.ledger.record_event(
                event_type,
                operation,
                summary=summary,
                details={
                    "success": success,
                    "from_status": previous_status,
                    "from_compensation_status": previous_compensation_status,
                },
            )
            self._save_state()
            return dict(operation)

    def compensate(self, *, task_id: int | None = None, operation_id: str | None = None, reason: str = "manual") -> dict:
        with self._lock:
            operation = None
            if task_id is not None:
                operation = self._find_operation_by_task_id(task_id)
            elif operation_id:
                operation = self._find_operation_by_id(operation_id)

            if operation is None:
                raise ValueError("execution contract not found")

            previous_compensation_status = operation.get("compensation_status")
            operation["compensation_status"] = "completed"
            operation["compensated_at"] = utc_now()
            operation["last_error"] = _optional_text(reason) or operation.get("last_error")

            self._log_event(
                "execution_compensated",
                f"compensation completed for task {operation['task_id']}",
                operation_id=operation["operation_id"],
                task_id=operation["task_id"],
                reason=reason,
            )
            self.ledger.record_event(
                "execution_compensated",
                operation,
                summary=f"compensation completed for task {operation['task_id']}",
                details={
                    "reason": reason,
                    "from_compensation_status": previous_compensation_status,
                },
            )
            self._save_state()
            return dict(operation)

    def feedback_summary(self, limit: int = 5) -> dict:
        with self._lock:
            operations = [dict(item) for item in self._operations]
            recent_events = list(self._events)[: max(1, int(limit))]

        pending_compensation = [
            item for item in operations if item.get("compensation_status") in {"pending", "available"}
        ]
        recent_failures = [
            {
                "operation_id": item.get("operation_id"),
                "task_id": item.get("task_id"),
                "task_title": item.get("task_title"),
                "branch_id": item.get("branch_id"),
                "attempts": int(item.get("attempts", 0) or 0),
                "last_error": item.get("last_error"),
                "compensation_status": item.get("compensation_status"),
            }
            for item in sorted(
                (op for op in operations if op.get("status") == "failed"),
                key=lambda op: str(op.get("completed_at") or op.get("created_at") or ""),
                reverse=True,
            )[:limit]
        ]
        repeated_attempts = [
            {
                "operation_id": item.get("operation_id"),
                "task_id": item.get("task_id"),
                "task_title": item.get("task_title"),
                "attempts": int(item.get("attempts", 0) or 0),
                "branch_id": item.get("branch_id"),
            }
            for item in sorted(
                (op for op in operations if int(op.get("attempts", 0) or 0) > 1),
                key=lambda op: int(op.get("attempts", 0) or 0),
                reverse=True,
            )[:limit]
        ]
        recovery_operations = [
            item
            for item in operations
            if str((item.get("metadata", {}) or {}).get("plan_kind", "")).strip() == "recovery"
        ]

        return {
            "failed_count": sum(1 for item in operations if item.get("status") == "failed"),
            "pending_compensation_count": len(
                [item for item in operations if item.get("compensation_status") == "pending"]
            ),
            "available_compensation_count": len(
                [item for item in operations if item.get("compensation_status") == "available"]
            ),
            "recent_failures": recent_failures,
            "pending_compensations": [
                {
                    "operation_id": item.get("operation_id"),
                    "task_id": item.get("task_id"),
                    "task_title": item.get("task_title"),
                    "branch_id": item.get("branch_id"),
                    "compensation_status": item.get("compensation_status"),
                }
                for item in pending_compensation[:limit]
            ],
            "repeated_attempts": repeated_attempts,
            "recent_events": recent_events,
            "recovery_counts": {
                "total": len(recovery_operations),
                "planned": sum(1 for item in recovery_operations if item.get("status") == "planned"),
                "in_progress": sum(1 for item in recovery_operations if item.get("status") == "in_progress"),
                "committed": sum(1 for item in recovery_operations if item.get("status") == "committed"),
                "failed": sum(1 for item in recovery_operations if item.get("status") == "failed"),
            },
            "recovery_compensation_counts": {
                "pending": sum(1 for item in recovery_operations if item.get("compensation_status") == "pending"),
                "available": sum(1 for item in recovery_operations if item.get("compensation_status") == "available"),
                "completed": sum(1 for item in recovery_operations if item.get("compensation_status") == "completed"),
                "not_required": sum(1 for item in recovery_operations if item.get("compensation_status") == "not_required"),
            },
            "active_recovery_branches": sorted(
                {
                    str(item.get("branch_id", "main")).strip() or "main"
                    for item in recovery_operations
                    if item.get("status") in {"planned", "in_progress", "failed"}
                }
            ),
            "branch_ids": sorted(
                {
                    str(item.get("branch_id", "main")).strip() or "main"
                    for item in operations
                }
            ),
        }

    def list_operations(self) -> list[dict]:
        with self._lock:
            return [dict(item) for item in sorted(self._operations, key=lambda op: int(op.get("task_id", 0)), reverse=True)]

    def recent_events(self) -> list[dict]:
        with self._lock:
            return list(self._events)

    def snapshot(self) -> dict:
        with self._lock:
            operations = [dict(item) for item in sorted(self._operations, key=lambda op: int(op.get("task_id", 0)), reverse=True)]
            snapshot = {
                "status": "ok",
                "service": SERVICE_NAME,
                "state_file": str(self.state_path),
                "operation_counts": {
                    "total": len(operations),
                    "planned": sum(1 for item in operations if item.get("status") == "planned"),
                    "in_progress": sum(1 for item in operations if item.get("status") == "in_progress"),
                    "committed": sum(1 for item in operations if item.get("status") == "committed"),
                    "failed": sum(1 for item in operations if item.get("status") == "failed"),
                },
                "compensation_counts": {
                    "ready": sum(1 for item in operations if item.get("compensation_status") == "ready"),
                    "available": sum(1 for item in operations if item.get("compensation_status") == "available"),
                    "pending": sum(1 for item in operations if item.get("compensation_status") == "pending"),
                    "completed": sum(1 for item in operations if item.get("compensation_status") == "completed"),
                    "not_required": sum(1 for item in operations if item.get("compensation_status") == "not_required"),
                },
                "feedback": self.feedback_summary(limit=5),
                "recovery_operation_counts": {
                    "total": sum(1 for item in operations if str((item.get("metadata", {}) or {}).get("plan_kind", "")).strip() == "recovery"),
                    "in_progress": sum(1 for item in operations if str((item.get("metadata", {}) or {}).get("plan_kind", "")).strip() == "recovery" and item.get("status") == "in_progress"),
                    "committed": sum(1 for item in operations if str((item.get("metadata", {}) or {}).get("plan_kind", "")).strip() == "recovery" and item.get("status") == "committed"),
                    "failed": sum(1 for item in operations if str((item.get("metadata", {}) or {}).get("plan_kind", "")).strip() == "recovery" and item.get("status") == "failed"),
                },
                "recovery_compensation_counts": {
                    "pending": sum(1 for item in operations if str((item.get("metadata", {}) or {}).get("plan_kind", "")).strip() == "recovery" and item.get("compensation_status") == "pending"),
                    "available": sum(1 for item in operations if str((item.get("metadata", {}) or {}).get("plan_kind", "")).strip() == "recovery" and item.get("compensation_status") == "available"),
                    "completed": sum(1 for item in operations if str((item.get("metadata", {}) or {}).get("plan_kind", "")).strip() == "recovery" and item.get("compensation_status") == "completed"),
                    "not_required": sum(1 for item in operations if str((item.get("metadata", {}) or {}).get("plan_kind", "")).strip() == "recovery" and item.get("compensation_status") == "not_required"),
                },
                "operations": operations,
                "events": list(self._events),
            }

        snapshot["lineage"] = self.ledger.feedback_summary(limit=5)
        return snapshot


EXECUTION_RUNTIME = ExecutionRuntime()
