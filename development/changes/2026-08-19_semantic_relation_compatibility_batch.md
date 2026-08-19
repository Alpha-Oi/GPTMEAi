# Semantic Mesh Stage F3C Direct-Input Compatibility Batch Inventory

Date: 2026-08-19

## Summary

Added a standalone pure batch builder that converts caller-supplied in-memory
relation inputs into an aggregate Semantic Relation compatibility inventory.

The builder closes the composition gap between the F3A classifier and F3B
inventory without reading memory blocks or accepting caller-created reports.

## Contract

`build_direct_semantic_relation_compatibility_inventory(...)` accepts an exact
list of exact frozen `SemanticRelationCompatibilityInput` objects. Each object
contains a caller-supplied `source_concept_id` and already loaded `relations`.

The builder:

- calls F3A once per input with the original relation and source-ID objects;
- sends only the generated F3A reports to the existing F3B builder;
- returns deterministic fixed-taxonomy aggregate counts;
- counts duplicate input entries independently without source-ID deduplication;
- raises `SemanticRelationCompatibilityBatchError` with safe
  `code/index/field` diagnostics for malformed outer batch envelopes.

The output is aggregate-only. It reports
`report_generation_provenance=direct_f3a_classifier` only for the internal
F3C-to-F3A call path, `writer_validation_provenance=not_available`, and
`target_lookup_performed=false`. The direct call-path marker does not prove the
origin, authenticity, freshness, completeness, uniqueness, storage ownership,
or writer validation of the caller-supplied inputs.

## Scope

This slice adds only:

- `ai_os/semantic_relation_compatibility_batch.py`;
- `development/scripts/smoke_semantic_relation_compatibility_batch.py`;
- directly related contract and developer documentation.

The builder does not accept storage handles, paths, memory blocks, Concept Core
metadata, iterators, generators, or caller-supplied compatibility reports. It
does not expose source IDs, relation payloads, individual reports, targets, or
evidence refs and does not derive readiness, migration, planner, or enforcement
decisions.

There is no integration with `MemoryEngine`, storage, Semantic Mesh, API,
writers, planner, runtime, or network surfaces. There is no target lookup,
reverse-edge creation, migration, backfill, schema mutation, persistence
metadata, package mutation, or live runtime startup.

## Verification

The missing-module RED was recorded before implementation. The focused GREEN
smoke verifies the complete F3A status taxonomy, exact direct F3A/F3B call path,
positive malformed-only coverage, deterministic order-independent aggregation,
explicit duplicate counting, direct object identity, no input mutation, safe
errors, aggregate-only output, exact import allowlist, no file writes, unchanged
project runtime metadata, and successful cleanup.

The regression matrix reruns F3B, F3A, F1, F2A, F2B, and Semantic Mesh
library/API smokes with the official external interpreter.

## Rollback

Remove the standalone batch builder and focused smoke, then revert only the F3C
documentation additions. No data rollback or user-data deletion is required.
