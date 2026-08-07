# Proposal — Exact Snapshot Timing Metadata

**Status:** Proposed; not applied to the frozen research specification and not represented as completed live evidence.

## Problem

The current Step 12 snapshot artifact records the connection identifier and book `lastUpdateId`, but it does not persist the REST request start, response receive, or write timestamps. Step 14 therefore carries only `connection_started_utc_ns` for snapshot rows.

That is sufficient to validate deterministic snapshot-plus-delta reconstruction, but it is insufficient to claim an exact causal availability timestamp for a research replay.

## Proposed additive capture fields

For every snapshot request:

- `request_started_utc_ns`;
- `response_received_utc_ns`;
- `response_received_monotonic_ns`;
- HTTP status and selected remote endpoint;
- request-attempt identifier;
- snapshot payload SHA-256;
- `lastUpdateId`;
- connection identifier and symbol.

Step 14 would then preserve `snapshot_response_received_utc_ns` in canonical snapshot rows.

## Safety rule

Until these fields exist on a live capture, Step 15 research replay remains blocked. The sample fixture may use the connection-start proxy only because observations are suppressed until the first sequence-bridging depth batch.

## Scope

This is an additive operational-metadata correction. It does not change the project question, strategies, hypotheses, data split, or intended research contribution.
