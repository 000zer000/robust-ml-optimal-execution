# Step 17 change log — exact accounting and execution metrics

## Status

Step 17 is complete. This milestone adds the common accounting and metric layer required by every later baseline, optimiser, supervised model, imitation policy, and reinforcement-learning policy. It does not report a strategy result and does not change the frozen research specification.

## Added

### C++ accounting and metrics

- Added exact episode-ledger types for fills, fees, markouts, decision timings, activity counters, performance measurements, and external benchmarks.
- Added exact quote-notional reconstruction from integer price ticks, quantity lots, tick size, lot size, and quote-atom size.
- Added side-consistent implementation shortfall, with positive values representing worse execution for both buys and sells.
- Added completion, residual inventory, inventory trajectory, time-to-first-fill, and time-to-completion metrics.
- Added separately identified terminal-completion quantity and cost.
- Added passive, aggressive, and unknown-liquidity quantities and fractions.
- Added quantity-weighted average execution price in ticks and quote units.
- Added horizon-specific adverse-selection markouts with explicit coverage.
- Added action counts, cancel-to-submit ratio, observation staleness, controller latency, inference latency, action-dispatch latency, throughput, wall time, and peak RSS fields.
- Added descriptive tail summaries: mean, sample variance and standard deviation, median, empirical nearest-rank VaR95/VaR99, and fractional empirical CVaR95/CVaR99.
- Added an independent C++ audit path in a separate translation unit.
- Added a deterministic C++ validation executable and installed public metrics API.

### Python evidence verification

- Added an independent Python reconstruction of exact notionals, signed cash, fees, implementation shortfall, terminal cost, inventory, fill composition, markouts, activity, throughput, all four latency families, and aggregate tail statistics.
- Added artifact-hash and CSV/JSON consistency verification.
- Added semantic tamper tests that rehash modified artifacts and still require rejection.
- Added primitive and exact-arithmetic failure-path tests.

### Contracts and reproducibility

- Added a versioned metric contract and three JSON schemas.
- Added deterministic JSON and CSV evidence under `data/sample/metrics/step17-metrics-validation/`.
- Added one-command fixture generation, validation, and demo-consistency checks.
- Added Step 17 checks to local validation and hosted CI/reproducibility workflows.
- Added documentation for accounting formulas, independent audits, and tail-risk conventions.

## Corrections found during implementation

1. **Action-dispatch latency omission.** The calculator populated action-dispatch latency, but the first canonical JSON implementation did not serialize it. The field is now serialized and independently verified.
2. **Premature determinism flag.** The first validation report serialized `deterministic=true` before running the second calculation. The second run is now performed before report serialization.
3. **Clang portability warning.** The tail aggregator implicitly promoted a completion rate from `double` to `long double`. The conversion is now explicit under the warnings-as-errors policy.
4. **Fixed-point test expectation.** A new non-unit tick/lot test initially used an incorrect manually expected quote-atom count. The implementation was correct; the test was corrected to account for the one-millionth quote atom and now validates 246,900,000 atoms, 12,345 ticks, and 123.45 quote units.
5. **Specification drift recovery.** `SPECIFICATION.yaml` had drifted from the approved lock. It was restored byte-for-byte from the corrected Step 2 package. The lock was not regenerated.
6. **Version-linked fixture propagation.** Steps 12–16 embed the repository software version and upstream hashes. Those synthetic fixtures were regenerated in dependency order for version 0.14.0. Raw-message counts, admission decisions, canonical row counts, replay event counts, queue scenarios, and all scientific status fields remained unchanged.

## Version

Repository version advanced from `0.13.0` to `0.14.0`.

## Boundaries

- No historical strategy outcome is reported.
- No profitability, speed, scale, or production-readiness claim is made.
- Step 17 tail summaries are descriptive; dependence-aware paired inference remains a later milestone.
- Incomplete or audit-failing episodes cannot enter aggregate tail results.
