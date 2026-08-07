# Step 12 validation — Raw market-data capture

**Decision:** CONDITIONAL PASS  
**Engineering implementation:** PASS  
**Mandatory live 72-hour pilot:** PENDING  
**Date:** 2026-08-06

## 1. Decision

The raw-capture implementation is complete and sufficiently tested to run the mandatory live pilot in a persistent networked environment. Step 12 cannot receive an unconditional completion decision until a real Binance Spot capture runs for at least 259,200 seconds and its manifest passes independent verification.

No real-market observation, valid day, storage-rate estimate, or continuity result is claimed from this environment.

## 2. Frozen specification

- Checked files: 7
- Status: PASS
- Lock regenerated: no
- `SPECIFICATION.yaml` was restored byte-for-byte from the approved corrected Step 2 package after a working-tree regression. Its SHA-256 again matches the existing lock.

## 3. Capture engineering evidence

The implementation covers:

- official market-data-only REST and WebSocket endpoints;
- BTCUSDT and ETHUSDT;
- raw diff-depth and trade messages;
- exact UTF-8 payload retention and embedded SHA-256;
- `exchangeInfo` and per-connection snapshots;
- buffering before snapshot installation;
- Binance `U`/`u` continuity diagnostics;
- duplicate, old, gap, crossed-book, resynchronization, and synchronized-interval accounting;
- immutable gzip JSONL segments and create-only manifests;
- UTC and monotonic receive timestamps;
- connection rotation, reconnect metadata, and bounded retries;
- explicit `live_binance` versus `synthetic_transport_fixture` provenance;
- independent artifact and manifest verification.

## 4. Deterministic fixture

The committed offline fixture is byte-reproducible in a clean temporary directory and includes:

- 2 connections;
- 1 forced reconnect;
- BTCUSDT and ETHUSDT;
- 2 snapshots;
- 6 exact WebSocket payload records;
- 2 raw segment rotations;
- 12 files in the immutable run tree;
- a manifest that correctly refuses to claim live 72-hour completion.

## 5. Live-access evidence

A short live attempt was made and preserved as evidence. Both selected Binance hosts failed DNS resolution in the current container. The live manifest is correctly marked `aborted`, contains zero messages, is labelled `live_binance`, and reports `pilot_72h_complete=false`.

The pilot must be run using `docs/data/STEP12_PILOT_RUNBOOK.md` in an environment that can maintain the process continuously.

## 6. Python validation

- Tests: 94/94 passed
- Branch-aware coverage: 90.66%
- Required threshold: 90%
- Capture configuration and manifest schemas: passed
- Deterministic fixture regeneration: byte-identical
- Independent fixture and live-attempt manifest verification: passed

## 7. Native regression matrix

Although Step 12 is Python-led, the complete existing C++ platform was rebuilt after integration fixes:

| Configuration | Result |
|---|---|
| GCC 14 Debug | 36/36 passed |
| Clang 17 Debug | 36/36 passed |
| GCC 14 Release + IPO | 36/36 passed |
| Clang 17 ASan + UBSan | 36/36 passed, no findings |
| Clean Release installation | passed |

## 8. Defects found and corrected

1. The C++ version assertion still expected 0.8.0 after the repository advanced to 0.9.0.
2. Release/IPO identified a possibly-uninitialized optional in terminal-order lookup. The ternary construction was replaced by explicit branches.
3. Release/IPO identified a potential invalid reference path in the independent reference book. The implementation now checks the queue-to-order invariant and copies values before mutation.

All affected configurations were rerun after the corrections.

## 9. Conditional acceptance criteria

Engineering gate: PASS.

Unconditional Step 12 completion requires all of the following from a real run:

- duration at least 259,200 seconds;
- status `complete`;
- both instruments present;
- verified artifacts and payload hashes;
- no unexplained partial files;
- reconnects and rotations recorded;
- synchronized intervals and all sequence gaps visible;
- measured daily storage and message rates;
- independent `verify-capture` success.

## 10. Exact next action

Run the 72-hour pilot on a persistent networked host. Once its immutable manifest exists, Step 13 can validate and quarantine days. Until then, Step 13 may be implemented and tested only against synthetic/corrupted fixtures; no real day can be admitted.
