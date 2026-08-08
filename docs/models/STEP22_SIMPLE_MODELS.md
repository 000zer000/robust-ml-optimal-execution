# Step 22 — Simple/interpretable prediction models

## Status

Step 22 validates the supervised-learning machinery on a deterministic synthetic engineering fixture. It does **not** select the research prediction horizon, select a final model family, open the locked historical test, or make a real-market prediction claim.

The central research question and Step 2 protocol remain unchanged.

## Required model ladder

For each candidate quote-depletion horizon (250 ms, 1 s, 5 s), the engineering gate trains:

1. constant training base rate;
2. L2-regularised logistic regression;
3. histogram gradient-boosted trees;
4. one-hidden-layer MLP.

The compact temporal deep model remains Step 23.

## Chronological data contract

The synthetic fixture mirrors the frozen whole-day research allocation:

- 50 train days;
- 20 validation days;
- 10 calibration days;
- 20 engineering-holdout days.

The fixture contains BTCUSDT and ETHUSDT, bid/ask oriented rows, and the exact 20 raw Step 21 features. It is labelled `synthetic_validation_only_non_research` everywhere.

The engineering holdout is **not** the protocol's locked historical test. Research mode refuses to run until a primary horizon has been frozen before calibration/test, exactly as required by `RESEARCH_PROTOCOL.md`.

## Model selection and preprocessing

Hyperparameters are chosen only by validation log loss, with validation Brier score and a deterministic parameter ordering as tie-breakers. This is within-family tuning only; Step 22 does not choose a final model family.

For logistic regression and the MLP:

- `StandardScaler` statistics are fitted on the training segment only;
- after hyperparameters are frozen, model weights may be fitted on train+validation transformed by the frozen train scaler;
- no calibration or holdout row contributes to scaler statistics.

The tree model receives raw Step 21 feature values and performs no scaling.

## Probability calibration

For non-constant models, Platt calibration is fitted **only** on the calibration segment. The calibrator consumes the logit of the uncalibrated probability. The base-rate comparator remains the training-segment base rate and is not recalibrated.

Both uncalibrated and calibrated predictions are retained.

## Evaluation

The engineering holdout records:

- log loss;
- Brier score;
- expected calibration error with ten equal-width probability bins;
- reliability-bin data;
- calibration intercept and slope when identifiable;
- ROC-AUC;
- PR-AUC with prevalence;
- precision/recall at probabilities 0.25, 0.50 and 0.75;
- BTCUSDT and ETHUSDT slices;
- bid/ask slices;
- first-half and second-half chronological holdout slices.

No model is promoted because of these synthetic metrics.

## Artifact policy

Every horizon/family stores a model card, calibrated/uncalibrated prediction table, reliability data, slice metrics and a trusted local pickle artifact. Pickle files are integrity-hashed but must only be loaded from trusted repository artifacts.

Scikit-learn tree/MLP pickle bytes are not treated as scientific reproducibility evidence because equivalent fitted objects can serialize differently after use. Every committed artifact is integrity-checked and every stored prediction is compared with a reloaded model. Regeneration must also produce byte-identical model cards, prediction tables, metrics/reliability artifacts, selected hyperparameters and reports across two independent runs on the executing host. Those fitted bytes are not claimed portable across different CPUs or ML/BLAS kernels.

## Research boundary

Step 22 does not establish predictive skill on Binance data. Gate C remains blocked because no live day has been admitted. The final horizon must later be selected on valid research validation data using the frozen ordered rule, including controller decision value; Step 22 deliberately does not substitute classification metrics for that decision.
