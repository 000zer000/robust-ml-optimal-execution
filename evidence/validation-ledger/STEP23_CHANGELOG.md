# Step 23 Changelog — Compact Causal Temporal Deep Model

**Step:** 23 of 32  
**Status:** Engineering complete; historical research activation remains blocked by Gate C  
**Research specification changed:** No  
**Repository version:** 0.14.0

## Added

- `python/robust_execution/prediction/temporal_models.py`
  - strict Step 23 configuration contract;
  - deterministic temporal sequence builder over the frozen twenty Step 21 features;
  - compact left-causal Conv1D -> GELU -> LSTM -> logit architecture;
  - validation-only within-family hyperparameter/epoch selection;
  - training-only feature scaling retained during train+validation refit;
  - calibration-only Platt scaling;
  - probability metrics, reliability and instrument/side/temporal slices;
  - fixed engineering decision proxy;
  - deterministic feature-stress and temporal-order OOD/ablation diagnostics;
  - canonical JSON network-weight representation and strict reconstruction;
  - batch-one inference timing helper.
- `python/robust_execution/prediction/temporal_model_artifacts.py`
  - immutable Step 23 source-row, sequence, model, prediction and diagnostic artifacts;
  - SHA-256 manifest and semantic prediction verification;
  - deterministic clean-rerun contract.
- Step 23 model config, two JSON schemas, generator, validator, benchmark, tests and methodology/inference docs.
- Optional `deep-models` dependency group pinned to PyTorch 2.10.0 plus the Step 22 NumPy/scikit-learn pins.
- Hosted Python CI execution of the Step 23 validator and temporal-model tests.

## Architecture decision

Exactly one serious temporal family is implemented: a compact causal Conv1D-LSTM. DeepLOB supports convolution plus recurrent temporal modelling, while Sirignano–Cont and Kolm–Turiel–Westray support exploiting order-flow history. The project input is the frozen engineered-feature vector rather than raw multi-level book tensors, so a literal DeepLOB copy would impose unsupported spatial semantics. A Transformer and additional deep families were deliberately not added.

## Corrections made during Step 23

1. Kept every temporal window inside one day/instrument/passive-side group and added mutation tests proving future rows cannot alter earlier windows.
2. Retained the training-only scaler when final neural weights are refit on train+validation.
3. Separated validation hyperparameter/epoch selection from calibration and engineering-holdout evaluation.
4. Stored named neural tensors in deterministic JSON and verified predictions after strict network reconstruction.
5. Marked feature-stress and temporal-reversal outputs as engineering perturbations rather than generalisation evidence.
6. Added a fixed decision proxy only as a diagnostic and prohibited it from model/horizon selection; true controller value remains Step 24.
7. Kept PyTorch optional so importing the Step 21 core prediction package does not acquire a hidden deep-learning dependency.
8. Corrected CI dependency installation so the existing Step 22 validator has NumPy/scikit-learn available and the Python matrix has the exact Step 23 PyTorch pin.
9. Extended the local validation script through Steps 18–23 rather than leaving it stale at Step 17.
10. Wrapped all Step 23 Python/test/script lines to the configured 100-character Ruff limit after the local Ruff executable proved unavailable.
11. Preserved a truthful validation boundary when the local execution harness could not complete the sequential combined coverage wrapper; the full raw suite and both coverage components were rerun independently instead of claiming a combined-green wrapper.

## Explicitly not changed

- central research question or hypotheses;
- candidate horizons (250 ms, 1 s, 5 s);
- selected-horizon placeholder;
- frozen twenty-feature Step 21 contract;
- 50/20/10/20 chronological research split analogue;
- Gate C historical-data requirement;
- Step 20 non-ML MPC comparator;
- Step 24 controller-integration contract;
- locked final historical test.
