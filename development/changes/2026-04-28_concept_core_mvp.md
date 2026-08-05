# 2026-04-28 - Concept Core MVP foundation

Added an additive-only `ai_os.concept_core` MVP with typed reasoning and safety primitives: `KnowledgeStatus`, `ForeignnessLevel`, `InterventionLevel`, `EvidenceItem`, `IdentityCore`, `RiskProfile`, `DecisionCommit`, `MemoryNode`, `SafetyGuard`, `DecisionEngine`, and `MemoryCommitValidator`.

The MVP distinguishes confirmed facts, inference, hypothesis, unknowns, and contradictions. It blocks red-button decisions without safe review/verification/rollback posture, blocks destructive actions on unknown objects, escalates contradictions to risky/verify, and rejects memory nodes without required source/status/context/confidence.

This slice does not change API routes, dashboard, planner behavior, cognitive loop behavior, memory storage schema, snapshot schema, execution ledger schema, or runtime storage. Existing memory-write routes are not yet wired to the validator; that remains a future migration-backed integration slice.

Verification added and passed through `development/scripts/smoke_concept_core.py`.
