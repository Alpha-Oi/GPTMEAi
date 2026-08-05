"""Persistent operation ledger with delta, branch and lineage tracking."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from threading import RLock

from ai_os.config import get_project_paths
from execution.contracts import normalize_delta, utc_now


SERVICE_NAME = "AI OS Operation Ledger"
DEFAULT_ENTRY_LIMIT = 500


def shorten_text(value: str, limit: int = 140) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3].rstrip()}..."


def optional_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class OperationLedger:
    def __init__(self, state_path: Path | None = None, *, max_entries: int = DEFAULT_ENTRY_LIMIT) -> None:
        paths = get_project_paths()
        self.state_path = state_path or paths.operation_ledger_file
        self.max_entries = max(50, int(max_entries))
        self._lock = RLock()
        self._entries: list[dict] = []
        self._branches: dict[str, dict] = {}
        self._next_entry_index = 1
        self._load_state()

    def _default_state(self) -> dict:
        return {
            "entries": [],
            "branches": {},
            "next_entry_index": 1,
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

        self._entries = [item for item in state.get("entries", []) if isinstance(item, dict)]
        self._branches = {
            str(branch_id).strip() or "main": dict(payload)
            for branch_id, payload in dict(state.get("branches", {})).items()
            if isinstance(payload, dict)
        }

        try:
            next_index = int(state.get("next_entry_index", 1))
        except (TypeError, ValueError):
            next_index = 1
        self._next_entry_index = max(next_index, len(self._entries) + 1, 1)

        if self._entries and "main" not in self._branches:
            self._branches["main"] = self._default_branch("main")

    def _save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        body = {
            "entries": self._entries,
            "branches": self._branches,
            "next_entry_index": self._next_entry_index,
            "last_updated": utc_now(),
        }
        self.state_path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")

    def _make_entry_id(self) -> str:
        entry_id = f"ledger_{utc_now().replace(':', '').replace('-', '')}_{self._next_entry_index:05d}"
        self._next_entry_index += 1
        return entry_id

    def _default_branch(self, branch_id: str, *, parent_branch_id: str | None = None, source: str | None = None) -> dict:
        depth = 0
        if parent_branch_id:
            parent = self._branches.get(parent_branch_id)
            depth = int(parent.get("depth", 0)) + 1 if isinstance(parent, dict) else 1
        elif branch_id != "main":
            depth = 1

        return {
            "branch_id": branch_id,
            "parent_branch_id": parent_branch_id,
            "depth": depth,
            "source": source,
            "created_at": utc_now(),
            "last_event_at": None,
            "first_entry_id": None,
            "last_entry_id": None,
            "event_count": 0,
            "operation_ids": [],
            "operation_count": 0,
        }

    def _ensure_branch(self, branch_id: str, *, parent_branch_id: str | None = None, source: str | None = None) -> dict:
        branch_id = str(branch_id or "main").strip() or "main"
        parent_branch_id = optional_text(parent_branch_id)
        if parent_branch_id == branch_id:
            parent_branch_id = None

        if parent_branch_id and parent_branch_id not in self._branches:
            self._branches[parent_branch_id] = self._default_branch(parent_branch_id)

        branch = self._branches.get(branch_id)
        if branch is None:
            branch = self._default_branch(branch_id, parent_branch_id=parent_branch_id, source=source)
            self._branches[branch_id] = branch
        else:
            if parent_branch_id and not branch.get("parent_branch_id"):
                branch["parent_branch_id"] = parent_branch_id
                parent = self._branches.get(parent_branch_id)
                branch["depth"] = int(parent.get("depth", 0)) + 1 if isinstance(parent, dict) else 1
            if source and not branch.get("source"):
                branch["source"] = source

        return branch

    def _find_last_entry_for_operation(self, operation_id: str | None) -> dict | None:
        if not operation_id:
            return None
        operation_id = str(operation_id).strip()
        for entry in self._entries:
            if str(entry.get("operation_id", "")).strip() == operation_id:
                return dict(entry)
        return None

    def _find_last_entry_for_branch(self, branch_id: str | None) -> dict | None:
        branch_id = str(branch_id or "main").strip() or "main"
        for entry in self._entries:
            if str(entry.get("branch_id", "main")).strip() == branch_id:
                return dict(entry)
        return None

    def _normalize_parent_branch_id(
        self,
        branch_id: str,
        metadata: dict,
        details: dict,
        parent_operation_entry: dict | None,
    ) -> str | None:
        parent_branch_id = optional_text(
            details.get("parent_branch_id")
            or metadata.get("parent_branch_id")
            or (parent_operation_entry or {}).get("branch_id")
        )
        if parent_branch_id == branch_id:
            return None
        if parent_branch_id is None and branch_id != "main":
            return "main"
        return parent_branch_id

    def _build_delta_summary(self, event_type: str, delta: dict, details: dict) -> str:
        parts: list[str] = []
        status_transition = delta.get("status_transition") or {}
        compensation_transition = delta.get("compensation_transition") or {}

        if status_transition.get("from") != status_transition.get("to"):
            parts.append(
                f"status {status_transition.get('from') or '-'} -> {status_transition.get('to') or '-'}"
            )
        if compensation_transition.get("from") != compensation_transition.get("to"):
            parts.append(
                "compensation "
                f"{compensation_transition.get('from') or '-'} -> {compensation_transition.get('to') or '-'}"
            )

        attempt_delta = int(delta.get("attempt_delta", 0) or 0)
        if attempt_delta:
            parts.append(f"attempts +{attempt_delta}")

        if details.get("reason"):
            parts.append(shorten_text(details["reason"], limit=60))

        if not parts:
            parts.append(event_type.replace("_", " "))

        return "; ".join(parts)

    def _normalize_delta_record(
        self,
        event_type: str,
        operation: dict,
        details: dict,
        previous_entry: dict | None,
    ) -> dict:
        metadata = operation.get("metadata", {})
        base_delta = normalize_delta(
            details.get("delta") if details.get("delta") is not None else operation.get("delta", metadata.get("delta")),
            title=operation.get("task_title", ""),
        )

        from_status = details.get("from_status")
        if from_status is None and previous_entry is not None:
            from_status = previous_entry.get("status")
        to_status = operation.get("status")

        from_compensation_status = details.get("from_compensation_status")
        if from_compensation_status is None and previous_entry is not None:
            from_compensation_status = previous_entry.get("compensation_status")
        to_compensation_status = operation.get("compensation_status")

        from_attempts = details.get("from_attempts")
        if from_attempts is None and previous_entry is not None:
            from_attempts = previous_entry.get("attempts", 0)
        to_attempts = int(operation.get("attempts", 0) or 0)

        base_delta.update(
            {
                "event_type": event_type,
                "status_transition": {"from": from_status, "to": to_status},
                "compensation_transition": {
                    "from": from_compensation_status,
                    "to": to_compensation_status,
                },
                "attempt_delta": to_attempts - int(from_attempts or 0),
            }
        )
        declared_summary = str(base_delta.get("summary", "")).strip()
        transition_summary = self._build_delta_summary(event_type, base_delta, details)
        if declared_summary.startswith("Expected state transition for task:"):
            base_delta["summary"] = transition_summary
        else:
            base_delta["declared_summary"] = declared_summary
            base_delta["summary"] = declared_summary
        base_delta["transition_summary"] = transition_summary
        return base_delta

    def record_event(
        self,
        event_type: str,
        operation: dict,
        *,
        summary: str = "",
        details: dict | None = None,
    ) -> dict:
        if not isinstance(operation, dict):
            raise ValueError("operation must be a dictionary")

        details = dict(details or {})
        failure_policy = operation.get("failure_policy", {})
        metadata = dict(operation.get("metadata", {}) or {})
        operation_id = str(operation.get("operation_id", "")).strip() or None
        branch_id = str(operation.get("branch_id", metadata.get("branch_id", "main"))).strip() or "main"

        with self._lock:
            previous_entry = self._find_last_entry_for_operation(operation_id)
            parent_operation_id = optional_text(
                operation.get("parent_operation_id")
                or metadata.get("parent_operation_id")
                or details.get("parent_operation_id")
            )
            parent_operation_entry = self._find_last_entry_for_operation(parent_operation_id)
            parent_branch_id = self._normalize_parent_branch_id(
                branch_id,
                metadata,
                details,
                parent_operation_entry,
            )

            branch = self._ensure_branch(
                branch_id,
                parent_branch_id=parent_branch_id,
                source=str(metadata.get("source", "")).strip() or None,
            )
            branch_sequence = int(branch.get("event_count", 0) or 0) + 1
            operation_sequence = int((previous_entry or {}).get("operation_sequence", 0) or 0) + 1
            previous_branch_entry = self._find_last_entry_for_branch(branch_id)

            parent_entry_id = None
            lineage_depth = int(branch.get("depth", 0) or 0)
            if previous_entry is not None:
                parent_entry_id = previous_entry.get("entry_id")
                lineage_depth = int(previous_entry.get("lineage_depth", lineage_depth) or lineage_depth) + 1
            elif parent_operation_entry is not None:
                parent_entry_id = parent_operation_entry.get("entry_id")
                lineage_depth = int(parent_operation_entry.get("lineage_depth", lineage_depth) or lineage_depth) + 1
            elif previous_branch_entry is not None:
                parent_entry_id = previous_branch_entry.get("entry_id")

            delta_record = self._normalize_delta_record(
                str(event_type).strip() or "execution_event",
                operation,
                details,
                previous_entry,
            )

            entry = {
                "entry_id": self._make_entry_id(),
                "timestamp": utc_now(),
                "logical_time": self._next_entry_index - 1,
                "event_type": str(event_type).strip() or "execution_event",
                "summary": str(summary).strip() or shorten_text(operation.get("task_title", "execution event")),
                "operation_id": operation_id,
                "task_id": int(operation.get("task_id", 0)) or None,
                "task_title": str(operation.get("task_title", "")).strip() or None,
                "branch_id": branch_id,
                "parent_branch_id": parent_branch_id,
                "branch_depth": int(branch.get("depth", 0) or 0),
                "branch_sequence": branch_sequence,
                "operation_sequence": operation_sequence,
                "previous_entry_id": (previous_entry or {}).get("entry_id"),
                "parent_entry_id": parent_entry_id,
                "parent_operation_id": parent_operation_id,
                "lineage_depth": lineage_depth,
                "execution_mode": str(operation.get("execution_mode", "commit")).strip() or "commit",
                "status": str(operation.get("status", "unknown")).strip() or "unknown",
                "compensation_status": str(operation.get("compensation_status", "")).strip() or None,
                "assigned_agent_id": optional_text(operation.get("assigned_agent_id")),
                "assigned_agent_name": optional_text(operation.get("assigned_agent_name")),
                "attempts": int(operation.get("attempts", 0) or 0),
                "rollback_on_error": bool(failure_policy.get("rollback_on_error", True)),
                "degraded_mode": str(failure_policy.get("degraded_mode", "report_only")).strip() or "report_only",
                "owner_hint": optional_text(metadata.get("owner_hint")),
                "source": optional_text(metadata.get("source")),
                "result": shorten_text(operation.get("result", "")),
                "last_error": shorten_text(operation.get("last_error", "")),
                "compensation_plan": list(operation.get("compensation_plan", [])),
                "delta": delta_record,
                "details": details,
            }

            self._entries.insert(0, entry)
            self._entries = self._entries[: self.max_entries]

            operation_ids = list(branch.get("operation_ids", []))
            if operation_id and operation_id not in operation_ids:
                operation_ids.append(operation_id)
            branch.update(
                {
                    "parent_branch_id": branch.get("parent_branch_id") or parent_branch_id,
                    "depth": int(branch.get("depth", 0) or 0),
                    "last_event_at": entry["timestamp"],
                    "last_entry_id": entry["entry_id"],
                    "event_count": branch_sequence,
                    "operation_ids": operation_ids[-100:],
                    "operation_count": len(operation_ids[-100:]),
                }
            )
            if not branch.get("first_entry_id"):
                branch["first_entry_id"] = entry["entry_id"]

            self._save_state()
            return dict(entry)

    def recent_entries(self, limit: int = 20) -> list[dict]:
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 20
        limit = max(1, min(limit, self.max_entries))

        with self._lock:
            return [dict(item) for item in self._entries[:limit]]

    def branch_registry(self, limit: int = 20) -> list[dict]:
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 20
        limit = max(1, min(limit, len(self._branches) or 1))

        with self._lock:
            branches = sorted(
                (dict(item) for item in self._branches.values()),
                key=lambda item: (
                    int(item.get("depth", 0) or 0),
                    -(int(item.get("event_count", 0) or 0)),
                    str(item.get("branch_id", "")),
                ),
            )
            return branches[:limit]

    def branch_details(self, branch_id: str | None) -> dict | None:
        branch_id = optional_text(branch_id)
        if not branch_id:
            return None
        with self._lock:
            branch = self._branches.get(branch_id)
            return dict(branch) if isinstance(branch, dict) else None

    def lineage(self, *, operation_id: str | None = None, branch_id: str | None = None, limit: int = 20) -> dict:
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 20
        limit = max(1, min(limit, self.max_entries))

        operation_id = str(operation_id).strip() or None if operation_id is not None else None
        branch_id = str(branch_id).strip() or None if branch_id is not None else None

        with self._lock:
            filtered = list(self._entries)
            if operation_id:
                filtered = [item for item in filtered if str(item.get("operation_id", "")).strip() == operation_id]
            if branch_id:
                filtered = [item for item in filtered if str(item.get("branch_id", "main")).strip() == branch_id]
            filtered = [dict(item) for item in filtered[:limit]]
            branch = dict(self._branches.get(branch_id, {})) if branch_id else None

        return {
            "status": "ok",
            "service": SERVICE_NAME,
            "filters": {
                "operation_id": operation_id,
                "branch_id": branch_id,
                "limit": limit,
            },
            "branch": branch,
            "entries": filtered,
        }

    def feedback_summary(self, limit: int = 10) -> dict:
        recent_entries = self.recent_entries(limit)
        recent_failures = [item for item in recent_entries if item.get("event_type") == "execution_failed"]
        recent_compensations = [item for item in recent_entries if item.get("event_type") == "execution_compensated"]
        recent_commits = [item for item in recent_entries if item.get("event_type") == "execution_committed"]

        with self._lock:
            failure_counter = Counter(
                str(item.get("task_title", "")).strip()
                for item in self._entries
                if item.get("event_type") == "execution_failed"
            )
            branches = [dict(item) for item in self._branches.values()]
            branch_counter = Counter(
                str(item.get("branch_id", "main")).strip() or "main"
                for item in self._entries
            )
            max_branch_depth = max((int(item.get("depth", 0) or 0) for item in branches), default=0)

        repeated_failures = [
            {"task_title": task_title, "count": count}
            for task_title, count in failure_counter.most_common(5)
            if task_title and count > 1
        ]

        hot_branches = [
            {
                "branch_id": branch_id,
                "events": count,
                "depth": next(
                    (
                        int(item.get("depth", 0) or 0)
                        for item in branches
                        if str(item.get("branch_id", "")).strip() == branch_id
                    ),
                    0,
                ),
                "parent_branch_id": next(
                    (
                        item.get("parent_branch_id")
                        for item in branches
                        if str(item.get("branch_id", "")).strip() == branch_id
                    ),
                    None,
                ),
            }
            for branch_id, count in branch_counter.most_common(5)
        ]

        recent_deltas = [
            {
                "entry_id": item.get("entry_id"),
                "operation_id": item.get("operation_id"),
                "branch_id": item.get("branch_id"),
                "summary": item.get("delta", {}).get("summary"),
            }
            for item in recent_entries
            if isinstance(item.get("delta"), dict) and item["delta"].get("summary")
        ][:5]

        return {
            "recent_failure_count": len(recent_failures),
            "recent_commit_count": len(recent_commits),
            "recent_compensation_count": len(recent_compensations),
            "recent_failures": recent_failures[:5],
            "recent_compensations": recent_compensations[:5],
            "repeated_failures": repeated_failures,
            "hot_branches": hot_branches,
            "recent_deltas": recent_deltas,
            "branch_count": len(branches),
            "non_main_branch_count": sum(1 for item in branches if item.get("branch_id") != "main"),
            "max_branch_depth": max_branch_depth,
        }

    def snapshot(self, limit: int = 50) -> dict:
        entries = self.recent_entries(limit)
        branches = self.branch_registry(limit=20)
        with self._lock:
            total_entries = len(self._entries)
            failed_events = sum(1 for item in self._entries if item.get("event_type") == "execution_failed")
            committed_events = sum(1 for item in self._entries if item.get("event_type") == "execution_committed")
            compensated_events = sum(1 for item in self._entries if item.get("event_type") == "execution_compensated")

        return {
            "status": "ok",
            "service": SERVICE_NAME,
            "state_file": str(self.state_path),
            "entry_counts": {
                "total": total_entries,
                "failed_events": failed_events,
                "committed_events": committed_events,
                "compensated_events": compensated_events,
            },
            "branch_counts": {
                "total": len(branches),
                "non_main": sum(1 for item in branches if item.get("branch_id") != "main"),
                "max_depth": max((int(item.get("depth", 0) or 0) for item in branches), default=0),
            },
            "feedback": self.feedback_summary(limit=min(limit, 20)),
            "branches": branches,
            "entries": entries,
        }


OPERATION_LEDGER = OperationLedger()
