# Step 22 Changelog — Interpretable and Simple Models

**Step:** 22 of 32  
**Status:** Engineering complete; research activation blocked by Gate C  
**Research specification changed:** No

## Added

- `python/robust_execution/prediction/simple_models.py`
  - deterministic engineering training fixture;
  - 50/20/10/20 whole-day chronological split analogue;
  - base-rate, logistic, histogram gradient-boosted tree, and simple MLP families;
  - validation-only hyperparameter selection;
  - training-only scaler fitting for logistic and MLP;
  - calibration-segment-only Platt calibration;
  - log loss, Brier score, ECE, reliability, ROC-AUC, PR-AUC, threshold and slice metrics;
  - trusted model serialization and batch-one inference timing helper.
- `python/robust_execution/prediction/simple_model_artifacts.py`
  - immutable model cards, predictions, reliability tables, slice metrics, report and manifest;
  - semantic rerun verification independent of unstable pickle byte streams.
- Step 22 model config, JSON schemas, fixture generator, validator, benchmark script and tests.
- Step 22 methodology and inference-contract documentation.
- `[models]` optional Python dependency group with NumPy and scikit-learn; the Step 21 core prediction package remains importable without those optional dependencies.

## Corrections made during Step 22

1. Replaced implicit lexicographic side ordering with an explicit canonical bid/ask key in the engineering fixture.
2. Preserved training-only scaler statistics when refitting logistic/MLP classifier weights on train+validation after hyperparameters are frozen.
3. Separated semantic model reproducibility from pickle byte determinism: committed pickle hashes are integrity checks, while predictions/cards/non-binary artifacts are the reproducibility contract.
4. Kept Step 22 ML imports out of `prediction.__init__` so scikit-learn is not a hidden core dependency.
5. Expanded negative/tamper tests rather than lowering the repository's 90% branch-coverage gate.
6. Wrapped all Step 22 source/test lines to the configured 100-character Ruff limit after Ruff proved unavailable from the local registry.
7. Added the inference benchmark script and result to the repository required-file contract.

## Explicitly not changed

- central research question;
- research hypotheses;
- candidate horizons (250 ms, 1 s, 5 s);
- selected horizon placeholder;
- Step 21 twenty-feature causal contract;
- chronological research split protocol;
- Gate C historical-data requirement;
- non-ML MPC comparison contract for Step 24.
