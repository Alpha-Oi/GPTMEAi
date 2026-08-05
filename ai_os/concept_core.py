"""Typed Concept Core primitives for GPTMEAi reasoning safety.

This module is intentionally additive-only. It defines validation and decision
helpers without mutating runtime state, storage schemas, API routes, or memory
records.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class KnowledgeStatus(str, Enum):
    CONFIRMED = "confirmed"
    INFERENCE = "inference"
    HYPOTHESIS = "hypothesis"
    UNKNOWN = "unknown"
    CONTRADICTION = "contradiction"


class ForeignnessLevel(str, Enum):
    KNOWN = "known"
    FAMILIAR = "familiar"
    PARTIALLY_UNDERSTOOD = "partially_understood"
    UNKNOWN = "unknown"
    RISKY = "risky"
    QUARANTINED = "quarantined"
    IRREVERSIBLE_THREAT = "irreversible_threat"


class InterventionLevel(str, Enum):
    OBSERVE = "observe"
    ASK = "ask"
    VERIFY = "verify"
    PATCH = "patch"
    REFACTOR = "refactor"
    REBUILD_FILE = "rebuild_file"
    REBUILD_MODULE = "rebuild_module"
    REDESIGN = "redesign"
    BLOCK = "block"


RED_BUTTON_TERMS = (
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

DESTRUCTIVE_TERMS = (
    "delete",
    "destroy",
    "drop",
    "remove",
    "overwrite",
    "move",
    "rename",
    "repair",
    "promote",
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _coerce_text(value: Any, field_name: str, *, required: bool = True) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise ValueError(f"{field_name} is required")
    return text


def _coerce_status(value: KnowledgeStatus | str) -> KnowledgeStatus:
    if isinstance(value, KnowledgeStatus):
        return value
    text = str(value or "").strip().lower()
    try:
        return KnowledgeStatus(text)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in KnowledgeStatus)
        raise ValueError(f"status must be one of: {allowed}") from exc


def _coerce_foreignness(value: ForeignnessLevel | str) -> ForeignnessLevel:
    if isinstance(value, ForeignnessLevel):
        return value
    text = str(value or "").strip().lower()
    try:
        return ForeignnessLevel(text)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in ForeignnessLevel)
        raise ValueError(f"foreignness must be one of: {allowed}") from exc


def _coerce_intervention(value: InterventionLevel | str) -> InterventionLevel:
    if isinstance(value, InterventionLevel):
        return value
    text = str(value or "").strip().lower()
    try:
        return InterventionLevel(text)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in InterventionLevel)
        raise ValueError(f"intervention must be one of: {allowed}") from exc


def _coerce_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("confidence must be a number between 0 and 1") from exc
    if confidence < 0 or confidence > 1:
        raise ValueError("confidence must be between 0 and 1")
    return confidence


def _coerce_string_list(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    return [str(item).strip() for item in value if str(item).strip()]


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = str(text or "").lower()
    return any(term in lowered for term in terms)


@dataclass
class EvidenceItem:
    content: str
    source: str
    status: KnowledgeStatus | str
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.content = _coerce_text(self.content, "content")
        self.source = _coerce_text(self.source, "source")
        self.status = _coerce_status(self.status)
        self.confidence = _coerce_confidence(self.confidence)
        self.metadata = dict(self.metadata or {})

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload


@dataclass
class IdentityCore:
    object_id: str
    object_type: str
    name: str
    invariants: list[str] = field(default_factory=list)
    boundaries: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.object_id = _coerce_text(self.object_id, "object_id")
        self.object_type = _coerce_text(self.object_type, "object_type")
        self.name = _coerce_text(self.name, "name")
        self.invariants = _coerce_string_list(self.invariants, "invariants")
        self.boundaries = _coerce_string_list(self.boundaries, "boundaries")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RiskProfile:
    reversible: bool
    blast_radius: str
    red_button: bool
    risks: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.reversible = bool(self.reversible)
        self.blast_radius = _coerce_text(self.blast_radius, "blast_radius")
        self.red_button = bool(self.red_button)
        self.risks = _coerce_string_list(self.risks, "risks")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DecisionCommit:
    goal: str
    identity: IdentityCore
    evidence: list[EvidenceItem]
    foreignness: str
    risk: RiskProfile
    intervention: InterventionLevel | str
    selected_action: str
    rejected_options: list[str]
    verification: list[str]
    rollback: list[str]
    reason: str = ""

    def __post_init__(self) -> None:
        self.goal = _coerce_text(self.goal, "goal")
        if not isinstance(self.identity, IdentityCore):
            raise ValueError("identity must be IdentityCore")
        if not all(isinstance(item, EvidenceItem) for item in self.evidence):
            raise ValueError("evidence must contain EvidenceItem objects")
        self.foreignness = _coerce_foreignness(self.foreignness).value
        if not isinstance(self.risk, RiskProfile):
            raise ValueError("risk must be RiskProfile")
        self.intervention = _coerce_intervention(self.intervention)
        self.selected_action = _coerce_text(self.selected_action, "selected_action")
        self.rejected_options = _coerce_string_list(self.rejected_options, "rejected_options")
        self.verification = _coerce_string_list(self.verification, "verification")
        self.rollback = _coerce_string_list(self.rollback, "rollback")
        self.reason = str(self.reason or "").strip()

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "identity": self.identity.to_dict(),
            "evidence": [item.to_dict() for item in self.evidence],
            "foreignness": self.foreignness,
            "risk": self.risk.to_dict(),
            "intervention": self.intervention.value,
            "selected_action": self.selected_action,
            "rejected_options": list(self.rejected_options),
            "verification": list(self.verification),
            "rollback": list(self.rollback),
            "reason": self.reason,
        }


@dataclass
class MemoryNode:
    id: str
    type: str
    title: str
    content: str
    status: KnowledgeStatus | str
    source: str
    confidence: float
    context: dict[str, Any]
    relations: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.id = _coerce_text(self.id, "id")
        self.type = _coerce_text(self.type, "type")
        self.title = _coerce_text(self.title, "title")
        self.content = _coerce_text(self.content, "content")
        self.status = _coerce_status(self.status)
        self.source = _coerce_text(self.source, "source")
        self.confidence = _coerce_confidence(self.confidence)
        if not isinstance(self.context, dict) or not self.context:
            raise ValueError("context must be a non-empty dictionary")
        if not isinstance(self.relations, list):
            raise ValueError("relations must be a list")
        self.context = dict(self.context)
        self.relations = [dict(item) for item in self.relations if isinstance(item, dict)]
        self.created_at = _coerce_text(self.created_at, "created_at")
        self.updated_at = _coerce_text(self.updated_at, "updated_at")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload


class SafetyGuard:
    """Blocks red-button and unverifiable decisions before execution."""

    def evaluate(
        self,
        *,
        identity: IdentityCore,
        evidence: list[EvidenceItem],
        risk: RiskProfile,
        selected_action: str,
        verification: list[str],
        rollback: list[str],
        foreignness: ForeignnessLevel | str,
    ) -> dict[str, Any]:
        action_text = str(selected_action or "").strip()
        verification_steps = _coerce_string_list(verification, "verification")
        rollback_steps = _coerce_string_list(rollback, "rollback")
        foreignness_level = _coerce_foreignness(foreignness)

        if not verification_steps:
            return {"allowed": False, "reason": "decision_without_verification"}

        action_is_red_button = risk.red_button or _contains_any(action_text, RED_BUTTON_TERMS)
        action_is_destructive = action_is_red_button or _contains_any(action_text, DESTRUCTIVE_TERMS)
        identity_unknown = identity.object_type == "unknown" or identity.object_id.startswith("unknown:")

        if identity_unknown and action_is_destructive:
            return {"allowed": False, "reason": "unknown_object_destructive_action"}

        if action_is_red_button:
            explicit_review = any("review" in item.lower() or "approval" in item.lower() for item in verification_steps)
            if not explicit_review or not rollback_steps or not risk.reversible:
                return {"allowed": False, "reason": "red_button_requires_review_verification_and_rollback"}

        if foreignness_level in {ForeignnessLevel.QUARANTINED, ForeignnessLevel.IRREVERSIBLE_THREAT}:
            return {"allowed": False, "reason": "foreignness_level_blocks_action"}

        if any(item.status == KnowledgeStatus.CONTRADICTION for item in evidence) and action_is_destructive:
            return {"allowed": False, "reason": "contradiction_blocks_destructive_action"}

        return {"allowed": True, "reason": "allowed"}


class MemoryCommitValidator:
    """Validates source-backed memory nodes before any future commit step."""

    def validate(
        self,
        payload: dict[str, Any],
        *,
        relation_contract_version: str | None = None,
    ) -> MemoryNode:
        if not isinstance(payload, dict):
            raise ValueError("memory payload must be a dictionary")

        required = ("id", "type", "title", "content", "status", "source", "confidence", "context")
        missing = [key for key in required if key not in payload]
        if missing:
            raise ValueError(f"memory node missing required fields: {', '.join(missing)}")

        relation_opt_in = relation_contract_version is not None
        node = MemoryNode(
            id=payload["id"],
            type=payload["type"],
            title=payload["title"],
            content=payload["content"],
            status=payload["status"],
            source=payload["source"],
            confidence=payload["confidence"],
            context=payload["context"],
            relations=[] if relation_opt_in else list(payload.get("relations") or []),
            created_at=str(payload.get("created_at") or utc_now()),
            updated_at=str(payload.get("updated_at") or utc_now()),
        )
        if not relation_opt_in:
            return node

        from ai_os.semantic_relation_contract import validate_semantic_relation_list

        raw_relations = payload["relations"] if "relations" in payload else []
        node.relations = validate_semantic_relation_list(
            raw_relations,
            source_concept_id=payload["id"],
            contract_version=relation_contract_version,
        )
        return node


class DecisionEngine:
    """Builds coherent, safety-gated Concept Core decisions."""

    def __init__(self, *, safety_guard: SafetyGuard | None = None) -> None:
        self.safety_guard = safety_guard or SafetyGuard()

    def classify_foreignness(
        self,
        *,
        identity: IdentityCore,
        evidence: list[EvidenceItem],
        risk: RiskProfile,
    ) -> ForeignnessLevel:
        if risk.red_button and not risk.reversible:
            return ForeignnessLevel.IRREVERSIBLE_THREAT
        if any(item.status == KnowledgeStatus.CONTRADICTION for item in evidence):
            return ForeignnessLevel.RISKY
        if identity.object_type == "unknown" or identity.object_id.startswith("unknown:"):
            return ForeignnessLevel.UNKNOWN
        if not evidence:
            return ForeignnessLevel.UNKNOWN

        statuses = {item.status for item in evidence}
        average_confidence = sum(item.confidence for item in evidence) / len(evidence)
        if KnowledgeStatus.UNKNOWN in statuses:
            return ForeignnessLevel.UNKNOWN
        if statuses & {KnowledgeStatus.HYPOTHESIS, KnowledgeStatus.INFERENCE}:
            return ForeignnessLevel.PARTIALLY_UNDERSTOOD if average_confidence < 0.75 else ForeignnessLevel.FAMILIAR
        if statuses == {KnowledgeStatus.CONFIRMED} and average_confidence >= 0.85:
            return ForeignnessLevel.KNOWN
        return ForeignnessLevel.FAMILIAR

    def _intervention_for_action(self, selected_action: str) -> InterventionLevel:
        action = str(selected_action or "").lower()
        if "observe" in action:
            return InterventionLevel.OBSERVE
        if "ask" in action:
            return InterventionLevel.ASK
        if "verify" in action:
            return InterventionLevel.VERIFY
        if "rebuild module" in action:
            return InterventionLevel.REBUILD_MODULE
        if "rebuild" in action:
            return InterventionLevel.REBUILD_FILE
        if "redesign" in action:
            return InterventionLevel.REDESIGN
        if "refactor" in action:
            return InterventionLevel.REFACTOR
        if "patch" in action:
            return InterventionLevel.PATCH
        return InterventionLevel.VERIFY

    def decide(
        self,
        *,
        goal: str,
        identity: IdentityCore,
        evidence: list[EvidenceItem],
        risk: RiskProfile,
        selected_action: str,
        verification: list[str],
        rollback: list[str],
        rejected_options: list[str] | None = None,
    ) -> DecisionCommit:
        if not evidence:
            evidence = [
                EvidenceItem(
                    content="No evidence provided for decision.",
                    source="concept_core",
                    status=KnowledgeStatus.UNKNOWN,
                    confidence=0.0,
                )
            ]
        if not all(isinstance(item, EvidenceItem) for item in evidence):
            raise ValueError("evidence must contain EvidenceItem objects")

        foreignness = self.classify_foreignness(identity=identity, evidence=evidence, risk=risk)
        safety = self.safety_guard.evaluate(
            identity=identity,
            evidence=evidence,
            risk=risk,
            selected_action=selected_action,
            verification=verification,
            rollback=rollback,
            foreignness=foreignness,
        )
        if not safety["allowed"]:
            intervention = InterventionLevel.BLOCK
            reason = str(safety["reason"])
        elif any(item.status == KnowledgeStatus.CONTRADICTION for item in evidence):
            intervention = InterventionLevel.VERIFY
            reason = "contradiction_requires_verification"
        elif foreignness in {ForeignnessLevel.UNKNOWN, ForeignnessLevel.PARTIALLY_UNDERSTOOD}:
            intervention = InterventionLevel.VERIFY
            reason = "insufficient_understanding_requires_verification"
        else:
            intervention = self._intervention_for_action(selected_action)
            reason = "safe_low_risk_action" if intervention == InterventionLevel.PATCH else "coherent_decision"

        return DecisionCommit(
            goal=goal,
            identity=identity,
            evidence=evidence,
            foreignness=foreignness.value,
            risk=risk,
            intervention=intervention,
            selected_action=selected_action,
            rejected_options=list(rejected_options or []),
            verification=verification,
            rollback=rollback,
            reason=reason,
        )


__all__ = [
    "DecisionCommit",
    "DecisionEngine",
    "EvidenceItem",
    "ForeignnessLevel",
    "IdentityCore",
    "InterventionLevel",
    "KnowledgeStatus",
    "MemoryCommitValidator",
    "MemoryNode",
    "RiskProfile",
    "SafetyGuard",
]
