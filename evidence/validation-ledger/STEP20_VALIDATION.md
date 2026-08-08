# Step 20 Validation — Queue-Aware Heuristic and Non-ML MPC

**Decision:** PASS for engineering Gate D.  
**Historical research activation:** BLOCKED until Gate C.  
**Research status:** `synthetic_validation_only_non_research`  
**Research specification changed:** No.

## 1. Purpose

Step 20 establishes the strong non-machine-learning adaptive comparators that later learned execution policies must face fairly. It adds:

1. a causal queue/liquidity-aware heuristic; and
2. a bounded finite-horizon, receding-horizon non-ML MPC controller.

Both use the Step 8 policy/action contract and Step 17 accounting. Neither may observe future events or exact historical FIFO position.

## 2. Non-ML signal contract

The adaptive signal layer uses only the current delivered observation:

- midpoint and spread;
- visible same/opposite-side best depth;
- visible queue-share proxy;
- recent aggressor-side trade pressure;
- elapsed, filled, remaining, and progress-lag fractions.

The engineering fill-probability proxy is rule-based and explicitly non-ML. The calibration object requires a provenance ID and a cutoff strictly before the parent-order start.

## 3. MPC contract

The MPC:

- enumerates a bounded finite-horizon action tree;
- uses only no-action, predeclared passive fractions, and predeclared aggressive fractions;
- caps passive child quantity at the configured maximum passive fraction;
- freezes the current observable book and non-ML fill model inside each local planning solve;
- executes only the first selected action;
- re-solves at the next causal observation;
- delegates terminal completion entirely to Step 8.

The future Step 24 ML-assisted MPC must retain the same action space, inventory/terminal rules, latency treatment, and controller constraints. It may add only the predeclared learned prediction inputs.

## 4. Deterministic validation oracles

Committed evidence: `data/sample/adaptive/step20-validation/report.json`.

- Early wide-spread / high-fill-probability MPC state: **passive**.
- Late low-fill-probability / urgent MPC state: **aggressive**.
- Early planning horizon used: 4 steps.
- Early bounded tree nodes evaluated: 937.
- Late planning horizon: 1 step.
- Historical exact queue used: false.
- ML or learned signal used: false.

Synthetic execution fixture results are retained only as test oracles:

- queue-aware heuristic: complete, 33 bps shortfall;
- non-ML MPC: complete, -111 bps shortfall.

These numbers are not a strategy ranking and are not historical or statistical evidence.

## 5. Failure-path checks

Tests reject or constrain:

- calibration cutoff at/after episode start;
- direct solver calls with leaked calibration;
- noncanonical quantity fractions;
- missing full-residual aggressive action;
- passive fractions above the configured maximum;
- non-finite cost parameters;
- invalid horizon/action-set sizes;
- incompatible policy environments;
- ordinary strategy actions after terminal completion begins.

## 6. Regression and platform matrix

| Gate | Result |
|---|---:|
| Frozen specification lock | 7/7 passed |
| Python tests | 308/308 passed |
| Python branch-aware coverage | 90.07% |
| GCC Debug C++ | 51/51 passed |
| Clang Debug C++ | 51/51 passed |
| GCC Release + IPO | 51/51 passed |
| ASan + UBSan | 51/51 passed, no findings |
| GCC/Clang/Release adaptive report | byte-identical |
| Step 18 validator | passed |
| Step 19 validator | passed |
| Step 20 validator | passed |
| Clean CMake installation | passed |
| External `find_package(robust_execution 0.14)` consumer | passed |
| Python bytecode compilation | passed |

The first ASan/UBSan command was interrupted during the rebuild by the execution window; the resumed full suite subsequently executed all 51 tests successfully.

## 7. Gate D decision

**Engineering decision: PASS.**

The repository now contains strong classical/adaptive non-ML baselines: immediate aggressive, TWAP, past-only volume scheduling, discrete Almgren–Chriss, queue/liquidity heuristic, and receding-horizon MPC.

**Historical research activation remains blocked.** Gate C still has zero admitted live days because the required live-data pilot has not completed in the available execution environment. Therefore no fair historical calibration, historical baseline ranking, or later ML-vs-MPC result may be claimed yet.

## 8. Scientific claim boundary

Step 20 does not establish:

- that the heuristic or MPC beats any classical baseline;
- that the synthetic fill-probability proxy is historically calibrated;
- exact historical queue position;
- real-market profitability;
- an ML result;
- a statistically significant result.

It establishes a reproducible, causal, non-ML adaptive comparator suitable for later locked comparisons once the data gate is satisfied.
