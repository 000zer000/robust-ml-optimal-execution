# Step 23 Validation — Compact Causal Temporal Deep Model

**Decision:** PASS for engineering/model-pipeline validation.  
**Research-result status:** `synthetic_validation_only_non_research`.  
**Historical research activation:** BLOCKED until Gate C admits real market-data days.  
**Research specification changed:** No; the frozen specification lock remains authoritative.

## 1. Scope validated

Step 23 implements exactly one temporal deep family, a compact causal Conv1D-LSTM, over the exact twenty causal Step 21 features and all three candidate depletion horizons. It does not select a research horizon or final model family and does not integrate the Step 24 ML-assisted MPC.

## 2. Chronological engineering fixture

The deterministic fixture contains 4,800 source rows over 100 synthetic whole days, BTCUSDT/ETHUSDT and both passive sides. Twelve decisions per symbol/side/day form length-8 stride-1 windows:

| Segment | Source days | Temporal sequences | Permitted use |
|---|---:|---:|---|
| Train | 50 | 1,000 | scaler fit and neural training |
| Validation | 20 | 400 | hyperparameter and epoch selection only |
| Calibration | 10 | 200 | Platt calibration only |
| Engineering holdout | 20 | 400 | engineering evaluation only |

Total: **2,000 temporal sequences**. No sequence crosses a day, instrument, passive side or chronological split boundary.

## 3. Leakage and mutation controls

Validated properties:

- feature ordering is exactly the frozen Step 21 dictionary;
- sequence windows contain only causal rows ending at the target decision row;
- mutating a future source row cannot alter an earlier temporal input;
- mutating a causal-past row inside a window changes the input;
- scaling statistics are fit only on training timesteps;
- within-family hyperparameters and stopping epoch are selected only on validation metrics;
- final neural weights may use train+validation only after configuration is frozen;
- calibration labels affect only the Platt calibrator, not raw neural predictions;
- engineering holdout labels and the decision proxy cannot select hyperparameters/horizon;
- the locked research test is unopened.

## 4. Architecture and deterministic artifacts

The committed family is `causal_conv1d_lstm`:

1. left-padded causal 1-D convolution (kernel 3);
2. GELU activation;
3. single LSTM over the full eight-step history;
4. one linear logit head.

Two width candidates (8/8 and 12/12 channels/hidden units) are validation-tuned within this single family. The selected engineering models contain 1,073–1,993 trainable parameters.

Weights are stored as named canonical JSON tensors. A fresh network is reconstructed from the model card + tensor file and its calibrated engineering-holdout probabilities must equal the committed prediction table exactly. A clean full rerun reproduces all manifest artifact hashes and the aggregate report byte-for-byte.

## 5. Calibration, decision-proxy and OOD diagnostics

Synthetic engineering metrics are test oracles, not research results. The committed fixture intentionally retains both positive and negative findings:

| Horizon | Params | Selected epoch | Raw log loss | Calibrated log loss | Raw Brier | Calibrated Brier |
|---|---:|---:|---:|---:|---:|---:|
| 250 ms | 1,993 | 3 | 0.14425 | 0.16179 | 0.03150 | 0.03362 |
| 1 s | 1,073 | 4 | 0.47376 | 0.47803 | 0.14965 | 0.15099 |
| 5 s | 1,993 | 5 | 0.66752 | 0.64009 | 0.23105 | 0.22444 |

Calibration therefore helps the 5 s fixture metric but slightly worsens the 250 ms and 1 s finite synthetic holdouts; this is retained rather than hidden.

The fixed engineering decision proxy produces no improvement over the training base rate at 250 ms or 1 s and is slightly worse at 5 s. This negative result is also retained. It is not the Step 24 MPC value and was not used for selection.

Deterministic feature-stress and temporal-history reversal produce non-zero probability shifts at all horizons. These are pipeline sensitivity checks only, explicitly not OOD generalisation claims.

## 6. Inference engineering smoke measurement

`results/validation/step23/inference_benchmark.json` records single-sequence, one-thread Python/PyTorch inference on the current machine. The observed p50 values are roughly **0.23 ms** for all three tiny models. This is labelled `engineering_machine_specific_not_step30_performance_claim`; compiled inference, hardware comparisons, batching, CPU/GPU scaling and CUDA remain Step 30 work.

## 7. Executed validation

### Python and Step 23 artifacts

- dedicated Step 23 temporal suite: **15/15 passed**;
- full Python suite without coverage instrumentation: **378/378 passed**;
- branch-aware coverage, combined from separately completed base and temporal coverage runs: **90.31%** (repository minimum: 90%);
- covered statements/lines: **5,029 / 5,420**;
- covered branches: **1,614 / 1,936**;
- independent Step 23 artifact validator: **passed**;
- Python `compileall`: **passed**;
- Step 23 source/test/script lines over the configured 100-character limit after manual formatting: **0**.

The local execution harness repeatedly terminated a single sequential `make test-python` coverage invocation during interpreter shutdown when both the existing scikit-learn suite and PyTorch suite were instrumented in the same shell. No combined-green claim is made for that wrapper. Both coverage components completed independently on the identical source state and their coverage data combined successfully above the 90% gate. The ordinary complete `pytest` run is green. Hosted CI remains configured to exercise the full repository.

### Native regression

Step 23 changes no C++ behaviour, but all native suites were rerun:

- GCC Debug: **51/51 passed**;
- Clang Debug: **51/51 passed**;
- GCC Release: **51/51 passed**;
- ASan + UBSan: **51/51 passed**, no findings.

### Packaging and integration

- frozen research specification: **7/7 hashes matched**;
- repository contract: **409 required files passed**;
- Step 23 JSON schema/config files: parsed successfully;
- workflow YAML: parsed successfully;
- clean Release CMake install: **passed**;
- external `find_package(robust_execution 0.14 CONFIG)` consumer: **passed**;
- core prediction package imported with PyTorch deliberately blocked: **passed**, confirming the deep dependency remains optional.

### Local tool limitations

- Ruff and mypy executables are not installed in this runtime, so no fresh local Ruff/mypy pass is claimed.
- The Step 23 files were manually audited against the configured 100-character limit and Python compilation passed.
- TSan retains the previously documented local toolchain limitation and is not newly claimed here.

## 8. Scientific boundary and next milestone

**Step 23 engineering gate: PASS.**

Still unresolved by design:

- real Binance predictive skill;
- final 250 ms / 1 s / 5 s horizon selection;
- final simple-versus-temporal model-family selection;
- controller-level execution decision value;
- any claim that ML beats the validated non-ML MPC;
- formal production inference performance.

The exact next milestone is **Step 24 — ML-assisted MPC**, which integrates calibrated predictions into the same controller contract and isolates predictive input from all other controller differences.
