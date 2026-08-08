# Step 18 validation — Basic schedules

**Decision:** PASS for Step 18 engineering and methodological acceptance.

The implemented baseline layer is ready to serve as a comparator family for Steps 19–20. This does not constitute a research result because no admitted historical evaluation has been run.

## Acceptance evidence

### Baseline definitions

- Immediate aggressive: one full-parent market/IOC release at episode start.
- TWAP: equal temporal spacing and equal integer-lot allocation up to deterministic remainder handling.
- Past-volume-informed: bucket weights are built from timestamped observations no later than a training cutoff strictly before episode start.
- Passive variants: supported for TWAP and volume-informed schedules using same-side-best, GTC, zero-offset, post-only placement.

### Leakage controls

The implementation rejects:

- source observations after the volume-profile cutoff;
- a profile cutoff at or after episode start;
- cross-domain timestamps;
- invalid profile buckets;
- zero-information profiles;
- missing profile provenance.

### Common-contract integration

`ScheduledBaselinePolicy` implements the Step 8 `ExecutionPolicy` interface. It catches up to cumulative schedule targets using cumulative fills, does not issue commands while another command is pending or a child is acknowledged live, canonicalizes rational quantity fractions, and leaves residual inventory to the common hard terminal-completion rule.

### Deterministic metric oracle

Using the same synthetic parent order, arrival price, and exogenous prices:

| Baseline | Slice lots | Validation shortfall |
|---|---|---:|
| Immediate aggressive | 100 | +100 bps |
| TWAP aggressive | 25 / 25 / 25 / 25 | 0 bps |
| Past-volume aggressive | 10 / 20 / 30 / 40 | -20 bps |

These values are deliberately constructed test oracles only. They do not establish any ranking in real or simulated market experiments.

Each metric result passes the Step 17 independent episode audit.

## Regression matrix

- frozen specification: 7/7 hashes passed;
- Python: 308/308 tests passed;
- Python branch-aware coverage: 90.07%;
- GCC Debug: 49/49 C++ tests passed;
- Clang Debug: 49/49 passed;
- GCC Release/IPO: 49/49 passed;
- ASan + UBSan: 49/49 passed, no findings;
- GCC, Clang, Release baseline output: byte-identical;
- clean CMake installation: passed;
- separate downstream `find_package(robust_execution 0.14)` consumer using Step 18 schedule API: passed;
- Step 18 deterministic report verifier: passed.

## Defects caught before freeze

1. Equivalent rational fractions were not canonicalized (`25/100` versus `1/4`). Fixed with `std::gcd` reduction.
2. Initial portable allocation used GCC/Clang `__int128`; `-Wpedantic -Werror` correctly rejected it. Replaced with checked standard C++20 arithmetic.
3. Initial Step 18 tests used `assert`; optimized builds compile assertions away. Replaced with always-on requirements.

## Remaining scientific blockers

- zero admitted real historical days remain available because the Step 12 live pilot has not run;
- Step 19 Almgren–Chriss is not implemented yet;
- Step 20 queue-aware heuristic/MPC is not implemented yet;
- no locked-test or statistical comparison is permitted at Step 18.

**Exact next step:** Step 19 — derive, implement and validate discrete Almgren–Chriss execution schedules and limiting cases.
