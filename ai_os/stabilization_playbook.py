"""Derive reusable branch stabilization playbooks from procedural memory."""

from __future__ import annotations

from collections import Counter, defaultdict


def normalize_optional_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


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


def _normalize_actions(metadata: dict) -> list[dict]:
    actions: list[dict] = []

    raw_actions = metadata.get("playbook_actions")
    if isinstance(raw_actions, list):
        for index, raw_action in enumerate(raw_actions, start=1):
            if not isinstance(raw_action, dict):
                continue
            key = normalize_optional_text(raw_action.get("key")) or f"action_{index}"
            if key == "branch_stabilization_coordination":
                continue
            title = normalize_optional_text(raw_action.get("title")) or key.replace("_", " ")
            actions.append(
                {
                    "key": key,
                    "title": title,
                    "owner_hint": normalize_optional_text(raw_action.get("owner_hint")),
                    "status": normalize_optional_text(raw_action.get("status")),
                }
            )
    if actions:
        return actions

    raw_step_keys = metadata.get("step_keys")
    raw_step_titles = metadata.get("step_titles")
    raw_owner_hints = metadata.get("owner_hints")
    if not isinstance(raw_step_keys, list):
        return []

    step_titles = list(raw_step_titles) if isinstance(raw_step_titles, list) else []
    owner_hints = list(raw_owner_hints) if isinstance(raw_owner_hints, list) else []
    for index, raw_key in enumerate(raw_step_keys, start=1):
        key = normalize_optional_text(raw_key)
        if not key or key == "branch_stabilization_coordination":
            continue
        title = normalize_optional_text(step_titles[index - 1] if index - 1 < len(step_titles) else None)
        owner_hint = normalize_optional_text(owner_hints[index - 1] if index - 1 < len(owner_hints) else None)
        actions.append(
            {
                "key": key,
                "title": title or key.replace("_", " "),
                "owner_hint": owner_hint,
                "status": None,
            }
        )
    return actions


def extract_stabilization_learning_records(memory_items: list[dict], *, limit: int | None = None) -> list[dict]:
    records: list[dict] = []
    for item in list(memory_items or []):
        metadata = dict(item.get("metadata") or {})
        if metadata.get("kind") != "branch_stabilization_learning":
            continue

        branch_id = normalize_optional_text(metadata.get("branch_id")) or "main"
        plan_status = normalize_optional_text(metadata.get("plan_status")) or "unknown"
        actions = _normalize_actions(metadata)
        record = {
            "memory_id": item.get("id"),
            "branch_id": branch_id,
            "plan_id": normalize_optional_text(metadata.get("plan_id")),
            "plan_status": plan_status,
            "pressure_level": normalize_optional_text(metadata.get("pressure_level")) or "unknown",
            "pressure_score": int(metadata.get("pressure_score", 0) or 0),
            "dispatch_mode": normalize_optional_text(metadata.get("dispatch_mode")) or "unknown",
            "dispatch_cap": metadata.get("dispatch_cap"),
            "quality_score": clamp_int(metadata.get("quality_score", 0)),
            "confidence_score": clamp_int(metadata.get("confidence_score", 0)),
            "recommendation": normalize_optional_text(metadata.get("recommendation")),
            "focus_area": normalize_optional_text(metadata.get("focus_area")),
            "created_at": item.get("created_at"),
            "summary": shorten_text(item.get("text", ""), limit=180),
            "actions": actions,
        }
        records.append(record)

    records.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    if limit is not None:
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = None
        if limit is not None and limit > 0:
            return records[:limit]
    return records


