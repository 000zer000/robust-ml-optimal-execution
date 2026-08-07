# Step 25 Validation — Prediction Versus Decision Value

**Decision:** PASS for engineering analysis and integration validation.  
**Research-result status:** `synthetic_validation_only_non_research`.  
**Historical research activation:** BLOCKED until Gate C admits real market-data days.  
**Research specification changed:** No; the frozen specification lock passes 7/7.

## 1. Scope validated

Step 25 implements the analysis layer that separates prediction quality from downstream execution behavior. It uses the exact Step 23 temporal-model engineering-holdout predictions and the exact Step 24 shared MPC. It does not select a final prediction horizon, select a final model family, tune a research controller weight, open the locked historical test, or make a real-market execution claim.

For every 250 ms / 1 s / 5 s candidate horizon the analysis evaluates 400 engineering-holdout prediction rows under calibrated, training-base-rate, deterministic within-slice shuffled, one-step stale, uncalibrated and perfect-event-oracle conditions.

The controller layer evaluates the same conditions on the Step 24 deterministic execution fixture across the engineering sensitivity grid:

`0, 50, 100, 250, 500, 1000, 2000, 5000, 10000, 25000` bps.

The grid exposes controller sensitivity only. It is not a research hyperparameter search.

## 2. Prediction and decision separation

The report records proper scoring metrics and downstream controller behavior independently. The committed fixture preserves all four observed relationship classes:

| Relationship | Count across registered comparisons/weights |
|---|---:|
| Prediction improved, decision unchanged | 84 |
| Prediction improved, decision changed | 26 |
| Prediction not improved, decision unchanged | 32 |
| Prediction not improved, decision changed | 8 |

This confirms that the Step 25 implementation does not reduce decision value to a prediction-metric ranking.

## 3. Engineering prediction observations

Engineering-holdout log loss for the key comparator conditions is:

| Horizon | Training base rate | Uncalibrated | Calibrated | Perfect event oracle |
|---|---:|---:|---:|---:|
| 250 ms | 0.145333 | 0.144247 | 0.161793 | ~1e-9 |
| 1 s | 0.482882 | 0.473758 | 0.478034 | ~1e-9 |
| 5 s | 0.689455 | 0.667523 | 0.640088 | ~1e-9 |

The values are synthetic engineering test oracles only. In particular, calibration helps 5 s log loss but worsens the 250 ms and 1 s log loss on this fixture. No horizon or model is promoted from these numbers.

## 4. Controller sensitivity observations

The first committed grid weight at which the action path differs from the non-ML MPC is:

| Horizon | Calibrated | Uncalibrated | Perfect event oracle |
|---|---:|---:|---:|
| 250 ms | 5000 bps | none on grid | none on grid |
| 1 s | none on grid | none on grid | 250 bps |
| 5 s | 10000 bps | 5000 bps | 500 bps |

The 5 s result is an explicit non-monotonic example: calibration improves log loss relative to the uncalibrated probabilities, while the uncalibrated tape changes this small controller fixture at a lower engineering weight.

## 5. Negative execution result retained

Lower Step 17 implementation shortfall is better. On the committed Step 25 fixture, no action change anywhere on the sensitivity grid improves implementation shortfall relative to the non-ML MPC.

For changed action paths, the observed shortfall deltas versus non-ML are positive (worse):

- 250 ms: +61 to +311 bps;
- 1 s: +61 bps;
- 5 s: +24 to +311 bps.

The perfect Step 21 quote-depletion/trade-through event oracle can also worsen the execution fixture. This is preserved deliberately. The event oracle is not an execution-cost oracle, so the result exposes target-to-objective mismatch rather than a contradiction in the implementation.

## 6. Causality, grouping and fairness checks

Validated properties include:

- shuffled probabilities rotate only inside the same synthetic day, instrument and passive side;
- stale probabilities use only the previous same-group prediction, with training base rate at the first endpoint;
- every Step 25 prediction table hash matches the committed Step 23 report;
- the Step 24 controller default invocation remains byte-identical after adding the validation-only weight override;
- zero prediction weight reproduces the non-ML action path for every prediction condition;
- centered training-base-rate predictions reproduce the non-ML action path at every grid weight;
- every parent order completes;
- no locked research test or historical research activation is used.

## 7. Determinism

The complete Step 25 report is byte-identical when the controller sweeps are produced by:

- GCC Debug;
- Clang Debug;
- GCC Release.

Canonical report file SHA-256:

`8df0d0fa11132db307c43880fbb33d5edc49d2935c04675d62d4e4e5e07873e9`

The report's canonical payload SHA-256 is:

`0d7a7003ae4761b19baff613bc3930642de8c3abeab3dc3c79b37f108d26c593`

## 8. Executed validation

### Python

- full Python suite: **402/402 passed**;
- Step 25 dedicated tests: **24/24 passed**;
- branch-aware repository coverage: **90.609899%** (required minimum 90%);
- Step 25 analysis module coverage: **98%** in the final combined coverage run;
- Step 25 semantic artifact validator: passed;
- Python `compileall`: passed;
- all 55 JSON configs/schemas parsed successfully;
- touched Step 25 Python/C++ lines over the configured 100-character limit: **0**.

### C++ regression

Step 25 changes no shared MPC algorithm. It adds only a validation-only executable weight override, while the complete native platform was rerun:

- GCC Debug: **52/52 passed**;
- Clang Debug: **52/52 passed**;
- GCC Release: **52/52 passed**;
- ASan + UBSan: **52/52 passed**, no findings.

### Packaging and repository integration

- frozen research specification: **7/7 hashes matched**;
- repository contract: **438 required files passed**;
- clean Release CMake install: passed;
- external `find_package(robust_execution 0.14 CONFIG REQUIRED)` consumer: passed;
- Step 24 semantic validator: passed on the final Step 25 source state;
- Steps 22, 23, 24 and 25 semantic validators: all passed separately on the identical final state.

## 9. Combined-command execution limitation

The repository-wide `make test` command passed every gate from specification verification through Step 21, then the execution harness terminated the command as the Step 22 simple-model semantic regeneration began. No failing assertion was reported.

The remaining validators were therefore executed separately on the identical final source state:

- Step 22: passed (12 models, 800 engineering rows);
- Step 23: passed (3 temporal models, 2,000 sequences / 4,800 source rows);
- Step 24: passed;
- Step 25: passed;
- complete native matrices and complete Python suite: passed separately as reported above.

No claim is made that the all-in-one `make test` process itself reached normal completion.

## 10. Local tool limitations

Ruff and mypy executables are not installed in the local environment, so no fresh local Ruff/mypy-green claim is made. The source was manually checked against the configured 100-character line limit for all Step 25 touched code.

## 11. Gate decision

**Step 25 engineering gate: PASS.**

The following remain deliberately unresolved:

- final 250 ms / 1 s / 5 s research horizon selection;
- final prediction model-family selection;
- research controller-weight selection;
- historical predictive performance;
- historical ML-assisted execution decision value;
- any claim that ML-MPC beats the non-ML MPC;
- profitability or venue generalisation.

Gate C remains the blocker for historical research activation. The exact next roadmap milestone is Step 26: imitation learning from the validated MPC teacher, with covariate-shift diagnostics and corrective/fallback logic when required.
