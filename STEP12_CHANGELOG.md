# Step 12 change log — Raw Binance Spot capture

**Date:** 2026-08-06  
**Repository version:** 0.9.0  
**Specification change:** None

## Added

- Asynchronous Binance Spot public-data collector for BTCUSDT and ETHUSDT.
- Combined diff-depth (`@depth@100ms`) and raw-trade (`@trade`) capture.
- REST transport for `exchangeInfo` and 5000-level depth snapshots.
- Snapshot buffering, sequence synchronization, duplicate/old-event accounting, gap invalidation, and resynchronization.
- Exact raw UTF-8 payload preservation with per-message SHA-256 hashes.
- Create-only gzip JSONL segments, atomic `.partial` finalization, periodic `fsync`, UTC-day rotation, and segment limits.
- Immutable metadata, snapshot, runtime, symbol-contract, manifest, and manifest-hash artifacts.
- Connection rotation before the documented 24-hour limit, reconnect diagnostics, and bounded retries.
- Capture configuration and manifest JSON Schemas.
- CLI commands for network checks, capture execution, and independent manifest verification.
- Deterministic offline two-connection fixture with forced reconnect and both selected instruments.
- 39 Step 12-focused Python tests, bringing the full Python suite to 94 tests.
- Step 12 capture, security/operations, and 72-hour pilot runbooks.

## Corrected during validation

- Restored `SPECIFICATION.yaml` byte-for-byte from the approved corrected Step 2 package after an external working-tree regression; the specification lock was not regenerated.
- Updated the stale C++ build-info test from version 0.8.0 to 0.9.0.
- Rewrote terminal-order state construction to avoid an optimizer-detected possibly-uninitialized `std::optional`.
- Strengthened the independent reference-book queue lookup with an explicit missing-order invariant and copied values before mutation, resolving a Release/IPO null-dereference warning.

## Not changed

- Central research question.
- Research scope, hypotheses, protocol, or definition of done.
- The approved seven-file frozen specification.
- Venue and instrument selection from Step 11.
- The unapproved Step 5 schema amendment.

## Not completed

- The mandatory live 72-hour pilot did not run because the current container could not resolve the Binance REST or WebSocket hosts.
- No real Binance market-data observation is claimed.
- No day is admitted as valid data; that remains Step 13.