def _playbook_summary(branch_id: str, records: list[dict]) -> dict:
    ordered_records = sorted(records, key=lambda item: str(item.get("created_at") or ""), reverse=True)
    total_records = len(ordered_records)
    successful_records = [item for item in ordered_records if item.get("plan_status") == "completed"]
    failed_records = [item for item in ordered_records if item.get("plan_status") == "failed"]
    success_count = len(successful_records)
    failed_count = len(failed_records)
    success_rate = clamp_int((success_count / total_records) * 100 if total_records else 0)

    quality_values = [int(item.get("quality_score", 0) or 0) for item in ordered_records]
    confidence_values = [int(item.get("confidence_score", 0) or 0) for item in ordered_records]
    average_quality = clamp_int(sum(quality_values) / len(quality_values) if quality_values else 0)
    average_confidence = clamp_int(sum(confidence_values) / len(confidence_values) if confidence_values else 0)

    pressure_counter = Counter(
        item.get("pressure_level") or "unknown"
        for item in ordered_records
        if normalize_optional_text(item.get("pressure_level"))
    )
    dispatch_counter = Counter(
        item.get("dispatch_mode") or "unknown"
        for item in ordered_records
        if normalize_optional_text(item.get("dispatch_mode"))
    )
    focus_counter = Counter(
        item.get("focus_area")
        for item in ordered_records
        if normalize_optional_text(item.get("focus_area"))
    )

    action_source = [item for item in successful_records if item.get("actions")] or [item for item in ordered_records if item.get("actions")]
    action_counter: Counter[str] = Counter()
    action_titles: dict[str, str] = {}
    action_owner_counters: dict[str, Counter[str]] = defaultdict(Counter)
    for item in action_source:
        for action in item.get("actions", []):
            key = normalize_optional_text(action.get("key"))
            if not key:
                continue
            action_counter[key] += 1
            if key not in action_titles:
                action_titles[key] = normalize_optional_text(action.get("title")) or key.replace("_", " ")
            owner_hint = normalize_optional_text(action.get("owner_hint"))
            if owner_hint:
                action_owner_counters[key][owner_hint] += 1

    recommended_actions = []
    for action_key, count in action_counter.most_common(4):
        owner_hint = None
        if action_owner_counters.get(action_key):
            owner_hint = action_owner_counters[action_key].most_common(1)[0][0]
        recommended_actions.append(
            {
                "key": action_key,
                "title": action_titles.get(action_key) or action_key.replace("_", " "),
                "count": int(count),
                "owner_hint": owner_hint,
            }
        )

    if success_count >= 3 and success_rate >= 60 and recommended_actions:
        support_level = "strong"
    elif success_count >= 2 and recommended_actions:
        support_level = "usable"
    elif total_records > 0:
        support_level = "emerging"
    else:
        support_level = "none"

    reuse_ready = support_level in {"usable", "strong"} and bool(recommended_actions)
    dominant_pressure = pressure_counter.most_common(1)[0][0] if pressure_counter else "unknown"
    dominant_dispatch = dispatch_counter.most_common(1)[0][0] if dispatch_counter else "unknown"
    focus_areas = [item[0] for item in focus_counter.most_common(3)]

    if support_level == "strong":
        summary = "branch has a strong stabilization playbook with repeated successful patterns"
    elif support_level == "usable":
        summary = "branch has a reusable stabilization playbook that can guide future recovery work"
    elif failed_count > success_count:
        summary = "branch stabilization history is still mixed and should stay under analyst review"
    elif total_records > 0:
        summary = "branch stabilization history is emerging but not yet strong enough for direct reuse"
    else:
        summary = "branch has no stabilization playbook history yet"

    return {
        "branch_id": branch_id,
        "support_level": support_level,
        "reuse_ready": reuse_ready,
        "record_count": total_records,
        "successful_records": success_count,
        "failed_records": failed_count,
        "success_rate": success_rate,
        "average_quality_score": average_quality,
        "average_confidence_score": average_confidence,
        "dominant_pressure_level": dominant_pressure,
        "dominant_dispatch_mode": dominant_dispatch,
        "focus_areas": focus_areas,
        "recommended_actions": recommended_actions,
        "recent_plan_ids": [item.get("plan_id") for item in ordered_records[:3] if item.get("plan_id")],
        "last_recorded_at": ordered_records[0].get("created_at") if ordered_records else None,
        "recent_learning": ordered_records[:3],
        "summary": summary,
    }


def build_stabilization_playbooks(memory_items: list[dict], *, limit: int | None = None) -> dict:
    records = extract_stabilization_learning_records(memory_items)
    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        grouped[str(record.get("branch_id") or "main").strip() or "main"].append(record)

    playbooks = [_playbook_summary(branch_id, branch_records) for branch_id, branch_records in grouped.items()]
    support_rank = {"strong": 0, "usable": 1, "emerging": 2, "none": 3}
    playbooks.sort(
        key=lambda item: (
            support_rank.get(str(item.get("support_level") or "none"), 9),
            -int(item.get("success_rate", 0) or 0),
            str(item.get("last_recorded_at") or ""),
            str(item.get("branch_id") or ""),
        ),
        reverse=False,
    )

    total_playbooks = len(playbooks)
    playbook_counts = {
        "total": total_playbooks,
        "strong": sum(1 for item in playbooks if item.get("support_level") == "strong"),
        "usable": sum(1 for item in playbooks if item.get("support_level") == "usable"),
        "emerging": sum(1 for item in playbooks if item.get("support_level") == "emerging"),
        "reuse_ready": sum(1 for item in playbooks if bool(item.get("reuse_ready"))),
    }

    if limit is not None:
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = None
        if limit is not None and limit > 0:
            playbooks = playbooks[:limit]

    return {
        "service": "AI OS Stabilization Playbooks",
        "playbook_counts": playbook_counts,
        "branches": playbooks,
    }
