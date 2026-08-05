"""Role policy helpers for capability-aware agent selection and dispatch."""

from __future__ import annotations

from collections import Counter


PLAN_KIND_PRIORITY = {
    "recovery": 0,
    "remediation": 1,
    "branch_stabilization": 2,
    "operational": 3,
}

OWNER_HINT_CAPABILITIES = {
    "Memory Manager": ["memory-core", "retrieval", "knowledge-graph"],
    "Research Manager": ["analysis", "synthesis", "planning"],
    "Development Manager": ["runtime", "integration", "delivery"],
    "Memory Agent": ["memory-ingestion", "graph-build", "vector-memory"],
    "Research Agent": ["retrieval", "analysis", "summarization"],
    "Coding Agent": ["runtime", "api", "dashboard"],
}

KEYWORD_CAPABILITY_HINTS = {
    "memory": ["memory-core", "memory-ingestion", "knowledge-graph", "vector-memory", "graph-build"],
    "knowledge": ["knowledge-graph", "graph-build"],
    "vector": ["vector-memory"],
    "graph": ["knowledge-graph", "graph-build"],
    "retrieval": ["retrieval", "analysis"],
    "research": ["retrieval", "analysis", "summarization", "synthesis"],
    "analy": ["analysis", "retrieval"],
    "review": ["analysis", "retrieval"],
    "reason": ["analysis", "planning"],
    "plan": ["planning", "synthesis"],
    "summary": ["summarization", "analysis"],
    "runtime": ["runtime", "integration", "delivery"],
    "recover": ["runtime", "integration", "delivery"],
    "remedi": ["runtime", "integration", "delivery"],
    "branch": ["runtime", "integration", "analysis"],
    "snapshot": ["runtime", "integration", "analysis"],
    "lineage": ["analysis", "planning"],
    "replay": ["runtime", "integration", "analysis"],
    "reconcile": ["runtime", "integration", "delivery"],
    "code": ["runtime", "api", "dashboard"],
    "develop": ["runtime", "integration", "delivery"],
    "api": ["api", "runtime"],
    "dashboard": ["dashboard", "runtime"],
}


def optional_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_capabilities(values) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for value in list(values or []):
        text = optional_text(value)
        if not text:
            continue
        token = text.lower()
        if token in seen:
            continue
        seen.add(token)
        normalized.append(token)
    return normalized


def normalize_words(value: str) -> set[str]:
    cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in str(value or ""))
    return {item for item in cleaned.split() if item}


def _coerce_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def dispatch_policy_for_task(task: dict) -> dict:
    metadata = dict(task.get("metadata", {}) or {})
    raw_policy = dict(metadata.get("dispatch_policy") or {})
    plan_kind = optional_text(metadata.get("plan_kind")) or optional_text(task.get("plan_kind")) or "operational"
    branch_id = (
        optional_text(task.get("branch_id"))
        or optional_text(metadata.get("branch_id"))
        or optional_text(metadata.get("plan_branch_id"))
        or "main"
    )

    mode = optional_text(raw_policy.get("mode")) or optional_text(metadata.get("branch_planner_gate_mode")) or "open"
    recommended_action = (
        optional_text(raw_policy.get("recommended_action"))
        or optional_text(metadata.get("branch_planner_gate_action"))
        or "normal_dispatch"
    )
    summary = optional_text(raw_policy.get("summary")) or "dispatch may proceed"
    pressure_level = (
        optional_text(raw_policy.get("pressure_level"))
        or optional_text(metadata.get("branch_pressure_level"))
        or "low"
    )
    pressure_score = max(0, _coerce_int(raw_policy.get("pressure_score", metadata.get("branch_pressure_score", 0)), 0))

    allow_dispatch = raw_policy.get("allow_dispatch")
    if allow_dispatch is None:
        allow_dispatch = mode != "blocked"
        if plan_kind == "operational" and mode == "restricted":
            allow_dispatch = False
    allow_dispatch = bool(allow_dispatch)

    max_assignments_for_branch = raw_policy.get("max_assignments_for_branch")
    if max_assignments_for_branch is not None:
        max_assignments_for_branch = max(0, min(_coerce_int(max_assignments_for_branch, 0), 8))
    elif not allow_dispatch:
        max_assignments_for_branch = 0
    elif mode == "restricted":
        max_assignments_for_branch = 1
    elif mode == "guarded":
        max_assignments_for_branch = 1 if plan_kind == "operational" else 2
    else:
        max_assignments_for_branch = None

    return {
        "branch_id": branch_id,
        "plan_kind": plan_kind,
        "mode": mode,
        "allow_dispatch": allow_dispatch,
        "max_assignments_for_branch": max_assignments_for_branch,
        "pressure_level": pressure_level,
        "pressure_score": pressure_score,
        "recommended_action": recommended_action,
        "summary": summary,
    }


