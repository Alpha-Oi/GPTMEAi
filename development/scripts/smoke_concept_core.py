"""Isolated smoke checks for the additive Concept Core MVP."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_os.concept_core import (
    DecisionEngine,
    EvidenceItem,
    IdentityCore,
    InterventionLevel,
    KnowledgeStatus,
    MemoryCommitValidator,
    RiskProfile,
)


def assert_true(name: str, value: bool, failures: list[str]) -> None:
    if not value:
        failures.append(name)


def assert_raises(name: str, fn, failures: list[str]) -> None:
    try:
        fn()
    except ValueError:
        return
    failures.append(name)


def main() -> int:
    failures: list[str] = []
    engine = DecisionEngine()
    validator = MemoryCommitValidator()

    identity = IdentityCore(
        object_id="file:ai_os/concept_core.py",
        object_type="file",
        name="Concept Core MVP",
        invariants=["additive-only"],
        boundaries=["no runtime storage writes"],
    )
    confirmed = EvidenceItem(
        content="The implementation is additive and isolated.",
        source="smoke_concept_core",
        status=KnowledgeStatus.CONFIRMED,
        confidence=0.95,
        metadata={"case": "confirmed_low_risk"},
    )
    contradiction = EvidenceItem(
        content="Conflicting safety claims exist.",
        source="smoke_concept_core",
        status=KnowledgeStatus.CONTRADICTION,
        confidence=0.8,
    )

    red_button = engine.decide(
        goal="delete runtime data",
        identity=identity,
        evidence=[confirmed],
        risk=RiskProfile(reversible=False, blast_radius="project_data", red_button=True, risks=["delete data"]),
        selected_action="delete storage",
        verification=["manual review noted"],
        rollback=[],
    )
    assert_true("red_button_action_blocked", red_button.intervention == InterventionLevel.BLOCK, failures)

    no_verification = engine.decide(
        goal="patch code",
        identity=identity,
        evidence=[confirmed],
        risk=RiskProfile(reversible=True, blast_radius="file", red_button=False, risks=[]),
        selected_action="patch file",
        verification=[],
        rollback=["revert patch"],
    )
    assert_true("decision_without_verification_blocked", no_verification.intervention == InterventionLevel.BLOCK, failures)

    unknown_identity = IdentityCore(
        object_id="unknown:artifact",
        object_type="unknown",
        name="Unknown Artifact",
        invariants=[],
        boundaries=["no destructive changes"],
    )
    unknown_destructive = engine.decide(
        goal="remove unknown artifact",
        identity=unknown_identity,
        evidence=[EvidenceItem(content="Unknown object.", source="smoke_concept_core", status=KnowledgeStatus.UNKNOWN, confidence=0.2)],
        risk=RiskProfile(reversible=False, blast_radius="unknown", red_button=False, risks=["unknown target"]),
        selected_action="delete artifact",
        verification=["manual inspection"],
        rollback=["restore from backup"],
    )
    assert_true("unknown_object_destructive_action_blocked", unknown_destructive.intervention == InterventionLevel.BLOCK, failures)

    assert_raises(
        "memory_node_without_source_status_context_rejected",
        lambda: validator.validate(
            {
                "id": "memory:test",
                "type": "decision",
                "title": "Invalid memory",
                "content": "Missing required source/status/context.",
                "confidence": 0.7,
                "context": {},
            }
        ),
        failures,
    )

    contradiction_decision = engine.decide(
        goal="resolve conflict",
        identity=identity,
        evidence=[confirmed, contradiction],
        risk=RiskProfile(reversible=True, blast_radius="file", red_button=False, risks=[]),
        selected_action="patch file",
        verification=["focused smoke"],
        rollback=["revert patch"],
    )
    assert_true("contradiction_increases_risk_or_foreignness", contradiction_decision.foreignness == "risky", failures)
    assert_true("contradiction_requires_verification_level", contradiction_decision.intervention == InterventionLevel.VERIFY, failures)

    low_risk = engine.decide(
        goal="apply additive patch",
        identity=identity,
        evidence=[confirmed],
        risk=RiskProfile(reversible=True, blast_radius="file", red_button=False, risks=[]),
        selected_action="patch file",
        verification=["py_compile"],
        rollback=["revert patch"],
    )
    assert_true("confirmed_evidence_allows_safe_low_risk_patch", low_risk.intervention == InterventionLevel.PATCH, failures)

    valid_memory = validator.validate(
        {
            "id": "memory:concept-core-smoke",
            "type": "decision",
            "title": "Concept Core smoke",
            "content": "Source-backed decision memory is valid.",
            "status": "confirmed",
            "source": "smoke_concept_core",
            "confidence": 0.9,
            "context": {"goal": "validate memory node"},
            "relations": [{"type": "supports", "target": "decision:concept-core"}],
        }
    )
    assert_true("valid_memory_node_accepted", valid_memory.status == KnowledgeStatus.CONFIRMED, failures)

    checks = {
        "red_button_action_blocked": "red_button_action_blocked" not in failures,
        "decision_without_verification_blocked": "decision_without_verification_blocked" not in failures,
        "unknown_object_destructive_action_blocked": "unknown_object_destructive_action_blocked" not in failures,
        "memory_node_without_source_status_context_rejected": "memory_node_without_source_status_context_rejected" not in failures,
        "contradiction_increases_risk_or_foreignness": "contradiction_increases_risk_or_foreignness" not in failures,
        "confirmed_evidence_allows_safe_low_risk_patch": "confirmed_evidence_allows_safe_low_risk_patch" not in failures,
        "valid_memory_node_accepted": "valid_memory_node_accepted" not in failures,
    }
    result = {
        "status": "ok" if not failures else "failed",
        "service": "AI OS Concept Core Smoke",
        "checks": checks,
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
