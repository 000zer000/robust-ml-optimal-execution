# Step 29 Changelog — Rigorous Statistical Analysis

**Step:** 29 of 32  
**Status:** Engineering statistical machinery complete; historical Tier-1 activation blocked by Gate C  
**Research specification changed:** No

## Added

- `python/robust_execution/statistics/inference.py`
  - deterministic circular moving-block bootstrap;
  - frozen autocorrelation block-length selection rule;
  - paired mean/median effect estimates and confidence intervals;
  - centered dependence-aware bootstrap p-values;
  - Holm multiplicity adjustment;
  - equal-instrument historical aggregation helper;
  - Tier-1 completion/CVaR95 guardrail implementation;
  - bootstrap policy-ranking stability.
- Step 29 config and Draft 2020-12 JSON schemas.
- Deterministic engineering inference artifacts:
  - `report.json`;
  - `contrasts.csv`;
  - `ranking-stability.json`;
  - artifact manifest.
- Step 29 generator, independent validator, methodology docs and 15 tests.
- `[statistics]` optional dependency group with NumPy; the core package remains independent of it.

## Engineering findings retained

- the frozen ACF rule selects a five-pseudo-day block on the Step 28 central engineering analogue;
- 85/129 engineering contrast intervals cross zero;
- 22/43 point-estimate winners have bootstrap win probability below 0.80;
- central liquidity-aware ranking has 0.8784 bootstrap win probability;
- PPO's apparent wins in several stress cells remain ranking-unstable after block resampling;
- Holm adjustment is applied to engineering stress families without promoting Tier-3 evidence.

## Explicitly not changed

- central research question;
- Tier-1 ML-MPC minus non-ML MPC contrast;
- completion/CVaR guardrail thresholds;
- historical whole-day resampling unit;
- locked-test procedure;
- final prediction horizon/model/controller selection;
- Gate C status;
- Step 30 performance boundary.

## Integration maintenance

Prior release manifests that hash shared integration files are refreshed only for their current
shared-file hashes. Their scientific reports, model/policy artifacts and datasets are unchanged.
