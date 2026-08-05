"""Persistent planner/runtime bridge between cognitive loop and agent execution."""

from __future__ import annotations

import json
from collections import deque
from dataclasses import asdict, dataclass, field, fields
from datetime import UTC, datetime
from itertools import count
from pathlib import Path
from threading import RLock

from ai_os.agent_runtime import AGENT_RUNTIME, AgentRuntime
from ai_os.config import get_project_paths
from ai_os.stabilization_playbook import build_stabilization_playbooks
from core.memory_engine import MemoryEngine
import execution.runtime as execution_runtime_module
from execution.snapshots import SNAPSHOT_LINEAGE


SERVICE_NAME = "AI OS Planner Runtime"
RECOVERY_PREVIEW_SERVICE_NAME = "AI OS Recovery Plan Preview"
TERMINAL_PLAN_STATUSES = {"completed", "failed"}
TERMINAL_STEP_STATUSES = {"completed", "failed"}
_PLAN_COUNTER = count(1)
_STEP_COUNTER = count(1)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def generate_plan_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return f"plan_{stamp}_{next(_PLAN_COUNTER):04d}"


def generate_step_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return f"step_{stamp}_{next(_STEP_COUNTER):04d}"


def normalize_optional_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_step_key(value, default: str) -> str:
    key = normalize_optional_text(value) or default
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in key)
    while "__" in safe:
        safe = safe.replace("__", "_")
    return safe.strip("_") or default


def shorten_text(value: str, limit: int = 120) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3].rstrip()}..."


def clamp_int(value: int | float, minimum: int = 0, maximum: int = 100) -> int:
    try:
        value = int(round(float(value)))
    except (TypeError, ValueError):
        value = minimum
    return max(minimum, min(int(value), maximum))


def parse_iso_timestamp(value) -> datetime | None:
    text = normalize_optional_text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def build_step_metadata(
    *,
    owner_hint: str,
    branch_id: str,
    execution_mode: str = "commit",
    timeout_seconds: int = 180,
    max_retries: int = 0,
    rollback_on_error: bool = True,
    compensation_action: str = "report_only",
    compensation_description: str = "",
    parent_operation_id: str | None = None,
    parent_branch_id: str | None = None,
) -> dict:
    metadata = {
        "owner_hint": owner_hint,
        "branch_id": str(branch_id or "main").strip() or "main",
        "execution_mode": str(execution_mode or "commit").strip() or "commit",
        "failure_policy": {
            "timeout_seconds": int(timeout_seconds),
            "max_retries": int(max_retries),
            "retry_backoff_seconds": 5,
            "degraded_mode": "report_only",
            "rollback_on_error": bool(rollback_on_error),
        },
        "compensation_plan": [
            {
                "action": compensation_action,
                "description": compensation_description or compensation_action.replace("_", " "),
                "params": {"owner_hint": owner_hint},
            }
        ],
    }
    if parent_operation_id:
        metadata["parent_operation_id"] = parent_operation_id
    if parent_branch_id and parent_branch_id != metadata["branch_id"]:
        metadata["parent_branch_id"] = parent_branch_id
    return metadata


def infer_recovery_owner_hint(replay_step: dict) -> tuple[str, list[str]]:
    text = " ".join(
        str(item or "")
        for item in [
            replay_step.get("summary"),
            replay_step.get("delta"),
        ]
    ).lower()

    if any(keyword in text for keyword in ("memory", "knowledge", "vector", "graph", "embed")):
        return "Memory Agent", ["memory-ingestion", "graph-build", "vector-memory"]
    if any(keyword in text for keyword in ("review", "analy", "research", "retriev", "inspect", "lineage")):
        return "Research Agent", ["retrieval", "analysis", "summarization"]
    return "Coding Agent", ["runtime", "integration", "delivery"]


RECOVERY_PHASE_ORDER = {
    "coordination": 0,
    "anchor_review": 1,
    "replay_execution": 2,
    "remediation": 3,
    "validation": 4,
}
DEFAULT_RECOVERY_REMEDIATION_POLICY = {
    "max_disrupted_replay_steps": 2,
    "mode": "pause_and_remediate",
    "max_parallel_steps": 1,
}
MAX_BRANCH_HEALTH_HISTORY_PER_BRANCH = 24
BRANCH_HEALTH_TREND_WINDOW = 6
BRANCH_HEALTH_DRIFT_WINDOW = 10
DEMO_RECOVERY_BRANCHES = (
    "demo/recovery-observe",
    "demo/recovery-remediation",
)


@dataclass
class PlanStepRecord:
    id: str
    key: str
    title: str
    preferred_role: str | None = None
    metadata: dict = field(default_factory=dict)
    branch_id: str = "main"
    dependency_keys: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    status: str = "planned"
    task_id: int | None = None
    operation_id: str | None = None
    created_at: str = field(default_factory=utc_now)
    queued_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    compensated_at: str | None = None
    compensation_status: str | None = None
    result: str | None = None
    last_error: str | None = None


@dataclass
class PlanRecord:
    id: str
    title: str
    source: str
    plan_kind: str = "operational"
    focus_area: str | None = None
    branch_id: str = "main"
    source_branch_id: str | None = None
    source_operation_id: str | None = None
    parent_plan_id: str | None = None
    max_parallel_steps: int = 1
    status: str = "planned"
    signature: str = ""
    context: dict = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    steps: list[PlanStepRecord] = field(default_factory=list)


