# Step 23 — Compact causal temporal deep model

## Status and boundary

Step 23 implements exactly one serious temporal neural architecture for the supervised prediction layer: a compact causal Conv1D -> LSTM binary classifier. The committed dataset is a deterministic synthetic engineering fixture. It does not establish real-market predictive skill, select the final 250 ms / 1 s / 5 s research horizon, select a final model family, open the locked historical test, or integrate the Step 24 ML-assisted MPC.

Gate C remains the blocker for historical research activation.

## Why this architecture

The literature review already records three relevant observations:

- DeepLOB (Zhang, Zohren, Roberts) combines convolutional feature extraction with recurrent temporal modelling for limit-order-book prediction.
- Sirignano and Cont report that including order-flow history improves out-of-sample forecasting and provides evidence of path dependence.
- Kolm, Turiel and Westray show that LSTM-style models on stationary/order-flow-derived representations can be competitive with models consuming raw book tensors.

The project, however, has a frozen Step 21 input contract of twenty engineered causal features rather than raw multi-level book tensors. Reproducing DeepLOB literally would therefore impose an unsupported spatial geometry. Step 23 keeps the defensible part of the idea: a small causal convolution over local time followed by an LSTM over the feature history.

A Transformer is deliberately not added. The fixture is small, the sequence length is eight, and Step 23 requires one justified temporal family rather than an architecture sweep.

## Input contract

Each model consumes an 8 x 20 sequence:

- eight contiguous decision rows;
- exact frozen Step 21 feature order;
- one instrument;
- one passive side;
- one synthetic whole day;
- no sequence may cross a day, instrument or side boundary.

The target is attached only to the final decision row in the sequence. Labels remain the three nested quote-depletion/trade-through candidates: 250 ms, 1 s and 5 s.

## Chronological engineering fixture

The fixture uses 100 whole synthetic days, BTCUSDT and ETHUSDT, both passive sides, and 12 decision rows per symbol/side/day.

This yields:

- 4,800 causal source rows;
- sequence length 8;
- stride 1;
- 2,000 sequences total;
- 1,000 training sequences;
- 400 validation sequences;
- 200 calibration sequences;
- 400 engineering-holdout sequences.

The split unit is always a complete synthetic day. No sequence is allowed to bridge split boundaries.

## Leakage and selection protocol

The protocol is deliberately stricter than an ordinary ML demo:

1. Feature scaling statistics are fit on training-segment timesteps only.
2. Candidate neural hyperparameters are compared only on validation log loss, then Brier score, then deterministic parameter ordering.
3. Validation early stopping determines the selected epoch for each candidate.
4. After hyperparameters/epoch are frozen, weights are refit on train + validation while retaining the frozen training-only scaler.
5. Platt calibration is fit only on the calibration segment.
6. Engineering-holdout labels are never passed into architecture/hyperparameter selection.
7. The fixed engineering decision proxy is diagnostic only and is explicitly prohibited from model or horizon selection.
8. The locked historical test remains unopened.

Mutation tests verify that altering a source row after an earlier sequence endpoint cannot change that sequence, while altering a row inside causal history does change it. Calibration-label mutation changes calibrated probabilities but leaves raw network predictions unchanged.

## Architecture

The model is intentionally small:

```text
8 x 20 causal feature history
        |
left-padded causal Conv1D (kernel 3)
        |
GELU
        |
LSTM over all 8 time steps
        |
last recurrent state
        |
linear logit head
        |
uncalibrated depletion probability
        |
Platt calibrator fitted on calibration days only
```

The two validation candidates differ only in width (8/8 versus 12/12 convolution/LSTM channels). This is within-family tuning, not an architecture search.

Training uses deterministic CPU execution, AdamW, gradient clipping, fixed chronological batch order, and no dropout. The model contains only about 1k–2k trainable parameters in the engineering configuration.

## Calibration and diagnostics

For each candidate horizon the committed artifacts include:

- uncalibrated and calibrated log loss;
- Brier score;
- ECE;
- calibration intercept/slope;
- ROC-AUC and PR-AUC;
- fixed-threshold precision/recall;
- reliability bins;
- BTCUSDT / ETHUSDT slices;
- bid / ask slices;
- first / second half temporal slices.

A calibration transform is not assumed to improve every finite synthetic holdout metric. Any deterioration is retained rather than hidden.

## Engineering decision proxy

Step 23 records a deliberately simple fixed diagnostic to detect whether probability differences can alter a downstream choice before Step 24 integration:

- aggressive action cost = 0.35 synthetic units;
- passive depletion cost = 1.0 synthetic unit;
- choose aggressive when predicted depletion probability is at least 0.35;
- compare realised proxy cost with a training-base-rate predictor and a perfect-label oracle.

This proxy is not the MPC objective, is not an execution-performance claim, and cannot select a model or horizon. Real prediction-to-controller value begins in Step 24.

## OOD / temporal diagnostics

Two deterministic perturbations are recorded on the engineering holdout:

1. **Feature stress:** wider spread, thinner same-side depth, heavier opposite-side depth, and older quote/trade ages.
2. **Temporal-order ablation:** reverse the feature history while keeping the endpoint target fixed.

These tests measure prediction sensitivity and pipeline behaviour only. Because the labels are retained from the original synthetic fixture, they are explicitly marked as engineering perturbations rather than a generalisation claim.

## Artifact and reproducibility contract

Network parameters are stored as canonical JSON arrays rather than pickle or opaque framework checkpoints. This gives the verifier an explicit shape/name contract and lets it reconstruct the network before comparing semantic predictions.

The committed manifest hashes:

- config and split metadata;
- source-row and sequence tables;
- model cards;
- deterministic weights;
- prediction tables;
- reliability/slice/OOD/decision-proxy artifacts;
- aggregate report.

A clean rerun must reproduce all semantic artifact hashes and the aggregate report byte-for-byte under the pinned environment.

## What Step 23 does not claim

Step 23 does not claim:

- DeepLOB has been reproduced;
- the compact Conv1D-LSTM beats Step 22 models on real data;
- any candidate horizon is the correct research horizon;
- synthetic metrics estimate Binance performance;
- OOD stress proves cross-regime generalisation;
- the fixed decision proxy is controller execution value;
- the measured Python/PyTorch latency is production latency;
- GPU/CUDA would help.

Those claims remain assigned to Gates C/E/F and Steps 24, 25, 28–30.
