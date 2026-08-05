"""Execution contracts and normalization helpers for the AI OS execution layer."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from itertools import count


VALID_EXECUTION_MODES = {"commit", "simulate"}
_OPERATION_COUNTER = count(1)

DEFAULT_FAILURE_POLICY = {
    "timeout_seconds": 120,
    "max_retries": 0,
    "retry_backoff_seconds": 0,
    "degraded_mode": "report_only",
    "rollback_on_error": True,
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def generate_operation_id(prefix: str = "op") -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{stamp}_{next(_OPERATION_COUNTER):04d}"


def _normalize_int(value, default: int, minimum: int = 0) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        normalized = default
    return normalized if normalized >= minimum else default


def _normalize_bool(value, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    return default


def _normalize_optional_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_failure_policy(policy: dict | None) -> dict:
    normalized = dict(DEFAULT_FAILURE_POLICY)
    if not isinstance(policy, dict):
        return normalized

    normalized["timeout_seconds"] = _normalize_int(policy.get("timeout_seconds"), normalized["timeout_seconds"], minimum=1)
    normalized["max_retries"] = _normalize_int(policy.get("max_retries"), normalized["max_retries"], minimum=0)
    normalized["retry_backoff_seconds"] = _normalize_int(
        policy.get("retry_backoff_seconds"),
        normalized["retry_backoff_seconds"],
        minimum=0,
    )

    degraded_mode = str(policy.get("degraded_mode", normalized["degraded_mode"])).strip().lower()
    normalized["degraded_mode"] = degraded_mode or normalized["degraded_mode"]
    normalized["rollback_on_error"] = _normalize_bool(
        policy.get("rollback_on_error"),
        normalized["rollback_on_error"],
    )
    return normalized


def normalize_compensation_plan(plan, title: str = "") -> list[dict]:
    normalized: list[dict] = []

    def _append_step(step_action: str, step_description: str = "", params: dict | None = None) -> None:
        action = str(step_action or "").strip() or "report_only"
        description = str(step_description or "").strip() or action.replace("_", " ")
        normalized.append(
            {
                "action": action,
                "description": description,
                "params": dict(params or {}),
            }
        )

    if isinstance(plan, list):
        for step in plan:
            if isinstance(step, str):
                _append_step(step, step)
            elif isinstance(step, dict):
                _append_step(step.get("action", "report_only"), step.get("description", ""), step.get("params"))
    elif isinstance(plan, dict):
        _append_step(plan.get("action", "report_only"), plan.get("description", ""), plan.get("params"))
    elif isinstance(plan, str) and plan.strip():
        _append_step(plan, plan)

    if not normalized:
        _append_step(
            "report_only",
            f"Manual compensation review for task: {str(title or 'unnamed task').strip()}",
        )

    return normalized


def normalize_delta(delta, title: str = "") -> dict:
    normalized: dict = {}

    if isinstance(delta, dict):
        normalized = dict(delta)
    elif isinstance(delta, str) and delta.strip():
        normalized = {"summary": delta.strip()}

    summary = str(
        normalized.get("summary")
        or normalized.get("description")
        or f"Expected state transition for task: {str(title or 'unnamed task').strip()}"
    ).strip()
    kind = str(normalized.get("kind", "state_transition")).strip() or "state_transition"

    normalized["summary"] = summary
    normalized["kind"] = kind
    return normalized


def build_execution_fields(
    title: str,
    *,
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
    metadata = dict(metadata or {})

    resolved_operation_id = str(operation_id or metadata.get("operation_id") or generate_operation_id()).strip()
    if not resolved_operation_id:
        resolved_operation_id = generate_operation_id()

    resolved_mode = str(execution_mode or metadata.get("execution_mode") or "commit").strip().lower()
    if resolved_mode not in VALID_EXECUTION_MODES:
        resolved_mode = "commit"

    resolved_branch_id = str(branch_id or metadata.get("branch_id") or "main").strip() or "main"
    resolved_parent_branch_id = _normalize_optional_text(
        parent_branch_id if parent_branch_id is not None else metadata.get("parent_branch_id")
    )
    if resolved_parent_branch_id == resolved_branch_id:
        resolved_parent_branch_id = None
    if resolved_parent_branch_id is None and resolved_branch_id != "main":
        resolved_parent_branch_id = "main"

    resolved_parent_operation_id = _normalize_optional_text(
        parent_operation_id if parent_operation_id is not None else metadata.get("parent_operation_id")
    )
    resolved_failure_policy = normalize_failure_policy(failure_policy if failure_policy is not None else metadata.get("failure_policy"))
    resolved_compensation_plan = normalize_compensation_plan(
        compensation_plan if compensation_plan is not None else metadata.get("compensation_plan"),
        title=title,
    )
    resolved_delta = normalize_delta(
        delta if delta is not None else metadata.get("delta"),
        title=title,
    )

    metadata.update(
        {
            "operation_id": resolved_operation_id,
            "execution_mode": resolved_mode,
            "branch_id": resolved_branch_id,
            "parent_branch_id": resolved_parent_branch_id,
            "parent_operation_id": resolved_parent_operation_id,
            "failure_policy": resolved_failure_policy,
            "compensation_plan": resolved_compensation_plan,
            "delta": resolved_delta,
        }
    )

    return {
        "operation_id": resolved_operation_id,
        "execution_mode": resolved_mode,
        "branch_id": resolved_branch_id,
        "parent_branch_id": resolved_parent_branch_id,
        "parent_operation_id": resolved_parent_operation_id,
        "failure_policy": resolved_failure_policy,
        "compensation_plan": resolved_compensation_plan,
        "delta": resolved_delta,
        "metadata": metadata,
    }


@dataclass
class OperationRecord:
    operation_id: str
    task_id: int
    task_title: str
    execution_mode: str = "commit"
    branch_id: str = "main"
    parent_branch_id: str | None = None
    parent_operation_id: str | None = None
    status: str = "planned"
    compensation_status: str = "ready"
    failure_policy: dict = field(default_factory=lambda: dict(DEFAULT_FAILURE_POLICY))
    compensation_plan: list[dict] = field(default_factory=list)
    delta: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)
    claimed_at: str | None = None
    completed_at: str | None = None
    compensated_at: str | None = None
    assigned_agent_id: str | None = None
    assigned_agent_name: str | None = None
    attempts: int = 0
    result: str | None = None
    last_error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)
