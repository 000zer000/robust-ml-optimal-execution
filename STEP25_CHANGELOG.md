# Step 25 Changelog — Prediction Versus Decision Value

**Step:** 25 of 32  
**Status:** Engineering complete candidate; historical research activation blocked by Gate C  
**Research specification changed:** No  
**Repository version:** 0.14.0

## Added

- `python/robust_execution/analysis/prediction_decision_value.py`
  - full-holdout prediction metrics for calibrated, base-rate, shuffled, stale, uncalibrated and perfect-event-oracle conditions;
  - deterministic within-day/instrument/passive-side ablations;
  - shared-MPC prediction-weight sensitivity sweep;
  - action-distance and implementation-shortfall comparison;
  - explicit prediction-versus-decision relationship classification;
  - engineering summary preserving negative and non-monotonic results.
- Step 25 engineering config and JSON Schema.
- Deterministic report generator and independent semantic validator.
- Dedicated Python tests for boundary enforcement, ablation grouping, metrics, action distance and relationship labels.
- Step 25 methodology and analysis-contract documentation.

## Changed

- `re_ml_mpc_demo` now accepts the validation-only environment override `RE_ML_MPC_WEIGHT_BPS`.
- Its no-override/default output remains byte-identical to the committed Step 24 controller artifact.
- Repository/bootstrap validation includes Step 25.

## Engineering observations preserved

- Better log loss can leave the MPC unchanged.
- Worse log loss can still change the MPC at a finite signal weight.
- Calibration can improve log loss without making the controller more sensitive.
- The perfect Step 21 event-label oracle can worsen the realized engineering-fixture execution cost.
- No changed action on the committed engineering grid improves implementation shortfall versus the non-ML MPC.

## Explicitly not changed

- central research question or hypotheses;
- candidate horizons (250 ms, 1 s, 5 s);
- final horizon placeholder;
- final model-family placeholder;
- Step 21 target/feature contract;
- Step 20/24 shared-MPC fairness contract;
- Gate C requirements;
- locked historical test status.
