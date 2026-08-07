# Step 22 Validation — Interpretable and Simple Models

**Decision:** PASS for engineering/model-pipeline validation.  
**Research-result status:** `synthetic_validation_only_non_research`.  
**Historical research activation:** BLOCKED until Gate C admits real market-data days.  
**Research specification changed:** No; the frozen specification lock passes 7/7.

## 1. Scope validated

Step 22 implements the simple/interpretable prediction ladder required before the temporal deep model:

1. training-prevalence/base-rate model;
2. regularised logistic regression;
3. histogram gradient-boosted trees;
4. one-hidden-layer MLP.

All consume the exact 20 raw causal features and the three quote-depletion/trade-through candidate horizons frozen in Step 21. Step 22 does not select the final research horizon or final model family.

## 2. Chronological engineering fixture

The committed deterministic fixture contains 100 synthetic whole days, two instruments and both passive sides, for 800 rows total. It mirrors the research split structure:

| Segment | Days | Rows | Permitted use |
|---|---:|---:|---|
| Train | 50 | 400 | scaler fitting and model fitting |
| Validation | 20 | 160 | hyperparameter selection only |
| Calibration | 10 | 80 | Platt calibration only |
| Engineering holdout | 20 | 160 | engineering evaluation only; never model selection |

This is a software-validation analogue, not a substitute for the future admitted historical dataset and not the locked research test period.

## 3. Leakage controls

Validated properties:

- hyperparameters are selected only from validation log loss, with Brier score and a deterministic parameter representation as tie-breakers;
- base-rate prevalence is computed from training only;
- `StandardScaler` statistics for logistic and MLP are fitted on training only and remain frozen if classifier weights are subsequently fitted on train+validation;
- Platt calibration sees only calibration rows;
- engineering-holdout labels cannot influence hyperparameter selection or calibration;
- research mode rejects the unresolved `PRE_DATA_FIELD_BEFORE_CALIBRATION` horizon placeholder;
- the Step 21 feature list must match exactly and in order.

Mutation tests confirm that changing calibration labels affects calibration but not underlying raw model predictions, and changing calibration/engineering-holdout labels does not change validation-selected hyperparameters.

## 4. Probability diagnostics

For every family and candidate horizon the fixture stores:

- uncalibrated and calibrated log loss;
- Brier score;
- expected calibration error;
- calibration intercept/slope where identifiable;
- ROC-AUC and PR-AUC;
- fixed-threshold precision/recall;
- reliability bins;
- instrument, passive-side and temporal slice metrics.

The synthetic values are test oracles only. They are not used to select the research horizon or make a claim about model superiority.

## 5. Artifact and reproducibility contract

Twelve fitted artifacts are produced (3 horizons x 4 families), each with:

- trusted `model.pkl` artifact;
- model card;
- engineering-holdout prediction table;
- reliability table;
- slice metrics.

The dataset also contains the exact config snapshot, chronological split manifest, training-row table, aggregate report and SHA-256 manifest.

Equivalent scikit-learn fits can produce different pickle byte streams after object use while retaining identical predictions. Therefore:

- pickle SHA-256 verifies the integrity of the specific committed binary;
- pickle byte identity is not treated as scientific reproducibility evidence;
- model cards, selected hyperparameters, reports and prediction artifacts must reproduce semantically/deterministically.

A clean rerun passes this semantic reproducibility check.

## 6. Inference engineering check

`results/validation/step22/inference_benchmark.json` records single-row inference measurements with one thread on the current machine for all 12 artifacts. It is explicitly marked `engineering_machine_specific_not_step30_performance_claim`.

This benchmark exists to expose obviously impractical inference paths before controller integration. Formal latency/throughput claims, hardware comparisons, compiled inference and CPU/GPU work remain Step 30 responsibilities.

## 7. Executed validation

### Python

- full test suite: **363/363 passed**;
- branch-aware coverage: **90.50%** (required minimum 90%);
- Step 22 semantic artifact validator: passed;
- Python compileall: passed;
- Step 22 source/test lines over configured 100-character limit after manual formatting: **0**.

### C++ regression

Step 22 changes no C++ behavior, but the entire native platform was rerun:

- GCC Debug: **51/51 passed**;
- Clang Debug: **51/51 passed**;
- GCC Release with IPO: **51/51 passed**;
- ASan + UBSan: **51/51 passed**, no findings.

### Packaging/integration

- combined `make test`: reached the Step 22 semantic model rerun after every upstream Step 5–21 validator passed, then was terminated by the execution window; the same Step 22 validator, complete Python suite and all native suites passed separately on the identical source state; no combined-green claim is made;
- frozen research specification: **7/7 hashes matched**;
- workflow YAML parsed successfully;
- Step 22 JSON schema files parsed successfully;
- clean Release CMake install: passed;
- external `find_package(robust_execution 0.14 CONFIG)` consumer: passed;
- core Step 21 prediction package imported successfully while NumPy/scikit-learn imports were deliberately blocked, confirming Step 22 dependencies remain optional.

## 8. Tool limitations

- Ruff and mypy are not installed locally and the configured package registry could not provide them. No fresh Ruff/mypy pass is claimed.
- A manual 100-character line-length audit was performed because the repository config would otherwise expose a known Ruff E501 risk.
- Hosted CI is configured to install the model dependencies and execute the Step 22 validator, but no hosted-green claim is made until CI actually runs on a pushed repository.

## 9. Gate decision

**Step 22 engineering gate: PASS.**

The following remain deliberately unresolved:

- final 250 ms / 1 s / 5 s research horizon selection;
- final model-family selection;
- historical predictive performance;
- ML-assisted execution decision value;
- any claim that a model beats the non-ML MPC;
- secondary adverse-selection regression as a final research result.

The exact next milestone is Step 23: one serious compact temporal deep model under the same causal data/split/calibration contract.
