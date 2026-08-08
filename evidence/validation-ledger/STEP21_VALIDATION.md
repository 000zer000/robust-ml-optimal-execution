# Step 21 Validation — Causal Targets and Features

## Decision

**Step 21 engineering/data-contract decision: PASS.**

This pass validates the target definitions, exact causal feature set, timestamp contract, mutation/leakage barriers, immutable artifact separation, and repository regression state. It does **not** open the historical research gate, select a prediction horizon, or train a model.

The central research question, hypotheses, scope, and Step 2 research protocol were not changed. `scripts/verify_specification_lock.py` passes all seven frozen hashes.

## Implemented contract

Step 21 freezes:

- candidate quote-depletion/trade-through horizons of 250 ms, 1 s and 5 s;
- side-signed adverse-selection labels at the same three horizons;
- a source-time plus availability-time causality rule;
- complete five-second causal-history requirement;
- complete five-second future-label-coverage requirement;
- reconnect/snapshot-boundary rejection inside label windows;
- separate bid- and ask-oriented rows;
- 20 raw causal model features;
- physically separate feature and label tables;
- immutable input, feature dictionary, table, manifest and sidecar hashes;
- no exact historical queue position and no future-volume profile in features.

The final horizon remains `PRE_DATA_FIELD_BEFORE_CALIBRATION`. Step 21 does not choose among the three candidates.

## Frozen feature set

The model-facing feature dictionary contains 20 fields:

1. spread;
2. passive-side and opposite top-1 depth;
3. passive-side and opposite top-5 depth;
4. side-normalized top-1 and top-5 imbalance;
5. side-normalized aggressor trade pressure over 250 ms, 1 s and 5 s;
6. trade counts over 1 s and 5 s;
7. side-normalized mid movement over 250 ms, 1 s and 5 s;
8. absolute realized mid movement over 1 s and 5 s;
9. one-second spread change;
10. current quote age;
11. time since the last causal trade.

All values are raw integer/fixed-point quantities. No normalization or learned transform is fitted in Step 21.

## Target validation oracle

The deterministic validation fixture has:

- 2 instruments: BTCUSDT and ETHUSDT;
- 2 decision checkpoints per instrument;
- 2 passive sides per checkpoint;
- 8 total feature rows;
- 20 model features per row.

Quote-depletion positive counts are:

| Horizon | Positive | Negative |
|---|---:|---:|
| 250 ms | 3 | 5 |
| 1 s | 3 | 5 |
| 5 s | 6 | 2 |

Both classes are therefore exercised at every candidate horizon.

The fixture is intentionally synthetic and is not a training sample.

## Leakage and mutation evidence

The committed mutation report proves four separate behaviors:

1. **Future-label mutation:** changing a future ask-depletion event changes the corresponding 250 ms target while leaving the same decision's feature row unchanged.
2. **Post-horizon mutation:** changing an event after all declared five-second horizons changes no feature or label row.
3. **Causal-past mutation:** changing a trade inside the causal 250 ms window changes the expected trade-flow feature.
4. **Cross-instrument isolation:** the same BTCUSDT causal-past mutation does not change the corresponding ETHUSDT row.

Structural tests additionally reject incomplete history, incomplete label coverage, snapshot/reconnect crossings, duplicate event sequences, ordering inversions, availability inversions, malformed events, crossed books, unknown symbols, duplicate decision rows and artifact tampering.

## Python validation

The complete Python suite passes:

- **347/347 tests**;
- **90.58% branch-aware coverage**.

The Step 21 focused suite contains 39 passing tests.

Python bytecode compilation also passes for package, scripts and tests.

Ruff and mypy were not available from this environment's package registry. A fresh local Ruff/mypy result is therefore not claimed. Their pinned hosted-CI jobs remain configured.

## Native regression matrix

Step 21 adds no new C++ production behavior, but the complete native platform was rerun on the exact source state:

| Configuration | Result |
|---|---:|
| GCC Debug | 51/51 passed |
| Clang Debug | 51/51 passed |
| GCC Release/IPO | 51/51 passed |
| ASan + UBSan | 51/51 passed, no findings |

The sanitizer suite was executed in two bounded commands because the all-tests command exceeded the execution window while running the long simulator-validation test. Test 36 passed separately and tests 37–51 passed immediately afterward on the same build.

## Installability

A clean Release installation was installed under an isolated prefix. A separate CMake project then successfully executed:

`find_package(robust_execution 0.14 CONFIG REQUIRED)`

and linked `robust_execution::core`.

## Research boundary

Step 21 does not establish:

- predictive skill;
- probability calibration;
- a selected prediction horizon;
- model generalization;
- decision value;
- ML-MPC superiority;
- historical queue reconstruction;
- real-market strategy performance.

Gate C remains blocked because no live market-data day has been admitted. Step 22 may implement and validate the model-training machinery on controlled/synthetic data, but no historical model result may be promoted to a research result until the live-data requirements are satisfied.

## Exact next step

Step 22 implements the simple/interpretable model stack under this frozen data contract: base-rate/rule baselines, logistic/GLM, gradient-boosted trees, simple MLP, chronological preprocessing, calibration diagnostics, temporal/instrument slices and deterministic prediction artifacts.
