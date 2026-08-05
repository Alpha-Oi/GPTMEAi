"""Snapshot lineage registry and replay planning for AI OS execution history."""

from __future__ import annotations

import json
from pathlib import Path
from threading import RLock

from ai_os.config import get_project_paths
from execution.ledger import OPERATION_LEDGER, OperationLedger, optional_text
from execution.contracts import utc_now


SERVICE_NAME = "AI OS Snapshot Lineage"
REPLAY_SERVICE_NAME = "AI OS Replay Plan"


def build_replay_step_summary(entry: dict) -> str:
    task_title = optional_text(entry.get("task_title"))
    summary = optional_text(entry.get("summary"))
    event_type = optional_text(entry.get("event_type"))
    transition = optional_text((entry.get("delta") or {}).get("transition_summary"))

    if task_title and transition:
        return f"{task_title} [{transition}]"
    if task_title and event_type:
        return f"{task_title} [{event_type}]"
    if task_title:
        return task_title
    if summary:
        return summary
    if event_type:
        return event_type.replace("_", " ")
    return "replay entry"


class SnapshotLineageRegistry:
    def __init__(self, state_path: Path | None = None, *, ledger: OperationLedger | None = None) -> None:
        paths = get_project_paths()
        self.state_path = state_path or paths.snapshot_lineage_file
        self.ledger = ledger or OPERATION_LEDGER
        self._lock = RLock()
        self._snapshots: list[dict] = []
        self._next_snapshot_index = 1
        self._load_state()

    def _default_state(self) -> dict:
        return {
            "snapshots": [],
            "next_snapshot_index": 1,
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

        self._snapshots = [item for item in state.get("snapshots", []) if isinstance(item, dict)]
        try:
            next_index = int(state.get("next_snapshot_index", 1))
        except (TypeError, ValueError):
            next_index = 1
        self._next_snapshot_index = max(next_index, len(self._snapshots) + 1, 1)

    def _save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        body = {
            "snapshots": self._snapshots,
            "next_snapshot_index": self._next_snapshot_index,
            "last_updated": utc_now(),
        }
        self.state_path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")

    def _make_snapshot_id(self) -> str:
        snapshot_id = f"snap_{utc_now().replace(':', '').replace('-', '')}_{self._next_snapshot_index:05d}"
        self._next_snapshot_index += 1
        return snapshot_id

    def _branch_details(self, branch_id: str | None) -> dict | None:
        if not branch_id:
            return None
        return self.ledger.branch_details(branch_id)

    def _latest_snapshot(self, *, branch_id: str | None = None) -> dict | None:
        for item in self._snapshots:
            if branch_id is None or str(item.get("branch_id", "main")).strip() == str(branch_id).strip():
                return dict(item)
        return None

    def _find_snapshot(self, snapshot_id: str | None) -> dict | None:
        snapshot_id = optional_text(snapshot_id)
        if not snapshot_id:
            return None
        for item in self._snapshots:
            if str(item.get("snapshot_id", "")).strip() == snapshot_id:
                return dict(item)
        return None

    def _find_source_entry(self, *, branch_id: str, operation_id: str | None = None, source_entry_id: str | None = None) -> dict | None:
        source_entry_id = optional_text(source_entry_id)
        if source_entry_id:
            for item in self.ledger.recent_entries(limit=200):
                if str(item.get("entry_id", "")).strip() == source_entry_id:
                    return dict(item)

        operation_id = optional_text(operation_id)
        if operation_id:
            lineage = self.ledger.lineage(operation_id=operation_id, limit=1)
            if lineage["entries"]:
                return dict(lineage["entries"][0])

        lineage = self.ledger.lineage(branch_id=branch_id, limit=1)
        if lineage["entries"]:
            return dict(lineage["entries"][0])
        return None

    def register_snapshot(
        self,
        snapshot_path: str | Path,
        snapshot_data: dict,
        *,
        branch_id: str | None = None,
        parent_snapshot_id: str | None = None,
        source_operation_id: str | None = None,
        source_entry_id: str | None = None,
        label: str | None = None,
    ) -> dict:
        if not isinstance(snapshot_data, dict):
            raise ValueError("snapshot_data must be a dictionary")

        snapshot_path = Path(snapshot_path)
        branch_id = str(branch_id or snapshot_data.get("branch_id") or "main").strip() or "main"
        source_operation_id = optional_text(source_operation_id or snapshot_data.get("source_operation_id"))
        source_entry = self._find_source_entry(
            branch_id=branch_id,
            operation_id=source_operation_id,
            source_entry_id=source_entry_id or snapshot_data.get("source_entry_id"),
        )

        branch = self._branch_details(branch_id) or {}
        parent_branch_id = optional_text(snapshot_data.get("parent_branch_id")) or optional_text(branch.get("parent_branch_id"))
        parent_snapshot_id = optional_text(parent_snapshot_id)

        with self._lock:
            if parent_snapshot_id is None:
                same_branch_latest = self._latest_snapshot(branch_id=branch_id)
                if same_branch_latest is not None:
                    parent_snapshot_id = same_branch_latest.get("snapshot_id")
                elif parent_branch_id:
                    parent_snapshot = self._latest_snapshot(branch_id=parent_branch_id)
                    if parent_snapshot is not None:
                        parent_snapshot_id = parent_snapshot.get("snapshot_id")

            snapshot_record = {
                "snapshot_id": self._make_snapshot_id(),
                "name": snapshot_path.name,
                "file": str(snapshot_path),
                "created_at": snapshot_data.get("snapshot_created_at") or utc_now(),
                "branch_id": branch_id,
                "parent_branch_id": parent_branch_id,
                "branch_depth": int(branch.get("depth", 0) or 0),
                "parent_snapshot_id": parent_snapshot_id,
                "source_operation_id": source_operation_id,
                "source_entry_id": (source_entry or {}).get("entry_id"),
                "entry_logical_time": (source_entry or {}).get("logical_time"),
                "memory_count": int(snapshot_data.get("memory_count", 0) or 0),
                "graph_nodes": int(snapshot_data.get("graph_nodes", 0) or 0),
                "graph_relations_total": int(snapshot_data.get("graph_relations_total", 0) or 0),
                "last_updated": snapshot_data.get("last_updated"),
                "label": optional_text(label) or optional_text(snapshot_data.get("label")) or snapshot_path.name,
            }
            self._snapshots.insert(0, snapshot_record)
            self._save_state()
            return dict(snapshot_record)

    def snapshot(self, *, branch_id: str | None = None, limit: int = 50) -> dict:
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 50
        limit = max(1, min(limit, 200))

        branch_id = optional_text(branch_id)
        with self._lock:
            items = [
                dict(item)
                for item in self._snapshots
                if branch_id is None or str(item.get("branch_id", "main")).strip() == branch_id
            ][:limit]
            total = len([1 for item in self._snapshots if branch_id is None or str(item.get("branch_id", "main")).strip() == branch_id])
            branch_ids = sorted(
                {
                    str(item.get("branch_id", "main")).strip() or "main"
                    for item in self._snapshots
                }
            )
            max_depth = max((int(item.get("branch_depth", 0) or 0) for item in self._snapshots), default=0)

        return {
            "status": "ok",
            "service": SERVICE_NAME,
            "state_file": str(self.state_path),
            "filters": {"branch_id": branch_id, "limit": limit},
            "snapshot_counts": {
                "total": total,
                "branch_count": len(branch_ids),
                "non_main_branch_count": sum(1 for item in branch_ids if item != "main"),
                "max_branch_depth": max_depth,
            },
            "snapshots": items,
        }

    def replay_plan(
        self,
        *,
        snapshot_id: str | None = None,
        branch_id: str | None = None,
        operation_id: str | None = None,
        limit: int = 50,
    ) -> dict:
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 50
        limit = max(1, min(limit, 200))

        snapshot_id = optional_text(snapshot_id)
        branch_id = optional_text(branch_id)
        operation_id = optional_text(operation_id)

        anchor = self._find_snapshot(snapshot_id)
        if anchor is None and operation_id:
            source_entry = self._find_source_entry(branch_id=branch_id or "main", operation_id=operation_id)
            if source_entry is not None:
                branch_id = branch_id or optional_text(source_entry.get("branch_id")) or "main"
                entry_logical_time = int(source_entry.get("logical_time", -1) or -1)
                with self._lock:
                    matching = [
                        dict(item)
                        for item in self._snapshots
                        if str(item.get("branch_id", "main")).strip() == branch_id
                        and int(item.get("entry_logical_time", -1) or -1) <= entry_logical_time
                    ]
                anchor = matching[0] if matching else None

        if anchor is None and branch_id:
            anchor = self._latest_snapshot(branch_id=branch_id)
        if anchor is None:
            anchor = self._latest_snapshot()

        effective_branch_id = branch_id or optional_text((anchor or {}).get("branch_id")) or "main"
        lineage = self.ledger.lineage(
            operation_id=operation_id,
            branch_id=None if operation_id else effective_branch_id,
            limit=limit,
        )

        anchor_logical_time = int((anchor or {}).get("entry_logical_time", -1) or -1)
        replay_entries = sorted(
            (
                dict(item)
                for item in lineage["entries"]
                if int(item.get("logical_time", -1) or -1) > anchor_logical_time
            ),
            key=lambda item: int(item.get("logical_time", -1) or -1),
        )
        replay_steps = [
            {
                "logical_time": item.get("logical_time"),
                "entry_id": item.get("entry_id"),
                "summary": build_replay_step_summary(item),
                "task_title": item.get("task_title"),
                "event_type": item.get("event_type"),
                "delta": item.get("delta", {}).get("transition_summary") or item.get("delta", {}).get("summary"),
            }
            for item in replay_entries
        ]

        return {
            "status": "ok",
            "service": REPLAY_SERVICE_NAME,
            "filters": {
                "snapshot_id": snapshot_id,
                "branch_id": branch_id,
                "operation_id": operation_id,
                "limit": limit,
            },
            "anchor_snapshot": anchor,
            "branch": self._branch_details(effective_branch_id),
            "replay_entries": replay_entries,
            "replay_steps": replay_steps,
            "replay_metadata": {
                "source": "raw_snapshot_lineage",
                "planner_context_included": False,
                "planner_context_endpoint": "/planner/recovery/preview",
                "anchor_selection_model": "explicit_snapshot_id -> operation_id -> branch_latest -> global_latest",
                "effective_branch_id": effective_branch_id,
                "anchor_snapshot_id": optional_text((anchor or {}).get("snapshot_id")),
                "anchor_entry_logical_time": anchor_logical_time,
                "replay_entry_count": len(replay_entries),
                "replay_step_count": len(replay_steps),
                "replay_order": "logical_time_ascending_after_anchor",
            },
        }


SNAPSHOT_LINEAGE = SnapshotLineageRegistry()