def evaluate_task_dispatch(task: dict, branch_assignment_counts: Counter | None = None) -> dict:
    policy = dispatch_policy_for_task(task)
    branch_id = policy["branch_id"]
    active_assignments = int((branch_assignment_counts or Counter()).get(branch_id, 0) or 0)
    branch_limit = policy.get("max_assignments_for_branch")

    if not policy.get("allow_dispatch", True):
        reason = policy.get("summary") or "dispatch blocked by branch policy"
        return {
            "eligible": False,
            "reason": reason,
            "active_assignments": active_assignments,
            "dispatch_policy": policy,
        }

    if branch_limit is not None and active_assignments >= int(branch_limit):
        reason = f"branch dispatch limit reached ({active_assignments}/{branch_limit})"
        return {
            "eligible": False,
            "reason": reason,
            "active_assignments": active_assignments,
            "dispatch_policy": policy,
        }

    return {
        "eligible": True,
        "reason": None,
        "active_assignments": active_assignments,
        "dispatch_policy": policy,
    }


def infer_required_capabilities(task: dict) -> list[str]:
    metadata = dict(task.get("metadata", {}) or {})
    owner_hint = optional_text(metadata.get("owner_hint"))
    inferred: list[str] = []
    inferred.extend(metadata.get("required_capabilities", []) or [])

    if owner_hint:
        inferred.extend(OWNER_HINT_CAPABILITIES.get(owner_hint, []))

    plan_kind = optional_text(metadata.get("plan_kind")) or optional_text(task.get("plan_kind"))
    if plan_kind == "recovery":
        inferred.extend(["runtime", "integration", "analysis"])
    elif plan_kind == "remediation":
        inferred.extend(["runtime", "integration", "delivery"])
    elif plan_kind == "branch_stabilization":
        inferred.extend(["runtime", "integration", "planning"])
    elif plan_kind == "operational":
        inferred.extend(["analysis", "planning"])

    combined_text = " ".join(
        str(item)
        for item in [
            task.get("title"),
            metadata.get("plan_focus_area"),
            metadata.get("plan_kind"),
            metadata.get("owner_hint"),
        ]
        if item
    ).lower()
    for keyword, capability_hints in KEYWORD_CAPABILITY_HINTS.items():
        if keyword in combined_text:
            inferred.extend(capability_hints)

    return normalize_capabilities(inferred)


def task_priority(task: dict) -> tuple[int, int, str, int]:
    metadata = dict(task.get("metadata", {}) or {})
    plan_kind = optional_text(metadata.get("plan_kind")) or optional_text(task.get("plan_kind")) or "operational"
    preferred_role = optional_text(task.get("preferred_role"))
    created_at = str(task.get("created_at") or "")
    task_id = int(task.get("id", 0) or 0)
    return (
        PLAN_KIND_PRIORITY.get(plan_kind, 99),
        0 if preferred_role == "manager" else 1,
        created_at,
        task_id,
    )


def _affinity_bonus(agent: dict, task: dict, required_capabilities: list[str]) -> tuple[int, list[str]]:
    reasons: list[str] = []
    bonus = 0
    agent_name = str(agent.get("name", "")).strip().lower()
    metadata = dict(task.get("metadata", {}) or {})
    plan_kind = optional_text(metadata.get("plan_kind")) or "operational"
    branch_id = optional_text(task.get("branch_id")) or optional_text(metadata.get("branch_id")) or "main"
    agent_metadata = dict(agent.get("metadata", {}) or {})

    if branch_id and optional_text(agent_metadata.get("last_branch_id")) == branch_id:
        bonus += 10
        reasons.append(f"branch continuity {branch_id}")

    if plan_kind == "recovery" and ("development" in agent_name or "coding" in agent_name):
        bonus += 15
        reasons.append("recovery affinity")
    elif plan_kind == "remediation" and ("development" in agent_name or "coding" in agent_name):
        bonus += 12
        reasons.append("remediation affinity")
    elif plan_kind == "operational" and ("research" in agent_name):
        bonus += 12
        reasons.append("operational affinity")
    elif plan_kind == "branch_stabilization" and ("development" in agent_name or "research" in agent_name):
        bonus += 10
        reasons.append("branch affinity")

    if "memory-core" in required_capabilities and "memory" in agent_name:
        bonus += 8
        reasons.append("memory affinity")
    if "analysis" in required_capabilities and "research" in agent_name:
        bonus += 8
        reasons.append("analysis affinity")
    if "runtime" in required_capabilities and ("development" in agent_name or "coding" in agent_name):
        bonus += 8
        reasons.append("runtime affinity")

    return bonus, reasons


