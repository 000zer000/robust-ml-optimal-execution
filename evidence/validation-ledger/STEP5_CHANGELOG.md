# Step 5 Change Log — Event and Market-Data Model

**Date:** 2026-08-06  
**Repository version:** 0.2.0  
**Research specification:** unchanged; specification lock passed for all seven frozen files

## Added

- C++ exact-unit types for prices, quantities, quote atoms, and rational increments.
- Strong numerical and textual identifier types.
- UTC/simulation nanosecond timestamps and deterministic event-order metadata.
- Canonical market, decision, order-lifecycle, fill, fee, terminal-completion, and timer payloads.
- Order-state transition and terminal-state rules.
- C++ semantic validators and immutable audit-record value type.
- Python event validator, canonical JSON encoder, create-only SHA-256 audit writer, and chain verifier.
- Draft 2020-12 schemas for event envelopes, audit records, instruments, and episode metadata.
- Deterministic non-empirical event/audit fixtures.
- CLI commands for fixture generation and audit verification.
- Step 5 design and schema-evolution documentation.
- C++ and Python tests for fixed-point overflow, event ordering, state transitions, payload invariants, schema fixtures, determinism, and audit tampering.

## Corrected during implementation

1. **Ordering ambiguity:** raw source sequence plus ingest order did not safely represent venue-specific equal-timestamp semantics. A mandatory adapter-assigned `canonical_sequence` now defines normalized order, while source and ingest sequences remain provenance fields.
2. **Misleading timestamp name:** a strategy decision or timer does not universally have an exchange timestamp. The generic envelope now uses `event_time`; exchange-specific timing remains in market/action fields.
3. **Audit durability:** the writer now refuses existing non-empty logs, uses canonical JSON, links every record by SHA-256, flushes, and calls `fsync` after each append.

## Modified bootstrap integration

- Project version advanced from 0.1.0 to 0.2.0.
- CMake builds and installs the event-model sources and headers.
- Repository and local validation commands include schema/audit verification.
- README and roadmap now identify Step 5 as complete and Step 6 as next.

## Not implemented in Step 5

- Matching or queue mutation.
- Venue/feed-specific event semantics.
- Real fee, tick, lot, latency, or sequence values.
- C++ JSON serialization or cross-process audit locking.
- Historical queue reconstruction.
- Strategy, model, benchmark, or empirical result.
