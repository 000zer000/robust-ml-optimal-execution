# Step 23 temporal-model inference contract

## Required input

The temporal model accepts a float tensor shaped `[batch, 8, 20]` using the exact Step 21 feature order. A production/research caller must construct each sequence causally from one instrument, one passive side and one chronological episode/day. No future padding, centered windows, cross-day context or label-derived feature is permitted.

## Preprocessing

The committed model card contains one mean and scale per frozen feature. These statistics are fitted on training-segment timesteps only and remain unchanged when final weights are trained on train + validation.

## Output

The network emits one binary logit per sequence endpoint. The inference wrapper exposes:

- uncalibrated probability from the neural logit;
- Platt-calibrated probability using a calibrator fitted only on the calibration segment.

Step 24 must consume a versioned prediction artifact keyed to the exact causal decision endpoint. It must not recompute history with a different cutoff.

## Saved representation

`weights.json` records every named state tensor with exact shape and flattened float values. `model-card.json` records architecture, hyperparameters, scaler and calibrator. The verifier reconstructs a fresh network, loads the named tensors strictly, regenerates holdout probabilities and requires exact equality with the stored prediction table.

## Latency boundary

`results/validation/step23/inference_benchmark.json` measures Python/PyTorch batch-one inference with one CPU thread and the committed 8 x 20 sequence. It is an engineering smoke measurement only. Formal latency, throughput, compiled inference, hardware comparison, CPU scaling and GPU/CUDA decisions remain Step 30 work.

Step 24 must account for whatever model latency is actually used by the controller so that ML-assisted and non-ML MPC comparisons do not receive asymmetric causality assumptions.

## Dependency boundary

PyTorch is an optional `deep-models` dependency and is not imported from `robust_execution.prediction.__init__`. The Step 21 core prediction package therefore remains usable without the deep-learning stack. Hosted Python CI installs the exact Step 23 dependency pins and reruns the deterministic validator.
