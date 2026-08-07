# Step 26 — Imitation learning

## Purpose

Step 26 validates the imitation-learning machinery on deterministic synthetic engineering regimes. It does not select a historical research teacher, start reinforcement learning, open the locked historical test, or make a real-market performance claim.

The final historical teacher remains blocked by Gate C. For engineering validation, the teacher is the exact shared MPC solver validated in Steps 20 and 24, exercised through a predeclared synthetic prediction-risk input so that the optimizer exposes a non-degenerate action surface. The synthetic risk input is causal, current-state-only, and explicitly non-research.

## Teacher and state contract

The C++ executable `robust_execution_imitation_oracle` receives causal parent-order and market states and returns:

- the exact shared MPC teacher action;
- the exact `AdaptiveSignals` used by the controller;
- a solver-only latency measurement used only by the separate engineering benchmark.

The behavior-cloning feature vector contains the twelve adaptive signals plus the current synthetic engineering prediction-risk input. No future event or future learner state is used.

## Data split

Whole synthetic episodes are separated into train, validation, correction, engineering-holdout and OOD groups. Hyperparameters are selected on validation only. The correction pool is untouched unless the validation rollout triggers the predeclared covariate-shift/correction rule. Engineering-holdout and OOD episodes never contribute to fitting, scaling, hyperparameter selection, DAgger correction or fallback-threshold selection.

## Behavior cloning

The student is a compact one-hidden-layer MLP classifier. `StandardScaler` statistics are fit only on the current training set. The validation grid selects hidden width and L2 regularisation by teacher-action agreement, then log loss and deterministic parameter ordering.

The model artifact is canonical JSON containing:

- ordered feature names;
- action classes;
- scaler statistics;
- hidden/output weights and biases;
- selected hidden width and regularisation.

A fresh NumPy implementation reconstructs the policy and must reproduce probabilities exactly on a validation probe.

## Covariate shift and corrective learning

Validation is rolled out sequentially under the learner so that learner actions alter later inventory state. The C++ teacher is queried on every learner-visited state. Step 26 measures raw teacher-action agreement and standardized feature-distribution shift between teacher-state and learner-state trajectories.

If validation agreement is below the frozen floor, completion fails, or shift exceeds the frozen threshold, one DAgger-style correction round is required. Learner-visited states from the separate correction pool are labelled by the exact teacher, appended to training, and the policy is retrained with the already-selected hyperparameters. No OOD or engineering-holdout labels enter correction.

## Fallback

The fallback study uses maximum student probability and maximum absolute standardized feature deviation. The confidence threshold is selected on validation only; the feature-distance threshold is computed from training/correction data only. When either detector abstains, the engineering fixture falls back to the exact MPC teacher.

Teacher fallback is an engineering reference, not a claim that a production system should always run both policies. Step 30 must account for the latency and deployment implications of any fallback path.

## Evaluation

Teacher and student are compared on identical engineering-holdout and deliberately shifted OOD episodes for:

- action agreement;
- completion;
- invalid-action rate;
- mean implementation shortfall;
- 95th-percentile implementation shortfall;
- teacher-relative shortfall deltas;
- standardized state-distribution shift;
- abstention/fallback rate.

The separate latency benchmark measures the C++ teacher solver and NumPy batch-one student inference on the current machine. It is not a Step 30 performance claim.

## Research boundary

The engineering teacher's synthetic prediction input and 10,000-bps risk weight exist only to exercise the validated MPC action surface. They do not select a Step 21 horizon, Step 22/23 model family, Step 24 research weight, or historical strategy. Those choices remain blocked until Gate C and the frozen research protocol permit them.
