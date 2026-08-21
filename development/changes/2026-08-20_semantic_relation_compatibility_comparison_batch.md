# Semantic Mesh Stage F3F Direct Comparison-Batch Inventory Composer

Date: 2026-08-20

## Summary

Added a standalone pure composer for an explicit caller-supplied list of direct
baseline/candidate compatibility input-batch pairs.

The composer reuses F3D once per explicit pair and F3E once for the generated
comparison list. It adds no source matching or policy interpretation.

## Contract

`build_direct_semantic_relation_compatibility_comparison_inventory(...)`
accepts an exact list of exact frozen
`SemanticRelationCompatibilityComparisonBatchInput` objects. It:

- treats each object as one explicit baseline/candidate comparison unit;
- calls F3D exactly once per object with the exact supplied batch identities;
- passes a new list containing the exact generated comparisons to F3E once;
- preserves the exact F3E baseline, candidate, and delta aggregate objects;
- wraps F3D failures with stable `comparison_index/batch/index/field` context;
- never includes rejected values in errors.

The output is aggregate-only and declares
`comparison_generation_provenance=direct_f3d_comparison_for_each_input` plus
`comparison_inventory_generation_provenance=direct_f3e_comparison_inventory_builder`.
These values describe only the direct in-process call path. They do not prove
input origin, authenticity, freshness, completeness, uniqueness, storage
ownership, source identity, or writer validation.

## Scope

This slice adds only:

- `ai_os/semantic_relation_compatibility_comparison_batch.py`;
- `development/scripts/smoke_semantic_relation_compatibility_comparison_batch.py`;
- directly related contract and developer documentation.

Explicit pair duplicates are counted independently and aggregate ordering is
irrelevant. F3F does not infer, discover, match, deduplicate, pair, or align
sources or relations. It does not retain input pairs, comparisons, nested
inventories, source IDs, relation payloads, reports, targets, or evidence refs.
It does not derive improvement, regression, trend, readiness, migration,
enforcement, or policy meaning.

There is no integration with `MemoryEngine`, storage, Semantic Mesh, API,
writers, planner, runtime, or network surfaces. There is no storage read, target
lookup, reverse-edge creation, migration, backfill, schema mutation, persistence
metadata, package mutation, file I/O, input mutation, or live runtime startup.

## Verification

The missing-module RED was recorded before implementation. The focused GREEN
smoke verifies the exact F3D-per-input and single-F3E identity chain, exact F3E
aggregate identity preservation, complete F3A taxonomy, direct F3D/F3E result
equivalence, positive/negative/zero/cancelling deltas, empty and malformed-only
fixtures, order independence, count-each duplicates, safe nested errors, no
rejected values, no input mutation, aggregate-only output, exact import
allowlist, no file writes, unchanged project runtime metadata, and successful
cleanup.

The regression matrix reruns F3E, F3D, F3C, F3B, F3A, F1, F2A, F2B, and
Semantic Mesh library/API smokes with the official external interpreter.

## Rollback

Remove the standalone comparison-batch composer and focused smoke, then revert
only the F3F documentation additions. No data rollback or user-data deletion is
required.
