# Step 17 validation — exact accounting and execution metrics

## Decision

**PASS.** The Step 17 accounting, audit, metric, and deterministic-evidence gates are complete. The implementation is suitable as the common metric layer for Step 18 and later strategies.

The result is a software and calculation validation only. The committed evidence is synthetic and non-research; it is not a historical strategy comparison.

## Specification integrity

- Frozen specification files checked: **7**
- Matching approved hashes: **7/7**
- Specification lock regenerated: **No**
- Research question, hypotheses, scope, and protocol changed: **No**

`SPECIFICATION.yaml` was restored byte-for-byte from the approved corrected Step 2 package after a working-tree drift was detected.

## Exact accounting fixture

The detailed buy-parent fixture contains four fills and completes 100 lots:

| Field | Validated result |
|---|---:|
| Gross execution notional | 10,080 quote atoms |
| Explicit fees/rebates | 3 quote atoms |
| Net cash flow | -10,083 quote atoms |
| Arrival-price implementation shortfall | 83 quote atoms |
| Implementation shortfall | 83 bps |
| Terminal-completion quantity | 10 lots |
| Terminal-completion cost | 52 quote atoms |
| Passive fraction | 40% |
| Aggressive fraction | 60% |
| Residual quantity | 0 lots |

Buy/sell symmetry, exact inventory bounds, final completion, fee convention, benchmark accounting, and the independent C++ audit all pass.

A separate rational-increment test validates exact accounting with:

- tick size `1/100` quote units;
- lot size `1/1000` base units;
- quote atom size `1/1,000,000` quote units;
- exact notional `246,900,000` quote atoms;
- average price `12,345` ticks = `123.45` quote units.

## Tail-risk fixture

The aggregate fixture contains **40 completed, independently audited episodes**. Its preregistered loss sequence produces:

| Statistic | Result |
|---|---:|
| Mean shortfall | 77.5 bps |
| VaR95 | 165.0 bps |
| CVaR95 | 172.5 bps |
| VaR99 | 175.0 bps |
| CVaR99 | 175.0 bps |

The aggregate API rejects incomplete, unaudited, or undefined-shortfall episodes.

## Python validation

- Tests: **308/308 passed**
- Branch-aware coverage: **90.07%**
- Independent Python accounting audit: **passed**
- Metric/report/manifest schemas: **passed**
- Deterministic fixture regeneration: **byte-identical**
- Correctly rehashed semantic-tamper artifacts rejected: **passed**

The Python verifier independently reconstructs all exact accounting, inventory, markout, activity, throughput, latency, and tail-risk values from the ledger and raw tail rows.

## C++ validation matrix

| Configuration | Result |
|---|---:|
| GCC 14 Debug | 48/48 passed |
| Clang 17 Debug | 48/48 passed |
| GCC 14 Release with IPO | 48/48 passed |
| GCC ASan + UBSan | 48/48 passed; no findings |

The GCC Debug, Clang Debug, and GCC Release metric-demo outputs are byte-identical with SHA-256:

```text
cdd1d8752074f67e7e68e7c2f4cf61a48fb9f419822063dc1ef8dcab8e693cdf
```

## Installation and downstream use

A clean Release installation was consumed from an independent CMake project using:

```cmake
find_package(robust_execution 0.14 REQUIRED CONFIG)
target_link_libraries(step17_consumer PRIVATE robust_execution::core)
```

The downstream executable called the installed `run_metrics_validation()` API and passed all gate flags.

## Version-linked fixture verification

Steps 12–16 were regenerated only because their manifests embed the software version or hashes of upstream synthetic artifacts. The following scientific invariants were checked before and after regeneration:

- Step 12 raw-message count and sequence diagnostics: unchanged;
- Step 13 structural/admission result: unchanged;
- Step 14 table row counts and non-research classification: unchanged;
- Step 15 connection/event/observation counts and blockers: unchanged;
- Step 16 exact-FIFO scenarios and sensitivity matrix: unchanged;
- Step 17 accounting and tail values: unchanged.

## Tool limitations

- Ruff and mypy were not freshly executed locally because their pinned packages were unavailable from the local registry.
- Docker, the hosted CI jobs, and local TSan were not newly executed in this step.
- No positive result is claimed for any unexecuted tool path.

## Scientific boundary

Step 17 validates formulas, exact accounting, audit controls, deterministic evidence, and descriptive metrics. It does not validate:

- any execution strategy;
- historical queue truth;
- an impact model;
- a benchmark as economically optimal;
- independence assumptions;
- confidence intervals or hypothesis tests;
- real-market profitability;
- production latency or throughput.

Those claims require the later baseline, robustness, and statistical-analysis milestones.

## Integrated-command execution note

The final combined `make test` invocation passed the specification, repository, Steps 5–17 validators, and the first 35 C++ tests, then was terminated by the environment's fixed command window while running the long Gate B test. This was not a test failure. The same GCC suite passed **48/48** separately, and all Python tests and every other compiler/sanitizer configuration also passed separately on the same source state.
