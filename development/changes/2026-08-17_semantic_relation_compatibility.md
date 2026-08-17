# Semantic Mesh Stage F3A Stored Relation Compatibility Classifier

Date: 2026-08-17

## Summary

Added a standalone pure classifier for the compatibility shape of already
loaded stored Semantic Relation lists.

The classifier distinguishes exact-v1-compatible, legacy, mixed, unsupported,
invalid, malformed, and empty relation lists without claiming that a stored
payload passed the F2A/F2B writer.

## Contract

`classify_semantic_relation_compatibility(...)` returns a frozen
`SemanticRelationCompatibilityReport` with aggregate counts, one stable status,
and an optional safe `code/index/field` issue. It never includes rejected
relation values.

Statuses are:

- `empty`;
- `compatible_v1_shape`;
- `legacy_unversioned`;
- `mixed_versioning`;
- `unsupported_version`;
- `invalid_v1`;
- `malformed_relations`.

Exact fully versioned lists reuse `validate_semantic_relation_list(...)` rather
than duplicating F1 validation rules. `compatible_v1_shape` is shape
compatibility only: the transport opt-in is not persisted, so stored data cannot
prove writer validation provenance.

## Scope

This slice adds only:

- `ai_os/semantic_relation_compatibility.py`;
- `development/scripts/smoke_semantic_relation_compatibility.py`;
- directly related contract and developer documentation.

There is no integration with `SemanticMeshIndex`, `build_semantic_mesh(...)`,
`GET /semantic-mesh/preview`, Concept Core, memory writers, planner, runtime, or
storage. There is no target lookup, reverse-edge creation, migration, backfill,
schema mutation, persistence metadata, API behavior change, package mutation,
or live runtime startup.

## Verification

The focused smoke records the expected missing-module RED before implementation
and then verifies the GREEN status taxonomy, exact import allowlist, F1 reuse,
safe diagnostics, no writer provenance claim, no target lookup, no file writes,
no input mutation, unchanged project runtime metadata, and successful cleanup.

The regression matrix reruns the F1/F2A/F2B and Semantic Mesh library/API
smokes with the official external interpreter.

## Rollback

Remove the standalone classifier and focused smoke, then revert only the F3A
documentation additions. No data rollback or user-data deletion is required.
