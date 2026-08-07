# Step 24 — ML-assisted model-predictive controller

## Status

Step 24 integrates precomputed supervised predictions into the validated Step 20 MPC without creating a second optimiser. The committed evidence is a deterministic synthetic engineering fixture only. Gate C remains closed, so this step does not establish historical execution value, select a prediction horizon, select a final model family, or open the locked research test.

## Fairness architecture

`solve_non_ml_mpc` and `solve_ml_mpc` call the same internal finite-horizon search. They therefore share the planning horizon, action fractions, passive participation cap, inventory risk, terminal penalties, queue/fill proxy, action contract, latency model, and terminal-completion semantics.

The only intended ML difference is one additive passive-risk term:

`prediction_adjustment_bps = prediction_risk_weight_bps * (p - training_base_rate)`

The quote-depletion/trade-through target is not renamed or treated as exact fill probability. Centering on the training base rate gives two strong neutral controls: replacing every prediction by the base rate and setting the prediction weight to zero must reproduce the non-ML MPC action/accounting path.

## Prediction input contract

Every controller prediction records:

- exact decision ID and endpoint time;
- causal feature cutoff time;
- inference availability time;
- probability and training base rate;
- candidate horizon;
- model family and provenance;
- ablation kind;
- prior source decision ID for stale predictions.

The controller rejects wrong decision IDs, endpoint-time mismatches, feature cutoffs after the observation cutoff, predictions unavailable at decision time, invalid probabilities, missing provenance, and malformed stale-input lineage. Missing precomputed prediction endpoints fail closed rather than silently falling back.

## Engineering integration fixture

The fixture uses the first four engineering-holdout endpoints from every still-unresolved Step 23 temporal-model horizon: 250 ms, 1 s and 5 s. The validator re-reads the Step 23 model cards and compressed prediction tables and requires the C++ controller inputs to match their endpoint IDs, probabilities, training prevalence, targets and prediction-table hashes.

The controller weight of 1000 bps is deliberately labelled `synthetic_engineering_fixture_not_research_tuned`. It exists to exercise sensitivity and is not a research hyperparameter result.

## Required ablations

For every candidate horizon the fixture runs:

1. calibrated temporal-model probabilities;
2. training-base-rate probabilities;
3. probabilities shuffled within the same synthetic day/instrument slice;
4. stale probabilities with explicit previous-decision provenance;
5. uncalibrated probabilities;
6. perfect-event oracle probabilities;
7. calibrated probabilities with prediction weight set to zero.

Step 24 stores these as integration evidence. Step 25 is responsible for the substantive prediction-value-versus-decision-value analysis.

## Determinism and claim boundary

The C++ executable emits a canonical JSON payload with a SHA-256 digest. GCC Debug, Clang Debug and GCC Release produce byte-identical output. All parent orders complete under the shared Step 17 accounting path.

The calibrated predictions do not alter the tiny committed synthetic episode's action path. This is retained as a negative engineering observation, not hidden. The oracle changes decisions for at least one candidate horizon, proving that the ML term is connected to the optimiser rather than dead code.

Step 24 does not claim that the ML-MPC improves implementation shortfall, that the fixed synthetic weight is useful, that any horizon is best, or that a temporal model is preferred over a Step 22 family. Those questions remain blocked by Gate C and assigned to Steps 25, 28 and 29.
