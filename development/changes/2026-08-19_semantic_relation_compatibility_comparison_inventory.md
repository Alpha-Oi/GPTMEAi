# Semantic Mesh Stage F3E Aggregate Compatibility-Comparison Inventory

Date: 2026-08-19

## Summary

Added a standalone pure inventory builder for caller-supplied F3D compatibility
comparison objects.

The builder validates public comparison value objects and aggregates their
baseline, candidate, and signed delta counts without regenerating comparisons or
interpreting the result.

## Contract

`build_semantic_relation_compatibility_comparison_inventory(...)` accepts an
exact list of exact `SemanticRelationCompatibilityComparison` objects. It
validates:

- exact comparison and nested F3C inventory types;
- canonical fixed-taxonomy status tuples;
- exact non-negative baseline and candidate counts;
- report/status, relation partition, issue-report, and status-derived minimum
  relation-count consistency;
- exact signed `candidate_minus_baseline` status and aggregate deltas.

Malformed inputs raise
`SemanticRelationCompatibilityComparisonInventoryError` with stable
`code/index/field` diagnostics and never include rejected values.

The output contains only `comparison_count`, summed baseline/candidate/delta
counts, fixed taxonomy, `comparison_direction=candidate_minus_baseline`, and
`aggregation_semantics=count_each_comparison`. Public F3D objects do not prove
how they were created, so the output reports
`comparison_generation_provenance=not_available` and
`writer_validation_provenance=not_available`.

## Scope

This slice adds only:

- `ai_os/semantic_relation_compatibility_comparison_inventory.py`;
- `development/scripts/smoke_semantic_relation_compatibility_comparison_inventory.py`;
- directly related contract and developer documentation.

F3E does not call F3D, retain individual comparisons or inventories, or expose
source IDs, relation payloads, reports, targets, or evidence refs. Duplicate
comparisons are counted independently, ordering is irrelevant, and signed
deltas may cancel without implying improvement, regression, trend, readiness,
migration, enforcement, or policy meaning.

There is no integration with `MemoryEngine`, storage, Semantic Mesh, API,
writers, planner, runtime, or network surfaces. There is no storage read, source
matching, deduplication, pairing, relation alignment, target lookup,
reverse-edge creation, migration, backfill, schema mutation, persistence
metadata, package mutation, file I/O, input mutation, or live runtime startup.

## Verification

The missing-module RED was recorded before implementation. The focused GREEN
smoke verifies canonical taxonomy reuse, exact summed aggregates, signed delta
arithmetic, positive/negative/zero cancellation, empty and malformed-only
fixtures, order independence, count-each duplicates, strict rejection of forged
public objects, safe errors, no rejected values, no retained references, exact
import allowlist, no F3D regeneration, no file writes, unchanged project runtime
metadata, and successful cleanup.

The regression matrix reruns F3D, F3C, F3B, F3A, F1, F2A, F2B, and Semantic
Mesh library/API smokes with the official external interpreter.

## Rollback

Remove the standalone comparison-inventory builder and focused smoke, then
revert only the F3E documentation additions. No data rollback or user-data
deletion is required.
