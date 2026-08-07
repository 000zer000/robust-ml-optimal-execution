# Step 25 — Prediction quality versus decision value

## Status and boundary

Step 25 implements the engineering analysis required to separate predictive quality from downstream execution behavior. The committed evidence remains `synthetic_validation_only_non_research`: Gate C is still closed, no historical research test is opened, no 250 ms / 1 s / 5 s horizon is selected, and no final model family is selected.

The purpose of this step is not to declare an ML winner. It is to establish an executable analysis that can answer, once admissible development data exist, whether a change in probability quality actually changes the common MPC and whether any changed decision improves execution cost.

## Prediction-quality analysis

For each Step 23 candidate horizon, Step 25 reads all 400 engineering-holdout temporal sequences and evaluates the same target under six prediction conditions:

1. calibrated temporal-model probability;
2. training base rate;
3. deterministic within-day/instrument/passive-side shuffle;
4. one-decision stale probability, with the first probability in each slice replaced by the training base rate;
5. uncalibrated temporal-model probability;
6. perfect quote-depletion/trade-through event oracle.

The stored metrics are log loss, Brier score, expected calibration error, ROC-AUC and PR-AUC. The oracle is a label oracle, not an execution-cost oracle.

Shuffling and staleness never cross a synthetic day, instrument or passive side. They therefore degrade information while preserving the declared engineering grouping boundaries rather than mixing unrelated slices.

## Decision-sensitivity analysis

Step 25 reuses the exact Step 24 shared MPC solver and controller fixture. The Step 24 executable accepts a validation-only `RE_ML_MPC_WEIGHT_BPS` override; the default invocation remains byte-identical to the committed Step 24 report.

Every prediction condition is evaluated over the deterministic grid:

`0, 50, 100, 250, 500, 1000, 2000, 5000, 10000, 25000` bps.

For each grid point the report records:

- controller action path;
- action distance from the non-ML MPC;
- implementation shortfall;
- shortfall delta versus the non-ML MPC;
- completion status;
- first grid weight at which the action path changes.

The weight grid is an engineering sensitivity device. It is not a research hyperparameter search and cannot be used to select the final controller weight.

## Engineering observations retained

The fixture intentionally retains several forms of prediction/decision divergence.

### 250 ms

The calibrated temporal model has worse engineering-holdout log loss than both the training-base-rate comparator and its uncalibrated probabilities. Nevertheless, the calibrated tape changes the small MPC fixture at 5,000 bps, while the uncalibrated tape does not change it anywhere on the committed grid.

This demonstrates that probability quality and controller sensitivity are different properties.

### 1 s

The calibrated model improves log loss over the training-base-rate, shuffled and stale conditions, but does not alter the controller anywhere on the committed grid. The perfect event oracle changes the action path beginning at 250 bps.

This is direct evidence of the case “prediction improves, decision unchanged.”

### 5 s

Calibration improves log loss relative to the uncalibrated temporal probabilities, but the uncalibrated tape changes the controller at 5,000 bps while the calibrated tape first changes it at 10,000 bps. Shuffled and stale inputs also change the fixture at 5,000 bps.

Again, a better proper scoring rule does not imply a larger or earlier optimizer response.

## Negative execution result

For this deterministic engineering path, every action change produced anywhere on the committed grid has implementation shortfall no better than the non-ML MPC. The perfect event oracle can also worsen the realized fixture shortfall.

That is not contradictory: the oracle predicts the Step 21 quote-depletion/trade-through label perfectly; it is not an oracle for future execution cost. The result therefore exposes possible target-to-objective mismatch rather than invalidating the model or controller implementation.

This negative result is preserved because Step 25 is explicitly about whether predictive improvements translate into decision value. The answer on this tiny synthetic engineering fixture is: not necessarily, and in the changed-action cases observed here, no execution improvement occurs.

## Research interpretation rules

The committed numbers are software-validation oracles only. They must not be used to claim:

- real-market predictive skill;
- a best prediction horizon;
- a best model family;
- an optimal prediction-risk weight;
- superiority of ML-MPC over the Step 20 non-ML MPC;
- profitability;
- generalisation to Binance or another venue.

Once Gate C admits historical development data, the frozen research protocol—not this synthetic fixture—controls horizon selection and controller comparison.
