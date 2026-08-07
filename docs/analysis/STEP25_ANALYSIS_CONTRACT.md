# Step 25 prediction/decision analysis contract

## Source immutability

Prediction metrics are computed directly from the committed Step 23 engineering-holdout prediction tables. The Step 25 report stores the Step 23 report, model-card and prediction-table SHA-256 values and refuses a prediction table whose data hash differs from the Step 23 report.

## Prediction ablations

All ablations use the same targets and rows. The within-slice shuffle is a deterministic one-position rotation inside `(day, instrument, passive side)` groups. The stale condition uses the prior calibrated probability inside the same group and substitutes the training base rate only for the first endpoint, where no earlier same-group prediction exists.

No ablation may mix rows across a day, instrument or passive side.

## Controller fairness

Every decision-sensitivity point calls the same Step 24 executable and therefore the same shared MPC solver. The only varied controller field is the synthetic prediction-risk weight. At zero weight every prediction condition must reproduce the non-ML action path. The centered training-base-rate condition must reproduce the non-ML action path at every weight.

The Step 24 default invocation with no environment override must remain byte-identical to the Step 24 committed controller report.

## Direction of cost

For the Step 17 implementation-shortfall metric used here, lower values are better. `shortfall_delta_bps_vs_non_ml = candidate - non_ml`; therefore a negative delta would be an improvement and a positive delta is worse.

## Claim boundary

The weight sweep is an engineering sensitivity grid, not a tuned policy parameter. First-change weights are reported only to expose the controller response surface. They cannot be promoted to research choices before Gate C and the frozen development protocol are active.
