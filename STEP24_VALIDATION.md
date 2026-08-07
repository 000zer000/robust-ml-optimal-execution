# Step 24 Validation — ML-Assisted MPC

**Decision:** PASS for engineering integration.  
**Research-result status:** `synthetic_validation_only_non_research`.  
**Historical research activation:** BLOCKED until Gate C admits real market-data days.  
**Research specification changed:** No; the frozen specification lock remains 7/7.

## 1. Scope validated

Step 24 integrates precomputed supervised probabilities into the same finite-horizon MPC search used by Step 20. The only intended controller difference is an additive passive-risk term based on probability minus training base rate. The prediction is not treated as exact fill probability.

All three unresolved candidate horizons are exercised. No horizon or final model family is selected and the locked historical test remains unopened.

## 2. Prediction and causality contract

Validated properties include:

- exact decision-ID and endpoint-time alignment;
- feature cutoff no later than the policy observation cutoff;
- inference availability no later than decision time;
- matching clock domains;
- probabilities and training base rates bounded to [0,1];
- explicit model/horizon/provenance metadata;
- stale predictions identify a strictly earlier source decision;
- duplicate prediction endpoints are rejected;
- missing active endpoints fail closed.

The committed prediction tapes are regenerated from Step 23 artifacts and independently checked against the exact first four engineering-holdout endpoints for every horizon.

## 3. Fairness controls

The non-ML and ML controllers use the same internal search implementation, action fractions, planning horizon, passive cap, inventory/terminal costs, queue/fill proxy, action validator and terminal completion.

Two neutral controls are executable invariants:

- prediction equals training base rate;
- prediction-risk weight equals zero.

Both reproduce the non-ML action path and implementation-shortfall accounting exactly in the committed fixture.

## 4. Ablation matrix

For 250 ms, 1 s and 5 s the report stores calibrated, training-base-rate, shuffled, stale, uncalibrated, perfect-event-oracle and zero-weight controller runs.

The calibrated model probabilities do not change the tiny synthetic episode's action path. This negative engineering observation is retained. The perfect-event oracle changes the controller path for at least one horizon, proving that the prediction term can alter optimisation decisions.

These episode values are test oracles only and are not a model/horizon ranking or empirical execution claim.

## 5. Deterministic artifact contract

Committed evidence:

- `data/sample/controller/step24-ml-mpc-validation/prediction-tapes.json`;
- `data/sample/controller/step24-ml-mpc-validation/report.json`;
- exact config and two JSON schemas;
- C++ canonical decision diagnostics and report payload SHA-256;
- cross-compiler report SHA-256.

GCC Debug, Clang Debug and GCC Release emit the same report SHA-256:

`17c59c051fb2063bccb9567a64651826accab40316bf11e0bb44ff14f5f903ea`

## 6. Executed validation

### Python and artifacts

- full Python suite: **378/378 passed**;
- branch-aware coverage: **90.3072%** (required minimum 90%);
- Step 24 semantic artifact validator: passed;
- Python compileall: passed;
- frozen research specification: **7/7 hashes matched**.

### C++ regression

- GCC Debug: **52/52 passed**;
- Clang Debug: **52/52 passed**;
- GCC Release: **52/52 passed**;
- ASan + UBSan: **52/52 passed**, no findings;
- Step 24 GCC/Clang/Release report: byte-identical.

### Packaging and integration

- clean Release CMake install: passed;
- external `find_package(robust_execution 0.14 CONFIG REQUIRED)` consumer using the Step 24 public API: passed;
- repository required-file contract: **424/424 passed**;
- Step 24 newly introduced/touched lines over the configured 100-character limit: **0** after manual formatting.

The repository-level `make test` command passed the frozen-specification/repository checks and every validator through Step 16, then the execution harness terminated the command while Step 17 was starting because the combined sequential run exceeded the available execution window. No failing assertion or validator result was emitted. On the identical final source state, the Step 17 through Step 24 validators were then run separately and all passed. Therefore no fully completed combined-`make test` green claim is made for this local session.

Ruff and mypy executables are not installed in the local environment, so no fresh local Ruff/mypy-green claim is made. Hosted CI retains those checks.

## 7. Scientific boundary

Step 24 does not establish:

- that ML-MPC beats non-ML MPC;
- that any prediction horizon is preferred;
- that the temporal deep model is the final model family;
- that the synthetic 1000-bps prediction weight is research-optimal;
- historical or live execution performance;
- statistical significance;
- real-market profitability.

The exact next milestone is Step 25: prediction versus decision value under the frozen ablation protocol, while historical claims remain Gate-C blocked.
