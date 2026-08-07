# Step 24 Changelog — ML-Assisted MPC

**Step:** 24 of 32  
**Status:** Engineering complete; historical research activation blocked by Gate C  
**Research specification changed:** No

## Added

- Step 24 prediction-input and ablation types in the adaptive-controller API.
- Shared MPC solver path used by both non-ML MPC and ML-MPC.
- `MlMpcPolicy` backed by a unique precomputed prediction tape keyed by decision ID.
- Causal prediction timestamp/provenance validation and fail-closed missing-endpoint behavior.
- Centered passive-risk prediction term that does not reinterpret quote depletion as exact fill probability.
- Deterministic C++ ML-MPC demo covering all three candidate horizons and all protocol ablations.
- Prediction-tape and controller-report JSON schemas.
- Generator and independent semantic validator linked directly to Step 23 prediction artifacts.
- Dedicated C++ tests for fairness, causality, prediction sensitivity, stale provenance, missing data, duplicates and Step 8 action validity.
- Step 24 documentation, CI/bootstrap integration and repository required-file contract.

## Required ablations implemented

- training base rate;
- shuffled within day/instrument;
- stale prediction;
- uncalibrated prediction;
- perfect-event oracle;
- prediction term weight set to zero.

## Corrections made during Step 24

1. Kept the Step 21 target as quote depletion/trade-through instead of calling it fill probability.
2. Used one shared search implementation rather than duplicating the MPC and risking unfair code-path drift.
3. Centered the prediction term on training prevalence so the base-rate ablation is a genuine no-information control.
4. Required prediction availability/cutoff metadata and rejected future or misaligned inputs.
5. Made missing prediction endpoints fail closed instead of silently substituting a value.
6. Ran every candidate horizon rather than implicitly selecting one before the frozen research rule can be applied.
7. Retained the negative result that calibrated predictions do not alter the tiny engineering episode.
8. Removed every newly introduced >100-character source/test line after the repository formatting audit.

## Explicitly not changed

- central research question or hypotheses;
- frozen 250 ms / 1 s / 5 s horizon-selection rule;
- Step 20 non-ML MPC action space, constraints, queue proxy or terminal handling;
- Gate C historical-data requirement;
- Step 21 twenty-feature contract;
- Step 22/23 model-selection boundaries;
- locked historical test state.
