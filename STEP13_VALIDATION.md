# Step 13 validation report — Raw-data validation and quarantine

**Status:** Engineering PASS; live-data admission remains blocked  
**Repository version:** 0.10.0  
**Date:** 2026-08-06

## Decision

The Step 13 validator is correct enough to proceed to Step 14 engineering using deterministic fixtures. It does not authorize a real canonical historical dataset because the live Step 12 72-hour pilot has not completed and no real UTC day has been admitted.

## Frozen-specification integrity

- specification lock: 7/7 passed;
- specification lock was not regenerated;
- central research question, hypotheses, scope, and protocol unchanged.

## Functional validation

The committed full-day fixture contains:

- one complete UTC day within a five-second boundary tolerance;
- BTCUSDT and ETHUSDT;
- two depth updates and two trades per symbol;
- one snapshot per connection and symbol;
- continuous update IDs;
- uncrossed reconstructed books;
- exact raw payload and artifact hashes.

Result:

- structural status: `valid`;
- admission status: `fixture_valid_not_admissible`;
- admitted days: 0;
- repaired events: 0.

The fixture is intentionally rejected for research admission because its origin is synthetic and the live 72-hour pilot is incomplete.

## Corruption and failure testing

The test suite proves quarantine or hard failure for:

1. depth-sequence gaps;
2. crossed reconstructed books;
3. negative trade quantities;
4. stored/raw stream mismatches;
5. connection message-index discontinuity;
6. receive-UTC timestamp reversal;
7. Step 12 manifest tampering;
8. invalid or weakened validation configuration;
9. validation-report tampering;
10. quarantine-manifest/report inconsistency;
11. output-directory reuse.

No corrupted fixture was admitted.

## Automated test results

- Python: 136/136 passed;
- branch-aware Python coverage: 90.72%;
- GCC Debug: 36/36 C++ tests passed;
- Clang Debug: 36/36 passed;
- GCC Release with IPO: 36/36 passed;
- ASan + UBSan: 36/36 passed, no findings;
- deterministic Step 13 capture fixture regeneration: byte-identical;
- deterministic validation/quarantine output regeneration: byte-identical;
- Step 13 JSON schemas: valid;
- clean CMake Release installation: passed;
- external `find_package(robust_execution 0.10)` consumer: passed.

## Tooling limitation

Pinned Ruff could not be resolved from the local package registry, so Ruff and its format check were not claimed as executed. Python bytecode compilation passed. The existing hosted lint/type-check jobs remain configured but have not been claimed as newly executed in this environment.

## Provisional thresholds

The checked-in minimum of two depth messages and two trades per symbol is only a deterministic-fixture threshold. It cannot admit real data because the live-origin, complete-capture, whole-day, and completed-pilot gates are independently mandatory.

After the live pilot, observed message-rate distributions may justify a separately reviewed operational threshold. No threshold inferred from unobserved live data has been fabricated.

## Remaining blocker

A live 72-hour Binance capture must complete successfully before Step 13 can admit any real day. Until then, Step 14 may implement and validate canonical conversion using fixtures only.
