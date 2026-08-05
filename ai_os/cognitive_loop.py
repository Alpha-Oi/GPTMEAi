"""Official cognitive loop for the AI OS runtime."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from threading import Event, Lock, Thread

from ai_os.agent_runtime import AGENT_RUNTIME, AgentRuntime
from ai_os.config import get_project_paths
from ai_os.concept_core import (
    DecisionEngine,
    EvidenceItem,
    ForeignnessLevel,
    IdentityCore,
    InterventionLevel,
    KnowledgeStatus,
    RiskProfile,
    SafetyGuard,
)
from ai_os.memory_pipeline import corpus_status
from ai_os.semantic_mesh import SemanticMeshIndex
from ai_os.semantic_mesh_advisory import build_semantic_mesh_advisory
from ai_os.stabilization_playbook import build_stabilization_playbooks
from core.memory_engine import MemoryEngine
from core.temporal_engine import TemporalMemory
from execution.ledger import OPERATION_LEDGER
from execution.snapshots import SNAPSHOT_LINEAGE
from execution.runtime import EXECUTION_RUNTIME
from planning.runtime import PLANNER_RUNTIME


SERVICE_NAME = "AI OS Cognitive Loop"
DEFAULT_INTERVAL_SECONDS = 30.0
ACTIVE_TASK_STATES = {"queued", "in_progress"}
CONCEPT_CORE_RED_BUTTON_TERMS = (
    "delete",
    "destroy",
    "drop",
    "remove data",
    "overwrite memory",
    "overwrite storage",
    "schema change",
    "change schema",
    "public api",
    "api-breaking",
    "modify contract",
    "change contract",
    "remove rollback",
    "external irreversible",
    "promote environment",
    "repair environment",
)

MANAGER_BLUEPRINTS = (
    {
        "name": "Memory Manager",
        "role": "manager",
        "capabilities": ["memory-core", "retrieval", "knowledge-graph"],
        "metadata": {"source": "official_cognitive_loop", "layer": "agent_hierarchy"},
    },
    {
        "name": "Research Manager",
        "role": "manager",
        "capabilities": ["analysis", "synthesis", "planning"],
        "metadata": {"source": "official_cognitive_loop", "layer": "agent_hierarchy"},
    },
    {
        "name": "Development Manager",
        "role": "manager",
        "capabilities": ["runtime", "integration", "delivery"],
        "metadata": {"source": "official_cognitive_loop", "layer": "agent_hierarchy"},
    },
)

WORKER_BLUEPRINTS = (
    {
        "name": "Memory Agent",
        "role": "worker",
        "capabilities": ["memory-ingestion", "graph-build", "vector-memory"],
        "metadata": {"source": "official_cognitive_loop", "layer": "execution"},
    },
    {
        "name": "Research Agent",
        "role": "worker",
        "capabilities": ["retrieval", "analysis", "summarization"],
        "metadata": {"source": "official_cognitive_loop", "layer": "execution"},
    },
    {
        "name": "Coding Agent",
        "role": "worker",
        "capabilities": ["runtime", "api", "dashboard"],
        "metadata": {"source": "official_cognitive_loop", "layer": "execution"},
    },
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def shorten_text(value: str, limit: int = 120) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3].rstrip()}..."


def build_task_metadata(
    *,
    owner_hint: str,
    timeout_seconds: int,
    max_retries: int,
    rollback_on_error: bool,
    compensation_action: str,
    compensation_description: str,
) -> dict:
    return {
        "source": "official_cognitive_loop",
        "owner_hint": owner_hint,
        "execution_mode": "commit",
        "branch_id": "main",
        "failure_policy": {
            "timeout_seconds": timeout_seconds,
            "max_retries": max_retries,
            "retry_backoff_seconds": 5,
            "degraded_mode": "report_only",
            "rollback_on_error": rollback_on_error,
        },
        "compensation_plan": [
            {
                "action": compensation_action,
                "description": compensation_description,
                "params": {"owner_hint": owner_hint},
            }
        ],
    }


class CognitiveLoop:
    def __init__(
        self,
        *,
        runtime: AgentRuntime | None = None,
        interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
        state_path: Path | None = None,
    ) -> None:
        self.runtime = runtime or AGENT_RUNTIME
        self.interval_seconds = self._normalize_interval(interval_seconds)
        self.state_path = state_path or (get_project_paths().storage_dir / "cognitive_loop_state.json")
        self._cycle_lock = Lock()
        self._stop_event = Event()
        self._thread: Thread | None = None
        self.running = False
        self._state = self._load_state()

    def _normalize_interval(self, value: float | int | str) -> float:
        try:
            interval = float(value)
        except (TypeError, ValueError):
            interval = DEFAULT_INTERVAL_SECONDS
        return interval if interval > 0 else DEFAULT_INTERVAL_SECONDS

    def _default_state(self) -> dict:
        return {
            "cycle_count": 0,
            "last_cycle_at": None,
            "last_trigger": None,
            "last_error": None,
            "recent_cycles": [],
            "last_cycle": None,
        }

    def _load_state(self) -> dict:
        if not self.state_path.exists():
            return self._default_state()

        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self._default_state()

        if not isinstance(data, dict):
            return self._default_state()

        state = self._default_state()
        state.update(data)
        return state

    def _save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(self._state_for_serialization(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _sanitize_plan_for_serialization(self, plan: dict | None) -> dict | None:
        if not isinstance(plan, dict):
            return plan
        payload = dict(plan)
        payload.pop("concept_core_advisory", None)
        payload.pop("semantic_mesh_advisory", None)
        return payload

    def _sanitize_cycle_for_serialization(self, cycle: dict | None) -> dict | None:
        if not isinstance(cycle, dict):
            return cycle
        payload = dict(cycle)
        payload["plan"] = self._sanitize_plan_for_serialization(payload.get("plan"))
        return payload

    def _state_for_serialization(self) -> dict:
        state = dict(self._state)
        state["last_cycle"] = self._sanitize_cycle_for_serialization(state.get("last_cycle"))
        return state

    def _active_task_titles(self) -> set[str]:
        return {
            str(task.get("title", "")).strip()
            for task in self.runtime.list_tasks()
            if task.get("status") in ACTIVE_TASK_STATES
        }

    def _recent_memory_summary(self, items: list[dict]) -> list[dict]:
        summary = []
        for item in items:
            summary.append(
                {
                    "id": item.get("id"),
                    "text": shorten_text(item.get("text", "")),
                    "tags": list(item.get("tags", [])),
                    "importance": item.get("importance", 0),
                    "created_at": item.get("created_at"),
                }
            )
        return summary

    def _parse_timestamp(self, value) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None

    def _snapshot_coverage_branches(self, planner_branches: list[dict]) -> list[dict]:
        coverage_branches: list[dict] = []

        for branch in planner_branches:
            if not isinstance(branch, dict):
                continue

            branch_id = str(branch.get("branch_id") or "main").strip() or "main"
            status = str(branch.get("status") or "").strip()
            recommendation = str(branch.get("recommendation") or "").strip()
            if status not in {"observe", "degraded"} and recommendation not in {"heightened_monitoring", "manual_review"}:
                continue

            latest_observation_at = self._parse_timestamp(branch.get("last_updated"))
            snapshot_payload = SNAPSHOT_LINEAGE.snapshot(branch_id=branch_id, limit=1)
            latest_snapshot = next(
                (dict(item) for item in list(snapshot_payload.get("snapshots") or []) if isinstance(item, dict)),
                {},
            )

            coverage_state = None
            snapshot_created_at = self._parse_timestamp(latest_snapshot.get("created_at"))
            if not latest_snapshot:
                coverage_state = "missing"
            elif latest_observation_at is not None and snapshot_created_at is not None and snapshot_created_at < latest_observation_at:
                coverage_state = "stale"

            if coverage_state is None:
                continue

            coverage_branches.append(
                {
                    "branch_id": branch_id,
                    "parent_branch_id": branch.get("parent_branch_id"),
                    "status": status or None,
                    "recommendation": recommendation or None,
                    "coverage_state": coverage_state,
                    "latest_observation_at": branch.get("last_updated"),
                    "snapshot_id": latest_snapshot.get("snapshot_id"),
                    "snapshot_created_at": latest_snapshot.get("created_at"),
                    "snapshot_label": latest_snapshot.get("label"),
                    "summary": (
                        f"branch {branch_id} has no registered snapshot coverage after stabilization"
                        if coverage_state == "missing"
                        else f"branch {branch_id} snapshot coverage predates the latest stabilization signal"
                    ),
                }
            )

        return coverage_branches

    def _branch_stabilization_memory(self, memory_items: list[dict], *, limit: int = 5) -> dict:
        records: list[dict] = []
        branch_counter: Counter[str] = Counter()

        for item in memory_items:
            metadata = dict(item.get("metadata") or {})
            if metadata.get("kind") != "branch_stabilization_learning":
                continue

            branch_id = str(metadata.get("branch_id") or "main").strip() or "main"
            branch_counter[branch_id] += 1
            records.append(
                {
                    "memory_id": item.get("id"),
                    "branch_id": branch_id,
                    "plan_id": metadata.get("plan_id"),
                    "plan_status": metadata.get("plan_status"),
                    "pressure_level": metadata.get("pressure_level"),
                    "dispatch_mode": metadata.get("dispatch_mode"),
                    "quality_score": metadata.get("quality_score"),
                    "confidence_score": metadata.get("confidence_score"),
                    "created_at": item.get("created_at"),
                    "text": shorten_text(item.get("text", ""), limit=180),
                }
            )

        records.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        return {
            "count": len(records),
            "recent": records[:limit],
            "branch_counts": [
                {"branch_id": branch_id, "count": count}
                for branch_id, count in branch_counter.most_common(limit)
            ],
        }

    def _persist_branch_stabilization_learning(self, planner_snapshot: dict) -> dict:
        memory_engine = MemoryEngine()
        memory_items = memory_engine.get_all()
        known_plan_states = {
            (
                str((item.get("metadata") or {}).get("plan_id") or "").strip(),
                str((item.get("metadata") or {}).get("plan_status") or "").strip(),
            )
            for item in memory_items
            if dict(item.get("metadata") or {}).get("kind") == "branch_stabilization_learning"
        }

        recorded: list[dict] = []
        for plan in planner_snapshot.get("plans", []):
            if str(plan.get("plan_kind") or "").strip() != "branch_stabilization":
                continue

            plan_id = str(plan.get("id") or "").strip()
            plan_status = str(plan.get("status") or "").strip()
            if not plan_id or plan_status not in {"completed", "failed"}:
                continue

            state_key = (plan_id, plan_status)
            if state_key in known_plan_states:
                continue

            branch_id = str(plan.get("branch_id") or "main").strip() or "main"
            branch_health = dict(plan.get("branch_health") or {})
            dispatch_policy = dict(plan.get("branch_dispatch_policy") or branch_health.get("dispatch_policy") or {})
            quality_drift = dict(branch_health.get("quality_drift") or {})
            plan_steps = [dict(step) for step in plan.get("steps", []) if isinstance(step, dict)]
            playbook_actions = []
            step_status_counts: Counter[str] = Counter()
            for step in plan_steps:
                step_status = str(step.get("status") or "").strip()
                if step_status:
                    step_status_counts[step_status] += 1
                step_key = str(step.get("key") or "").strip()
                step_title = str(step.get("title") or "").strip()
                if not step_key or not step_title or step_key == "branch_stabilization_coordination":
                    continue
                step_metadata = dict(step.get("metadata") or {})
                playbook_actions.append(
                    {
                        "key": step_key,
                        "title": step_title,
                        "owner_hint": step_metadata.get("owner_hint"),
                        "status": step_status or None,
                    }
                )
            text = (
                f"Branch stabilization outcome for {branch_id}: "
                f"status={plan_status}, "
                f"pressure={quality_drift.get('pressure_level', '-')}, "
                f"dispatch={dispatch_policy.get('mode', '-')}, "
                f"quality={branch_health.get('quality_score', '-')}, "
                f"confidence={branch_health.get('confidence_score', '-')}, "
                f"focus={plan.get('focus_area', '-')}, "
                f"title={plan.get('title', '-')}"
            )
            tags = [
                "branch_stabilization",
                "procedural_learning",
                f"status-{plan_status}",
                f"pressure-{quality_drift.get('pressure_level', 'unknown')}",
                f"dispatch-{dispatch_policy.get('mode', 'unknown')}",
            ]
            metadata = {
                "kind": "branch_stabilization_learning",
                "source": "official_cognitive_loop",
                "plan_id": plan_id,
                "plan_status": plan_status,
                "branch_id": branch_id,
                "pressure_level": quality_drift.get("pressure_level"),
                "pressure_score": quality_drift.get("pressure_score"),
                "dispatch_mode": dispatch_policy.get("mode"),
                "dispatch_cap": dispatch_policy.get("max_assignments_for_branch"),
                "quality_score": branch_health.get("quality_score"),
                "confidence_score": branch_health.get("confidence_score"),
                "recommendation": branch_health.get("recommendation"),
                "focus_area": plan.get("focus_area"),
                "step_keys": [item["key"] for item in playbook_actions],
                "step_titles": [item["title"] for item in playbook_actions],
                "owner_hints": [item.get("owner_hint") for item in playbook_actions if item.get("owner_hint")],
                "step_status_counts": dict(step_status_counts),
                "playbook_actions": playbook_actions,
            }
            importance = 9 if plan_status == "failed" else 7
            block = memory_engine.add(text, tags=tags, importance=importance, metadata=metadata)
            known_plan_states.add(state_key)
            recorded.append(
                {
                    "memory_id": block.get("id"),
                    "plan_id": plan_id,
                    "plan_status": plan_status,
                    "branch_id": branch_id,
                    "pressure_level": metadata["pressure_level"],
                    "dispatch_mode": metadata["dispatch_mode"],
                }
            )

        return {
            "recorded_count": len(recorded),
            "records": recorded,
        }

    def perceive(self) -> dict:
        memory_engine = MemoryEngine()
        temporal_engine = TemporalMemory(memory_engine)
        memory_items = memory_engine.get_all()
        runtime_snapshot = self.runtime.snapshot()
        planner_branch_health = PLANNER_RUNTIME.branch_health_snapshot(limit=10)
        stabilization_memory = self._branch_stabilization_memory(memory_items)
        stabilization_playbooks = build_stabilization_playbooks(memory_items, limit=10)
        pipeline_snapshot = corpus_status()
        execution_feedback = EXECUTION_RUNTIME.feedback_summary(limit=5)
        ledger_feedback = OPERATION_LEDGER.feedback_summary(limit=10)
        snapshot_feedback = SNAPSHOT_LINEAGE.snapshot(limit=10)

        tag_counter: Counter[str] = Counter()
        for item in memory_items:
            tag_counter.update(str(tag) for tag in item.get("tags", []))

        return {
            "timestamp": utc_now(),
            "memory_count": len(memory_items),
            "recent_memory": self._recent_memory_summary(temporal_engine.get_recent(5)),
            "top_tags": [{"tag": tag, "count": count} for tag, count in tag_counter.most_common(5)],
            "agent_counts": runtime_snapshot["agent_counts"],
            "task_counts": runtime_snapshot["task_counts"],
            "stabilization_memory": stabilization_memory,
            "stabilization_playbooks": stabilization_playbooks,
            "planner_branch_health": {
                "counts": planner_branch_health.get("branch_counts", {}),
                "branches": planner_branch_health.get("branches", []),
                "playbook_counts": planner_branch_health.get("playbook_counts", {}),
                "playbooks": planner_branch_health.get("playbooks", []),
            },
            "pipeline": {
                "counts": pipeline_snapshot["counts"],
                "available": pipeline_snapshot["available"],
            },
            "execution": execution_feedback,
            "operation_ledger": ledger_feedback,
            "snapshot_lineage": snapshot_feedback,
        }

    def reason(self, perception: dict) -> dict:
        observations: list[str] = []
        focus_tags = [item["tag"] for item in perception["top_tags"]]
        missing_artifacts = [
            artifact
            for artifact, available in perception["pipeline"]["available"].items()
            if not available
        ]
        pressure_branches: list[dict] = []
        stabilization_branch_counts = {
            str(item.get("branch_id") or "main").strip() or "main": int(item.get("count", 0) or 0)
            for item in perception.get("stabilization_memory", {}).get("branch_counts", [])
        }
        stabilization_recent = list(perception.get("stabilization_memory", {}).get("recent", []))
        stabilization_playbook_lookup = {
            str(item.get("branch_id") or "main").strip() or "main": dict(item)
            for item in perception.get("stabilization_playbooks", {}).get("branches", [])
            if isinstance(item, dict)
        }
        snapshot_coverage_branches = self._snapshot_coverage_branches(
            list(perception.get("planner_branch_health", {}).get("branches", []))
        )
        for branch in perception.get("planner_branch_health", {}).get("branches", []):
            pressure_level = str((branch.get("quality_drift") or {}).get("pressure_level", "")).strip()
            dispatch_mode = str((branch.get("dispatch_policy") or {}).get("mode", "")).strip()
            planner_gate = str((branch.get("planner_gate") or {}).get("mode", "")).strip()
            if pressure_level not in {"critical", "high"} and dispatch_mode not in {"blocked", "restricted"} and planner_gate not in {"blocked", "restricted"}:
                continue
            branch_id = branch.get("branch_id") or "main"
            recent_stabilization = next(
                (item for item in stabilization_recent if (item.get("branch_id") or "main") == branch_id),
                None,
            )
            stabilization_playbook = dict(
                (branch.get("stabilization_playbook") or {})
                or stabilization_playbook_lookup.get(str(branch_id), {})
            )
            pressure_branches.append(
                {
                    "branch_id": branch_id,
                    "parent_branch_id": branch.get("parent_branch_id"),
                    "status": branch.get("status"),
                    "pressure_level": pressure_level or "unknown",
                    "pressure_score": (branch.get("quality_drift") or {}).get("pressure_score", 0),
                    "dispatch_mode": dispatch_mode or "open",
                    "planner_gate": planner_gate or "open",
                    "recommendation": branch.get("recommendation"),
                    "summary": branch.get("summary"),
                    "stabilization_memory_count": stabilization_branch_counts.get(str(branch_id), 0),
                    "recent_stabilization_memory": recent_stabilization,
                    "stabilization_playbook": stabilization_playbook or None,
                    "stabilization_playbook_support": stabilization_playbook.get("support_level"),
                    "stabilization_playbook_ready": bool(stabilization_playbook.get("reuse_ready")),
                    "stabilization_playbook_action_count": len(stabilization_playbook.get("recommended_actions", []) or []),
                }
            )

        if perception["agent_counts"]["managers"] < len(MANAGER_BLUEPRINTS):
            observations.append("manager hierarchy is incomplete")
        if perception["agent_counts"]["workers"] < len(WORKER_BLUEPRINTS):
            observations.append("worker hierarchy is incomplete")
        if missing_artifacts:
            observations.append("memory pipeline has missing artifacts")
        if perception["task_counts"]["queued"] == 0 and perception["task_counts"]["in_progress"] == 0:
            observations.append("execution queue is idle")
        if perception["memory_count"] == 0:
            observations.append("runtime memory is empty")
        if perception["execution"]["failed_count"] > 0:
            observations.append("execution layer has failed operations")
        if perception["execution"]["pending_compensation_count"] > 0:
            observations.append("execution layer has pending compensations")
        if perception["execution"]["available_compensation_count"] > 0:
            observations.append("execution layer has available compensations for manual review")
        if perception["execution"]["repeated_attempts"]:
            observations.append("some operations required repeated attempts")
        if perception["operation_ledger"]["repeated_failures"]:
            observations.append("operation ledger shows repeated failure patterns")
        if perception["operation_ledger"]["non_main_branch_count"] > 0:
            observations.append("operation ledger has non-main branch activity")
        if perception["operation_ledger"]["max_branch_depth"] > 0:
            observations.append("operation ledger lineage depth is increasing")
        if perception["snapshot_lineage"]["snapshot_counts"]["total"] == 0:
            observations.append("snapshot lineage has no registered snapshots")
        if (
            perception["operation_ledger"]["non_main_branch_count"]
            > perception["snapshot_lineage"]["snapshot_counts"]["non_main_branch_count"]
        ):
            observations.append("some active branches do not have snapshot coverage yet")
        if snapshot_coverage_branches:
            observations.append("some stabilized branches need refreshed snapshot coverage")
        if pressure_branches:
            observations.append("planner branch pressure requires stabilization work")
        if any(item["dispatch_mode"] == "blocked" for item in pressure_branches):
            observations.append("some branches have dispatch policies that block new work")
        if perception.get("stabilization_memory", {}).get("count", 0) > 0:
            observations.append("branch stabilization memory is available for reuse")
        if any(item.get("stabilization_memory_count", 0) > 0 for item in pressure_branches):
            observations.append("pressure-heavy branches already have stabilization memory")
        if perception.get("stabilization_playbooks", {}).get("playbook_counts", {}).get("reuse_ready", 0) > 0:
            observations.append("stabilization playbooks are available for direct branch reuse")
        if any(item.get("stabilization_playbook_ready") for item in pressure_branches):
            observations.append("pressure-heavy branches already have reusable stabilization playbooks")

        primary_focus = focus_tags[0] if focus_tags else "system"
        execution_attention = (
            perception["execution"]["failed_count"] > 0
            or perception["execution"]["pending_compensation_count"] > 0
            or bool(perception["operation_ledger"]["repeated_failures"])
        )

        return {
            "observations": observations,
            "focus_tags": focus_tags,
            "primary_focus": primary_focus,
            "missing_artifacts": missing_artifacts,
            "queue_idle": perception["task_counts"]["queued"] == 0 and perception["task_counts"]["in_progress"] == 0,
            "execution_attention": execution_attention,
            "recent_failures": perception["execution"]["recent_failures"],
            "pending_compensations": perception["execution"]["pending_compensations"],
            "repeated_attempts": perception["execution"]["repeated_attempts"],
            "repeated_failures": perception["operation_ledger"]["repeated_failures"],
            "hot_branches": perception["operation_ledger"]["hot_branches"],
            "non_main_branch_count": perception["operation_ledger"]["non_main_branch_count"],
            "snapshot_branch_count": perception["snapshot_lineage"]["snapshot_counts"]["branch_count"],
            "snapshot_coverage_branches": snapshot_coverage_branches,
            "pressure_branches": pressure_branches[:3],
            "planner_branch_counts": perception.get("planner_branch_health", {}).get("counts", {}) or perception.get("planner_branch_health", {}).get("branch_counts", {}),
            "stabilization_memory_count": perception.get("stabilization_memory", {}).get("count", 0),
            "stabilization_memory_branches": perception.get("stabilization_memory", {}).get("branch_counts", []),
            "stabilization_playbook_counts": perception.get("stabilization_playbooks", {}).get("playbook_counts", {}),
        }

    def plan(
        self,
        perception: dict,
        reasoning: dict,
        *,
        semantic_mesh_index: SemanticMeshIndex | None = None,
    ) -> dict:
        existing_names = {agent["name"] for agent in self.runtime.list_agents()}
        active_titles = self._active_task_titles()

        registrations: list[dict] = []
        for blueprint in (*MANAGER_BLUEPRINTS, *WORKER_BLUEPRINTS):
            if blueprint["name"] not in existing_names:
                registrations.append(dict(blueprint))

        plan_groups: list[dict] = []

        def apply_lineage(
            task_spec: dict,
            *,
            branch_id: str,
            parent_operation_id: str | None = None,
            parent_branch_id: str | None = None,
        ) -> dict:
            item = dict(task_spec)
            metadata = dict(item.get("metadata", {}))
            metadata["branch_id"] = branch_id
            if parent_operation_id:
                metadata["parent_operation_id"] = parent_operation_id
            if parent_branch_id and parent_branch_id != branch_id:
                metadata["parent_branch_id"] = parent_branch_id
            item["metadata"] = metadata
            return item

        def manager_step(
            *,
            step_key: str,
            title: str,
            owner_hint: str,
            branch_id: str,
            compensation_action: str,
            compensation_description: str,
            parent_operation_id: str | None = None,
            parent_branch_id: str | None = None,
        ) -> dict:
            metadata = build_task_metadata(
                owner_hint=owner_hint,
                timeout_seconds=180,
                max_retries=0,
                rollback_on_error=True,
                compensation_action=compensation_action,
                compensation_description=compensation_description,
            )
            metadata["branch_id"] = branch_id
            if parent_operation_id:
                metadata["parent_operation_id"] = parent_operation_id
            if parent_branch_id and parent_branch_id != branch_id:
                metadata["parent_branch_id"] = parent_branch_id
            return {
                "step_key": step_key,
                "title": title,
                "preferred_role": "manager",
                "metadata": metadata,
            }

        def append_plan_group(
            *,
            group_key: str,
            title: str,
            plan_kind: str,
            focus_area: str,
            branch_id: str,
            manager_owner_hint: str,
            manager_title: str,
            manager_compensation_action: str,
            manager_compensation_description: str,
            tasks: list[dict],
            max_parallel_steps: int = 1,
            source_operation_id: str | None = None,
            parent_branch_id: str | None = None,
        ) -> None:
            if not tasks:
                return

            coordination_key = f"{group_key}_coordination"
            coordination_step = manager_step(
                step_key=coordination_key,
                title=manager_title,
                owner_hint=manager_owner_hint,
                branch_id=branch_id,
                compensation_action=manager_compensation_action,
                compensation_description=manager_compensation_description,
                parent_operation_id=source_operation_id,
                parent_branch_id=parent_branch_id,
            )

            group_tasks = [coordination_step]
            for task_spec in tasks:
                depends_on = list(task_spec.get("depends_on", []))
                if coordination_key not in depends_on:
                    depends_on.insert(0, coordination_key)
                enriched = apply_lineage(
                    {
                        **dict(task_spec),
                        "depends_on": depends_on,
                    },
                    branch_id=branch_id,
                    parent_operation_id=source_operation_id,
                    parent_branch_id=parent_branch_id,
                )
                group_tasks.append(enriched)

            plan_groups.append(
                {
                    "group_key": group_key,
                    "title": title,
                    "plan_kind": plan_kind,
                    "focus_area": focus_area,
                    "branch_id": branch_id,
                    "source_operation_id": source_operation_id,
                    "parent_branch_id": parent_branch_id,
                    "max_parallel_steps": max_parallel_steps,
                    "tasks": group_tasks,
                }
            )

        missing_artifacts = set(reasoning["missing_artifacts"])
        if missing_artifacts:
            memory_tasks: list[dict] = []
            if "index" in missing_artifacts:
                memory_tasks.append(
                    {
                        "step_key": "rebuild_index",
                        "title": "Rebuild chat corpus index",
                        "preferred_role": "worker",
                        "metadata": build_task_metadata(
                            owner_hint="Memory Agent",
                            timeout_seconds=300,
                            max_retries=1,
                            rollback_on_error=False,
                            compensation_action="restore_previous_artifact",
                            compensation_description="Restore previous corpus index if rebuild fails or corrupts the artifact.",
                        ),
                    }
                )
            if "parsed" in missing_artifacts:
                memory_tasks.append(
                    {
                        "step_key": "parse_corpus",
                        "depends_on": ["rebuild_index"] if "index" in missing_artifacts else [],
                        "title": "Parse chat corpus into structured memory",
                        "preferred_role": "worker",
                        "metadata": build_task_metadata(
                            owner_hint="Memory Agent",
                            timeout_seconds=300,
                            max_retries=1,
                            rollback_on_error=False,
                            compensation_action="restore_previous_artifact",
                            compensation_description="Restore previous parsed chats artifact if parsing fails.",
                        ),
                    }
                )
            if "knowledge" in missing_artifacts:
                memory_tasks.append(
                    {
                        "step_key": "build_knowledge",
                        "depends_on": ["parse_corpus"] if "parsed" in missing_artifacts else [],
                        "title": "Build knowledge graph from parsed chats",
                        "preferred_role": "worker",
                        "metadata": build_task_metadata(
                            owner_hint="Memory Agent",
                            timeout_seconds=300,
                            max_retries=1,
                            rollback_on_error=False,
                            compensation_action="restore_previous_artifact",
                            compensation_description="Restore previous knowledge graph artifact if build fails.",
                        ),
                    }
                )
            if "vectors" in missing_artifacts:
                memory_tasks.append(
                    {
                        "step_key": "vectorize_memory",
                        "depends_on": ["parse_corpus"] if "parsed" in missing_artifacts else [],
                        "title": "Vectorize structured chat memory",
                        "preferred_role": "worker",
                        "metadata": build_task_metadata(
                            owner_hint="Memory Agent",
                            timeout_seconds=600,
                            max_retries=0,
                            rollback_on_error=False,
                            compensation_action="restore_previous_artifact",
                            compensation_description="Restore previous vector memory artifact if vectorization fails.",
                        ),
                    }
                )

            append_plan_group(
                group_key="memory_recovery",
                title="Memory pipeline recovery plan",
                plan_kind="recovery",
                focus_area="memory_pipeline",
                branch_id="main",
                manager_owner_hint="Memory Manager",
                manager_title="Coordinate memory pipeline recovery",
                manager_compensation_action="record_memory_recovery_decision",
                manager_compensation_description="Keep the recovery coordination trace even if the memory recovery plan pauses or fails.",
                tasks=memory_tasks,
                max_parallel_steps=1,
            )

        if reasoning["queue_idle"]:
            runtime_tasks = [
                {
                    "step_key": "review_memory_context",
                    "title": f"Review memory context for focus area: {reasoning['primary_focus']}",
                    "preferred_role": "worker",
                    "metadata": build_task_metadata(
                        owner_hint="Research Agent",
                        timeout_seconds=180,
                        max_retries=1,
                        rollback_on_error=True,
                        compensation_action="release_task_claim",
                        compensation_description="Release the research review task and keep only trace metadata if the run fails.",
                    ),
                },
                {
                    "step_key": "inspect_runtime_health",
                    "title": "Inspect AI OS runtime health and propose next actions",
                    "preferred_role": "worker",
                    "metadata": build_task_metadata(
                        owner_hint="Coding Agent",
                        timeout_seconds=180,
                        max_retries=1,
                        rollback_on_error=True,
                        compensation_action="release_task_claim",
                        compensation_description="Release the runtime inspection task and preserve only the failure trace.",
                    ),
                },
            ]

            append_plan_group(
                group_key="runtime_observation",
                title=f"Runtime observation plan for {reasoning['primary_focus']}",
                plan_kind="operational",
                focus_area=reasoning["primary_focus"],
                branch_id="main",
                manager_owner_hint="Research Manager",
                manager_title=f"Coordinate runtime observation for focus area: {reasoning['primary_focus']}",
                manager_compensation_action="record_runtime_observation",
                manager_compensation_description="Keep the runtime observation trail even if the observation plan cannot complete fully.",
                tasks=runtime_tasks,
                max_parallel_steps=2,
            )

        remediation_source = None
        if reasoning["pending_compensations"]:
            remediation_source = dict(reasoning["pending_compensations"][0])
        elif reasoning["recent_failures"]:
            remediation_source = dict(reasoning["recent_failures"][0])
        elif reasoning["repeated_attempts"]:
            remediation_source = dict(reasoning["repeated_attempts"][0])

        remediation_tasks: list[dict] = []
        remediation_branch = str((remediation_source or {}).get("branch_id") or "main").strip() or "main"
        remediation_operation_id = (remediation_source or {}).get("operation_id")

        if reasoning["pending_compensations"]:
            pending_focus = reasoning["pending_compensations"][0]["task_title"] or "execution contract"
            remediation_tasks.append(
                {
                    "step_key": "resolve_pending_compensations",
                    "title": f"Resolve pending execution compensations for: {pending_focus}",
                    "preferred_role": "worker",
                    "metadata": build_task_metadata(
                        owner_hint="Coding Agent",
                        timeout_seconds=180,
                        max_retries=0,
                        rollback_on_error=True,
                        compensation_action="record_compensation_review",
                        compensation_description="Record the compensation decision and keep the operation ledger consistent.",
                    ),
                }
            )

        if reasoning["recent_failures"]:
            failed_focus = reasoning["recent_failures"][0]["task_title"] or "recent execution failure"
            remediation_tasks.append(
                {
                    "step_key": "analyze_recent_failure",
                    "title": f"Analyze recent execution failure: {failed_focus}",
                    "preferred_role": "worker",
                    "metadata": build_task_metadata(
                        owner_hint="Research Agent",
                        timeout_seconds=180,
                        max_retries=0,
                        rollback_on_error=True,
                        compensation_action="record_failure_analysis",
                        compensation_description="Preserve the failure analysis and avoid mutating runtime state if analysis fails.",
                    ),
                }
            )

        if reasoning["repeated_failures"]:
            repeated_focus = reasoning["repeated_failures"][0]["task_title"] or "repeated operation failure"
            remediation_tasks.append(
                {
                    "step_key": "stabilize_repeated_failures",
                    "title": f"Stabilize repeated execution pattern: {repeated_focus}",
                    "preferred_role": "worker",
                    "metadata": build_task_metadata(
                        owner_hint="Coding Agent",
                        timeout_seconds=240,
                        max_retries=0,
                        rollback_on_error=True,
                        compensation_action="record_stability_review",
                        compensation_description="Keep only the stability review trace if the mitigation task cannot complete safely.",
                    ),
                }
            )

        if remediation_tasks:
            append_plan_group(
                group_key="execution_remediation",
                title=f"Execution remediation plan for branch: {remediation_branch}",
                plan_kind="remediation",
                focus_area="execution_resilience",
                branch_id=remediation_branch,
                manager_owner_hint="Development Manager",
                manager_title=f"Coordinate execution remediation for branch: {remediation_branch}",
                manager_compensation_action="record_execution_remediation",
                manager_compensation_description="Preserve the execution remediation trace even if the plan cannot complete fully.",
                tasks=remediation_tasks,
                max_parallel_steps=2,
                source_operation_id=remediation_operation_id,
            )

        branch_tasks: list[dict] = []
        branch_focus = None
        parent_branch_id = None
        branch_max_parallel = 2
        if reasoning["pressure_branches"]:
            pressure_focus = reasoning["pressure_branches"][0]
            branch_focus = str(pressure_focus.get("branch_id") or "main")
            parent_branch_id = pressure_focus.get("parent_branch_id")
            if pressure_focus.get("dispatch_mode") in {"blocked", "restricted"} or pressure_focus.get("pressure_level") == "critical":
                branch_max_parallel = 1
            playbook = dict(pressure_focus.get("stabilization_playbook") or {})
            if playbook.get("reuse_ready") and playbook.get("recommended_actions"):
                branch_tasks.append(
                    {
                        "step_key": "review_branch_stabilization_playbook",
                        "title": f"Review branch stabilization playbook for: {branch_focus}",
                        "preferred_role": "worker",
                        "metadata": build_task_metadata(
                            owner_hint="Research Agent",
                            timeout_seconds=180,
                            max_retries=0,
                            rollback_on_error=True,
                            compensation_action="record_stabilization_playbook_review",
                            compensation_description="Keep only the playbook review trace if the branch pattern cannot be fully validated.",
                        ) | {
                            "playbook_support_level": playbook.get("support_level"),
                            "playbook_action_count": len(playbook.get("recommended_actions", []) or []),
                            "playbook_summary": playbook.get("summary"),
                            "playbook_actions": list(playbook.get("recommended_actions", []))[:4],
                        },
                    }
                )
                branch_tasks.append(
                    {
                        "step_key": "apply_branch_stabilization_playbook",
                        "depends_on": ["review_branch_stabilization_playbook"],
                        "title": f"Apply branch stabilization playbook for: {branch_focus}",
                        "preferred_role": "worker",
                        "metadata": build_task_metadata(
                            owner_hint="Coding Agent",
                            timeout_seconds=240,
                            max_retries=0,
                            rollback_on_error=True,
                            compensation_action="record_branch_playbook_application",
                            compensation_description="Keep only the playbook application trace if the branch controls cannot be tightened safely.",
                        ) | {
                            "playbook_support_level": playbook.get("support_level"),
                            "playbook_action_count": len(playbook.get("recommended_actions", []) or []),
                            "playbook_actions": list(playbook.get("recommended_actions", []))[:4],
                        },
                    }
                )
            elif pressure_focus.get("stabilization_memory_count", 0) > 0:
                recent_memory = pressure_focus.get("recent_stabilization_memory") or {}
                branch_tasks.append(
                    {
                        "step_key": "review_prior_branch_stabilization_memory",
                        "title": f"Review prior stabilization memory for: {branch_focus}",
                        "preferred_role": "worker",
                        "metadata": build_task_metadata(
                            owner_hint="Research Agent",
                            timeout_seconds=180,
                            max_retries=0,
                            rollback_on_error=True,
                            compensation_action="record_stabilization_memory_review",
                            compensation_description="Keep only the stabilization memory review trace if prior branch lessons cannot be fully synthesized.",
                        ) | {
                            "stabilization_memory_count": pressure_focus.get("stabilization_memory_count", 0),
                            "recent_stabilization_plan_id": recent_memory.get("plan_id"),
                            "recent_stabilization_status": recent_memory.get("plan_status"),
                        },
                    }
                )
            branch_tasks.append(
                {
                    "step_key": "review_branch_pressure_controls",
                    "title": f"Review branch pressure controls for: {branch_focus}",
                    "preferred_role": "worker",
                    "metadata": build_task_metadata(
                        owner_hint="Research Agent",
                        timeout_seconds=180,
                        max_retries=0,
                        rollback_on_error=True,
                        compensation_action="record_branch_pressure_review",
                        compensation_description="Keep only branch pressure analysis if the stabilization review cannot complete safely.",
                    ),
                }
            )
            branch_tasks.append(
                {
                    "step_key": "stabilize_branch_dispatch_policy",
                    "title": f"Stabilize dispatch policy for branch: {branch_focus}",
                    "preferred_role": "worker",
                    "metadata": build_task_metadata(
                        owner_hint="Coding Agent",
                        timeout_seconds=240,
                        max_retries=0,
                        rollback_on_error=True,
                        compensation_action="record_branch_dispatch_stabilization",
                        compensation_description="Keep only dispatch stabilization intent if branch controls cannot be tightened safely.",
                    ),
                }
            )
        if reasoning["non_main_branch_count"] > 0 and reasoning["hot_branches"]:
            branch_focus = branch_focus or (reasoning["hot_branches"][0]["branch_id"] or "main")
            parent_branch_id = parent_branch_id or reasoning["hot_branches"][0].get("parent_branch_id")
            branch_tasks.append(
                {
                    "step_key": "review_branch_lineage",
                    "title": f"Review operation lineage for branch: {branch_focus}",
                    "preferred_role": "worker",
                    "metadata": build_task_metadata(
                        owner_hint="Research Agent",
                        timeout_seconds=180,
                        max_retries=0,
                        rollback_on_error=True,
                        compensation_action="record_lineage_review",
                        compensation_description="Keep only lineage analysis metadata if the review cannot complete safely.",
                    ),
                }
            )

        snapshot_coverage_branches = list(reasoning.get("snapshot_coverage_branches", []))
        snapshot_count_gap = reasoning["snapshot_branch_count"] < max(reasoning["non_main_branch_count"] + 1, 1)
        if snapshot_count_gap or snapshot_coverage_branches:
            if snapshot_coverage_branches:
                snapshot_focus = dict(snapshot_coverage_branches[0])
                branch_focus = branch_focus or (snapshot_focus.get("branch_id") or "main")
                parent_branch_id = parent_branch_id or snapshot_focus.get("parent_branch_id")
            else:
                branch_focus = branch_focus or (
                    reasoning["hot_branches"][0]["branch_id"] if reasoning["hot_branches"] else "main"
                )
                parent_branch_id = parent_branch_id or (
                    reasoning["hot_branches"][0].get("parent_branch_id") if reasoning["hot_branches"] else None
                )
            branch_tasks.append(
                {
                    "step_key": "capture_snapshot_coverage",
                    "title": "Capture snapshot coverage for active execution branches",
                    "preferred_role": "worker",
                    "metadata": build_task_metadata(
                        owner_hint="Coding Agent",
                        timeout_seconds=180,
                        max_retries=0,
                        rollback_on_error=True,
                        compensation_action="record_snapshot_review",
                        compensation_description="Keep only snapshot coverage analysis if runtime snapshot capture cannot complete safely.",
                    ),
                }
            )

        if branch_tasks:
            append_plan_group(
                group_key="branch_stabilization",
                title=f"Branch stabilization plan for: {branch_focus or 'main'}",
                plan_kind="branch_stabilization",
                focus_area="branch_time_model",
                branch_id=str(branch_focus or "main"),
                manager_owner_hint="Development Manager",
                manager_title=f"Coordinate branch stabilization for: {branch_focus or 'main'}",
                manager_compensation_action="record_branch_stabilization",
                manager_compensation_description="Keep the branch stabilization trace even if lineage repair pauses or fails.",
                tasks=branch_tasks,
                max_parallel_steps=branch_max_parallel,
                parent_branch_id=parent_branch_id,
            )

        recovery_requests: list[dict] = []
        recovery_candidates: list[dict] = []
        if remediation_tasks:
            recovery_candidates.append(
                {
                    "branch_id": remediation_branch,
                    "operation_id": remediation_operation_id,
                }
            )
        if branch_tasks and branch_focus:
            recovery_candidates.append(
                {
                    "branch_id": str(branch_focus),
                    "operation_id": None,
                }
            )

        seen_recovery_keys: set[tuple[str, str | None]] = set()
        for candidate in recovery_candidates:
            candidate_branch = str(candidate.get("branch_id") or "main").strip() or "main"
            candidate_operation = candidate.get("operation_id")
            cache_key = (candidate_branch, str(candidate_operation or ""))
            if cache_key in seen_recovery_keys:
                continue
            seen_recovery_keys.add(cache_key)

            replay = SNAPSHOT_LINEAGE.replay_plan(
                branch_id=candidate_branch,
                operation_id=candidate_operation,
                limit=10,
            )
            if replay.get("anchor_snapshot") or replay.get("replay_steps"):
                recovery_requests.append(
                    {
                        "title": f"Snapshot replay recovery plan for branch: {candidate_branch}",
                        "branch_id": candidate_branch,
                        "operation_id": candidate_operation,
                        "snapshot_id": (replay.get("anchor_snapshot") or {}).get("snapshot_id"),
                        "replay_step_count": len(replay.get("replay_steps") or []),
                    }
                )

        task_specs = [task for group in plan_groups for task in group["tasks"]]
        planned_titles = [task["title"] for task in task_specs]
        active_conflicts = [title for title in planned_titles if title in active_titles]

        plan_payload = {
            "registrations": registrations,
            "tasks": task_specs,
            "plan_groups": plan_groups,
            "recovery_requests": recovery_requests,
            "skipped_existing_tasks": active_conflicts,
            "focus_area": reasoning["primary_focus"],
            "memory_count": perception["memory_count"],
            "planned_task_titles": planned_titles,
        }
        plan_payload["concept_core_advisory"] = self._build_concept_core_plan_advisory(
            perception,
            reasoning,
            plan_payload,
        )
        if semantic_mesh_index is not None:
            plan_payload["semantic_mesh_advisory"] = build_semantic_mesh_advisory(
                semantic_mesh_index,
                plan=plan_payload,
            ).to_dict()
        return plan_payload

    def _build_concept_core_plan_advisory(self, perception: dict, reasoning: dict, plan: dict) -> dict:
        planned_titles = [str(item or "").strip() for item in list(plan.get("planned_task_titles") or []) if str(item or "").strip()]
        plan_group_count = len(plan.get("plan_groups") or [])
        task_count = len(plan.get("tasks") or [])
        recovery_request_count = len(plan.get("recovery_requests") or [])
        focus_area = str(plan.get("focus_area") or reasoning.get("primary_focus") or "system").strip() or "system"

        action_parts = [
            f"advise cognitive-loop plan for focus area {focus_area}",
            f"plan groups={plan_group_count}",
            f"tasks={task_count}",
            f"recovery requests={recovery_request_count}",
        ]
        if planned_titles:
            action_parts.append("planned titles: " + " | ".join(planned_titles[:8]))
        selected_action = "; ".join(action_parts)

        action_text = selected_action.lower()
        red_button_detected = any(term in action_text for term in CONCEPT_CORE_RED_BUTTON_TERMS)
        evidence = [
            EvidenceItem(
                content=f"memory_count={perception.get('memory_count', 0)}",
                source="cognitive_loop.perceive",
                status=KnowledgeStatus.CONFIRMED,
                confidence=0.9,
                metadata={"field": "memory_count"},
            ),
            EvidenceItem(
                content=f"planned plan groups={plan_group_count}, tasks={task_count}, recovery requests={recovery_request_count}",
                source="cognitive_loop.plan",
                status=KnowledgeStatus.INFERENCE,
                confidence=0.82,
                metadata={"focus_area": focus_area},
            ),
        ]
        observations = [str(item).strip() for item in list(reasoning.get("observations") or []) if str(item).strip()]
        if observations:
            evidence.append(
                EvidenceItem(
                    content=shorten_text(" | ".join(observations[:4]), limit=180),
                    source="cognitive_loop.reason",
                    status=KnowledgeStatus.CONFIRMED,
                    confidence=0.86,
                    metadata={"observation_count": len(observations)},
                )
            )
        if red_button_detected:
            evidence.append(
                EvidenceItem(
                    content="Planned task title contains red-button-like language.",
                    source="cognitive_loop.plan",
                    status=KnowledgeStatus.HYPOTHESIS,
                    confidence=0.7,
                    metadata={"red_button_terms": [term for term in CONCEPT_CORE_RED_BUTTON_TERMS if term in action_text]},
                )
            )

        risk = RiskProfile(
            reversible=not red_button_detected,
            blast_radius="planner_preview" if not red_button_detected else "runtime_or_project_state",
            red_button=red_button_detected,
            risks=["advisory_only_false_positive"] if red_button_detected else [],
        )
        decision = DecisionEngine(safety_guard=SafetyGuard()).decide(
            goal="Provide advisory-only Concept Core decision preview before cognitive-loop act phase.",
            identity=IdentityCore(
                object_id=f"cognitive_loop:plan:{focus_area}",
                object_type="planner_plan_preview",
                name=f"Cognitive loop plan preview for {focus_area}",
                invariants=[
                    "advisory must not change task generation",
                    "advisory must not change planner calls",
                    "advisory must not enforce runtime blocking",
                ],
                boundaries=[
                    "top-level plan output only",
                    "not attached to task metadata",
                    "not attached to planner context",
                ],
            ),
            evidence=evidence,
            risk=risk,
            selected_action=selected_action,
            verification=[
                "review advisory payload before using it for enforcement",
                "run temp-state Concept Core decision advisory smoke",
            ],
            rollback=[
                "remove concept_core_advisory from plan output",
                "keep act() behavior unchanged",
            ],
            rejected_options=[
                "hard planner enforcement",
                "dispatch policy mutation",
                "planner context persistence",
            ],
        )

        decision_payload = decision.to_dict()
        evidence_status_counts = Counter(item.status.value for item in evidence)
        would_block = decision.intervention == InterventionLevel.BLOCK
        red_button_reason = decision.reason if red_button_detected or would_block else None
        if decision_payload.get("foreignness") in {
            ForeignnessLevel.QUARANTINED.value,
            ForeignnessLevel.IRREVERSIBLE_THREAT.value,
        }:
            red_button_reason = red_button_reason or decision.reason

        return {
            "mode": "advisory_only",
            "runtime_enforcement": False,
            "would_block_if_enforced": bool(would_block),
            "decision": decision_payload,
            "evidence_status_counts": dict(evidence_status_counts),
            "red_button": {
                "detected": bool(red_button_detected),
                "reason": red_button_reason,
                "runtime_blocking_applied": False,
            },
            "planned_action_summary": {
                "plan_group_count": plan_group_count,
                "task_count": task_count,
                "recovery_request_count": recovery_request_count,
                "planned_task_titles": planned_titles,
            },
        }

    def act(self, plan: dict) -> dict:
        registered_agents = []
        queued_tasks = []
        planner_plans = []
        planner_execution = {
            "queued_count": 0,
            "queued_steps": [],
        }

        for blueprint in plan["registrations"]:
            record = self.runtime.register_agent(
                name=blueprint["name"],
                role=blueprint["role"],
                capabilities=list(blueprint.get("capabilities", [])),
                metadata=dict(blueprint.get("metadata", {})),
            )
            self.runtime.heartbeat(record["id"], "idle")
            registered_agents.append(
                {
                    "id": record["id"],
                    "name": record["name"],
                    "role": record["role"],
                }
            )

        for plan_group in plan.get("plan_groups", []):
            planner_plan = PLANNER_RUNTIME.create_or_refresh_plan(
                title=plan_group["title"],
                source="official_cognitive_loop",
                plan_kind=plan_group.get("plan_kind", "operational"),
                focus_area=plan_group.get("focus_area"),
                branch_id=plan_group.get("branch_id"),
                source_branch_id=plan_group.get("branch_id"),
                source_operation_id=plan_group.get("source_operation_id"),
                max_parallel_steps=plan_group.get("max_parallel_steps", 1),
                task_specs=plan_group.get("tasks", []),
                context={
                    "memory_count": plan.get("memory_count"),
                    "group_key": plan_group.get("group_key"),
                    "planned_task_titles": [task["title"] for task in plan_group.get("tasks", [])],
                    "skipped_existing_tasks": list(plan.get("skipped_existing_tasks", [])),
                },
            )
            planner_plans.append(planner_plan)
            plan_execution = PLANNER_RUNTIME.execute_ready_steps(plan_id=planner_plan["id"])
            planner_execution["queued_count"] += int(plan_execution.get("queued_count", 0))
            planner_execution["queued_steps"].extend(plan_execution.get("queued_steps", []))
            queued_tasks.extend(plan_execution.get("queued_steps", []))

        for recovery_request in plan.get("recovery_requests", []):
            recovery_plan = PLANNER_RUNTIME.create_recovery_plan_from_replay(
                snapshot_id=recovery_request.get("snapshot_id"),
                branch_id=recovery_request.get("branch_id"),
                operation_id=recovery_request.get("operation_id"),
                title=recovery_request.get("title"),
                max_parallel_steps=1,
            )
            planner_plans.append(recovery_plan)
            recovery_execution = PLANNER_RUNTIME.execute_ready_steps(plan_id=recovery_plan["id"])
            planner_execution["queued_count"] += int(recovery_execution.get("queued_count", 0))
            planner_execution["queued_steps"].extend(recovery_execution.get("queued_steps", []))
            queued_tasks.extend(recovery_execution.get("queued_steps", []))

        return {
            "registered_agents": registered_agents,
            "queued_tasks": queued_tasks,
            "registered_count": len(registered_agents),
            "queued_count": len(queued_tasks),
            "planner_plans": planner_plans,
            "planner_execution": planner_execution,
        }

    def learn(self, perception: dict, reasoning: dict, action: dict) -> dict:
        planner_snapshot = PLANNER_RUNTIME.status_snapshot(limit=20)
        stabilization_learning = self._persist_branch_stabilization_learning(planner_snapshot)
        return {
            "focus_area": reasoning["primary_focus"],
            "observations": list(reasoning["observations"]),
            "registered_count": action["registered_count"],
            "queued_count": action["queued_count"],
            "memory_count": perception["memory_count"],
            "queue_depth_after_cycle": self.runtime.snapshot()["task_counts"]["queued"],
            "planner_feedback": {
                "plan_counts": planner_snapshot["plan_counts"],
                "plan_kind_counts": planner_snapshot.get("plan_kind_counts", {}),
                "step_counts": planner_snapshot["step_counts"],
                "active_focus": planner_snapshot["active_focus"],
                "created_plan_ids": [item.get("id") for item in action.get("planner_plans", []) if item.get("id")],
                "created_plan_kinds": [
                    item.get("plan_kind") for item in action.get("planner_plans", []) if item.get("plan_kind")
                ],
                "reused_count": sum(1 for item in action.get("planner_plans", []) if item.get("reused")),
                "recovery_plan_count": sum(
                    1 for item in action.get("planner_plans", []) if item.get("plan_kind") == "recovery"
                ),
                "branch_stabilization_plan_count": sum(
                    1 for item in action.get("planner_plans", []) if item.get("plan_kind") == "branch_stabilization"
                ),
            },
            "execution_feedback": {
                "failed_count": perception["execution"]["failed_count"],
                "pending_compensation_count": perception["execution"]["pending_compensation_count"],
                "available_compensation_count": perception["execution"]["available_compensation_count"],
                "recent_failure_titles": [
                    item.get("task_title") for item in perception["execution"]["recent_failures"][:3]
                ],
                "repeated_failure_titles": [
                    item.get("task_title") for item in perception["operation_ledger"]["repeated_failures"][:3]
                ],
                "branch_count": perception["operation_ledger"]["branch_count"],
                "non_main_branch_count": perception["operation_ledger"]["non_main_branch_count"],
                "snapshot_count": perception["snapshot_lineage"]["snapshot_counts"]["total"],
            },
            "stabilization_feedback": {
                "memory_count": perception.get("stabilization_memory", {}).get("count", 0),
                "memory_branches": perception.get("stabilization_memory", {}).get("branch_counts", []),
                "playbook_counts": perception.get("stabilization_playbooks", {}).get("playbook_counts", {}),
                "pressure_branch_count": len(reasoning.get("pressure_branches", [])),
                "recorded_learning_count": stabilization_learning["recorded_count"],
                "recorded_learning": stabilization_learning["records"],
            },
        }

    def _record_error(self, trigger: str, exc: Exception) -> None:
        self._state["last_error"] = {
            "timestamp": utc_now(),
            "trigger": trigger,
            "message": str(exc),
        }
        self._save_state()

    def _record_cycle(self, trigger: str, cycle: dict) -> None:
        self._state["cycle_count"] = int(self._state.get("cycle_count", 0)) + 1
        self._state["last_cycle_at"] = cycle["timestamp"]
        self._state["last_trigger"] = trigger
        self._state["last_error"] = None
        self._state["last_cycle"] = self._sanitize_cycle_for_serialization(cycle)

        history_item = {
            "timestamp": cycle["timestamp"],
            "trigger": trigger,
            "focus_area": cycle["reasoning"]["primary_focus"],
            "observations": list(cycle["reasoning"]["observations"]),
            "registered_count": cycle["action"]["registered_count"],
            "queued_count": cycle["action"]["queued_count"],
            "active_plans": cycle["learning"]["planner_feedback"]["plan_counts"]["active"],
            "remediation_plans": cycle["learning"]["planner_feedback"]["plan_kind_counts"].get("remediation", 0),
            "branch_stabilization_plans": cycle["learning"]["planner_feedback"].get("branch_stabilization_plan_count", 0),
            "blocked_plan_steps": cycle["learning"]["planner_feedback"]["step_counts"]["blocked"],
            "failed_operations": cycle["learning"]["execution_feedback"]["failed_count"],
            "pending_compensations": cycle["learning"]["execution_feedback"]["pending_compensation_count"],
            "stabilization_learning_records": cycle["learning"]["stabilization_feedback"]["recorded_learning_count"],
        }

        recent_cycles = [history_item]
        recent_cycles.extend(item for item in self._state.get("recent_cycles", [])[:9] if isinstance(item, dict))
        self._state["recent_cycles"] = recent_cycles
        self._save_state()

    def run_cycle(self, *, trigger: str = "manual") -> dict:
        if not self._cycle_lock.acquire(blocking=False):
            return {
                "status": "busy",
                "service": SERVICE_NAME,
                "message": "cognitive cycle is already in progress",
            }

        try:
            perception = self.perceive()
            reasoning = self.reason(perception)
            plan = self.plan(perception, reasoning)
            action = self.act(plan)
            learning = self.learn(perception, reasoning, action)

            cycle = {
                "timestamp": utc_now(),
                "trigger": trigger,
                "perception": perception,
                "reasoning": reasoning,
                "plan": plan,
                "action": action,
                "learning": learning,
            }
            self._record_cycle(trigger, cycle)

            snapshot = self.status_snapshot()
            snapshot["message"] = "cognitive cycle completed"
            return snapshot
        except Exception as exc:
            self._record_error(trigger, exc)
            raise
        finally:
            self._cycle_lock.release()

    def _loop_runner(self) -> None:
        self.running = True
        try:
            while not self._stop_event.is_set():
                try:
                    self.run_cycle(trigger="background")
                except Exception:
                    pass
                self._stop_event.wait(self.interval_seconds)
        finally:
            self.running = False

    def start(self, *, interval_seconds: float | int | str | None = None) -> dict:
        if interval_seconds is not None:
            self.interval_seconds = self._normalize_interval(interval_seconds)

        if self._thread and self._thread.is_alive():
            return self.status_snapshot()

        self._stop_event.clear()
        self._thread = Thread(target=self._loop_runner, name="ai-os-cognitive-loop", daemon=True)
        self._thread.start()
        snapshot = self.status_snapshot()
        snapshot["message"] = "cognitive loop started"
        return snapshot

    def stop(self) -> dict:
        self._stop_event.set()
        self.running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        snapshot = self.status_snapshot()
        snapshot["message"] = "cognitive loop stopped"
        return snapshot

    def status_snapshot(self) -> dict:
        runtime_snapshot = self.runtime.snapshot()
        memory_engine = MemoryEngine()
        memory_items = memory_engine.get_all()
        return {
            "status": "ok",
            "service": SERVICE_NAME,
            "running": bool(self._thread and self._thread.is_alive() and self.running),
            "interval_seconds": self.interval_seconds,
            "state_file": str(self.state_path),
            "cycle_count": int(self._state.get("cycle_count", 0)),
            "last_cycle_at": self._state.get("last_cycle_at"),
            "last_trigger": self._state.get("last_trigger"),
            "last_error": self._state.get("last_error"),
            "agent_counts": runtime_snapshot["agent_counts"],
            "task_counts": runtime_snapshot["task_counts"],
            "planner_feedback": PLANNER_RUNTIME.status_snapshot(limit=5),
            "execution_feedback": EXECUTION_RUNTIME.feedback_summary(limit=5),
            "ledger_feedback": OPERATION_LEDGER.feedback_summary(limit=10),
            "snapshot_feedback": SNAPSHOT_LINEAGE.snapshot(limit=10),
            "stabilization_memory": self._branch_stabilization_memory(memory_items),
            "stabilization_playbooks": build_stabilization_playbooks(memory_items, limit=10),
            "last_cycle": self._sanitize_cycle_for_serialization(self._state.get("last_cycle")),
            "recent_cycles": self._state.get("recent_cycles", []),
        }


COGNITIVE_LOOP = CognitiveLoop()
