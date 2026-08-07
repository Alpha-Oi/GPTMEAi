# Semantic Mesh Stage F2B API Relation Writer Wiring

Date: 2026-08-07

## Summary

Implemented exact opt-in API wiring for authored `semantic_relation.v1`
validation on `POST /memory/add`.

The top-level `relation_contract_version` field is a transport control. It is
accepted only when `strict` is exactly `True`, is never persisted, and is
forwarded to the already existing Stage F2A writer only for exact
`semantic_relation.v1` requests.

## Contract

- requests without `relation_contract_version` retain the existing permissive
  strict route and omit the writer keyword;
- relation content does not activate the contract automatically;
- exact `semantic_relation.v1` opt-in validates relations before any write;
- unsupported, non-string, and `null` versions return
  `400 unsupported_contract_version;field=contract_version`;
- opt-in outside strict mode returns
  `400 relation_contract_requires_strict_mode;field=relation_contract_version`
  before a legacy text write can run;
- existing typed F1 relation errors remain stable API error strings;
- missing `relations` defaults to `[]`, while explicit non-list and malformed
  values are rejected without writes;
- success retains HTTP 201 and the existing
  `status/message/memory_count/item` response shape;
- the transport control is absent from stored blocks and Concept Core metadata.

## Scope

This slice changes only the strict `/memory/add` transport gate and forwarding,
adds a focused handler-level smoke, and updates directly related developer
documentation.

There is no storage schema change, migration, backfill, target lookup,
reverse-edge creation, `/concept-core/status` change, Semantic Mesh read-model
change, planner/dispatch/replay change, package/environment mutation, or live
runtime startup. Legacy text requests and strict requests without the transport
field preserve their previous behavior.

## Verification

The focused smoke uses a temporary runtime and verifies deterministic RED/GREEN
behavior, exact conditional keyword forwarding, stable errors, no-write
rejections, unchanged response shape, dangling-target acceptance without
lookup, absence of reverse blocks, unchanged project runtime metadata, and
successful cleanup.

The full Stage F2B matrix also reruns the F1/F2A, Concept Core, memory route/read
visibility, status, and Semantic Mesh library/API smokes with the official
external interpreter.

## Rollback

Remove the `/memory/add` transport gate and conditional forwarding, remove the
focused API smoke, and revert these documentation updates. Keep Stage F1/F2A
and existing stored data. No data rollback or user-data deletion is required.
