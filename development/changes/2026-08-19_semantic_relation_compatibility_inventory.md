# Semantic Mesh Stage F3B Aggregate Relation Compatibility Inventory

Date: 2026-08-19

## Summary

Added a standalone pure inventory builder for caller-supplied
`SemanticRelationCompatibilityReport` objects.

The inventory provides deterministic fixed-taxonomy status counts and aggregate
relation counts without reading stored blocks or exposing report-level payloads.

## Contract

`build_semantic_relation_compatibility_inventory(...)` accepts an exact list of
`SemanticRelationCompatibilityReport` objects. It validates:

- exact report type;
- a status from the F3A taxonomy;
- exact non-negative integer counts;
- aggregate and status-specific count consistency;
- expected issue presence for diagnostic statuses;
- absence of issues for `empty`, `compatible_v1_shape`, and `legacy_unversioned`.

Malformed inventory inputs raise
`SemanticRelationCompatibilityInventoryError` with stable `code/index/field`
diagnostics and never include rejected values.

The output contains only report count, fixed-taxonomy status counts, aggregate
relation counts, issue-report count,
`report_generation_provenance=not_available`,
`writer_validation_provenance=not_available`, and
`target_lookup_performed=false`. Public report value objects do not establish
their generation provenance.

## Scope

This slice adds only:

- `ai_os/semantic_relation_compatibility_inventory.py`;
- `development/scripts/smoke_semantic_relation_compatibility_inventory.py`;
- directly related contract and developer documentation.

The builder does not accept or expose memory blocks, Concept Core metadata,
source concept IDs, relation payloads, targets, or evidence refs. It does not
derive an overall readiness, migration, planner, or enforcement decision.

There is no integration with `MemoryEngine`, storage, Semantic Mesh, API,
writers, planner, runtime, or network surfaces. There is no target lookup,
reverse-edge creation, migration, backfill, schema mutation, persistence
metadata, package mutation, or live runtime startup.

## Verification

The focused smoke records the expected missing-module RED before implementation
and then verifies exact F3A taxonomy reuse, all-status aggregation, deterministic
order-independent output, strict report invariants, safe errors, no rejected
values, no report-level payloads, exact import allowlist, no file writes,
unchanged project runtime metadata, and successful cleanup.

The regression matrix reruns F3A, F1, F2A, F2B, and Semantic Mesh library/API
smokes with the official external interpreter.

## Rollback

Remove the standalone inventory builder and focused smoke, then revert only the
F3B documentation additions. No data rollback or user-data deletion is required.