class PlannerRuntime:
    def __init__(self, state_path: Path | None = None, *, runtime: AgentRuntime | None = None) -> None:
        paths = get_project_paths()
        self.state_path = state_path or paths.planner_runtime_file
        self.runtime = runtime or AGENT_RUNTIME
        self._lock = RLock()
        self._plans: list[PlanRecord] = []
        self._events: deque[dict] = deque(maxlen=100)
        self._branch_health_history: dict[str, list[dict]] = {}
        self._load_state()

    def _default_state(self) -> dict:
        return {
            "plans": [],
            "events": [],
            "branch_health_history": {},
            "last_updated": None,
        }

    def _record_fields(self, record_type) -> set[str]:
        return {item.name for item in fields(record_type)}

    def _restore_step_record(self, payload: dict) -> PlanStepRecord:
        allowed = self._record_fields(PlanStepRecord)
        data = {key: payload[key] for key in allowed if key in payload}
        return PlanStepRecord(**data)

    def _restore_plan_record(self, payload: dict) -> PlanRecord:
        allowed = self._record_fields(PlanRecord)
        data = {key: payload[key] for key in allowed if key in payload}
        steps = [self._restore_step_record(item) for item in payload.get("steps", []) if isinstance(item, dict)]
        data["steps"] = steps
        return PlanRecord(**data)

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

        plans: list[PlanRecord] = []
        for payload in state.get("plans", []):
            if not isinstance(payload, dict):
                continue
            try:
                plans.append(self._restore_plan_record(payload))
            except TypeError:
                continue

        events = [item for item in state.get("events", []) if isinstance(item, dict)]
        branch_health_history: dict[str, list[dict]] = {}
        for branch_id, items in dict(state.get("branch_health_history") or {}).items():
            normalized_branch_id = normalize_optional_text(branch_id)
            if not normalized_branch_id or not isinstance(items, list):
                continue
            branch_health_history[normalized_branch_id] = [
                dict(item)
                for item in items
                if isinstance(item, dict)
            ][-MAX_BRANCH_HEALTH_HISTORY_PER_BRANCH:]
        self._plans = plans
        self._events = deque(events[:100], maxlen=100)
        self._branch_health_history = branch_health_history

    def _save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        body = {
            "plans": [asdict(plan) for plan in self._plans],
            "events": list(self._events),
            "branch_health_history": self._branch_health_history,
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

    def _stabilization_playbook_snapshot(self, *, limit: int | None = None) -> dict:
        memory_items = MemoryEngine().get_all()
        return build_stabilization_playbooks(memory_items, limit=limit)

    def stabilization_playbooks_snapshot(self, *, limit: int = 10) -> dict:
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 10
        limit = max(1, min(limit, 50))
        playbook_snapshot = self._stabilization_playbook_snapshot(limit=limit)
        return {
            "status": "ok",
            "service": "AI OS Stabilization Playbooks",
            "playbook_counts": playbook_snapshot.get("playbook_counts", {}),
            "branches": list(playbook_snapshot.get("branches", []))[:limit],
        }

    def _build_signature(
        self,
        *,
        source: str,
        plan_kind: str,
        focus_area: str | None,
        branch_id: str,
        task_specs: list[dict],
    ) -> str:
        normalized_specs = []
        for index, task_spec in enumerate(task_specs, start=1):
            metadata = dict(task_spec.get("metadata", {}) or {})
            normalized_specs.append(
                {
                    "index": index,
                    "key": normalize_step_key(task_spec.get("step_key"), f"step_{index}"),
                    "title": str(task_spec.get("title", "")).strip(),
                    "preferred_role": normalize_optional_text(task_spec.get("preferred_role")),
                    "branch_id": str(metadata.get("branch_id") or branch_id or "main").strip() or "main",
                    "depends_on": [
                        normalize_step_key(dep, f"step_{dep_index}")
                        for dep_index, dep in enumerate(task_spec.get("depends_on", []), start=1)
                    ],
                }
            )
        return json.dumps(
            {
                "source": str(source).strip(),
                "plan_kind": str(plan_kind).strip() or "operational",
                "focus_area": normalize_optional_text(focus_area),
                "branch_id": branch_id,
                "steps": normalized_specs,
            },
            ensure_ascii=False,
            sort_keys=True,
        )

    def _find_open_plan_by_signature(self, signature: str) -> PlanRecord | None:
        for plan in self._plans:
            if plan.signature == signature and plan.status not in TERMINAL_PLAN_STATUSES:
                return plan
        return None

    def _find_plan(self, plan_id: str | None) -> PlanRecord | None:
        plan_id = normalize_optional_text(plan_id)
        if not plan_id:
            return None
        for plan in self._plans:
            if plan.id == plan_id:
                return plan
        return None

    def _find_step(self, plan: PlanRecord, step_id: str) -> PlanStepRecord | None:
        for step in plan.steps:
            if step.id == step_id:
                return step
        return None

    def _select_recovery_plan(
        self,
        *,
        plan_id: str | None = None,
        branch_id: str | None = None,
    ) -> PlanRecord | None:
        if plan_id:
            plan = self._find_plan(plan_id)
            if plan is not None and plan.plan_kind == "recovery":
                return plan
            return None

        normalized_branch_id = normalize_optional_text(branch_id)
        for plan in self._plans:
            if plan.plan_kind != "recovery":
                continue
            if normalized_branch_id and plan.branch_id != normalized_branch_id:
                continue
            if plan.status not in TERMINAL_PLAN_STATUSES:
                return plan

        for plan in self._plans:
            if plan.plan_kind != "recovery":
                continue
            if normalized_branch_id and plan.branch_id != normalized_branch_id:
                continue
            return plan

        return None

    def _plan_counts(self, plan: PlanRecord) -> dict:
        statuses = [step.status for step in plan.steps]
        return {
            "total": len(plan.steps),
            "planned": sum(1 for status in statuses if status == "planned"),
            "blocked": sum(1 for status in statuses if status == "blocked"),
            "queued": sum(1 for status in statuses if status == "queued"),
            "in_progress": sum(1 for status in statuses if status == "in_progress"),
            "completed": sum(1 for status in statuses if status == "completed"),
            "failed": sum(1 for status in statuses if status == "failed"),
        }

    def _runtime_task_index(self) -> dict[int, dict]:
        return {
            int(task["id"]): task
            for task in self.runtime.list_tasks()
            if int(task.get("id", 0) or 0) > 0
        }

    def _current_plan_step(self, plan: PlanRecord) -> PlanStepRecord | None:
        for status in ("failed", "in_progress", "queued", "planned", "blocked"):
            for step in plan.steps:
                if step.status == status:
                    return step
        return None

    def _child_plans(self, parent_plan_id: str, *, plan_kind: str | None = None) -> list[PlanRecord]:
        children = [
            plan
            for plan in self._plans
            if plan.parent_plan_id == parent_plan_id and (plan_kind is None or plan.plan_kind == plan_kind)
        ]
        children.sort(
            key=lambda item: (
                str(item.updated_at or item.created_at or ""),
                item.id,
            ),
            reverse=True,
        )
        return children

    def _latest_child_plan(self, parent_plan_id: str, *, plan_kind: str | None = None) -> PlanRecord | None:
        children = self._child_plans(parent_plan_id, plan_kind=plan_kind)
        for plan in children:
            if plan.status not in TERMINAL_PLAN_STATUSES:
                return plan
        return children[0] if children else None

    def _recovery_replay_steps(self, plan: PlanRecord) -> list[PlanStepRecord]:
        return [
            step
            for step in plan.steps
            if isinstance(step.metadata, dict) and step.metadata.get("recovery_phase") == "replay_execution"
        ]

    def _recovery_validation_steps(self, plan: PlanRecord) -> list[PlanStepRecord]:
        return [
            step
            for step in plan.steps
            if isinstance(step.metadata, dict) and step.metadata.get("recovery_phase") == "validation"
        ]

    def _recovery_remediation_policy(self, plan: PlanRecord) -> dict:
        raw_policy = dict((plan.context or {}).get("remediation_policy") or {})
        policy = dict(DEFAULT_RECOVERY_REMEDIATION_POLICY)
        policy.update(raw_policy)

        try:
            policy["max_disrupted_replay_steps"] = int(policy.get("max_disrupted_replay_steps", 2))
        except (TypeError, ValueError):
            policy["max_disrupted_replay_steps"] = 2
        policy["max_disrupted_replay_steps"] = max(1, min(policy["max_disrupted_replay_steps"], 6))

        try:
            policy["max_parallel_steps"] = int(policy.get("max_parallel_steps", 1))
        except (TypeError, ValueError):
            policy["max_parallel_steps"] = 1
        policy["max_parallel_steps"] = max(1, min(policy["max_parallel_steps"], 2))

        policy["mode"] = normalize_optional_text(policy.get("mode")) or "pause_and_remediate"
        current_step = self._current_plan_step(plan)
        current_phase = (
            normalize_optional_text((current_step.metadata or {}).get("recovery_phase"))
            if current_step is not None and isinstance(current_step.metadata, dict)
            else None
        ) or plan.status
        drift = self._branch_quality_drift_summary(
            plan.branch_id,
            current_plan_id=plan.id,
            current_plan_status=plan.status,
            current_phase=current_phase,
        )
        pressure_level = normalize_optional_text(drift.get("pressure_level")) or "low"
        adapted = False
        adaptation_notes: list[str] = []

        if pressure_level == "critical":
            previous_threshold = int(policy["max_disrupted_replay_steps"])
            policy["max_disrupted_replay_steps"] = max(1, previous_threshold - 1)
            policy["max_parallel_steps"] = 1
            adapted = adapted or policy["max_disrupted_replay_steps"] != previous_threshold
            adaptation_notes.append("critical branch pressure lowered remediation threshold")
        elif pressure_level == "high":
            previous_parallel = int(policy["max_parallel_steps"])
            policy["max_parallel_steps"] = 1
            adapted = adapted or policy["max_parallel_steps"] != previous_parallel
            adaptation_notes.append("high branch pressure serialized remediation execution")

        policy["pressure_level"] = pressure_level
        policy["pressure_score"] = int(drift.get("pressure_score", 0) or 0)
        policy["adapted_by_pressure"] = bool(adapted)
        policy["adaptation_summary"] = "; ".join(adaptation_notes) if adaptation_notes else None
        return policy

    def _recovery_remediation_state(self, plan: PlanRecord) -> dict:
        return dict((plan.context or {}).get("remediation_state") or {})

    def _update_recovery_remediation_state(self, plan: PlanRecord, **updates) -> dict:
        state = self._recovery_remediation_state(plan)
        for key, value in updates.items():
            if value is None:
                state.pop(key, None)
            else:
                state[key] = value
        plan.context["remediation_state"] = state
        plan.updated_at = utc_now()
        return state

    def _recovery_disruption_profile(self, plan: PlanRecord) -> dict:
        replay_steps = self._recovery_replay_steps(plan)
        disrupted_steps = [
            step
            for step in replay_steps
            if step.status == "failed" or step.compensation_status == "completed"
        ]
        failed_steps = [step for step in replay_steps if step.status == "failed"]
        compensated_steps = [step for step in replay_steps if step.compensation_status == "completed"]
        latest_step = disrupted_steps[-1] if disrupted_steps else None
        remediation_state = self._recovery_remediation_state(plan)
        try:
            resolved_disruption_count = int(remediation_state.get("resolved_disruption_count", 0) or 0)
        except (TypeError, ValueError):
            resolved_disruption_count = 0
        policy = self._recovery_remediation_policy(plan)
        new_disruption_count = max(len(disrupted_steps) - resolved_disruption_count, 0)

        return {
            "disrupted_count": len(disrupted_steps),
            "failed_count": len(failed_steps),
            "compensated_count": len(compensated_steps),
            "resolved_disruption_count": resolved_disruption_count,
            "new_disruption_count": new_disruption_count,
            "threshold": int(policy["max_disrupted_replay_steps"]),
            "requires_remediation": new_disruption_count >= int(policy["max_disrupted_replay_steps"]),
            "trigger_step_keys": [step.key for step in disrupted_steps[-3:]],
            "latest_step_key": latest_step.key if latest_step is not None else None,
            "latest_step_title": latest_step.title if latest_step is not None else None,
            "latest_operation_id": latest_step.operation_id if latest_step is not None else None,
            "latest_task_id": latest_step.task_id if latest_step is not None else None,
            "latest_error": latest_step.last_error if latest_step is not None else None,
        }

    def _recovery_remediation_summary(self, plan: PlanRecord) -> dict:
        remediation_plan = self._latest_child_plan(plan.id, plan_kind="remediation")
        remediation_state = self._recovery_remediation_state(plan)
        disruption = self._recovery_disruption_profile(plan)
        policy = self._recovery_remediation_policy(plan)
        current_step = self._current_plan_step(remediation_plan) if remediation_plan is not None else None

        required = bool(disruption["requires_remediation"])
        status = "not_required"
        if remediation_plan is not None:
            if remediation_plan.status in TERMINAL_PLAN_STATUSES:
                status = remediation_plan.status
            else:
                status = remediation_plan.status or "planned"
        elif required:
            status = "required"
        elif normalize_optional_text(remediation_state.get("status")):
            status = normalize_optional_text(remediation_state.get("status")) or "not_required"

        if status == "completed" and required:
            status = "required"

        active = remediation_plan is not None and remediation_plan.status not in TERMINAL_PLAN_STATUSES
        blocking = required and (active or remediation_plan is None or remediation_plan.status == "failed")

        return {
            "required": required,
            "active": active,
            "blocking_recovery": blocking,
            "status": status,
            "mode": policy["mode"],
            "threshold": int(policy["max_disrupted_replay_steps"]),
            "max_parallel_steps": int(policy.get("max_parallel_steps", 1) or 1),
            "pressure_level": policy.get("pressure_level"),
            "pressure_score": int(policy.get("pressure_score", 0) or 0),
            "adapted_by_pressure": bool(policy.get("adapted_by_pressure")),
            "adaptation_summary": normalize_optional_text(policy.get("adaptation_summary")),
            "disrupted_replay_steps": int(disruption["disrupted_count"]),
            "new_disruption_count": int(disruption["new_disruption_count"]),
            "resolved_disruption_count": int(disruption["resolved_disruption_count"]),
            "failed_replay_steps": int(disruption["failed_count"]),
            "compensated_replay_steps": int(disruption["compensated_count"]),
            "trigger_step_keys": list(disruption["trigger_step_keys"]),
            "latest_step_key": disruption["latest_step_key"],
            "latest_step_title": disruption["latest_step_title"],
            "latest_error": disruption["latest_error"],
            "plan_id": remediation_plan.id if remediation_plan is not None else normalize_optional_text(remediation_state.get("active_plan_id")),
            "plan_status": remediation_plan.status if remediation_plan is not None else None,
            "plan_title": remediation_plan.title if remediation_plan is not None else None,
            "step_counts": self._plan_counts(remediation_plan) if remediation_plan is not None else None,
            "current_step_key": current_step.key if current_step is not None else None,
            "current_step_title": current_step.title if current_step is not None else None,
            "triggered_at": remediation_state.get("triggered_at"),
            "completed_at": remediation_state.get("completed_at"),
            "last_completed_plan_id": remediation_state.get("last_completed_plan_id"),
        }

    def _get_branch_health_history(self, branch_id: str | None) -> list[dict]:
        normalized_branch_id = normalize_optional_text(branch_id) or "main"
        return [dict(item) for item in self._branch_health_history.get(normalized_branch_id, []) if isinstance(item, dict)]

    def _branch_health_record_signature(self, item: dict | None) -> tuple:
        payload = dict(item or {})
        return (
            normalize_optional_text(payload.get("branch_id")) or "main",
            normalize_optional_text(payload.get("plan_id")),
            normalize_optional_text(payload.get("plan_status")),
            normalize_optional_text(payload.get("current_phase")),
            normalize_optional_text(payload.get("status")),
            normalize_optional_text(payload.get("recommendation")),
            clamp_int(payload.get("quality_score", 0)),
            clamp_int(payload.get("confidence_score", 0)),
            normalize_optional_text(payload.get("remediation_status")),
            bool(payload.get("remediation_blocking")),
            bool(payload.get("validation_passed")),
            int(payload.get("disrupted_replay_steps", 0) or 0),
            int(payload.get("compensated_replay_steps", 0) or 0),
            normalize_optional_text(payload.get("planner_gate_mode")),
        )

    def _branch_health_observation_from_source(
        self,
        *,
        branch_id: str | None,
        plan_id: str | None = None,
        plan_status: str | None = None,
        current_phase: str | None = None,
        branch_health: dict | None = None,
        timestamp: str | None = None,
    ) -> dict | None:
        health = dict(branch_health or {})
        status = normalize_optional_text(health.get("status"))
        if not status:
            return None

        normalized_branch_id = normalize_optional_text(branch_id) or "main"
        trend = dict(health.get("trend") or {})
        planner_gate = dict(health.get("planner_gate") or {})
        return {
            "timestamp": timestamp or utc_now(),
            "branch_id": normalized_branch_id,
            "plan_id": normalize_optional_text(plan_id or health.get("plan_id")),
            "plan_status": normalize_optional_text(plan_status or health.get("plan_status")),
            "current_phase": normalize_optional_text(current_phase or health.get("current_phase")),
            "status": status,
            "recommendation": normalize_optional_text(health.get("recommendation")),
            "quality_score": clamp_int(health.get("quality_score", 0)),
            "confidence_score": clamp_int(health.get("confidence_score", 0)),
            "quality_grade": normalize_optional_text(health.get("quality_grade")),
            "confidence_level": normalize_optional_text(health.get("confidence_level")),
            "workflow_completed": bool(health.get("workflow_completed")),
            "validation_passed": bool(health.get("validation_passed")),
            "validation_required": bool(health.get("validation_required")),
            "remediation_used": bool(health.get("remediation_used")),
            "remediation_status": normalize_optional_text(health.get("remediation_status")),
            "remediation_blocking": bool(health.get("remediation_blocking")),
            "disrupted_replay_steps": int(health.get("disrupted_replay_steps", 0) or 0),
            "compensated_replay_steps": int(health.get("compensated_replay_steps", 0) or 0),
            "completed_replay_steps": int(health.get("completed_replay_steps", 0) or 0),
            "replay_step_count": int(health.get("replay_step_count", 0) or 0),
            "trend_direction": normalize_optional_text(trend.get("direction")),
            "planner_gate_mode": normalize_optional_text(planner_gate.get("mode")),
            "planner_gate_action": normalize_optional_text(planner_gate.get("recommended_action")),
        }

    def _branch_health_trend_summary(
        self,
        branch_id: str | None,
        *,
        current_health: dict | None = None,
        current_plan_id: str | None = None,
        current_plan_status: str | None = None,
        current_phase: str | None = None,
    ) -> dict:
        normalized_branch_id = normalize_optional_text(branch_id) or "main"
        observations = self._get_branch_health_history(normalized_branch_id)
        synthetic_observation = self._branch_health_observation_from_source(
            branch_id=normalized_branch_id,
            plan_id=current_plan_id,
            plan_status=current_plan_status,
            current_phase=current_phase,
            branch_health=current_health,
        )
        if synthetic_observation is not None:
            if not observations or self._branch_health_record_signature(observations[-1]) != self._branch_health_record_signature(synthetic_observation):
                observations.append(synthetic_observation)

        recent = observations[-BRANCH_HEALTH_TREND_WINDOW:]
        if not recent:
            return {
                "direction": "insufficient_history",
                "observation_count": 0,
                "recent_window": 0,
                "quality_delta": 0,
                "confidence_delta": 0,
                "recent_statuses": [],
                "summary": "branch health history is not available yet",
                "latest_timestamp": None,
            }

        latest = dict(recent[-1])
        latest_quality = clamp_int(latest.get("quality_score", 0))
        latest_confidence = clamp_int(latest.get("confidence_score", 0))
        previous_window = recent[:-1][-3:] if len(recent) > 1 else []
        if previous_window:
            baseline_quality = round(sum(clamp_int(item.get("quality_score", 0)) for item in previous_window) / len(previous_window))
            baseline_confidence = round(sum(clamp_int(item.get("confidence_score", 0)) for item in previous_window) / len(previous_window))
        else:
            baseline_quality = latest_quality
            baseline_confidence = latest_confidence

        quality_delta = int(latest_quality - baseline_quality)
        confidence_delta = int(latest_confidence - baseline_confidence)
        recent_statuses = [
            normalize_optional_text(item.get("status")) or "unknown"
            for item in recent
        ]
        latest_status = normalize_optional_text(latest.get("status")) or "unknown"
        status_window = set(recent_statuses[-4:])

        if len(recent) <= 1:
            direction = "insufficient_history"
        elif latest_status in {"blocked", "degraded"}:
            direction = "declining"
        elif "blocked" in status_window and any(item in status_window for item in {"healthy", "observe"}):
            direction = "volatile"
        elif len(status_window) >= 3:
            direction = "volatile"
        elif quality_delta >= 6 and confidence_delta >= 5:
            direction = "improving"
        elif quality_delta <= -6 or confidence_delta <= -6:
            direction = "declining"
        else:
            direction = "stable"

        drift_level = (
            "high" if max(abs(quality_delta), abs(confidence_delta)) >= 15 else
            "moderate" if max(abs(quality_delta), abs(confidence_delta)) >= 6 else
            "low"
        )
        if direction == "improving":
            summary = "branch health is improving across recent recovery observations"
        elif direction == "declining":
            summary = "branch health is declining and should tighten planner activity"
        elif direction == "volatile":
            summary = "branch health is volatile and should remain under close supervision"
        elif direction == "stable":
            summary = "branch health is stable across recent recovery observations"
        else:
            summary = "branch health needs more observations before trend analysis is reliable"

        return {
            "direction": direction,
            "drift_level": drift_level,
            "observation_count": len(observations),
            "recent_window": len(recent),
            "latest_status": latest_status,
            "latest_recommendation": normalize_optional_text(latest.get("recommendation")),
            "latest_quality_score": latest_quality,
            "latest_confidence_score": latest_confidence,
            "quality_delta": quality_delta,
            "confidence_delta": confidence_delta,
            "recent_statuses": recent_statuses[-5:],
            "latest_timestamp": latest.get("timestamp"),
            "summary": summary,
        }

    def _branch_quality_drift_summary(
        self,
        branch_id: str | None,
        *,
        current_health: dict | None = None,
        current_plan_id: str | None = None,
        current_plan_status: str | None = None,
        current_phase: str | None = None,
    ) -> dict:
        normalized_branch_id = normalize_optional_text(branch_id) or "main"
        observations = self._get_branch_health_history(normalized_branch_id)
        synthetic_observation = self._branch_health_observation_from_source(
            branch_id=normalized_branch_id,
            plan_id=current_plan_id,
            plan_status=current_plan_status,
            current_phase=current_phase,
            branch_health=current_health,
        )
        if synthetic_observation is not None:
            if not observations or self._branch_health_record_signature(observations[-1]) != self._branch_health_record_signature(synthetic_observation):
                observations.append(synthetic_observation)

        horizon = observations[-BRANCH_HEALTH_DRIFT_WINDOW:]
        if not horizon:
            return {
                "pressure_level": "insufficient_history",
                "pressure_score": 0,
                "observation_count": 0,
                "baseline_quality_score": 0,
                "baseline_confidence_score": 0,
                "latest_quality_score": 0,
                "latest_confidence_score": 0,
                "quality_delta": 0,
                "confidence_delta": 0,
                "recent_gate_modes": [],
                "recent_statuses": [],
                "summary": "branch quality drift is not available yet",
            }

        latest = dict(horizon[-1])
        latest_quality = clamp_int(latest.get("quality_score", 0))
        latest_confidence = clamp_int(latest.get("confidence_score", 0))
        baseline_window = horizon[:-1][-5:] if len(horizon) > 1 else []
        if baseline_window:
            baseline_quality = round(sum(clamp_int(item.get("quality_score", 0)) for item in baseline_window) / len(baseline_window))
            baseline_confidence = round(sum(clamp_int(item.get("confidence_score", 0)) for item in baseline_window) / len(baseline_window))
        else:
            baseline_quality = latest_quality
            baseline_confidence = latest_confidence

        quality_delta = int(latest_quality - baseline_quality)
        confidence_delta = int(latest_confidence - baseline_confidence)
        recent_gate_modes = [
            normalize_optional_text(item.get("planner_gate_mode")) or "unknown"
            for item in horizon[-6:]
        ]
        recent_statuses = [
            normalize_optional_text(item.get("status")) or "unknown"
            for item in horizon[-6:]
        ]
        guarded_count = sum(1 for item in recent_gate_modes if item == "guarded")
        restricted_count = sum(1 for item in recent_gate_modes if item == "restricted")
        blocked_count = sum(1 for item in recent_gate_modes if item == "blocked")
        degraded_count = sum(1 for item in recent_statuses if item in {"degraded", "blocked"})
        observe_count = sum(1 for item in recent_statuses if item == "observe")
        recovering_count = sum(1 for item in recent_statuses if item in {"recovering", "verifying"})

        pressure_score = 0
        pressure_score += min(guarded_count, 3)
        pressure_score += restricted_count * 2
        pressure_score += blocked_count * 3
        pressure_score += degraded_count * 2
        pressure_score += 1 if observe_count >= 3 else 0
        pressure_score += 1 if recovering_count >= 2 else 0
        if quality_delta <= -12 or confidence_delta <= -12:
            pressure_score += 2
        elif quality_delta <= -6 or confidence_delta <= -6:
            pressure_score += 1
        if quality_delta >= 8 and confidence_delta >= 8 and pressure_score > 0:
            pressure_score = max(0, pressure_score - 1)

        latest_gate_mode = recent_gate_modes[-1] if recent_gate_modes else "unknown"
        latest_status = recent_statuses[-1] if recent_statuses else "unknown"
        if latest_gate_mode == "blocked" or blocked_count > 0:
            pressure_level = "critical"
        elif pressure_score >= 7 or restricted_count >= 2 or degraded_count >= 2:
            pressure_level = "high"
        elif pressure_score >= 4 or guarded_count >= 2 or observe_count >= 2:
            pressure_level = "medium"
        else:
            pressure_level = "low"

        if pressure_level == "critical":
            summary = "branch accumulated critical pressure and should remain tightly constrained"
        elif pressure_level == "high":
            summary = "branch drift remains elevated and should restrict normal planner activity"
        elif pressure_level == "medium":
            summary = "branch drift is noticeable and should stay under guarded monitoring"
        elif latest_status in {"healthy"} and quality_delta >= 0 and confidence_delta >= 0:
            summary = "branch drift is low and quality remains stable"
        else:
            summary = "branch drift is currently low"

        return {
            "pressure_level": pressure_level,
            "pressure_score": int(pressure_score),
            "observation_count": len(observations),
            "horizon_window": len(horizon),
            "baseline_quality_score": int(baseline_quality),
            "baseline_confidence_score": int(baseline_confidence),
            "latest_quality_score": latest_quality,
            "latest_confidence_score": latest_confidence,
            "quality_delta": quality_delta,
            "confidence_delta": confidence_delta,
            "recent_gate_modes": recent_gate_modes,
            "recent_statuses": recent_statuses,
            "guarded_count": guarded_count,
            "restricted_count": restricted_count,
            "blocked_count": blocked_count,
            "degraded_count": degraded_count,
            "observe_count": observe_count,
            "recovering_count": recovering_count,
            "summary": summary,
        }

    def _planner_gate_summary(
        self,
        branch_id: str | None,
        *,
        plan_kind: str | None = None,
        current_health: dict | None = None,
        trend: dict | None = None,
        drift: dict | None = None,
        playbook: dict | None = None,
    ) -> dict:
        normalized_branch_id = normalize_optional_text(branch_id) or "main"
        health = dict(current_health or {})
        trend = dict(trend or self._branch_health_trend_summary(normalized_branch_id, current_health=health))
        drift = dict(drift or self._branch_quality_drift_summary(normalized_branch_id, current_health=health))
        latest_status = normalize_optional_text(health.get("status")) or normalize_optional_text(trend.get("latest_status")) or "unknown"
        recommendation = normalize_optional_text(health.get("recommendation")) or normalize_optional_text(trend.get("latest_recommendation")) or "inspect_workflow"
        direction = normalize_optional_text(trend.get("direction")) or "insufficient_history"
        quality_score = clamp_int(health.get("quality_score", trend.get("latest_quality_score", 0)))
        confidence_score = clamp_int(health.get("confidence_score", trend.get("latest_confidence_score", 0)))
        pressure_level = normalize_optional_text(drift.get("pressure_level")) or "low"
        playbook_payload = dict(playbook or {})
        playbook_reuse_ready = bool(playbook_payload.get("reuse_ready"))
        playbook_support_level = normalize_optional_text(playbook_payload.get("support_level")) or "none"
        playbook_action_count = len(playbook_payload.get("recommended_actions", []) or [])
        try:
            pressure_score = int(drift.get("pressure_score", 0) or 0)
        except (TypeError, ValueError):
            pressure_score = 0

        if latest_status == "blocked" or recommendation == "pause_and_review":
            mode = "blocked"
            recommended_action = "pause_and_review"
            summary = "planner should pause non-recovery work until the branch clears remediation pressure"
            allowed_plan_kinds = ["recovery", "remediation", "branch_stabilization"]
            parallel_limit = 1
        elif latest_status == "degraded" or recommendation == "manual_review":
            mode = "restricted"
            recommended_action = "manual_review"
            summary = "planner should hold operational work on this branch and prefer recovery-oriented actions"
            allowed_plan_kinds = ["recovery", "remediation", "branch_stabilization"]
            parallel_limit = 1
        elif latest_status in {"recovering", "verifying"}:
            mode = "restricted"
            recommended_action = "wait_for_recovery_completion"
            summary = "planner should avoid new operational work while branch recovery is still running"
            allowed_plan_kinds = ["recovery", "remediation", "branch_stabilization"]
            parallel_limit = 1
        elif pressure_level in {"critical", "high"}:
            mode = "restricted"
            recommended_action = "apply_stabilization_playbook" if playbook_reuse_ready else "stabilize_branch_pressure"
            summary = (
                "planner should temporarily restrict operational work and apply the learned branch stabilization playbook"
                if playbook_reuse_ready
                else "planner should temporarily restrict operational work because branch quality drift remains elevated"
            )
            allowed_plan_kinds = ["recovery", "remediation", "branch_stabilization"]
            parallel_limit = 1
        elif latest_status == "observe" or recommendation == "heightened_monitoring" or direction in {"declining", "volatile"}:
            mode = "guarded"
            recommended_action = "review_stabilization_playbook" if playbook_reuse_ready else "heightened_monitoring"
            summary = (
                "planner may continue, but should review the branch stabilization playbook while running guarded"
                if playbook_reuse_ready
                else "planner may continue, but should run the branch in guarded mode with reduced parallelism"
            )
            allowed_plan_kinds = ["operational", "recovery", "remediation", "branch_stabilization"]
            parallel_limit = 1
        elif pressure_level == "medium":
            mode = "guarded"
            recommended_action = "heightened_monitoring"
            summary = "planner may continue, but branch drift history is elevated enough to stay guarded"
            allowed_plan_kinds = ["operational", "recovery", "remediation", "branch_stabilization"]
            parallel_limit = 1
        else:
            mode = "open"
            recommended_action = "normal_operation"
            summary = "planner can run the branch normally"
            allowed_plan_kinds = ["operational", "recovery", "remediation", "branch_stabilization"]
            parallel_limit = None

        normalized_plan_kind = normalize_optional_text(plan_kind)
        allow_execution = normalized_plan_kind in allowed_plan_kinds if normalized_plan_kind else "operational" in allowed_plan_kinds
        return {
            "branch_id": normalized_branch_id,
            "mode": mode,
            "recommended_action": recommended_action,
            "summary": summary,
            "allow_execution": bool(allow_execution),
            "allow_new_operational_steps": "operational" in allowed_plan_kinds,
            "parallel_limit": parallel_limit,
            "allowed_plan_kinds": allowed_plan_kinds,
            "source_status": latest_status,
            "source_recommendation": recommendation,
            "trend_direction": direction,
            "quality_score": quality_score,
            "confidence_score": confidence_score,
            "pressure_level": pressure_level,
            "pressure_score": pressure_score,
            "drift_summary": normalize_optional_text(drift.get("summary")),
            "playbook_reuse_ready": playbook_reuse_ready,
            "playbook_support_level": playbook_support_level,
            "playbook_action_count": playbook_action_count,
        }

    def _execution_dispatch_policy(
        self,
        branch_id: str | None,
        *,
        plan_kind: str | None = None,
        current_health: dict | None = None,
        trend: dict | None = None,
        drift: dict | None = None,
        playbook: dict | None = None,
    ) -> dict:
        normalized_branch_id = normalize_optional_text(branch_id) or "main"
        normalized_plan_kind = normalize_optional_text(plan_kind) or "operational"
        gate = self._planner_gate_summary(
            normalized_branch_id,
            plan_kind=normalized_plan_kind,
            current_health=current_health,
            trend=trend,
            drift=drift,
            playbook=playbook,
        )
        pressure_level = normalize_optional_text(gate.get("pressure_level")) or "low"
        playbook_payload = dict(playbook or {})
        playbook_reuse_ready = bool(playbook_payload.get("reuse_ready"))
        playbook_support_level = normalize_optional_text(playbook_payload.get("support_level")) or "none"
        try:
            pressure_score = int(gate.get("pressure_score", 0) or 0)
        except (TypeError, ValueError):
            pressure_score = 0

        allow_dispatch = bool(gate.get("allow_execution", True))
        mode = "open"
        max_assignments_for_branch = None
        summary = "dispatch can proceed normally for this branch"

        if not allow_dispatch:
            mode = "blocked"
            max_assignments_for_branch = 0
            summary = "dispatch is blocked because planner gate does not allow new work on this branch"
        elif normalized_plan_kind == "operational":
            if str(gate.get("mode")) == "guarded":
                mode = "guarded"
                max_assignments_for_branch = 1
                summary = "operational dispatch should stay serialized while the branch remains guarded"
        elif normalized_plan_kind in {"recovery", "remediation", "branch_stabilization"}:
            if pressure_level in {"critical", "high"} or str(gate.get("mode")) == "restricted":
                mode = "restricted"
                max_assignments_for_branch = 1
                summary = (
                    "recovery-oriented dispatch should stay serialized and follow the branch stabilization playbook"
                    if playbook_reuse_ready
                    else "recovery-oriented dispatch should stay serialized while branch pressure remains elevated"
                )
            elif pressure_level == "medium" or str(gate.get("mode")) == "guarded":
                mode = "guarded"
                max_assignments_for_branch = 2
                summary = (
                    "recovery-oriented dispatch should stay constrained and review the branch stabilization playbook"
                    if playbook_reuse_ready
                    else "recovery-oriented dispatch should stay constrained while the branch remains under observation"
                )

        return {
            "branch_id": normalized_branch_id,
            "plan_kind": normalized_plan_kind,
            "mode": mode,
            "allow_dispatch": allow_dispatch,
            "max_assignments_for_branch": max_assignments_for_branch,
            "recommended_action": gate.get("recommended_action"),
            "summary": summary,
            "pressure_level": pressure_level,
            "pressure_score": pressure_score,
            "gate_mode": gate.get("mode"),
            "gate_summary": gate.get("summary"),
            "playbook_reuse_ready": playbook_reuse_ready,
            "playbook_support_level": playbook_support_level,
        }

    def _branch_health_summary(
        self,
        branch_id: str | None,
        *,
        runtime_tasks: dict[int, dict] | None = None,
        playbook_lookup: dict[str, dict] | None = None,
    ) -> dict | None:
        normalized_branch_id = normalize_optional_text(branch_id) or "main"
        if playbook_lookup is None:
            playbook_lookup = {
                str(item.get("branch_id") or "main").strip() or "main": dict(item)
                for item in self._stabilization_playbook_snapshot(limit=100).get("branches", [])
                if isinstance(item, dict)
            }
        playbook = dict((playbook_lookup or {}).get(normalized_branch_id) or {})
        recovery_plan = self._select_recovery_plan(branch_id=normalized_branch_id)
        workflow = None
        current_health = None
        if recovery_plan is not None:
            workflow = self._recovery_workflow_summary(recovery_plan, runtime_tasks=runtime_tasks)
            current_health = dict(workflow.get("branch_health") or {})

        latest_record = self._get_branch_health_history(normalized_branch_id)[-1] if self._get_branch_health_history(normalized_branch_id) else None
        if not current_health and latest_record is None:
            return None

        trend = dict((current_health or {}).get("trend") or self._branch_health_trend_summary(
            normalized_branch_id,
            current_health=current_health,
            current_plan_id=recovery_plan.id if recovery_plan is not None else normalize_optional_text((latest_record or {}).get("plan_id")),
            current_plan_status=recovery_plan.status if recovery_plan is not None else normalize_optional_text((latest_record or {}).get("plan_status")),
            current_phase=workflow.get("current_phase") if workflow else normalize_optional_text((latest_record or {}).get("current_phase")),
        ))
        drift = dict((current_health or {}).get("quality_drift") or self._branch_quality_drift_summary(
            normalized_branch_id,
            current_health=current_health,
            current_plan_id=recovery_plan.id if recovery_plan is not None else normalize_optional_text((latest_record or {}).get("plan_id")),
            current_plan_status=recovery_plan.status if recovery_plan is not None else normalize_optional_text((latest_record or {}).get("plan_status")),
            current_phase=workflow.get("current_phase") if workflow else normalize_optional_text((latest_record or {}).get("current_phase")),
        ))
        planner_gate = self._planner_gate_summary(
            normalized_branch_id,
            current_health=current_health or latest_record,
            trend=trend,
            drift=drift,
            playbook=playbook,
        )
        dispatch_policy = self._execution_dispatch_policy(
            normalized_branch_id,
            current_health=current_health or latest_record,
            trend=trend,
            drift=drift,
            playbook=playbook,
        )
        source = dict(current_health or latest_record or {})
        return {
            "branch_id": normalized_branch_id,
            "plan_id": recovery_plan.id if recovery_plan is not None else normalize_optional_text(source.get("plan_id")),
            "plan_status": workflow.get("status") if workflow else normalize_optional_text(source.get("plan_status")),
            "current_phase": workflow.get("current_phase") if workflow else normalize_optional_text(source.get("current_phase")),
            "status": normalize_optional_text(source.get("status")),
            "recommendation": normalize_optional_text(source.get("recommendation")),
            "quality_score": clamp_int(source.get("quality_score", trend.get("latest_quality_score", 0))),
            "confidence_score": clamp_int(source.get("confidence_score", trend.get("latest_confidence_score", 0))),
            "summary": normalize_optional_text(source.get("summary")) or trend.get("summary"),
            "last_updated": trend.get("latest_timestamp") or (latest_record or {}).get("timestamp"),
            "observation_count": int(trend.get("observation_count", 0) or 0),
            "trend": trend,
            "quality_drift": drift,
            "planner_gate": planner_gate,
            "dispatch_policy": dispatch_policy,
            "stabilization_playbook": playbook or None,
        }

    def _branch_recovery_signal(
        self,
        *,
        branch_id: str | None,
        anchor_snapshot_id: str | None,
        replay_step_count: int,
    ) -> dict | None:
        normalized_branch_id = normalize_optional_text(branch_id) or "main"
        history = self._get_branch_health_history(normalized_branch_id)
        latest_record = history[-1] if history else None
        if latest_record is None:
            return None

        if normalize_optional_text(latest_record.get("current_phase")) != "stabilization":
            return None

        trend = self._branch_health_trend_summary(
            normalized_branch_id,
            current_health=latest_record,
            current_plan_id=normalize_optional_text(latest_record.get("plan_id")),
            current_plan_status=normalize_optional_text(latest_record.get("plan_status")),
            current_phase=normalize_optional_text(latest_record.get("current_phase")),
        )
        drift = self._branch_quality_drift_summary(
            normalized_branch_id,
            current_health=latest_record,
            current_plan_id=normalize_optional_text(latest_record.get("plan_id")),
            current_plan_status=normalize_optional_text(latest_record.get("plan_status")),
            current_phase=normalize_optional_text(latest_record.get("current_phase")),
        )
        planner_gate = self._planner_gate_summary(
            normalized_branch_id,
            plan_kind="recovery",
            current_health=latest_record,
            trend=trend,
            drift=drift,
            playbook={},
        )
        dispatch_policy = self._execution_dispatch_policy(
            normalized_branch_id,
            plan_kind="recovery",
            current_health=latest_record,
            trend=trend,
            drift=drift,
            playbook={},
        )

        status = normalize_optional_text(latest_record.get("status"))
        recommendation = normalize_optional_text(latest_record.get("recommendation"))
        advisory = None
        if status == "observe" and recommendation == "heightened_monitoring":
            advisory = "heightened_monitoring_during_replay"
        elif status == "degraded" and recommendation == "manual_review":
            advisory = "manual_review_before_replay"

        return {
            "status": status,
            "recommendation": recommendation,
            "policy_scope": "recovery_preview",
            "planner_gate_scope": "recovery",
            "dispatch_policy_scope": "recovery",
            "planner_gate_mode": normalize_optional_text(planner_gate.get("mode")),
            "dispatch_policy_mode": normalize_optional_text(dispatch_policy.get("mode")),
            "pressure_level": normalize_optional_text(drift.get("pressure_level")),
            "anchor_snapshot_id": normalize_optional_text(anchor_snapshot_id),
            "replay_step_count": int(replay_step_count),
            "advisory": advisory,
        }

    def _latest_stabilization_branch_health_record(self, branch_id: str | None) -> dict | None:
        normalized_branch_id = normalize_optional_text(branch_id) or "main"
        history = self._get_branch_health_history(normalized_branch_id)
        latest_record = history[-1] if history else None
        if latest_record is None:
            return None
        if normalize_optional_text(latest_record.get("current_phase")) != "stabilization":
            return None
        return dict(latest_record)

    def _branch_recovery_signal_is_meaningful(self, signal: dict | None) -> bool:
        payload = dict(signal or {})
        status = normalize_optional_text(payload.get("status"))
        recommendation = normalize_optional_text(payload.get("recommendation"))
        return bool(
            status in {"observe", "degraded"}
            or recommendation in {"heightened_monitoring", "manual_review"}
        )

    def _recovery_continuity_metadata(
        self,
        *,
        branch_recovery_signal: dict | None,
        anchor_bias: dict | None,
        branch_id: str | None,
        anchor_snapshot: dict | None,
        operation_id: str | None,
    ) -> dict | None:
        signal = dict(branch_recovery_signal or {})
        bias = dict(anchor_bias or {})
        signal_meaningful = self._branch_recovery_signal_is_meaningful(signal)
        bias_meaningful = bool(bias) and (
            bias.get("applied") is True
            or signal_meaningful
        )
        if not signal_meaningful and not bias_meaningful:
            return None

        anchor = dict(anchor_snapshot or {})
        snapshot_id = (
            normalize_optional_text(anchor.get("snapshot_id"))
            or normalize_optional_text(signal.get("anchor_snapshot_id"))
            or normalize_optional_text(bias.get("selected_anchor_snapshot_id"))
        )
        payload = {
            "policy_scope": normalize_optional_text(signal.get("policy_scope")) or "recovery_preview",
            "planner_gate_scope": normalize_optional_text(signal.get("planner_gate_scope")) or "recovery",
            "dispatch_policy_scope": normalize_optional_text(signal.get("dispatch_policy_scope")) or "recovery",
            "branch_id": (
                normalize_optional_text(branch_id)
                or normalize_optional_text(signal.get("branch_id"))
                or normalize_optional_text(bias.get("branch_id"))
                or "main"
            ),
            "snapshot_id": snapshot_id,
            "anchor_snapshot_id": snapshot_id,
        }
        if operation_id is not None:
            payload["operation_id"] = operation_id
        if signal:
            payload["branch_recovery_signal"] = signal
        if bias:
            payload["anchor_bias"] = bias
        return payload

    def _latest_same_branch_snapshot_after(
        self,
        *,
        branch_id: str | None,
        threshold: str | None,
    ) -> dict | None:
        normalized_branch_id = normalize_optional_text(branch_id) or "main"
        threshold_dt = parse_iso_timestamp(threshold)
        if threshold_dt is None:
            return None

        snapshot_listing = SNAPSHOT_LINEAGE.snapshot(branch_id=normalized_branch_id, limit=200)
        for item in snapshot_listing.get("snapshots", []):
            if not isinstance(item, dict):
                continue
            snapshot = dict(item)
            if (normalize_optional_text(snapshot.get("branch_id")) or "main") != normalized_branch_id:
                continue
            created_at = parse_iso_timestamp(snapshot.get("created_at"))
            if created_at is not None and created_at >= threshold_dt:
                return snapshot
        return None

    def _branch_stabilization_health_summary(self, plan: PlanRecord) -> dict | None:
        if plan.plan_kind != "branch_stabilization":
            return None

        plan_status = normalize_optional_text(plan.status)
        if plan_status not in TERMINAL_PLAN_STATUSES:
            return None

        step_counts = self._plan_counts(plan)
        completed_steps = int(step_counts.get("completed", 0) or 0)
        failed_steps = int(step_counts.get("failed", 0) or 0)
        total_steps = int(step_counts.get("total", 0) or 0)
        focus_area = normalize_optional_text(plan.focus_area) or "branch_stabilization"

        if plan_status == "completed":
            return {
                "status": "observe",
                "recommendation": "heightened_monitoring",
                "quality_score": 78,
                "confidence_score": 74,
                "summary": (
                    "branch stabilization completed; keep the branch under heightened monitoring while learned controls settle "
                    f"({completed_steps}/{total_steps} steps completed, focus={focus_area})"
                ),
            }

        return {
            "status": "degraded",
            "recommendation": "manual_review",
            "quality_score": 48,
            "confidence_score": 42,
            "summary": (
                "branch stabilization failed; require manual review before normal branch activity resumes "
                f"({failed_steps}/{total_steps} failed steps, focus={focus_area})"
            ),
        }

    def _record_branch_health_observation(self, plan: PlanRecord, *, runtime_tasks: dict[int, dict] | None = None) -> bool:
        branch_health = None
        current_phase = None

        if plan.plan_kind == "recovery":
            workflow = self._recovery_workflow_summary(plan, runtime_tasks=runtime_tasks)
            branch_health = workflow.get("branch_health")
            current_phase = workflow.get("current_phase")
        elif plan.plan_kind == "branch_stabilization":
            branch_health = self._branch_stabilization_health_summary(plan)
            current_phase = "stabilization" if branch_health is not None else None
        else:
            return False

        observation = self._branch_health_observation_from_source(
            branch_id=plan.branch_id,
            plan_id=plan.id,
            plan_status=plan.status,
            current_phase=current_phase,
            branch_health=branch_health,
        )
        if observation is None:
            return False

        branch_id = observation["branch_id"]
        history = self._branch_health_history.setdefault(branch_id, [])
        if history and self._branch_health_record_signature(history[-1]) == self._branch_health_record_signature(observation):
            return False

        history.append(observation)
        self._branch_health_history[branch_id] = history[-MAX_BRANCH_HEALTH_HISTORY_PER_BRANCH:]
        return True

    def _recovery_branch_health_summary(
        self,
        plan: PlanRecord,
        *,
        current_phase: str | None,
        playbook_lookup: dict[str, dict] | None = None,
    ) -> dict:
        if playbook_lookup is None:
            playbook_lookup = {
                str(item.get("branch_id") or "main").strip() or "main": dict(item)
                for item in self._stabilization_playbook_snapshot(limit=100).get("branches", [])
                if isinstance(item, dict)
            }
        playbook = dict((playbook_lookup or {}).get(str(plan.branch_id or "main").strip() or "main") or {})
        remediation = self._recovery_remediation_summary(plan)
        replay_steps = self._recovery_replay_steps(plan)
        validation_steps = self._recovery_validation_steps(plan)
        remediation_cycles = len(self._child_plans(plan.id, plan_kind="remediation"))
        alignment_only = bool(plan.context.get("recovery_alignment_only"))
        workflow_completed = plan.status == "completed"

        completed_validation_steps = sum(1 for step in validation_steps if step.status == "completed")
        validation_required = bool(validation_steps) and not alignment_only
        validation_passed = (
            completed_validation_steps == len(validation_steps)
            if validation_steps
            else bool(alignment_only and workflow_completed)
        )

        disrupted_replay_steps = int(remediation.get("disrupted_replay_steps", 0) or 0)
        compensated_replay_steps = int(remediation.get("compensated_replay_steps", 0) or 0)
        remediation_used = remediation_cycles > 0 or bool(remediation.get("completed_at")) or bool(remediation.get("active"))
        remediation_failed = remediation.get("status") == "failed"
        remediation_blocking = bool(remediation.get("blocking_recovery"))

        quality_score = 100
        quality_score -= min(disrupted_replay_steps * 8, 24)
        quality_score -= 6 if compensated_replay_steps > 0 else 0
        quality_score -= 8 if remediation_used else 0
        quality_score -= 20 if remediation_failed else 0
        quality_score -= 24 if remediation_blocking else 0
        quality_score -= 18 if validation_required and not validation_passed else 0
        quality_score -= 10 if plan.status not in TERMINAL_PLAN_STATUSES else 0
        quality_score = clamp_int(quality_score)

        confidence_score = 100
        confidence_score -= min(disrupted_replay_steps * 8, 24)
        confidence_score -= 10 if remediation_used else 0
        confidence_score -= 25 if remediation_failed else 0
        confidence_score -= 20 if remediation_blocking else 0
        confidence_score -= 18 if validation_required and not validation_passed else 0
        confidence_score -= 10 if plan.status not in TERMINAL_PLAN_STATUSES else 0
        confidence_score = clamp_int(confidence_score)

        reasons: list[str] = []
        if disrupted_replay_steps:
            reasons.append(f"disrupted replay steps: {disrupted_replay_steps}")
        if compensated_replay_steps:
            reasons.append(f"compensated replay steps: {compensated_replay_steps}")
        if remediation_used:
            reasons.append(f"remediation cycles: {remediation_cycles}")
        if validation_required and validation_passed:
            reasons.append("validation completed")
        elif validation_required:
            reasons.append("validation incomplete")
        if remediation_blocking:
            reasons.append("recovery paused on remediation")
        if remediation_failed:
            reasons.append("remediation failed")

        if remediation_blocking:
            status = "blocked"
            recommendation = "pause_and_review"
        elif plan.status == "failed" or remediation_failed:
            status = "degraded"
            recommendation = "manual_review"
        elif plan.status != "completed":
            status = "verifying" if current_phase == "validation" else "recovering"
            recommendation = "continue_monitoring"
        elif quality_score >= 90 and confidence_score >= 90 and disrupted_replay_steps == 0 and not remediation_used:
            status = "healthy"
            recommendation = "normal_operation"
        elif quality_score >= 70 and confidence_score >= 65:
            status = "observe"
            recommendation = "heightened_monitoring"
        else:
            status = "degraded"
            recommendation = "manual_review"

        quality_grade = (
            "A" if quality_score >= 90 else
            "B" if quality_score >= 80 else
            "C" if quality_score >= 70 else
            "D" if quality_score >= 55 else
            "E"
        )
        confidence_level = (
            "high" if confidence_score >= 85 else
            "medium" if confidence_score >= 65 else
            "low"
        )

        if status == "healthy":
            summary = "branch is healthy and recovery quality is high"
        elif status == "observe":
            summary = "branch recovered successfully but should stay under observation"
        elif status == "blocked":
            summary = "branch recovery is paused pending remediation progress"
        elif status == "verifying":
            summary = "branch is in post-recovery validation"
        elif status == "recovering":
            summary = "branch recovery is still in progress"
        else:
            summary = "branch remains degraded and needs manual review"

        summary_payload = {
            "status": status,
            "recommendation": recommendation,
            "summary": summary,
            "quality_score": quality_score,
            "quality_grade": quality_grade,
            "confidence_score": confidence_score,
            "confidence_level": confidence_level,
            "workflow_completed": workflow_completed,
            "current_phase": current_phase,
            "validation_required": validation_required,
            "validation_passed": validation_passed,
            "validation_completed_steps": completed_validation_steps,
            "validation_total_steps": len(validation_steps),
            "remediation_used": remediation_used,
            "remediation_cycles": remediation_cycles,
            "remediation_status": remediation.get("status"),
            "remediation_blocking": remediation_blocking,
            "disrupted_replay_steps": disrupted_replay_steps,
            "compensated_replay_steps": compensated_replay_steps,
            "completed_replay_steps": sum(1 for step in replay_steps if step.status == "completed"),
            "replay_step_count": len(replay_steps),
            "reasons": reasons,
        }
        trend = self._branch_health_trend_summary(
            plan.branch_id,
            current_health=summary_payload,
            current_plan_id=plan.id,
            current_plan_status=plan.status,
            current_phase=current_phase,
        )
        summary_payload["trend"] = trend
        drift = self._branch_quality_drift_summary(
            plan.branch_id,
            current_health=summary_payload,
            current_plan_id=plan.id,
            current_plan_status=plan.status,
            current_phase=current_phase,
        )
        summary_payload["quality_drift"] = drift
        summary_payload["planner_gate"] = self._planner_gate_summary(
            plan.branch_id,
            current_health=summary_payload,
            trend=trend,
            drift=drift,
            playbook=playbook,
        )
        summary_payload["dispatch_policy"] = self._execution_dispatch_policy(
            plan.branch_id,
            plan_kind=plan.plan_kind,
            current_health=summary_payload,
            trend=trend,
            drift=drift,
            playbook=playbook,
        )
        summary_payload["stabilization_playbook"] = playbook or None
        return summary_payload

    def _build_recovery_remediation_task_specs(
        self,
        plan: PlanRecord,
        *,
        disruption: dict,
    ) -> list[dict]:
        branch_id = str(plan.branch_id or "main").strip() or "main"
        source_operation_id = disruption.get("latest_operation_id") or plan.source_operation_id
        trigger_title = disruption.get("latest_step_title") or f"recovery disruption on {branch_id}"
        trigger_error = disruption.get("latest_error") or "recovery disruption budget reached"
        trigger_keys = list(disruption.get("trigger_step_keys") or [])

        return [
            {
                "step_key": "coordinate_recovery_remediation",
                "title": f"Coordinate recovery remediation for branch: {branch_id}",
                "preferred_role": "manager",
                "metadata": {
                    **build_step_metadata(
                        owner_hint="Development Manager",
                        branch_id=branch_id,
                        execution_mode="simulate",
                        parent_operation_id=source_operation_id,
                        parent_branch_id=plan.source_branch_id,
                        compensation_action="record_recovery_remediation_decision",
                        compensation_description="Preserve the remediation coordination trace even if the mitigation plan pauses.",
                    ),
                    "required_capabilities": ["planning", "coordination", "recovery"],
                    "remediation_phase": "coordination",
                    "remediation_step_kind": "coordinate_recovery_remediation",
                    "recovery_parent_plan_id": plan.id,
                    "recovery_trigger_step_keys": trigger_keys,
                },
            },
            {
                "step_key": "analyze_recovery_disruption",
                "depends_on": ["coordinate_recovery_remediation"],
                "title": f"Analyze repeated recovery failure pattern: {shorten_text(trigger_title, limit=90)}",
                "preferred_role": "worker",
                "metadata": {
                    **build_step_metadata(
                        owner_hint="Research Agent",
                        branch_id=branch_id,
                        execution_mode="simulate",
                        parent_operation_id=source_operation_id,
                        parent_branch_id=plan.source_branch_id,
                        compensation_action="record_recovery_failure_analysis",
                        compensation_description="Keep the remediation analysis trace even if deeper investigation cannot complete.",
                    ),
                    "required_capabilities": ["analysis", "retrieval", "summarization"],
                    "remediation_phase": "analysis",
                    "remediation_step_kind": "analyze_recovery_disruption",
                    "recovery_parent_plan_id": plan.id,
                    "recovery_trigger_error": trigger_error,
                    "recovery_trigger_step_keys": trigger_keys,
                },
            },
            {
                "step_key": "stabilize_recovery_branch_state",
                "depends_on": ["analyze_recovery_disruption"],
                "title": f"Stabilize recovery branch state after repeated failures: {branch_id}",
                "preferred_role": "worker",
                "metadata": {
                    **build_step_metadata(
                        owner_hint="Coding Agent",
                        branch_id=branch_id,
                        execution_mode="commit",
                        timeout_seconds=240,
                        parent_operation_id=source_operation_id,
                        parent_branch_id=plan.source_branch_id,
                        compensation_action="record_branch_stabilization_attempt",
                        compensation_description="Preserve the branch stabilization trace if mitigation cannot be completed safely.",
                    ),
                    "required_capabilities": ["runtime", "integration", "delivery"],
                    "remediation_phase": "stabilization",
                    "remediation_step_kind": "stabilize_recovery_branch_state",
                    "recovery_parent_plan_id": plan.id,
                    "recovery_trigger_step_keys": trigger_keys,
                },
            },
            {
                "step_key": "approve_recovery_resume",
                "depends_on": ["stabilize_recovery_branch_state"],
                "title": f"Approve recovery resume after remediation for branch: {branch_id}",
                "preferred_role": "manager",
                "metadata": {
                    **build_step_metadata(
                        owner_hint="Development Manager",
                        branch_id=branch_id,
                        execution_mode="simulate",
                        parent_operation_id=source_operation_id,
                        parent_branch_id=plan.source_branch_id,
                        compensation_action="record_recovery_resume_decision",
                        compensation_description="Keep the recovery resume decision trace even if the branch stays paused.",
                    ),
                    "required_capabilities": ["planning", "coordination", "recovery"],
                    "remediation_phase": "resume_decision",
                    "remediation_step_kind": "approve_recovery_resume",
                    "recovery_parent_plan_id": plan.id,
                    "recovery_trigger_step_keys": trigger_keys,
                },
            },
        ]

    def _default_dispatch_result(self, *, plan_id: str | None = None) -> dict:
        return {
            "status": "ok",
            "service": "AI OS Agent Dispatch",
            "filters": {"plan_id": plan_id},
            "dispatch_count": 0,
            "assignments": [],
            "errors": [],
            "policy_preview": {
                "assignment_count": 0,
                "assignments": [],
                "recommendations": [],
                "unassigned": [],
                "required_capabilities": [],
                "filters": {"plan_id": plan_id},
            },
            "snapshot": self.runtime.snapshot(),
        }

    def _advance_plan_dispatch_cycle(
        self,
        *,
        plan_id: str,
        auto_dispatch: bool,
        dispatch_limit: int,
    ) -> tuple[dict, dict]:
        queue_result = self.execute_ready_steps(plan_id=plan_id)
        dispatch_result = self._default_dispatch_result(plan_id=plan_id)
        if auto_dispatch:
            dispatch_result = self.runtime.dispatch_ready_tasks(
                limit=dispatch_limit,
                plan_id=plan_id,
            )
        return queue_result, dispatch_result

    def _maybe_activate_recovery_remediation(
        self,
        plan: PlanRecord,
        *,
        auto_dispatch: bool,
        dispatch_limit: int,
    ) -> dict:
        disruption = self._recovery_disruption_profile(plan)
        policy = self._recovery_remediation_policy(plan)
        remediation_plan = self._latest_child_plan(plan.id, plan_kind="remediation")
        remediation_summary = self._recovery_remediation_summary(plan)

        if remediation_plan is not None and remediation_plan.status not in TERMINAL_PLAN_STATUSES:
            self._update_recovery_remediation_state(
                plan,
                status=remediation_plan.status,
                active_plan_id=remediation_plan.id,
                triggered_at=self._recovery_remediation_state(plan).get("triggered_at") or utc_now(),
                threshold=disruption["threshold"],
                trigger_step_keys=list(disruption["trigger_step_keys"]),
                resolved_disruption_count=disruption["resolved_disruption_count"],
            )
            queue_result, dispatch_result = self._advance_plan_dispatch_cycle(
                plan_id=remediation_plan.id,
                auto_dispatch=auto_dispatch,
                dispatch_limit=dispatch_limit,
            )
            remediation_summary = self._recovery_remediation_summary(plan)
            return {
                "required": True,
                "activated": False,
                "blocked_recovery": True,
                "plan": self._plan_to_dict(remediation_plan),
                "queue": queue_result,
                "dispatch": dispatch_result,
                "summary": remediation_summary,
            }

        if not remediation_summary.get("required"):
            self._update_recovery_remediation_state(
                plan,
                status="not_required" if disruption["new_disruption_count"] <= 0 else remediation_summary.get("status"),
                threshold=disruption["threshold"],
                trigger_step_keys=list(disruption["trigger_step_keys"]),
                active_plan_id=remediation_summary.get("plan_id") if remediation_summary.get("status") == "completed" else None,
            )
            return {
                "required": False,
                "activated": False,
                "blocked_recovery": False,
                "plan": self._plan_to_dict(remediation_plan) if remediation_plan is not None else None,
                "queue": {"status": "ok", "service": SERVICE_NAME, "queued_steps": [], "queued_count": 0, "snapshot": self.status_snapshot(limit=10)},
                "dispatch": self._default_dispatch_result(plan_id=remediation_summary.get("plan_id")),
                "summary": remediation_summary,
            }

        remediation_title = f"Recovery remediation plan for branch: {plan.branch_id}"
        remediation_context = {
            "parent_recovery_plan_id": plan.id,
            "parent_recovery_branch_id": plan.branch_id,
            "trigger_disruption_count": disruption["disrupted_count"],
            "new_disruption_count": disruption["new_disruption_count"],
            "resolved_disruption_count_before": disruption["resolved_disruption_count"],
            "trigger_step_keys": list(disruption["trigger_step_keys"]),
            "trigger_error": disruption["latest_error"],
            "remediation_mode": policy["mode"],
        }
        remediation_payload = self.create_or_refresh_plan(
            title=remediation_title,
            source="recovery_failure_remediation",
            plan_kind="remediation",
            focus_area="recovery_resilience",
            branch_id=plan.branch_id,
            source_branch_id=plan.branch_id,
            source_operation_id=disruption.get("latest_operation_id") or plan.source_operation_id,
            parent_plan_id=plan.id,
            max_parallel_steps=policy["max_parallel_steps"],
            context=remediation_context,
            task_specs=self._build_recovery_remediation_task_specs(plan, disruption=disruption),
        )
        remediation_plan = self._find_plan(remediation_payload["id"])
        self._update_recovery_remediation_state(
            plan,
            required=True,
            status=remediation_plan.status if remediation_plan is not None else "planned",
            active_plan_id=remediation_payload["id"],
            triggered_at=utc_now(),
            threshold=disruption["threshold"],
            trigger_step_keys=list(disruption["trigger_step_keys"]),
            last_error=disruption["latest_error"],
            completed_at=None,
        )
        queue_result, dispatch_result = self._advance_plan_dispatch_cycle(
            plan_id=remediation_payload["id"],
            auto_dispatch=auto_dispatch,
            dispatch_limit=dispatch_limit,
        )
        remediation_summary = self._recovery_remediation_summary(plan)
        return {
            "required": True,
            "activated": True,
            "blocked_recovery": True,
            "plan": self._plan_to_dict(remediation_plan) if remediation_plan is not None else remediation_payload,
            "queue": queue_result,
            "dispatch": dispatch_result,
            "summary": remediation_summary,
        }

    def _compensate_recovery_failures(self, plan: PlanRecord, *, reason: str) -> dict:
        runtime_tasks = self._runtime_task_index()
        compensated: list[dict] = []
        skipped: list[dict] = []

        for step in plan.steps:
            if step.status != "failed" or step.task_id is None:
                continue

            runtime_task = runtime_tasks.get(int(step.task_id))
            if not runtime_task:
                skipped.append(
                    {
                        "step_key": step.key,
                        "task_id": step.task_id,
                        "reason": "runtime task not found",
                    }
                )
                continue

            compensation_status = normalize_optional_text(runtime_task.get("compensation_status")) or "unknown"
            if compensation_status not in {"pending", "available"}:
                skipped.append(
                    {
                        "step_key": step.key,
                        "task_id": step.task_id,
                        "compensation_status": compensation_status,
                        "reason": "compensation not available",
                    }
                )
                continue

            operation = execution_runtime_module.EXECUTION_RUNTIME.compensate(
                task_id=int(step.task_id),
                reason=reason,
            )
            self._log_event(
                "recovery_step_compensated",
                f"compensated recovery step {step.key}",
                plan_id=plan.id,
                step_id=step.id,
                task_id=step.task_id,
                operation_id=operation.get("operation_id"),
            )
            compensated.append(
                {
                    "step_key": step.key,
                    "task_id": step.task_id,
                    "operation_id": operation.get("operation_id"),
                    "compensation_status": operation.get("compensation_status"),
                    "compensated_at": operation.get("compensated_at"),
                }
            )

        if compensated:
            self._save_state()

        return {
            "compensated_count": len(compensated),
            "operations": compensated,
            "skipped": skipped,
        }

    def _recovery_workflow_actions(self, plan: PlanRecord, runtime_tasks: dict[int, dict]) -> list[dict]:
        remediation = self._recovery_remediation_summary(plan)
        remediation_plan = self._latest_child_plan(plan.id, plan_kind="remediation")
        if remediation.get("blocking_recovery"):
            if remediation_plan is None:
                return [
                    {
                        "type": "start_remediation_plan",
                        "phase": "remediation",
                        "plan_id": remediation.get("plan_id"),
                        "threshold": remediation.get("threshold"),
                        "disrupted_replay_steps": remediation.get("disrupted_replay_steps"),
                    }
                ]

            remediation_current_step = self._current_plan_step(remediation_plan)
            if remediation_plan.status == "failed":
                return [
                    {
                        "type": "review_remediation_failure",
                        "phase": "remediation",
                        "plan_id": remediation_plan.id,
                        "current_step_key": remediation_current_step.key if remediation_current_step is not None else None,
                        "current_step_title": remediation_current_step.title if remediation_current_step is not None else None,
                    }
                ]
            if remediation_current_step is not None and remediation_current_step.status == "queued":
                return [
                    {
                        "type": "dispatch_remediation_steps",
                        "phase": "remediation",
                        "plan_id": remediation_plan.id,
                        "step_keys": [step.key for step in remediation_plan.steps if step.status == "queued"],
                    }
                ]
            if remediation_current_step is not None and remediation_current_step.status == "in_progress":
                return [
                    {
                        "type": "await_remediation_completion",
                        "phase": "remediation",
                        "plan_id": remediation_plan.id,
                        "step_keys": [step.key for step in remediation_plan.steps if step.status == "in_progress"],
                    }
                ]
            if remediation_current_step is not None and remediation_current_step.status == "planned":
                return [
                    {
                        "type": "queue_remediation_steps",
                        "phase": "remediation",
                        "plan_id": remediation_plan.id,
                        "step_keys": [step.key for step in remediation_plan.steps if step.status == "planned"],
                    }
                ]
            if remediation_current_step is not None and remediation_current_step.status == "blocked":
                return [
                    {
                        "type": "await_remediation_dependencies",
                        "phase": "remediation",
                        "plan_id": remediation_plan.id,
                        "step_keys": [step.key for step in remediation_plan.steps if step.status == "blocked"],
                    }
                ]

        failed_steps = [step for step in plan.steps if step.status == "failed"]
        if failed_steps:
            actions: list[dict] = []
            for step in failed_steps[:3]:
                runtime_task = runtime_tasks.get(int(step.task_id or 0), {})
                compensation_status = normalize_optional_text(runtime_task.get("compensation_status"))
                actions.append(
                    {
                        "type": "compensate_failed_step" if compensation_status in {"pending", "available"} else "review_failed_step",
                        "phase": step.metadata.get("recovery_phase"),
                        "step_key": step.key,
                        "task_id": step.task_id,
                        "operation_id": step.operation_id or runtime_task.get("operation_id"),
                        "compensation_status": compensation_status,
                        "title": step.title,
                        "reason": step.last_error or runtime_task.get("last_error"),
                    }
                )
            return actions

        queued_steps = [step for step in plan.steps if step.status == "queued"]
        if queued_steps:
            return [
                {
                    "type": "dispatch_ready_steps",
                    "phase": queued_steps[0].metadata.get("recovery_phase"),
                    "step_keys": [step.key for step in queued_steps],
                    "task_ids": [int(step.task_id) for step in queued_steps if step.task_id is not None],
                }
            ]

        in_progress_steps = [step for step in plan.steps if step.status == "in_progress"]
        if in_progress_steps:
            return [
                {
                    "type": "await_step_completion",
                    "phase": in_progress_steps[0].metadata.get("recovery_phase"),
                    "step_keys": [step.key for step in in_progress_steps],
                    "task_ids": [int(step.task_id) for step in in_progress_steps if step.task_id is not None],
                }
            ]

        planned_steps = [step for step in plan.steps if step.task_id is None and step.status == "planned"]
        if planned_steps:
            return [
                {
                    "type": "queue_next_phase",
                    "phase": planned_steps[0].metadata.get("recovery_phase"),
                    "step_keys": [step.key for step in planned_steps[:3]],
                }
            ]

        blocked_steps = [step for step in plan.steps if step.status == "blocked"]
        if blocked_steps:
            return [
                {
                    "type": "await_dependencies",
                    "phase": blocked_steps[0].metadata.get("recovery_phase"),
                    "step_keys": [step.key for step in blocked_steps[:3]],
                }
            ]

        if plan.status == "completed":
            return [{"type": "workflow_complete", "phase": "completed"}]

        return [{"type": "inspect_workflow", "phase": plan.status}]

    def _plan_to_dict(
        self,
        plan: PlanRecord,
        *,
        runtime_tasks: dict[int, dict] | None = None,
        playbook_lookup: dict[str, dict] | None = None,
    ) -> dict:
        payload = asdict(plan)
        payload["step_counts"] = self._plan_counts(plan)
        payload["is_terminal"] = plan.status in TERMINAL_PLAN_STATUSES
        payload["owner_hints"] = sorted(
            {
                str(step.metadata.get("owner_hint", "")).strip()
                for step in plan.steps
                if isinstance(step.metadata, dict) and str(step.metadata.get("owner_hint", "")).strip()
            }
        )
        branch_summary = self._branch_health_summary(
            plan.branch_id,
            runtime_tasks=runtime_tasks,
            playbook_lookup=playbook_lookup,
        )
        if branch_summary is not None:
            payload["branch_health"] = branch_summary
            payload["branch_planner_gate"] = self._planner_gate_summary(
                plan.branch_id,
                plan_kind=plan.plan_kind,
                current_health=branch_summary,
                trend=(branch_summary or {}).get("trend"),
                drift=(branch_summary or {}).get("quality_drift"),
                playbook=(branch_summary or {}).get("stabilization_playbook"),
            )
            payload["branch_dispatch_policy"] = self._execution_dispatch_policy(
                plan.branch_id,
                plan_kind=plan.plan_kind,
                current_health=branch_summary,
                trend=(branch_summary or {}).get("trend"),
                drift=(branch_summary or {}).get("quality_drift"),
                playbook=(branch_summary or {}).get("stabilization_playbook"),
            )
        if plan.plan_kind == "recovery":
            payload["recovery_workflow"] = self._recovery_workflow_summary(
                plan,
                runtime_tasks=runtime_tasks,
                playbook_lookup=playbook_lookup,
            )
        return payload

    def _recovery_workflow_summary(
        self,
        plan: PlanRecord,
        *,
        runtime_tasks: dict[int, dict] | None = None,
        playbook_lookup: dict[str, dict] | None = None,
    ) -> dict:
        runtime_tasks = runtime_tasks or self._runtime_task_index()
        remediation = self._recovery_remediation_summary(plan)
        remediation_plan = self._latest_child_plan(plan.id, plan_kind="remediation")
        replay_steps = [
            step for step in plan.steps
            if isinstance(step.metadata, dict) and step.metadata.get("recovery_phase") == "replay_execution"
        ]
        phase_counts: dict[str, dict] = {}
        current_phase = None
        current_step_title = None

        for step in plan.steps:
            phase = str(step.metadata.get("recovery_phase", "unclassified")) if isinstance(step.metadata, dict) else "unclassified"
            counts = phase_counts.setdefault(
                phase,
                {"total": 0, "planned": 0, "blocked": 0, "queued": 0, "in_progress": 0, "completed": 0, "failed": 0},
            )
            counts["total"] += 1
            counts[step.status] = counts.get(step.status, 0) + 1

        if remediation_plan is not None:
            phase_counts["remediation"] = self._plan_counts(remediation_plan)

        for phase in sorted(phase_counts, key=lambda item: RECOVERY_PHASE_ORDER.get(item, 99)):
            counts = phase_counts[phase]
            if counts.get("failed", 0) > 0:
                current_phase = phase
                current_step_title = next(
                    (step.title for step in plan.steps if step.metadata.get("recovery_phase") == phase and step.status == "failed"),
                    None,
                )
                break
            if counts.get("in_progress", 0) > 0 or counts.get("queued", 0) > 0 or counts.get("planned", 0) > 0:
                current_phase = phase
                current_step_title = next(
                    (
                        step.title
                        for step in plan.steps
                        if step.metadata.get("recovery_phase") == phase
                        and step.status in {"in_progress", "queued", "planned", "blocked"}
                    ),
                    None,
                )
                break

        if current_phase is None and phase_counts:
            current_phase = "completed"

        if remediation.get("blocking_recovery"):
            current_phase = "remediation"
            current_step_title = remediation.get("current_step_title") or remediation.get("plan_title")

        branch_health = self._recovery_branch_health_summary(
            plan,
            current_phase=current_phase,
            playbook_lookup=playbook_lookup,
        )

        return {
            "workflow_key": plan.context.get("workflow_key"),
            "recovery_mode": plan.context.get("recovery_mode"),
            "alignment_only": bool(plan.context.get("recovery_alignment_only")),
            "anchor_snapshot_id": ((plan.context.get("anchor_snapshot") or {}) or {}).get("snapshot_id"),
            "branch_id": plan.branch_id,
            "status": plan.status,
            "current_phase": current_phase,
            "current_step_title": current_step_title,
            "phase_counts": phase_counts,
            "replay_step_count": int(plan.context.get("replay_step_count", 0) or 0),
            "planned_replay_step_count": int(plan.context.get("planned_replay_step_count", 0) or 0),
            "completed_replay_steps": sum(1 for step in replay_steps if step.status == "completed"),
            "failed_replay_steps": sum(1 for step in replay_steps if step.status == "failed"),
            "in_progress_replay_steps": sum(1 for step in replay_steps if step.status in {"queued", "in_progress"}),
            "compensated_replay_steps": sum(1 for step in replay_steps if step.compensation_status == "completed"),
            "remediation": remediation,
            "branch_health": branch_health,
            "next_actions": self._recovery_workflow_actions(plan, runtime_tasks),
        }

    def _sync_plan_status(self, plan: PlanRecord) -> None:
        counts = self._plan_counts(plan)
        if counts["failed"] > 0:
            plan.status = "failed"
        elif counts["total"] > 0 and counts["completed"] == counts["total"]:
            plan.status = "completed"
        elif counts["in_progress"] > 0:
            plan.status = "in_progress"
        elif counts["queued"] > 0:
            plan.status = "queued"
        elif counts["planned"] > 0 or counts["blocked"] > 0:
            plan.status = "planned"
        else:
            plan.status = "planned"
        plan.updated_at = utc_now()

    def create_or_refresh_plan(
        self,
        *,
        title: str,
        source: str,
        plan_kind: str = "operational",
        focus_area: str | None = None,
        task_specs: list[dict] | None = None,
        context: dict | None = None,
        branch_id: str | None = None,
        source_branch_id: str | None = None,
        source_operation_id: str | None = None,
        parent_plan_id: str | None = None,
        max_parallel_steps: int = 1,
    ) -> dict:
        task_specs = [dict(item) for item in list(task_specs or []) if isinstance(item, dict)]
        branch_id = str(branch_id or "main").strip() or "main"
        title = str(title).strip() or f"AI OS plan for {focus_area or 'system'}"
        source = str(source).strip() or "manual"
        plan_kind = str(plan_kind or "operational").strip() or "operational"
        source_branch_id = normalize_optional_text(source_branch_id) or branch_id
        source_operation_id = normalize_optional_text(source_operation_id)
        parent_plan_id = normalize_optional_text(parent_plan_id)
        try:
            max_parallel_steps = int(max_parallel_steps)
        except (TypeError, ValueError):
            max_parallel_steps = 1
        max_parallel_steps = max(1, min(max_parallel_steps, 5))
        signature = self._build_signature(
            source=source,
            plan_kind=plan_kind,
            focus_area=focus_area,
            branch_id=branch_id,
            task_specs=task_specs,
        )

        with self._lock:
            existing = self._find_open_plan_by_signature(signature)
            if existing is not None:
                existing.title = title
                existing.plan_kind = plan_kind
                existing.focus_area = normalize_optional_text(focus_area)
                existing.branch_id = branch_id
                existing.source_branch_id = source_branch_id
                existing.source_operation_id = source_operation_id
                existing.parent_plan_id = parent_plan_id
                existing.max_parallel_steps = max_parallel_steps
                existing.context.update(dict(context or {}))
                self._sync_plan_status(existing)
                if existing.plan_kind in {"recovery", "branch_stabilization"}:
                    self._record_branch_health_observation(existing)
                self._log_event(
                    "plan_reused",
                    f"reused plan {existing.id}",
                    plan_id=existing.id,
                    source=existing.source,
                )
                self._save_state()
                payload = self._plan_to_dict(existing)
                payload["reused"] = True
                return payload

            key_map: dict[str, str] = {}
            steps: list[PlanStepRecord] = []
            for index, task_spec in enumerate(task_specs, start=1):
                metadata = dict(task_spec.get("metadata", {}) or {})
                step_key = normalize_step_key(task_spec.get("step_key"), f"step_{index}")
                if step_key in key_map:
                    step_key = f"{step_key}_{index}"

                dependency_keys = [
                    normalize_step_key(dep, f"step_{dep_index}")
                    for dep_index, dep in enumerate(task_spec.get("depends_on", []), start=1)
                ]
                step_branch_id = str(metadata.get("branch_id") or branch_id or "main").strip() or "main"
                step = PlanStepRecord(
                    id=generate_step_id(),
                    key=step_key,
                    title=str(task_spec.get("title", "")).strip(),
                    preferred_role=normalize_optional_text(task_spec.get("preferred_role")),
                    metadata=metadata,
                    branch_id=step_branch_id,
                    dependency_keys=dependency_keys,
                    status="blocked" if dependency_keys else "planned",
                )
                key_map[step_key] = step.id
                steps.append(step)

            for step in steps:
                step.depends_on = [key_map[key] for key in step.dependency_keys if key in key_map]
                if step.depends_on:
                    step.status = "blocked"

            plan = PlanRecord(
                id=generate_plan_id(),
                title=title,
                source=source,
                plan_kind=plan_kind,
                focus_area=normalize_optional_text(focus_area),
                branch_id=branch_id,
                source_branch_id=source_branch_id,
                source_operation_id=source_operation_id,
                parent_plan_id=parent_plan_id,
                max_parallel_steps=max_parallel_steps,
                signature=signature,
                context=dict(context or {}),
                steps=steps,
            )
            self._sync_plan_status(plan)
            if plan.plan_kind in {"recovery", "branch_stabilization"}:
                self._record_branch_health_observation(plan)
            self._plans.insert(0, plan)
            self._log_event(
                "plan_created",
                f"created plan {plan.id}",
                plan_id=plan.id,
                source=plan.source,
                step_count=len(plan.steps),
            )
            self._save_state()
            payload = self._plan_to_dict(plan)
            payload["reused"] = False
            return payload

    def create_recovery_plan_from_replay(
        self,
        *,
        snapshot_id: str | None = None,
        branch_id: str | None = None,
        operation_id: str | None = None,
        title: str | None = None,
        max_parallel_steps: int = 1,
        max_replay_steps: int = 6,
    ) -> dict:
        preview = self.preview_recovery_plan_from_replay(
            snapshot_id=snapshot_id,
            branch_id=branch_id,
            operation_id=operation_id,
            max_parallel_steps=max_parallel_steps,
            max_replay_steps=max_replay_steps,
            title=title,
        )
        return self.create_or_refresh_plan(
            title=preview["title"],
            source="snapshot_replay_recovery",
            plan_kind="recovery",
            focus_area="snapshot_recovery",
            branch_id=preview["branch_id"],
            source_branch_id=preview["branch_id"],
            source_operation_id=operation_id,
            max_parallel_steps=max_parallel_steps,
            context=dict(preview["context"]),
            task_specs=list(preview["task_specs"]),
        )

    def _is_demo_seed_plan(self, plan: PlanRecord) -> bool:
        return bool((plan.context or {}).get("demo_seed"))

    def _clear_demo_seed_state(self) -> dict:
        removed_plans = [
            plan.id
            for plan in self._plans
            if self._is_demo_seed_plan(plan)
            or (normalize_optional_text(plan.branch_id) or "") in DEMO_RECOVERY_BRANCHES
        ]
        if removed_plans:
            self._plans = [plan for plan in self._plans if plan.id not in removed_plans]

        cleared_branches = []
        for branch_id in DEMO_RECOVERY_BRANCHES:
            if branch_id in self._branch_health_history:
                self._branch_health_history.pop(branch_id, None)
                cleared_branches.append(branch_id)

        return {
            "removed_plan_count": len(removed_plans),
            "removed_plan_ids": removed_plans,
            "cleared_branch_count": len(cleared_branches),
            "cleared_branches": cleared_branches,
        }

    def _build_demo_recovery_task_specs(
        self,
        *,
        branch_id: str,
        replay_steps: int = 2,
        workflow_key: str,
    ) -> list[dict]:
        normalized_branch_id = normalize_optional_text(branch_id) or "main"
        replay_steps = max(1, min(int(replay_steps), 6))
        specs = [
            {
                "step_key": "coordinate_snapshot_recovery",
                "title": f"Coordinate demo recovery for branch: {normalized_branch_id}",
                "preferred_role": "manager",
                "metadata": {
                    **build_step_metadata(
                        owner_hint="Development Manager",
                        branch_id=normalized_branch_id,
                        execution_mode="simulate",
                        compensation_action="report_only",
                        compensation_description="Record coordination-only compensation for demo recovery seed",
                    ),
                    "recovery_phase": "coordination",
                    "workflow_key": workflow_key,
                    "demo_seed": True,
                },
            },
            {
                "step_key": "review_recovery_anchor",
                "title": f"Review demo recovery anchor for branch: {normalized_branch_id}",
                "preferred_role": "worker",
                "depends_on": ["coordinate_snapshot_recovery"],
                "metadata": {
                    **build_step_metadata(
                        owner_hint="Research Agent",
                        branch_id=normalized_branch_id,
                        execution_mode="simulate",
                        compensation_action="report_only",
                        compensation_description="Record anchor-review compensation for demo recovery seed",
                    ),
                    "recovery_phase": "anchor_review",
                    "workflow_key": workflow_key,
                    "demo_seed": True,
                },
            },
        ]

        previous_key = "review_recovery_anchor"
        for index in range(1, replay_steps + 1):
            step_key = f"replay_step_{index:02d}"
            owner_hint = "Memory Agent" if index % 2 else "Coding Agent"
            specs.append(
                {
                    "step_key": step_key,
                    "title": f"Replay demo recovery step {index:02d} for branch: {normalized_branch_id}",
                    "preferred_role": "worker",
                    "depends_on": [previous_key],
                    "metadata": {
                        **build_step_metadata(
                            owner_hint=owner_hint,
                            branch_id=normalized_branch_id,
                            execution_mode="commit",
                            compensation_action="report_only",
                            compensation_description="Capture compensation trace for demo replay step",
                        ),
                        "recovery_phase": "replay_execution",
                        "replay_logical_time": index,
                        "workflow_key": workflow_key,
                        "demo_seed": True,
                    },
                }
            )
            previous_key = step_key

        specs.append(
            {
                "step_key": "validate_recovered_branch",
                "title": f"Validate demo recovered branch: {normalized_branch_id}",
                "preferred_role": "worker",
                "depends_on": [previous_key],
                "metadata": {
                    **build_step_metadata(
                        owner_hint="Research Agent",
                        branch_id=normalized_branch_id,
                        execution_mode="simulate",
                        compensation_action="report_only",
                        compensation_description="Record validation-only compensation for demo recovery seed",
                    ),
                    "recovery_phase": "validation",
                    "workflow_key": workflow_key,
                    "demo_seed": True,
                },
            }
        )
        return specs

    def _build_demo_remediation_task_specs(self, *, branch_id: str, workflow_key: str) -> list[dict]:
        normalized_branch_id = normalize_optional_text(branch_id) or "main"
        return [
            {
                "step_key": "assess_recovery_drift",
                "title": f"Assess recovery drift for branch: {normalized_branch_id}",
                "preferred_role": "manager",
                "metadata": {
                    **build_step_metadata(
                        owner_hint="Research Manager",
                        branch_id=normalized_branch_id,
                        execution_mode="simulate",
                        compensation_action="report_only",
                        compensation_description="Record remediation assessment compensation for demo seed",
                    ),
                    "remediation_phase": "assessment",
                    "workflow_key": workflow_key,
                    "demo_seed": True,
                },
            },
            {
                "step_key": "stabilize_recovery_branch",
                "title": f"Stabilize recovery branch: {normalized_branch_id}",
                "preferred_role": "worker",
                "depends_on": ["assess_recovery_drift"],
                "metadata": {
                    **build_step_metadata(
                        owner_hint="Coding Agent",
                        branch_id=normalized_branch_id,
                        execution_mode="commit",
                        compensation_action="report_only",
                        compensation_description="Record remediation stabilization compensation for demo seed",
                    ),
                    "remediation_phase": "stabilization",
                    "workflow_key": workflow_key,
                    "demo_seed": True,
                },
            },
        ]

    def _apply_demo_step_update(
        self,
        plan: PlanRecord,
        step_key: str,
        *,
        status: str,
        result: str | None = None,
        last_error: str | None = None,
        compensation_status: str | None = None,
    ) -> PlanStepRecord | None:
        step = next((item for item in plan.steps if item.key == step_key), None)
        if step is None:
            return None

        step.status = str(status).strip() or step.status
        if step.status in {"queued", "in_progress"}:
            step.queued_at = step.queued_at or utc_now()
        if step.status == "in_progress":
            step.started_at = step.started_at or utc_now()
        if step.status in TERMINAL_STEP_STATUSES:
            step.completed_at = step.completed_at or utc_now()
        step.result = normalize_optional_text(result)
        step.last_error = normalize_optional_text(last_error)
        if compensation_status is not None:
            step.compensation_status = normalize_optional_text(compensation_status)
            if step.compensation_status == "completed":
                step.compensated_at = step.compensated_at or utc_now()
        return step

    def seed_demo_recovery_state(self, *, reset_existing: bool = True) -> dict:
        observe_branch_id = DEMO_RECOVERY_BRANCHES[0]
        remediation_branch_id = DEMO_RECOVERY_BRANCHES[1]

        with self._lock:
            removed = self._clear_demo_seed_state() if reset_existing else {
                "removed_plan_count": 0,
                "removed_plan_ids": [],
                "cleared_branch_count": 0,
                "cleared_branches": [],
            }

            observe_payload = self.create_or_refresh_plan(
                title="Demo recovery workflow for dashboard visualization",
                source="dashboard_demo_seed",
                plan_kind="recovery",
                focus_area="demo_recovery_visualization",
                branch_id=observe_branch_id,
                source_branch_id=observe_branch_id,
                max_parallel_steps=1,
                context={
                    "demo_seed": True,
                    "demo_label": "observe_recovery",
                    "workflow_key": "demo_observe_recovery",
                    "recovery_mode": "demo_observe",
                    "replay_step_count": 2,
                    "planned_replay_step_count": 2,
                    "anchor_snapshot": {
                        "snapshot_id": "demo_snapshot_observe",
                        "branch_id": observe_branch_id,
                        "label": "Demo observe anchor",
                    },
                    "replay_summary": "Demo recovery flow with one compensated replay step and successful validation",
                },
                task_specs=self._build_demo_recovery_task_specs(
                    branch_id=observe_branch_id,
                    replay_steps=2,
                    workflow_key="demo_observe_recovery",
                ),
            )
            observe_plan = self._find_plan(observe_payload["id"])
            if observe_plan is None:
                raise RuntimeError("failed to create observe demo recovery plan")
            self._apply_demo_step_update(
                observe_plan,
                "coordinate_snapshot_recovery",
                status="completed",
                result="Demo coordination completed",
            )
            self._apply_demo_step_update(
                observe_plan,
                "review_recovery_anchor",
                status="completed",
                result="Demo anchor review completed",
            )
            self._apply_demo_step_update(
                observe_plan,
                "replay_step_01",
                status="completed",
                result="Replay step completed cleanly",
            )
            self._apply_demo_step_update(
                observe_plan,
                "replay_step_02",
                status="completed",
                result="Replay step completed after compensation",
                last_error="demo anomaly compensated during replay execution",
                compensation_status="completed",
            )
            self._apply_demo_step_update(
                observe_plan,
                "validate_recovered_branch",
                status="completed",
                result="Recovered branch validated successfully",
            )
            self._sync_plan_status(observe_plan)
            self._record_branch_health_observation(observe_plan)

            remediation_payload = self.create_or_refresh_plan(
                title="Demo remediation-aware recovery workflow",
                source="dashboard_demo_seed",
                plan_kind="recovery",
                focus_area="demo_recovery_visualization",
                branch_id=remediation_branch_id,
                source_branch_id=remediation_branch_id,
                max_parallel_steps=1,
                context={
                    "demo_seed": True,
                    "demo_label": "remediation_recovery",
                    "workflow_key": "demo_remediation_recovery",
                    "recovery_mode": "demo_remediation",
                    "replay_step_count": 3,
                    "planned_replay_step_count": 3,
                    "anchor_snapshot": {
                        "snapshot_id": "demo_snapshot_remediation",
                        "branch_id": remediation_branch_id,
                        "label": "Demo remediation anchor",
                    },
                    "replay_summary": "Demo recovery flow that triggers remediation before validation completes",
                    "remediation_policy": {
                        "max_disrupted_replay_steps": 2,
                        "mode": "pause_and_remediate",
                        "max_parallel_steps": 1,
                    },
                },
                task_specs=self._build_demo_recovery_task_specs(
                    branch_id=remediation_branch_id,
                    replay_steps=3,
                    workflow_key="demo_remediation_recovery",
                ),
            )
            remediation_parent = self._find_plan(remediation_payload["id"])
            if remediation_parent is None:
                raise RuntimeError("failed to create remediation demo recovery plan")

            self._apply_demo_step_update(
                remediation_parent,
                "coordinate_snapshot_recovery",
                status="completed",
                result="Demo coordination completed",
            )
            self._apply_demo_step_update(
                remediation_parent,
                "review_recovery_anchor",
                status="completed",
                result="Demo anchor review completed",
            )
            self._apply_demo_step_update(
                remediation_parent,
                "replay_step_01",
                status="completed",
                result="Replay step completed after compensation",
                last_error="demo replay drift corrected by compensation",
                compensation_status="completed",
            )
            self._apply_demo_step_update(
                remediation_parent,
                "replay_step_02",
                status="completed",
                result="Replay step completed after compensation",
                last_error="demo replay anomaly required repeated compensation",
                compensation_status="completed",
            )
            replay_step_03 = self._apply_demo_step_update(
                remediation_parent,
                "replay_step_03",
                status="blocked",
                last_error="waiting for remediation stabilization",
            )
            validation_step = self._apply_demo_step_update(
                remediation_parent,
                "validate_recovered_branch",
                status="blocked",
                last_error="waiting for remediation stabilization",
            )
            self._sync_plan_status(remediation_parent)
            self._record_branch_health_observation(remediation_parent)

            remediation_child_payload = self.create_or_refresh_plan(
                title="Demo remediation child plan",
                source="dashboard_demo_seed",
                plan_kind="remediation",
                focus_area="demo_recovery_visualization",
                branch_id=remediation_branch_id,
                source_branch_id=remediation_branch_id,
                parent_plan_id=remediation_parent.id,
                max_parallel_steps=1,
                context={
                    "demo_seed": True,
                    "demo_label": "remediation_child",
                    "workflow_key": "demo_remediation_recovery",
                    "parent_recovery_plan_id": remediation_parent.id,
                },
                task_specs=self._build_demo_remediation_task_specs(
                    branch_id=remediation_branch_id,
                    workflow_key="demo_remediation_recovery",
                ),
            )
            remediation_child = self._find_plan(remediation_child_payload["id"])
            if remediation_child is None:
                raise RuntimeError("failed to create remediation demo child plan")
            self._apply_demo_step_update(
                remediation_child,
                "assess_recovery_drift",
                status="completed",
                result="Remediation assessment completed",
            )
            self._apply_demo_step_update(
                remediation_child,
                "stabilize_recovery_branch",
                status="completed",
                result="Branch stabilization completed",
            )
            self._sync_plan_status(remediation_child)
            self._update_recovery_remediation_state(
                remediation_parent,
                required=False,
                status="completed",
                active_plan_id=None,
                triggered_at=utc_now(),
                completed_at=utc_now(),
                threshold=2,
                trigger_step_keys=["replay_step_01", "replay_step_02"],
                resolved_disruption_count=2,
                last_completed_plan_id=remediation_child.id,
                last_error=None,
            )
            if replay_step_03 is not None:
                replay_step_03.last_error = None
            if validation_step is not None:
                validation_step.last_error = None
            self._apply_demo_step_update(
                remediation_parent,
                "replay_step_03",
                status="completed",
                result="Replay resumed after remediation",
            )
            self._apply_demo_step_update(
                remediation_parent,
                "validate_recovered_branch",
                status="completed",
                result="Recovered branch validated after remediation",
            )
            self._sync_plan_status(remediation_parent)
            self._record_branch_health_observation(remediation_parent)

            self._log_event(
                "demo_recovery_seeded",
                "seeded demo recovery workflows for dashboard visualization",
                demo_seed=True,
                branches=list(DEMO_RECOVERY_BRANCHES),
                recovery_plan_ids=[observe_plan.id, remediation_parent.id],
                remediation_plan_id=remediation_child.id,
            )
            self._save_state()

        recovery_snapshot = self.recovery_workflows_snapshot(limit=10, active_only=False)
        branch_snapshot = self.branch_health_snapshot(limit=10)
        status_snapshot = self.status_snapshot(limit=10, sync=False)
        demo_workflows = [
            workflow
            for workflow in list(recovery_snapshot.get("workflows") or [])
            if normalize_optional_text(workflow.get("branch_id")) in DEMO_RECOVERY_BRANCHES
        ]
        demo_branches = [
            branch
            for branch in list(branch_snapshot.get("branches") or [])
            if normalize_optional_text(branch.get("branch_id")) in DEMO_RECOVERY_BRANCHES
        ]

        return {
            "status": "ok",
            "service": "AI OS Recovery Demo Seed",
            "message": "demo recovery workflows were seeded into the live planner runtime",
            "reset_existing": bool(reset_existing),
            "removed": removed,
            "demo_branches": list(DEMO_RECOVERY_BRANCHES),
            "seeded_workflow_count": len(demo_workflows),
            "seeded_branch_count": len(demo_branches),
            "recovery_workflows": demo_workflows,
            "branch_health": demo_branches,
            "snapshot": status_snapshot,
        }

    def preview_recovery_plan_from_replay(
        self,
        *,
        snapshot_id: str | None = None,
        branch_id: str | None = None,
        operation_id: str | None = None,
        title: str | None = None,
        max_parallel_steps: int = 1,
        max_replay_steps: int = 6,
    ) -> dict:
        replay = SNAPSHOT_LINEAGE.replay_plan(
            snapshot_id=snapshot_id,
            branch_id=branch_id,
            operation_id=operation_id,
            limit=20,
        )
        anchor_snapshot = dict(replay.get("anchor_snapshot") or {})
        branch = dict(replay.get("branch") or {})
        replay_steps = list(replay.get("replay_steps") or [])
        replay_entries = list(replay.get("replay_entries") or [])

        try:
            max_replay_steps = int(max_replay_steps)
        except (TypeError, ValueError):
            max_replay_steps = 6
        max_replay_steps = max(1, min(max_replay_steps, 12))

        explicit_snapshot_id = normalize_optional_text(snapshot_id)
        effective_branch_id = (
            normalize_optional_text(branch.get("branch_id"))
            or normalize_optional_text(branch_id)
            or normalize_optional_text(anchor_snapshot.get("branch_id"))
            or "main"
        )
        branch_recovery_signal = self._branch_recovery_signal(
            branch_id=effective_branch_id,
            anchor_snapshot_id=normalize_optional_text(anchor_snapshot.get("snapshot_id")),
            replay_step_count=len(replay_steps),
        )

        anchor_bias = None
        original_anchor_snapshot_id = normalize_optional_text(anchor_snapshot.get("snapshot_id"))
        branch_health_record = self._latest_stabilization_branch_health_record(effective_branch_id)
        branch_health_last_updated = normalize_optional_text((branch_health_record or {}).get("timestamp"))

        if explicit_snapshot_id:
            anchor_bias = {
                "applied": False,
                "reason": "explicit_snapshot_id_bypassed",
                "original_anchor_snapshot_id": original_anchor_snapshot_id,
                "selected_anchor_snapshot_id": original_anchor_snapshot_id,
                "branch_id": effective_branch_id,
                "branch_health_last_updated": branch_health_last_updated,
                "explicit_snapshot_bypassed": True,
            }
            if operation_id is not None:
                anchor_bias["operation_id"] = operation_id
        elif self._branch_recovery_signal_is_meaningful(branch_recovery_signal):
            anchor_created_at = parse_iso_timestamp(anchor_snapshot.get("created_at"))
            branch_health_updated_at = parse_iso_timestamp(branch_health_last_updated)
            if anchor_created_at is not None and branch_health_updated_at is not None and anchor_created_at < branch_health_updated_at:
                fresher_snapshot = self._latest_same_branch_snapshot_after(
                    branch_id=effective_branch_id,
                    threshold=branch_health_last_updated,
                )
                selected_snapshot_id = normalize_optional_text((fresher_snapshot or {}).get("snapshot_id"))
                if selected_snapshot_id and selected_snapshot_id != original_anchor_snapshot_id:
                    replay = SNAPSHOT_LINEAGE.replay_plan(
                        snapshot_id=selected_snapshot_id,
                        branch_id=effective_branch_id,
                        operation_id=operation_id,
                        limit=20,
                    )
                    anchor_snapshot = dict(replay.get("anchor_snapshot") or {})
                    branch = dict(replay.get("branch") or {})
                    replay_steps = list(replay.get("replay_steps") or [])
                    replay_entries = list(replay.get("replay_entries") or [])
                    effective_branch_id = (
                        normalize_optional_text(branch.get("branch_id"))
                        or normalize_optional_text(branch_id)
                        or normalize_optional_text(anchor_snapshot.get("branch_id"))
                        or "main"
                    )
                    branch_recovery_signal = self._branch_recovery_signal(
                        branch_id=effective_branch_id,
                        anchor_snapshot_id=normalize_optional_text(anchor_snapshot.get("snapshot_id")),
                        replay_step_count=len(replay_steps),
                    )
                    anchor_bias = {
                        "applied": True,
                        "reason": "preferred_post_stabilization_snapshot",
                        "original_anchor_snapshot_id": original_anchor_snapshot_id,
                        "selected_anchor_snapshot_id": normalize_optional_text(anchor_snapshot.get("snapshot_id")),
                        "branch_id": effective_branch_id,
                        "branch_health_last_updated": branch_health_last_updated,
                        "explicit_snapshot_bypassed": False,
                    }
                    if operation_id is not None:
                        anchor_bias["operation_id"] = operation_id
                else:
                    anchor_bias = {
                        "applied": False,
                        "reason": "no_fresh_post_stabilization_snapshot",
                        "original_anchor_snapshot_id": original_anchor_snapshot_id,
                        "selected_anchor_snapshot_id": original_anchor_snapshot_id,
                        "branch_id": effective_branch_id,
                        "branch_health_last_updated": branch_health_last_updated,
                        "explicit_snapshot_bypassed": False,
                    }
                    if operation_id is not None:
                        anchor_bias["operation_id"] = operation_id

        parent_branch_id = normalize_optional_text(
            branch.get("parent_branch_id") or anchor_snapshot.get("parent_branch_id")
        )
        title = str(title or f"Snapshot replay recovery plan for branch: {effective_branch_id}").strip()
        anchor_label = (
            anchor_snapshot.get("label")
            or anchor_snapshot.get("name")
            or anchor_snapshot.get("snapshot_id")
            or "latest snapshot"
        )
        replay_summary = shorten_text(
            " | ".join(str(item.get("summary", "")).strip() for item in replay_steps[:3] if item.get("summary")),
            limit=160,
        )
        planned_replay_steps = replay_steps[:max_replay_steps]
        recovery_continuity = self._recovery_continuity_metadata(
            branch_recovery_signal=branch_recovery_signal,
            anchor_bias=anchor_bias,
            branch_id=effective_branch_id,
            anchor_snapshot=anchor_snapshot,
            operation_id=operation_id,
        )
        recovery_continuity_metadata = (
            {"recovery_continuity": recovery_continuity}
            if recovery_continuity is not None
            else {}
        )

        task_specs = [
            {
                "step_key": "coordinate_snapshot_recovery",
                "title": f"Coordinate snapshot replay recovery for branch: {effective_branch_id}",
                "preferred_role": "manager",
                "metadata": {
                    **build_step_metadata(
                        owner_hint="Development Manager",
                        branch_id=effective_branch_id,
                        execution_mode="simulate",
                        parent_operation_id=operation_id,
                        parent_branch_id=parent_branch_id,
                        compensation_action="record_snapshot_recovery_decision",
                        compensation_description="Preserve the snapshot recovery coordination trace even if execution pauses.",
                    ),
                    "recovery_phase": "coordination",
                    "recovery_step_kind": "coordinate_recovery",
                    **recovery_continuity_metadata,
                },
            },
            {
                "step_key": "review_recovery_anchor",
                "depends_on": ["coordinate_snapshot_recovery"],
                "title": f"Review recovery anchor snapshot: {anchor_label}",
                "preferred_role": "worker",
                "metadata": {
                    **build_step_metadata(
                        owner_hint="Research Agent",
                        branch_id=effective_branch_id,
                        execution_mode="simulate",
                        parent_operation_id=operation_id,
                        parent_branch_id=parent_branch_id,
                        compensation_action="record_anchor_review",
                        compensation_description="Keep only the anchor review trace if the recovery review cannot complete.",
                    ),
                    "required_capabilities": ["analysis", "retrieval"],
                    "anchor_snapshot_id": anchor_snapshot.get("snapshot_id"),
                    "recovery_phase": "anchor_review",
                    "recovery_step_kind": "review_anchor_snapshot",
                    **recovery_continuity_metadata,
                },
            },
        ]

        previous_step_key = "review_recovery_anchor"
        replay_step_keys: list[str] = []
        if planned_replay_steps:
            for index, replay_step in enumerate(planned_replay_steps, start=1):
                entry_id = normalize_optional_text(replay_step.get("entry_id")) or f"entry_{index}"
                logical_time = replay_step.get("logical_time")
                owner_hint, required_capabilities = infer_recovery_owner_hint(replay_step)
                step_key = f"replay_step_{index:02d}"
                replay_step_keys.append(step_key)
                summary_text = shorten_text(
                    replay_step.get("summary") or replay_step.get("delta") or entry_id,
                    limit=90,
                )
                task_specs.append(
                    {
                        "step_key": step_key,
                        "depends_on": [previous_step_key],
                        "title": f"Replay recovery step {index} for branch {effective_branch_id}: {summary_text}",
                        "preferred_role": "worker",
                        "metadata": {
                            **build_step_metadata(
                                owner_hint=owner_hint,
                                branch_id=effective_branch_id,
                                execution_mode="commit",
                                timeout_seconds=240,
                                parent_operation_id=operation_id,
                                parent_branch_id=parent_branch_id,
                                compensation_action="record_replay_recovery_step",
                                compensation_description="Preserve replay-step recovery trace even if the branch cannot be fully recovered.",
                            ),
                            "required_capabilities": required_capabilities,
                            "replay_entry_id": entry_id,
                            "replay_logical_time": logical_time,
                            "replay_summary": replay_step.get("summary"),
                            "replay_delta": replay_step.get("delta"),
                            "recovery_phase": "replay_execution",
                            "recovery_step_kind": "replay_entry",
                            "recovery_step_index": index,
                            "recovery_step_total": len(planned_replay_steps),
                            **recovery_continuity_metadata,
                        },
                    }
                )
                previous_step_key = step_key
        else:
            task_specs.append(
                {
                    "step_key": "confirm_recovery_alignment",
                    "depends_on": [previous_step_key],
                    "title": f"Confirm recovery alignment for branch: {effective_branch_id}",
                    "preferred_role": "worker",
                    "metadata": {
                        **build_step_metadata(
                        owner_hint="Research Agent",
                        branch_id=effective_branch_id,
                        execution_mode="simulate",
                        parent_operation_id=operation_id,
                        parent_branch_id=parent_branch_id,
                        compensation_action="record_alignment_confirmation",
                        compensation_description="Keep the alignment confirmation trace if no replay actions are needed.",
                    ),
                    "required_capabilities": ["analysis", "planning"],
                    "recovery_alignment_only": True,
                    "recovery_phase": "validation",
                    "recovery_step_kind": "confirm_alignment",
                    **recovery_continuity_metadata,
                },
            }
        )
            previous_step_key = "confirm_recovery_alignment"

        task_specs.append(
            {
                "step_key": "validate_recovered_branch",
                "depends_on": [previous_step_key],
                "title": f"Validate recovered branch snapshot coverage: {effective_branch_id}",
                "preferred_role": "worker",
                "metadata": {
                    **build_step_metadata(
                        owner_hint="Memory Agent",
                        branch_id=effective_branch_id,
                        execution_mode="commit",
                        timeout_seconds=180,
                        parent_operation_id=operation_id,
                        parent_branch_id=parent_branch_id,
                        compensation_action="record_recovery_validation",
                        compensation_description="Keep the recovery validation trace if post-recovery verification cannot complete.",
                    ),
                    "required_capabilities": ["memory-ingestion", "graph-build", "vector-memory"],
                    "replay_step_keys": replay_step_keys,
                    "recovery_phase": "validation",
                    "recovery_step_kind": "validate_recovered_branch",
                    **recovery_continuity_metadata,
                },
            }
        )

        context = {
            "anchor_snapshot": anchor_snapshot,
            "branch": branch,
            "operation_id": operation_id,
            "replay_step_count": len(replay_steps),
            "planned_replay_step_count": len(planned_replay_steps),
            "replay_steps_preview": replay_steps[:10],
            "replay_entries_preview": replay_entries[:10],
            "replay_summary": replay_summary,
            "recovery_mode": "anchored_replay",
            "recovery_alignment_only": not bool(planned_replay_steps),
            "workflow_key": f"recovery:{effective_branch_id}:{normalize_optional_text(anchor_snapshot.get('snapshot_id')) or 'latest'}",
        }
        if branch_recovery_signal is not None:
            context["branch_recovery_signal"] = branch_recovery_signal
        if anchor_bias is not None:
            context["anchor_bias"] = anchor_bias

        return {
            "status": "ok",
            "service": RECOVERY_PREVIEW_SERVICE_NAME,
            "title": title,
            "branch_id": effective_branch_id,
            "source_operation_id": operation_id,
            "snapshot_id": normalize_optional_text(anchor_snapshot.get("snapshot_id")),
            "max_parallel_steps": max_parallel_steps,
            "max_replay_steps": max_replay_steps,
            "replay_step_count": len(replay_steps),
            "planned_replay_step_count": len(planned_replay_steps),
            "task_specs": task_specs,
            "context": context,
            "anchor_snapshot": anchor_snapshot,
            "branch": branch,
            "branch_recovery_signal": branch_recovery_signal,
            "anchor_bias": anchor_bias,
        }

    def sync_with_runtime(self, *, limit: int = 10, plan_id: str | None = None) -> dict:
        runtime_tasks = {int(task["id"]): task for task in self.runtime.list_tasks()}
        changed = False

        with self._lock:
            for plan in self._plans:
                for step in plan.steps:
                    previous_status = step.status
                    task = runtime_tasks.get(int(step.task_id)) if step.task_id is not None else None
                    if task is not None:
                        task_status = str(task.get("status", "")).strip()
                        compensation_status = normalize_optional_text(task.get("compensation_status"))
                        normalized_task_result = normalize_optional_text(task.get("result"))
                        normalized_task_error = normalize_optional_text(task.get("last_error"))
                        step.compensation_status = compensation_status
                        step.compensated_at = task.get("compensated_at") or step.compensated_at
                        if task_status == "queued":
                            step.status = "queued"
                        elif task_status == "in_progress":
                            step.status = "in_progress"
                        elif task_status == "done":
                            step.status = "completed"
                        elif task_status == "failed":
                            if compensation_status == "completed" and plan.plan_kind == "recovery":
                                step.status = "completed"
                                step.result = normalized_task_result or (
                                    f"compensated after failure: {normalized_task_error}"
                                    if normalized_task_error
                                    else "compensated recovery step"
                                )
                            else:
                                step.status = "failed"

                        step.operation_id = normalize_optional_text(task.get("operation_id")) or step.operation_id
                        if not (task_status == "failed" and compensation_status == "completed" and plan.plan_kind == "recovery"):
                            step.result = normalized_task_result
                        step.last_error = normalized_task_error
                        step.queued_at = task.get("created_at") or step.queued_at
                        step.started_at = task.get("started_at") or step.started_at
                        if step.status in TERMINAL_STEP_STATUSES:
                            step.completed_at = (
                                task.get("compensated_at")
                                or task.get("completed_at")
                                or step.completed_at
                                or utc_now()
                            )
                    elif step.task_id is None:
                        dependencies = [self._find_step(plan, dependency_id) for dependency_id in step.depends_on]
                        if dependencies and all(item is not None and item.status == "completed" for item in dependencies):
                            step.status = "planned"
                            if step.last_error == "waiting for dependencies":
                                step.last_error = None
                        elif dependencies:
                            step.status = "blocked"
                            step.last_error = "waiting for dependencies"
                        elif step.status not in TERMINAL_STEP_STATUSES:
                            step.status = "planned"
                            if step.last_error == "waiting for dependencies":
                                step.last_error = None

                    if step.status != previous_status:
                        changed = True

                previous_plan_status = plan.status
                self._sync_plan_status(plan)
                if plan.status != previous_plan_status:
                    changed = True
                if plan.plan_kind in {"recovery", "branch_stabilization"} and self._record_branch_health_observation(plan, runtime_tasks=runtime_tasks):
                    changed = True

            if changed:
                self._save_state()

            return self.status_snapshot(limit=limit, plan_id=plan_id, sync=False)

    def execute_ready_steps(self, *, plan_id: str | None = None) -> dict:
        self.sync_with_runtime(plan_id=plan_id)
        queued_steps: list[dict] = []
        gating_events: list[dict] = []
        active_runtime_titles = {
            str(task.get("title", "")).strip()
            for task in self.runtime.list_tasks()
            if str(task.get("status", "")).strip() in {"queued", "in_progress"}
        }
        runtime_tasks = self._runtime_task_index()

        with self._lock:
            selected_plans = [self._find_plan(plan_id)] if plan_id else list(self._plans)
            for plan in [item for item in selected_plans if item is not None]:
                if plan.status in TERMINAL_PLAN_STATUSES:
                    continue
                if plan.plan_kind == "recovery" and self._recovery_remediation_summary(plan).get("blocking_recovery"):
                    self._log_event(
                        "recovery_waiting_on_remediation",
                        f"recovery plan {plan.id} is waiting on remediation",
                        plan_id=plan.id,
                        remediation=self._recovery_remediation_summary(plan),
                    )
                    self._sync_plan_status(plan)
                    continue

                branch_summary = self._branch_health_summary(plan.branch_id, runtime_tasks=runtime_tasks)
                branch_gate = self._planner_gate_summary(
                    plan.branch_id,
                    plan_kind=plan.plan_kind,
                    current_health=branch_summary,
                    trend=(branch_summary or {}).get("trend"),
                    drift=(branch_summary or {}).get("quality_drift"),
                )
                dispatch_policy = self._execution_dispatch_policy(
                    plan.branch_id,
                    plan_kind=plan.plan_kind,
                    current_health=branch_summary,
                    trend=(branch_summary or {}).get("trend"),
                    drift=(branch_summary or {}).get("quality_drift"),
                )
                gated_ready_steps = [
                    step for step in plan.steps
                    if step.task_id is None and step.status in {"planned", "blocked"}
                ]
                if not branch_gate.get("allow_execution", True):
                    gate_reason = f"branch gate {branch_gate.get('mode')}: {branch_gate.get('summary')}"
                    for step in gated_ready_steps:
                        step.status = "blocked"
                        step.last_error = gate_reason
                    gating_events.append(
                        {
                            "plan_id": plan.id,
                            "plan_kind": plan.plan_kind,
                            "branch_id": plan.branch_id,
                            "mode": branch_gate.get("mode"),
                            "recommended_action": branch_gate.get("recommended_action"),
                            "blocked_step_count": len(gated_ready_steps),
                            "summary": branch_gate.get("summary"),
                        }
                    )
                    self._log_event(
                        "plan_branch_gate_blocked",
                        f"planner gate blocked plan {plan.id}",
                        plan_id=plan.id,
                        branch_id=plan.branch_id,
                        gate=branch_gate,
                    )
                    self._sync_plan_status(plan)
                    continue

                active_steps = [
                    step for step in plan.steps if step.status in {"queued", "in_progress"}
                ]
                available_slots = max(int(plan.max_parallel_steps or 1) - len(active_steps), 0)
                try:
                    gate_parallel_limit = int(branch_gate.get("parallel_limit")) if branch_gate.get("parallel_limit") is not None else None
                except (TypeError, ValueError):
                    gate_parallel_limit = None
                if gate_parallel_limit is not None:
                    previous_slots = available_slots
                    available_slots = min(available_slots, max(1, gate_parallel_limit))
                    if branch_gate.get("mode") != "open" and available_slots != previous_slots:
                        gating_events.append(
                            {
                                "plan_id": plan.id,
                                "plan_kind": plan.plan_kind,
                                "branch_id": plan.branch_id,
                                "mode": branch_gate.get("mode"),
                                "recommended_action": branch_gate.get("recommended_action"),
                                "parallel_limit": gate_parallel_limit,
                                "summary": branch_gate.get("summary"),
                            }
                        )
                        self._log_event(
                            "plan_branch_gate_guarded",
                            f"planner gate adjusted parallelism for plan {plan.id}",
                            plan_id=plan.id,
                            branch_id=plan.branch_id,
                            gate=branch_gate,
                            previous_slots=previous_slots,
                            enforced_slots=available_slots,
                        )
                if available_slots <= 0:
                    self._sync_plan_status(plan)
                    continue

                ready_steps = [
                    step for step in plan.steps
                    if step.task_id is None and step.status == "planned"
                ]
                ready_steps.sort(
                    key=lambda step: (
                        0 if step.preferred_role == "manager" else 1,
                        next((index for index, item in enumerate(plan.steps) if item.id == step.id), 999),
                    )
                )

                for step in ready_steps[:available_slots]:
                    if step.title in active_runtime_titles:
                        step.last_error = "waiting on active task with same title"
                        self._log_event(
                            "plan_step_waiting",
                            f"plan step {step.id} is waiting on active task with same title",
                            plan_id=plan.id,
                            step_id=step.id,
                            title=step.title,
                        )
                        continue

                    step_metadata = dict(step.metadata)
                    step_metadata.update(
                        {
                            "plan_id": plan.id,
                            "plan_step_id": step.id,
                            "plan_source": plan.source,
                            "plan_kind": plan.plan_kind,
                            "plan_focus_area": plan.focus_area,
                            "plan_branch_id": plan.branch_id,
                            "parent_plan_id": plan.parent_plan_id,
                            "source_branch_id": plan.source_branch_id,
                            "source_operation_id": plan.source_operation_id,
                            "branch_health_status": (branch_summary or {}).get("status"),
                            "branch_planner_gate_mode": branch_gate.get("mode"),
                            "branch_planner_gate_action": branch_gate.get("recommended_action"),
                            "branch_pressure_level": dispatch_policy.get("pressure_level"),
                            "branch_pressure_score": dispatch_policy.get("pressure_score"),
                            "dispatch_policy": dispatch_policy,
                        }
                    )

                    try:
                        task = self.runtime.queue_task(
                            title=step.title,
                            preferred_role=step.preferred_role,
                            metadata=step_metadata,
                        )
                    except Exception as exc:
                        step.status = "blocked"
                        step.last_error = str(exc)
                        self._log_event(
                            "plan_step_queue_failed",
                            f"failed to queue plan step {step.id}",
                            plan_id=plan.id,
                            step_id=step.id,
                            reason=str(exc),
                        )
                        continue

                    step.task_id = int(task["id"])
                    step.operation_id = normalize_optional_text(task.get("operation_id"))
                    step.status = "queued"
                    step.queued_at = utc_now()
                    step.last_error = None
                    active_runtime_titles.add(step.title)
                    queued_steps.append(
                        {
                            "plan_id": plan.id,
                            "plan_title": plan.title,
                            "step_id": step.id,
                            "step_key": step.key,
                            "task_id": step.task_id,
                            "title": step.title,
                            "preferred_role": step.preferred_role,
                            "branch_id": step.branch_id,
                            "plan_kind": plan.plan_kind,
                        }
                    )
                    self._log_event(
                        "plan_step_queued",
                        f"queued plan step {step.id}",
                        plan_id=plan.id,
                        step_id=step.id,
                        task_id=step.task_id,
                    )

                self._sync_plan_status(plan)

            self._save_state()

        return {
            "status": "ok",
            "service": SERVICE_NAME,
            "queued_steps": queued_steps,
            "queued_count": len(queued_steps),
            "gating": {
                "count": len(gating_events),
                "plans": gating_events[:10],
            },
            "snapshot": self.status_snapshot(limit=10),
        }

    def advance_recovery_workflow(
        self,
        *,
        plan_id: str | None = None,
        branch_id: str | None = None,
        auto_dispatch: bool = True,
        auto_compensate: bool = True,
        compensation_reason: str | None = None,
        dispatch_limit: int = 3,
    ) -> dict:
        with self._lock:
            plan = self._select_recovery_plan(plan_id=plan_id, branch_id=branch_id)
            if plan is None:
                raise ValueError("recovery plan not found")
            selected_plan_id = plan.id

        before = self.status_snapshot(limit=10, plan_id=selected_plan_id)
        compensation = {
            "compensated_count": 0,
            "operations": [],
            "skipped": [],
        }
        if auto_compensate:
            with self._lock:
                plan = self._find_plan(selected_plan_id)
                if plan is None:
                    raise ValueError("recovery plan not found")
                compensation = self._compensate_recovery_failures(
                    plan,
                    reason=str(
                        compensation_reason
                        or f"automated recovery advance compensation for plan {selected_plan_id}"
                    ).strip(),
                )
            if compensation.get("compensated_count"):
                self.sync_with_runtime(plan_id=selected_plan_id)
        with self._lock:
            plan = self._find_plan(selected_plan_id)
            if plan is None:
                raise ValueError("recovery plan not found")
            remediation = self._maybe_activate_recovery_remediation(
                plan,
                auto_dispatch=auto_dispatch,
                dispatch_limit=dispatch_limit,
            )

        advance_target = "recovery"
        queue_result = {
            "status": "ok",
            "service": SERVICE_NAME,
            "queued_steps": [],
            "queued_count": 0,
            "snapshot": self.status_snapshot(limit=10),
        }
        dispatch_result = self._default_dispatch_result(plan_id=selected_plan_id)
        if remediation.get("blocked_recovery"):
            advance_target = "remediation"
            queue_result = remediation.get("queue") or queue_result
            dispatch_result = remediation.get("dispatch") or self._default_dispatch_result(
                plan_id=(remediation.get("plan") or {}).get("id")
            )
        else:
            queue_result, dispatch_result = self._advance_plan_dispatch_cycle(
                plan_id=selected_plan_id,
                auto_dispatch=auto_dispatch,
                dispatch_limit=dispatch_limit,
            )

        after = self.status_snapshot(limit=10, plan_id=selected_plan_id)
        plan_payload = (after.get("plans") or [{}])[0]

        return {
            "status": "ok",
            "service": "AI OS Recovery Workflow Advance",
            "plan_id": selected_plan_id,
            "branch_id": plan_payload.get("branch_id") or branch_id,
            "advance_target": advance_target,
            "auto_dispatch": bool(auto_dispatch),
            "auto_compensate": bool(auto_compensate),
            "before": before,
            "compensation": compensation,
            "remediation": remediation,
            "queue": queue_result,
            "dispatch": dispatch_result,
            "workflow": dict(plan_payload.get("recovery_workflow") or {}),
            "plan": plan_payload,
            "next_actions": list((plan_payload.get("recovery_workflow") or {}).get("next_actions", [])),
        }

    def advance_from_task(
        self,
        task: dict | None,
        *,
        auto_dispatch: bool = True,
        auto_compensate: bool = True,
        compensation_reason: str | None = None,
        dispatch_limit: int = 3,
    ) -> dict:
        if not isinstance(task, dict):
            return self.run_once()

        metadata = dict(task.get("metadata", {}) or {})
        plan_id = normalize_optional_text(metadata.get("plan_id"))
        plan_kind = normalize_optional_text(metadata.get("plan_kind"))

        if plan_id and plan_kind == "recovery":
            return self.advance_recovery_workflow(
                plan_id=plan_id,
                auto_dispatch=auto_dispatch,
                auto_compensate=auto_compensate,
                compensation_reason=compensation_reason,
                dispatch_limit=dispatch_limit,
            )

        if plan_id and plan_kind == "remediation":
            sync_snapshot = self.sync_with_runtime(plan_id=plan_id)
            queue_result, dispatch_result = self._advance_plan_dispatch_cycle(
                plan_id=plan_id,
                auto_dispatch=auto_dispatch,
                dispatch_limit=dispatch_limit,
            )
            remediation_progress = {
                "status": "ok",
                "service": "AI OS Remediation Workflow Advance",
                "plan_id": plan_id,
                "sync": sync_snapshot,
                "queue": queue_result,
                "dispatch": dispatch_result,
            }
            parent_plan_id = normalize_optional_text(metadata.get("parent_plan_id"))
            if not parent_plan_id:
                return remediation_progress

            with self._lock:
                remediation_plan = self._find_plan(plan_id)
                parent_plan = self._find_plan(parent_plan_id)
                if remediation_plan is None or parent_plan is None or parent_plan.plan_kind != "recovery":
                    return remediation_progress
                remediation_progress["plan"] = self._plan_to_dict(remediation_plan)

                if remediation_plan.status == "completed":
                    disruption = self._recovery_disruption_profile(parent_plan)
                    self._update_recovery_remediation_state(
                        parent_plan,
                        required=False,
                        status="completed",
                        active_plan_id=None,
                        completed_at=utc_now(),
                        last_completed_plan_id=remediation_plan.id,
                        resolved_disruption_count=disruption["disrupted_count"],
                    )
                    self._save_state()
                elif remediation_plan.status == "failed":
                    self._update_recovery_remediation_state(
                        parent_plan,
                        required=True,
                        status="failed",
                        active_plan_id=remediation_plan.id,
                    )
                    self._save_state()

            if remediation_plan is not None and remediation_plan.status == "completed":
                return self.advance_recovery_workflow(
                    plan_id=parent_plan_id,
                    auto_dispatch=auto_dispatch,
                    auto_compensate=auto_compensate,
                    compensation_reason=compensation_reason,
                    dispatch_limit=dispatch_limit,
                )

            remediation_progress["parent_recovery_plan_id"] = parent_plan_id
            return remediation_progress

        if plan_id:
            return self.run_once(plan_id=plan_id)

        return self.run_once()

    def run_once(self, *, plan_id: str | None = None) -> dict:
        sync_snapshot = self.sync_with_runtime(plan_id=plan_id)
        execution = self.execute_ready_steps(plan_id=plan_id)
        return {
            "status": "ok",
            "service": SERVICE_NAME,
            "sync": sync_snapshot,
            "execution": execution,
            "snapshot": self.status_snapshot(limit=10),
        }

    def branch_health_snapshot(self, *, limit: int = 10) -> dict:
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 10
        limit = max(1, min(limit, 50))
        runtime_tasks = self._runtime_task_index()
        playbook_snapshot = self._stabilization_playbook_snapshot(limit=100)
        playbook_lookup = {
            str(item.get("branch_id") or "main").strip() or "main": dict(item)
            for item in playbook_snapshot.get("branches", [])
            if isinstance(item, dict)
        }

        with self._lock:
            branch_ids = {
                normalize_optional_text(branch_id) or "main"
                for branch_id in self._branch_health_history
                if normalize_optional_text(branch_id)
            }
            branch_ids.update(
                normalize_optional_text(plan.branch_id) or "main"
                for plan in self._plans
                if normalize_optional_text(plan.branch_id)
            )
            branch_summaries = [
                summary
                for branch_id in branch_ids
                if (
                    summary := self._branch_health_summary(
                        branch_id,
                        runtime_tasks=runtime_tasks,
                        playbook_lookup=playbook_lookup,
                    )
                ) is not None
            ]

        pressure_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "insufficient_history": 4}
        gate_rank = {"blocked": 0, "restricted": 1, "guarded": 2, "open": 3}
        trend_rank = {"declining": 0, "volatile": 1, "stable": 2, "improving": 3, "insufficient_history": 4}
        branch_summaries.sort(
            key=lambda item: (
                pressure_rank.get(str((item.get("quality_drift") or {}).get("pressure_level", "")).strip(), 9),
                gate_rank.get(str((item.get("planner_gate") or {}).get("mode", "")).strip(), 9),
                trend_rank.get(str((item.get("trend") or {}).get("direction", "")).strip(), 9),
                str(item.get("last_updated") or ""),
                str(item.get("branch_id") or ""),
            )
        )
        all_branch_summaries = list(branch_summaries)
        branch_summaries = all_branch_summaries[:limit]

        branch_counts = {
            "total": len(all_branch_summaries),
            "open": sum(1 for item in all_branch_summaries if str((item.get("planner_gate") or {}).get("mode", "")).strip() == "open"),
            "guarded": sum(1 for item in all_branch_summaries if str((item.get("planner_gate") or {}).get("mode", "")).strip() == "guarded"),
            "restricted": sum(1 for item in all_branch_summaries if str((item.get("planner_gate") or {}).get("mode", "")).strip() == "restricted"),
            "blocked": sum(1 for item in all_branch_summaries if str((item.get("planner_gate") or {}).get("mode", "")).strip() == "blocked"),
            "dispatch_open": sum(1 for item in all_branch_summaries if str((item.get("dispatch_policy") or {}).get("mode", "")).strip() == "open"),
            "dispatch_guarded": sum(1 for item in all_branch_summaries if str((item.get("dispatch_policy") or {}).get("mode", "")).strip() == "guarded"),
            "dispatch_restricted": sum(1 for item in all_branch_summaries if str((item.get("dispatch_policy") or {}).get("mode", "")).strip() == "restricted"),
            "dispatch_blocked": sum(1 for item in all_branch_summaries if str((item.get("dispatch_policy") or {}).get("mode", "")).strip() == "blocked"),
            "improving": sum(1 for item in all_branch_summaries if str((item.get("trend") or {}).get("direction", "")).strip() == "improving"),
            "stable": sum(1 for item in all_branch_summaries if str((item.get("trend") or {}).get("direction", "")).strip() == "stable"),
            "declining": sum(1 for item in all_branch_summaries if str((item.get("trend") or {}).get("direction", "")).strip() == "declining"),
            "volatile": sum(1 for item in all_branch_summaries if str((item.get("trend") or {}).get("direction", "")).strip() == "volatile"),
            "pressure_medium": sum(1 for item in all_branch_summaries if str((item.get("quality_drift") or {}).get("pressure_level", "")).strip() == "medium"),
            "pressure_high": sum(1 for item in all_branch_summaries if str((item.get("quality_drift") or {}).get("pressure_level", "")).strip() == "high"),
            "pressure_critical": sum(1 for item in all_branch_summaries if str((item.get("quality_drift") or {}).get("pressure_level", "")).strip() == "critical"),
        }

        return {
            "status": "ok",
            "service": "AI OS Branch Health",
            "branch_counts": branch_counts,
            "counts": branch_counts,
            "playbook_counts": playbook_snapshot.get("playbook_counts", {}),
            "playbooks": list(playbook_snapshot.get("branches", []))[:limit],
            "branches": branch_summaries,
        }

    def recovery_workflows_snapshot(self, *, limit: int = 10, active_only: bool = False) -> dict:
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 10
        limit = max(1, min(limit, 50))
        runtime_tasks = self._runtime_task_index()
        playbook_snapshot = self._stabilization_playbook_snapshot(limit=100)
        playbook_lookup = {
            str(item.get("branch_id") or "main").strip() or "main": dict(item)
            for item in playbook_snapshot.get("branches", [])
            if isinstance(item, dict)
        }

        with self._lock:
            recovery_plans = [plan for plan in self._plans if plan.plan_kind == "recovery"]
            workflows = []
            for plan in recovery_plans:
                workflow = self._recovery_workflow_summary(
                    plan,
                    runtime_tasks=runtime_tasks,
                    playbook_lookup=playbook_lookup,
                )
                if active_only and plan.status in TERMINAL_PLAN_STATUSES:
                    continue
                workflows.append(
                    {
                        "plan_id": plan.id,
                        "title": plan.title,
                        "created_at": plan.created_at,
                        "updated_at": plan.updated_at,
                        **workflow,
                    }
                )

        workflows.sort(
            key=lambda item: (
                0 if item.get("status") not in TERMINAL_PLAN_STATUSES else 1,
                RECOVERY_PHASE_ORDER.get(item.get("current_phase"), 99),
                str(item.get("updated_at") or ""),
            )
        )
        workflows = workflows[:limit]

        return {
            "status": "ok",
            "service": "AI OS Recovery Workflows",
            "workflow_counts": {
                "total": len(recovery_plans),
                "active": sum(1 for plan in recovery_plans if plan.status not in TERMINAL_PLAN_STATUSES),
                "completed": sum(1 for plan in recovery_plans if plan.status == "completed"),
                "failed": sum(1 for plan in recovery_plans if plan.status == "failed"),
                "remediation_blocked": sum(1 for item in workflows if bool(item.get("remediation", {}).get("blocking_recovery"))),
                "healthy": sum(1 for item in workflows if str((item.get("branch_health") or {}).get("status", "")).strip() == "healthy"),
                "observe": sum(1 for item in workflows if str((item.get("branch_health") or {}).get("status", "")).strip() == "observe"),
                "degraded": sum(1 for item in workflows if str((item.get("branch_health") or {}).get("status", "")).strip() == "degraded"),
                "recovering": sum(1 for item in workflows if str((item.get("branch_health") or {}).get("status", "")).strip() == "recovering"),
                "blocked": sum(1 for item in workflows if str((item.get("branch_health") or {}).get("status", "")).strip() == "blocked"),
            },
            "workflows": workflows,
        }

    def status_snapshot(self, *, limit: int = 10, plan_id: str | None = None, sync: bool = True) -> dict:
        if sync:
            return self.sync_with_runtime(limit=limit, plan_id=plan_id)

        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 10
        limit = max(1, min(limit, 50))
        runtime_tasks = self._runtime_task_index()
        playbook_snapshot = self._stabilization_playbook_snapshot(limit=100)
        playbook_lookup = {
            str(item.get("branch_id") or "main").strip() or "main": dict(item)
            for item in playbook_snapshot.get("branches", [])
            if isinstance(item, dict)
        }

        with self._lock:
            if plan_id:
                plans = [self._find_plan(plan_id)]
                plans = [item for item in plans if item is not None]
            else:
                plans = list(self._plans[:limit])

            counts = {
                "total": len(self._plans),
                "active": sum(1 for plan in self._plans if plan.status not in TERMINAL_PLAN_STATUSES),
                "completed": sum(1 for plan in self._plans if plan.status == "completed"),
                "failed": sum(1 for plan in self._plans if plan.status == "failed"),
            }
            plan_kind_counts: dict[str, int] = {}
            for plan in self._plans:
                plan_kind_counts[plan.plan_kind] = plan_kind_counts.get(plan.plan_kind, 0) + 1
            step_counts = {
                "total": sum(len(plan.steps) for plan in self._plans),
                "planned": sum(1 for plan in self._plans for step in plan.steps if step.status == "planned"),
                "blocked": sum(1 for plan in self._plans for step in plan.steps if step.status == "blocked"),
                "queued": sum(1 for plan in self._plans for step in plan.steps if step.status == "queued"),
                "in_progress": sum(1 for plan in self._plans for step in plan.steps if step.status == "in_progress"),
                "completed": sum(1 for plan in self._plans for step in plan.steps if step.status == "completed"),
                "failed": sum(1 for plan in self._plans for step in plan.steps if step.status == "failed"),
            }
            active_focus = [
                {
                    "plan_id": plan.id,
                    "title": plan.title,
                    "plan_kind": plan.plan_kind,
                    "focus_area": plan.focus_area,
                    "branch_id": plan.branch_id,
                    "status": plan.status,
                }
                for plan in self._plans
                if plan.status not in TERMINAL_PLAN_STATUSES
            ][:5]
            recovery_workflows = [
                {
                    "plan_id": plan.id,
                    "title": plan.title,
                    **self._recovery_workflow_summary(
                        plan,
                        runtime_tasks=runtime_tasks,
                        playbook_lookup=playbook_lookup,
                    ),
                }
                for plan in self._plans
                if plan.plan_kind == "recovery"
            ][:5]
            branch_ids = {
                normalize_optional_text(branch_id) or "main"
                for branch_id in self._branch_health_history
                if normalize_optional_text(branch_id)
            }
            branch_ids.update(
                normalize_optional_text(plan.branch_id) or "main"
                for plan in self._plans
                if normalize_optional_text(plan.branch_id)
            )
            branch_health_summaries = [
                summary
                for branch_id in branch_ids
                if (
                    summary := self._branch_health_summary(
                        branch_id,
                        runtime_tasks=runtime_tasks,
                        playbook_lookup=playbook_lookup,
                    )
                ) is not None
            ]
            pressure_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "insufficient_history": 4}
            gate_rank = {"blocked": 0, "restricted": 1, "guarded": 2, "open": 3}
            trend_rank = {"declining": 0, "volatile": 1, "stable": 2, "improving": 3, "insufficient_history": 4}
            branch_health_summaries.sort(
                key=lambda item: (
                    pressure_rank.get(str((item.get("quality_drift") or {}).get("pressure_level", "")).strip(), 9),
                    gate_rank.get(str((item.get("planner_gate") or {}).get("mode", "")).strip(), 9),
                    trend_rank.get(str((item.get("trend") or {}).get("direction", "")).strip(), 9),
                    str(item.get("last_updated") or ""),
                    str(item.get("branch_id") or ""),
                )
            )
            all_branch_health_summaries = list(branch_health_summaries)
            branch_health_summaries = branch_health_summaries[:5]

            return {
                "status": "ok",
                "service": SERVICE_NAME,
                "state_file": str(self.state_path),
                "plan_counts": counts,
                "plan_kind_counts": plan_kind_counts,
                "step_counts": step_counts,
                "recovery_counts": {
                    "total": len(recovery_workflows),
                    "remediation_blocked": sum(
                        1 for workflow in recovery_workflows
                        if bool((workflow.get("remediation") or {}).get("blocking_recovery"))
                    ),
                    "remediation_required": sum(
                        1 for workflow in recovery_workflows
                        if bool((workflow.get("remediation") or {}).get("required"))
                    ),
                    "healthy": sum(
                        1 for workflow in recovery_workflows
                        if str((workflow.get("branch_health") or {}).get("status", "")).strip() == "healthy"
                    ),
                    "observe": sum(
                        1 for workflow in recovery_workflows
                        if str((workflow.get("branch_health") or {}).get("status", "")).strip() == "observe"
                    ),
                    "degraded": sum(
                        1 for workflow in recovery_workflows
                        if str((workflow.get("branch_health") or {}).get("status", "")).strip() == "degraded"
                    ),
                    "recovering": sum(
                        1 for workflow in recovery_workflows
                        if str((workflow.get("branch_health") or {}).get("status", "")).strip() == "recovering"
                    ),
                    "blocked": sum(
                        1 for workflow in recovery_workflows
                        if str((workflow.get("branch_health") or {}).get("status", "")).strip() == "blocked"
                    ),
                },
                "branch_health_counts": {
                    "total": len(all_branch_health_summaries),
                    "open": sum(1 for item in all_branch_health_summaries if str((item.get("planner_gate") or {}).get("mode", "")).strip() == "open"),
                    "guarded": sum(1 for item in all_branch_health_summaries if str((item.get("planner_gate") or {}).get("mode", "")).strip() == "guarded"),
                    "restricted": sum(1 for item in all_branch_health_summaries if str((item.get("planner_gate") or {}).get("mode", "")).strip() == "restricted"),
                    "blocked": sum(1 for item in all_branch_health_summaries if str((item.get("planner_gate") or {}).get("mode", "")).strip() == "blocked"),
                    "dispatch_open": sum(1 for item in all_branch_health_summaries if str((item.get("dispatch_policy") or {}).get("mode", "")).strip() == "open"),
                    "dispatch_guarded": sum(1 for item in all_branch_health_summaries if str((item.get("dispatch_policy") or {}).get("mode", "")).strip() == "guarded"),
                    "dispatch_restricted": sum(1 for item in all_branch_health_summaries if str((item.get("dispatch_policy") or {}).get("mode", "")).strip() == "restricted"),
                    "dispatch_blocked": sum(1 for item in all_branch_health_summaries if str((item.get("dispatch_policy") or {}).get("mode", "")).strip() == "blocked"),
                    "improving": sum(1 for item in all_branch_health_summaries if str((item.get("trend") or {}).get("direction", "")).strip() == "improving"),
                    "stable": sum(1 for item in all_branch_health_summaries if str((item.get("trend") or {}).get("direction", "")).strip() == "stable"),
                    "declining": sum(1 for item in all_branch_health_summaries if str((item.get("trend") or {}).get("direction", "")).strip() == "declining"),
                    "volatile": sum(1 for item in all_branch_health_summaries if str((item.get("trend") or {}).get("direction", "")).strip() == "volatile"),
                    "pressure_medium": sum(1 for item in all_branch_health_summaries if str((item.get("quality_drift") or {}).get("pressure_level", "")).strip() == "medium"),
                    "pressure_high": sum(1 for item in all_branch_health_summaries if str((item.get("quality_drift") or {}).get("pressure_level", "")).strip() == "high"),
                    "pressure_critical": sum(1 for item in all_branch_health_summaries if str((item.get("quality_drift") or {}).get("pressure_level", "")).strip() == "critical"),
                },
                "playbook_counts": playbook_snapshot.get("playbook_counts", {}),
                "playbooks": list(playbook_snapshot.get("branches", []))[:5],
                "active_focus": active_focus,
                "branch_health": branch_health_summaries,
                "recovery_workflows": recovery_workflows,
                "plans": [
                    self._plan_to_dict(
                        plan,
                        runtime_tasks=runtime_tasks,
                        playbook_lookup=playbook_lookup,
                    )
                    for plan in plans
                ],
                "events": list(self._events),
            }


PLANNER_RUNTIME = PlannerRuntime()
