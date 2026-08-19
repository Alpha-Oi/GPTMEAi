# Semantic Mesh Stage F3D Direct-Batch Aggregate Compatibility Comparison

Date: 2026-08-19

## Summary

Added a standalone pure comparison function for two caller-supplied direct
relation-input batches.

The comparison composes the existing F3C batch builder and reports descriptive
aggregate differences without source matching or policy interpretation.

## Contract

`compare_direct_semantic_relation_compatibility_batches(...)` accepts exact
`baseline_inputs` and `candidate_inputs` values supported by F3C. It:

- calls the existing F3C builder exactly once for each direct batch;
- retains the exact baseline and candidate F3C inventory objects;
- returns their aggregate counts plus signed `candidate_minus_baseline` deltas;
- covers every fixed-taxonomy status and aggregate count;
- wraps F3C envelope failures with safe `batch/code/index/field` diagnostics;
- never includes rejected values in errors.

`inventory_generation_provenance=direct_f3c_batch_builder_for_both_batches`
describes only the internal call path. It does not establish input origin,
authenticity, freshness, completeness, uniqueness, storage ownership, or writer
validation. `writer_validation_provenance` remains `not_available`.

## Scope

This slice adds only:

- `ai_os/semantic_relation_compatibility_comparison.py`;
- `development/scripts/smoke_semantic_relation_compatibility_comparison.py`;
- directly related contract and developer documentation.

The comparison does not match, deduplicate, pair, or align sources or relations.
It does not derive trends, readiness, migration, enforcement, planner, or policy
decisions and does not expose source IDs, relation payloads, individual reports,
targets, or evidence refs.

There is no integration with `MemoryEngine`, storage, Semantic Mesh, API,
writers, planner, runtime, or network surfaces. There is no storage read, target
lookup, reverse-edge creation, migration, backfill, schema mutation, persistence
metadata, package mutation, file I/O, input mutation, or live runtime startup.

## Verification

The missing-module RED was recorded before implementation. The focused GREEN
smoke verifies exact F3C call and identity preservation, exact retained inventory
identity, complete signed delta direction, swapped antisymmetry, same and empty
batches, positive malformed-only input, duplicate count semantics, safe
baseline/candidate errors, aggregate-only output, exact import allowlist, no
retained relation references, no file writes, unchanged project runtime metadata,
and successful cleanup.

The regression matrix reruns F3C, F3B, F3A, F1, F2A, F2B, and Semantic Mesh
library/API smokes with the official external interpreter.

## Rollback

Remove the standalone comparison module and focused smoke, then revert only the
F3D documentation additions. No data rollback or user-data deletion is required.
