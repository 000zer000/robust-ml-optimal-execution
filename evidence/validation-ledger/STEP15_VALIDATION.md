# Step 15 validation report

**Repository version:** 0.12.0  
**Step:** 15 — Historical aggregate-L2 replay  
**Status:** Engineering pass; empirical research replay pending live data, exact snapshot timing, and Step 16 queue models  
**Research specification changed:** No  
**Specification lock regenerated:** No

## Acceptance decision

The Step 15 replay, causality, synchronization, aggregate-book reconstruction, provenance, immutability, deterministic-output, and scientific-boundary layers pass their engineering gate.

The committed replay is not a research dataset. Its manifest states:

- `source_dataset_classification = sample_only_non_research`;
- `research_admissible = false`;
- `exact_fifo_reconstructed = false`;
- `queue_position_semantics = not_reconstructed_until_step16`;
- `endogenous_impact_modelled = false`;
- `market_impact_semantics = ghost_small_agent_no_endogenous_impact`.

## Replay fixture evidence

- venue: Binance Spot semantic contract;
- instruments: BTCUSDT and ETHUSDT;
- source: deterministic Step 14 synthetic canonical fixture;
- connections: 2;
- replay events: 10;
- causal validation observations: 8;
- tables: 3;
- sequence gaps: 0;
- locked or crossed policy-ready books: 0;
- exact FIFO positions produced: 0;
- endogenous-impact claims produced: 0;
- manifest SHA-256: `f34d7faf0b497d89ca20a7f293d73844e991775998a08bd9eac141314e6add01`.

The replay regenerates byte-for-byte from the immutable Step 14 fixture.

## Causal timing evidence

The C++ kernel preserves three distinct timestamps:

1. historical exchange event time;
2. local collector receive time;
3. policy availability time after explicit processing delay.

A direct kernel test proves that an event is unavailable before `available_time`, that all three timestamps are retained, and that invalid timestamp orderings or unsupported event origins are rejected.

A snapshot is treated only as bootstrap state. Policy observations are suppressed after every connection start until a depth update bridges the snapshot sequence. The current fixture uses a connection-start proxy internally, but that proxy is never exposed as a policy-ready observation.

## Python validation

- tests: 202/202 passed;
- branch-aware coverage: 90.17%;
- configuration, table, builder, verifier, CLI, tamper, duplicate, malformed-gzip, causal-order, claim-boundary, and immutable-output tests passed;
- two Step 15 JSON schemas validated;
- Python compilation passed.

## Native validation

- GCC Debug: 41/41 tests passed;
- Clang Debug: 41/41 tests passed;
- GCC Release with IPO: 41/41 tests passed;
- GCC ASan + UBSan: 41/41 tests passed, no findings;
- historical demo output is byte-identical under GCC Debug, Clang Debug, and GCC Release;
- historical demo SHA-256: `d6f6af88d425a766faeff414ba46fe0aeae9523a3e3c55c186278e012b690035`;
- clean Release installation passed;
- external `find_package(robust_execution 0.12)` consumer compiled, linked, and ran.

## Governance and repository checks

- frozen specification hashes: 7/7 passed;
- specification lock unchanged;
- Step 12 capture fixture validation passed;
- Step 13 admission/quarantine validation passed;
- Step 14 canonical dataset validation passed;
- Step 15 replay validation and deterministic regeneration passed;
- no real market day or strategy result was claimed.

## Reconnect-isolation correction

A final audit found a real causal-state defect: a trade received on a replacement connection before snapshot synchronization could be ingested while the prior connection still appeared policy-ready. The corrected implementation applies an internal connection-reset boundary at the captured connection start, clears stale book and historical trade state, allows new-connection trades to accumulate causally, and suppresses observations until the new depth stream bridges the snapshot.

Dedicated C++ and Python tests prove that no pre-bridge decision is emitted and that the first post-bridge observation contains the new book and only new-connection trade history.

## Snapshot-timestamp limitation

The current Step 12/14 contracts do not retain exact REST snapshot request-start and response-receive timestamps. A separate additive proposal records the required metadata fields. It has not been silently treated as approved or implemented.

Until exact live snapshot timing exists, a research replay is blocked. The deterministic sample remains valid only because observation readiness is suppressed until sequence synchronization.

## Tool limitations

Ruff and mypy were unavailable locally. Python compilation, all executable tests, both compilers, optimized builds, sanitizers, installation, and downstream consumption passed. Hosted CI remains configured for the pinned quality tools.

The Step 12 live 72-hour Binance pilot is still pending because the execution environment cannot access the selected endpoints. Consequently, no real historical replay, real storage-rate measurement, or historical result is claimed.

## Decision

**Step 15 engineering gate: PASS.**  
**Research historical replay: PENDING.**

Step 16 queue models may be implemented and tested against deterministic fixtures. No historical execution-quality result may be reported until live days pass Steps 12–15 and the explicit queue-model assumptions are applied.