def score_agent_for_task(agent: dict, task: dict, *, allow_busy: bool = False) -> dict:
    metadata = dict(task.get("metadata", {}) or {})
    preferred_role = optional_text(task.get("preferred_role"))
    owner_hint = optional_text(metadata.get("owner_hint"))
    preferred_agent_id = optional_text(metadata.get("preferred_agent_id"))
    required_capabilities = infer_required_capabilities(task)
    agent_capabilities = normalize_capabilities(agent.get("capabilities", []))
    agent_name = str(agent.get("name", "")).strip()
    agent_words = normalize_words(agent_name)
    owner_words = normalize_words(owner_hint or "")
    reasons: list[str] = []

    agent_role = optional_text(agent.get("role"))
    if preferred_role and agent_role != preferred_role:
        return {
            "eligible": False,
            "score": -999,
            "reasons": [f"role mismatch: needs {preferred_role}"],
            "required_capabilities": required_capabilities,
        }

    is_busy = str(agent.get("status", "")).strip() == "busy" or agent.get("current_task_id") is not None
    if is_busy and not allow_busy:
        return {
            "eligible": False,
            "score": -500,
            "reasons": ["agent is busy"],
            "required_capabilities": required_capabilities,
        }

    score = 20
    if preferred_role and agent_role == preferred_role:
        score += 40
        reasons.append(f"preferred role {preferred_role}")

    if preferred_agent_id and preferred_agent_id == optional_text(agent.get("id")):
        score += 140
        reasons.append("preferred agent id match")

    exact_owner_match = bool(owner_hint and owner_hint.casefold() == agent_name.casefold())
    if exact_owner_match:
        score += 120
        reasons.append("owner hint exact match")
    elif owner_hint and owner_words and agent_words.intersection(owner_words):
        score += 28
        reasons.append("owner hint partial match")

    capability_overlap = [cap for cap in required_capabilities if cap in agent_capabilities]
    if capability_overlap:
        score += 18 * len(capability_overlap)
        reasons.append("capability overlap: " + ", ".join(capability_overlap[:3]))
    elif required_capabilities and not exact_owner_match:
        score -= 12
        reasons.append("no direct capability overlap")

    affinity_bonus, affinity_reasons = _affinity_bonus(agent, task, required_capabilities)
    score += affinity_bonus
    reasons.extend(affinity_reasons)

    tasks_completed = int(agent.get("tasks_completed", 0) or 0)
    tasks_failed = int(agent.get("tasks_failed", 0) or 0)
    tasks_claimed = int(agent.get("tasks_claimed", 0) or 0)
    if tasks_completed:
        score += min(tasks_completed, 10)
        reasons.append(f"completion history {tasks_completed}")
    if tasks_failed:
        score -= min(tasks_failed * 6, 30)
        reasons.append(f"failure penalty {tasks_failed}")
    if tasks_claimed:
        score -= min(tasks_claimed // 3, 10)
        reasons.append(f"load balance penalty {tasks_claimed}")

    return {
        "eligible": True,
        "score": score,
        "reasons": reasons,
        "required_capabilities": required_capabilities,
        "capability_overlap": capability_overlap,
        "owner_hint": owner_hint,
        "preferred_role": preferred_role,
    }


def rank_agents_for_task(task: dict, agents: list[dict], *, include_busy: bool = False, limit: int = 5) -> list[dict]:
    ranked: list[dict] = []
    for agent in list(agents or []):
        scorecard = score_agent_for_task(agent, task, allow_busy=include_busy)
        ranked.append(
            {
                "agent_id": agent.get("id"),
                "agent_name": agent.get("name"),
                "role": agent.get("role"),
                "status": agent.get("status"),
                "current_task_id": agent.get("current_task_id"),
                "capabilities": list(agent.get("capabilities", [])),
                **scorecard,
            }
        )

    ranked.sort(
        key=lambda item: (
            0 if item["eligible"] else 1,
            -int(item.get("score", -9999)),
            0 if item.get("status") == "idle" else 1,
            str(item.get("agent_name", "")).lower(),
        )
    )
    return ranked[: max(1, int(limit or 1))]


def rank_tasks_for_agent(
    agent: dict,
    tasks: list[dict],
    *,
    limit: int = 5,
    branch_assignment_counts: Counter | None = None,
) -> list[dict]:
    ranked: list[dict] = []
    for task in list(tasks or []):
        if str(task.get("status", "")).strip() != "queued":
            continue
        dispatch = evaluate_task_dispatch(task, branch_assignment_counts)
        scorecard = score_agent_for_task(agent, task, allow_busy=True)
        eligible = bool(scorecard.get("eligible")) and bool(dispatch.get("eligible"))
        reasons = list(scorecard.get("reasons", []))
        if dispatch.get("reason"):
            reasons.append(str(dispatch["reason"]))
        ranked.append(
            {
                "task_id": task.get("id"),
                "title": task.get("title"),
                "status": task.get("status"),
                "branch_id": task.get("branch_id"),
                "created_at": task.get("created_at"),
                "preferred_role": task.get("preferred_role"),
                "plan_kind": dict(task.get("metadata", {}) or {}).get("plan_kind"),
                **scorecard,
                "eligible": eligible,
                "score": scorecard.get("score", -999) if eligible else -900,
                "reasons": reasons,
                "dispatch_policy": dispatch.get("dispatch_policy"),
                "dispatch_blocked_reason": dispatch.get("reason"),
                "active_branch_assignments": dispatch.get("active_assignments", 0),
            }
        )

    ranked.sort(
        key=lambda item: (
            0 if item["eligible"] else 1,
            -int(item.get("score", -9999)),
            task_priority(item),
            int(item.get("task_id", 0) or 0),
        )
    )
    return ranked[: max(1, int(limit or 1))]


def build_dispatch_plan(tasks: list[dict], agents: list[dict], *, limit: int = 10) -> dict:
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 10
    limit = max(1, min(limit, 25))

    queued_tasks = [dict(task) for task in list(tasks or []) if str(task.get("status", "")).strip() == "queued"]
    queued_tasks.sort(key=task_priority)

    idle_agents = {
        str(agent.get("id")): dict(agent)
        for agent in list(agents or [])
        if str(agent.get("status", "")).strip() == "idle" and agent.get("current_task_id") is None
    }

    assignments: list[dict] = []
    recommendations: list[dict] = []
    unassigned: list[dict] = []
    branch_assignment_counts: Counter[str] = Counter()
    for task in list(tasks or []):
        if str(task.get("status", "")).strip() != "in_progress":
            continue
        branch_id = dispatch_policy_for_task(task).get("branch_id") or "main"
        branch_assignment_counts[str(branch_id)] += 1

    for task in queued_tasks[:limit]:
        dispatch = evaluate_task_dispatch(task, branch_assignment_counts)
        ranked = rank_agents_for_task(
            task,
            list(idle_agents.values()),
            include_busy=False,
            limit=max(len(idle_agents), 1),
        )
        selected = next((item for item in ranked if item.get("eligible")), None)
        recommendation = {
            "task_id": task.get("id"),
            "title": task.get("title"),
            "branch_id": task.get("branch_id"),
            "preferred_role": task.get("preferred_role"),
            "plan_kind": dict(task.get("metadata", {}) or {}).get("plan_kind"),
            "owner_hint": dict(task.get("metadata", {}) or {}).get("owner_hint"),
            "required_capabilities": infer_required_capabilities(task),
            "dispatch_policy": dispatch.get("dispatch_policy"),
            "dispatch_blocked_reason": dispatch.get("reason"),
            "active_branch_assignments": dispatch.get("active_assignments", 0),
            "selected_agent": selected,
            "candidates": ranked[:3],
        }
        recommendations.append(recommendation)

        if not dispatch.get("eligible") or selected is None:
            unassigned.append(recommendation)
            continue

        assignments.append(
            {
                "task_id": task.get("id"),
                "title": task.get("title"),
                "branch_id": task.get("branch_id"),
                "plan_kind": dict(task.get("metadata", {}) or {}).get("plan_kind"),
                "agent_id": selected.get("agent_id"),
                "agent_name": selected.get("agent_name"),
                "score": selected.get("score"),
                "reasons": list(selected.get("reasons", [])),
                "dispatch_policy": dispatch.get("dispatch_policy"),
            }
        )
        branch_id = dispatch.get("dispatch_policy", {}).get("branch_id") or task.get("branch_id") or "main"
        branch_assignment_counts[str(branch_id)] += 1
        idle_agents.pop(str(selected.get("agent_id")), None)

    required_capability_counter: Counter[str] = Counter()
    for item in recommendations:
        required_capability_counter.update(item.get("required_capabilities", []))

    return {
        "assignment_count": len(assignments),
        "assignments": assignments,
        "recommendations": recommendations,
        "unassigned": unassigned,
        "required_capabilities": [
            {"capability": capability, "count": count}
            for capability, count in required_capability_counter.most_common(6)
        ],
    }
