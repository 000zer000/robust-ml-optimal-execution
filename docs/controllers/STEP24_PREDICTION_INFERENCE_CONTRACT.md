# Step 24 prediction-to-controller inference contract

## Artifact alignment

Step 24 consumes versioned precomputed predictions keyed to the exact causal sequence endpoint. The committed `prediction-tapes.json` is generated directly from Step 23 engineering-holdout artifacts; the controller validator checks source endpoint IDs and prediction artifact SHA-256 values before accepting the fixture.

A research run must never reconstruct the Step 23 temporal sequence with a different cutoff inside the controller. Feature construction and model inference happen upstream; the controller receives only an audited prediction record.

## Causality checks

For a decision at time `t`:

- prediction `decision_id` must equal the policy observation decision ID;
- prediction endpoint time must equal `t`;
- feature cutoff must be no later than `observation_cutoff`;
- prediction availability must be no later than `t`;
- all timestamps must share the observation clock domain.

A stale ablation is the only input allowed to declare a different source-prediction decision ID, and that source ID must be strictly earlier than the current decision.

## Latency boundary

The engineering fixture uses already-available precomputed probabilities and therefore does not make a production inference-latency claim. The schema nevertheless records availability time explicitly so that future historical/synthetic experiments can inject measured feature, inference and optimiser latency causally as required by the research protocol.

Formal compiled inference, CPU/GPU comparison and end-to-end compute-latency injection remain Step 30 responsibilities.

## Fail-closed policy

`MlMpcPolicy` requires a unique prediction for every active decision endpoint. Duplicate prediction decision IDs are rejected at construction. A missing active endpoint raises an error; it is not replaced by a base rate, zero signal or last observation unless that behavior is an explicit registered ablation.

## Neutral controls

The following must match the non-ML MPC in action path and accounting under the same fixture:

- training-base-rate predictions with nonzero prediction weight;
- any valid prediction tape with prediction weight equal to zero.

These controls protect the claim that differences between non-ML MPC and ML-MPC come only from the prediction-derived term.
