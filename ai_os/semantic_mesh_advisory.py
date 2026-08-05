"""Pure advisory translation for an already-built Semantic Mesh index.

The adapter intentionally performs no storage, planner, dispatch, API, or
runtime work. It exposes aggregate diagnostics only and never copies mesh
nodes, relation payloads, evidence refs, or planned task titles.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ai_os.semantic_mesh import REQUIRED_DIAGNOSTICS, SemanticMeshIndex


ADVISORY_MODE = "advisory_only"
ADVISORY_SOURCE = "semantic_mesh_index"
MAX_FOCUS_AREA_LENGTH = 120


@dataclass(frozen=True)
class SemanticMeshPlanSummary:
    focus_area: str
    plan_group_count: int
    task_count: int
    recovery_request_count: int
    planned_task_title_count: int

    @classmethod
    def from_plan(cls, plan: Mapping[str, Any] | None) -> "SemanticMeshPlanSummary":
        payload = plan if isinstance(plan, Mapping) else {}
        return cls(
            focus_area=_normalize_focus_area(payload.get("focus_area")),
            plan_group_count=_item_count(payload.get("plan_groups")),
            task_count=_item_count(payload.get("tasks")),
            recovery_request_count=_item_count(payload.get("recovery_requests")),
            planned_task_title_count=_item_count(payload.get("planned_task_titles")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "focus_area": self.focus_area,
            "plan_group_count": self.plan_group_count,
            "task_count": self.task_count,
            "recovery_request_count": self.recovery_request_count,
            "planned_task_title_count": self.planned_task_title_count,
        }


@dataclass(frozen=True)
class SemanticMeshAdvisory:
    coverage_state: str
    mesh_diagnostics: dict[str, int]
    relation_evidence_counts: dict[str, int]
    plan_summary: SemanticMeshPlanSummary
    attention_signals: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": ADVISORY_MODE,
            "source": ADVISORY_SOURCE,
            "runtime_enforcement": False,
            "planner_input_applied": False,
            "dispatch_input_applied": False,
            "planner_context_persistence": False,
            "storage_schema_mutation": False,
            "public_api_behavior_mutation": False,
            "coverage_state": self.coverage_state,
            "mesh_diagnostics": dict(self.mesh_diagnostics),
            "relation_evidence_counts": dict(self.relation_evidence_counts),
            "plan_summary": self.plan_summary.to_dict(),
            "attention_signals": [dict(item) for item in self.attention_signals],
        }


def build_semantic_mesh_advisory(
    mesh: SemanticMeshIndex,
    *,
    plan: Mapping[str, Any] | None = None,
) -> SemanticMeshAdvisory:
    """Translate a Semantic Mesh index into a non-enforcing aggregate advisory."""

    if not isinstance(mesh, SemanticMeshIndex):
        raise TypeError("mesh must be a SemanticMeshIndex")

    diagnostics = {
        key: _safe_nonnegative_int(mesh.diagnostics.get(key))
        for key in REQUIRED_DIAGNOSTICS
    }
    relation_evidence_counts = {
        "total": len(mesh.relations),
        "explicit_concept_core": sum(
            1 for relation in mesh.relations if relation.relation_source == "explicit_concept_core"
        ),
        "weak_derived": sum(
            1 for relation in mesh.relations if relation.relation_source == "weak_derived"
        ),
        "diagnostic": sum(1 for relation in mesh.relations if relation.status == "diagnostic"),
        "unclassified_source": sum(
            1
            for relation in mesh.relations
            if relation.relation_source not in {"explicit_concept_core", "weak_derived"}
        ),
    }

    return SemanticMeshAdvisory(
        coverage_state=_coverage_state(diagnostics),
        mesh_diagnostics=diagnostics,
        relation_evidence_counts=relation_evidence_counts,
        plan_summary=SemanticMeshPlanSummary.from_plan(plan),
        attention_signals=_attention_signals(diagnostics),
    )


def _normalize_focus_area(value: object) -> str:
    text = " ".join(str(value or "system").split()).strip() or "system"
    return text[:MAX_FOCUS_AREA_LENGTH]


def _item_count(value: object) -> int:
    return len(value) if isinstance(value, (list, tuple)) else 0


def _safe_nonnegative_int(value: object) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, number)


def _coverage_state(diagnostics: Mapping[str, int]) -> str:
    total_blocks = diagnostics.get("total_blocks", 0)
    strict_blocks = diagnostics.get("strict_concept_blocks", 0)
    legacy_blocks = diagnostics.get("legacy_blocks", 0)
    malformed_blocks = diagnostics.get("malformed_concept_blocks", 0)

    if total_blocks == 0:
        return "empty"
    if strict_blocks > 0 and legacy_blocks == 0 and malformed_blocks == 0:
        return "strict_only"
    if legacy_blocks > 0 and strict_blocks == 0 and malformed_blocks == 0:
        return "legacy_only"
    if malformed_blocks > 0 and strict_blocks == 0 and legacy_blocks == 0:
        return "malformed_only"
    return "mixed"


def _attention_signals(diagnostics: Mapping[str, int]) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    total_blocks = diagnostics.get("total_blocks", 0)
    strict_blocks = diagnostics.get("strict_concept_blocks", 0)

    if total_blocks == 0:
        signals.append(_signal("semantic_mesh_empty", "info", 0, "total_blocks"))
    elif strict_blocks == 0:
        signals.append(
            _signal(
                "strict_concept_coverage_absent",
                "review",
                total_blocks,
                "strict_concept_blocks",
            )
        )

    diagnostic_signals = (
        ("malformed_concept_metadata", "review", "malformed_concept_blocks"),
        ("dangling_relation_targets", "review", "dangling_relation_count"),
        ("unknown_relation_types", "review", "unknown_relation_type_count"),
        ("weak_derived_relations_present", "info", "weak_derived_relation_count"),
    )
    for code, level, diagnostic_key in diagnostic_signals:
        count = diagnostics.get(diagnostic_key, 0)
        if count > 0:
            signals.append(_signal(code, level, count, diagnostic_key))

    return signals


def _signal(code: str, level: str, count: int, basis: str) -> dict[str, Any]:
    return {
        "code": code,
        "level": level,
        "count": _safe_nonnegative_int(count),
        "basis": basis,
        "advisory_only": True,
    }


__all__ = [
    "ADVISORY_MODE",
    "ADVISORY_SOURCE",
    "SemanticMeshAdvisory",
    "SemanticMeshPlanSummary",
    "build_semantic_mesh_advisory",
]
