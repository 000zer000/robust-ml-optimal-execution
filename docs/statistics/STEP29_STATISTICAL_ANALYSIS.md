# Step 29 — Rigorous statistical analysis

## Status and boundary

Step 29 implements the frozen statistical machinery but does **not** open the locked historical
Tier-1 test. Gate C has no admitted historical research dataset, so the committed numerical
inference is a synthetic engineering validation of the method only.

The frozen Tier-1 estimand remains ML-assisted MPC minus the same non-ML MPC on paired locked-test
execution episodes. No result in this step substitutes PPO, TWAP, or the liquidity-aware heuristic
for that confirmatory contrast.

## Engineering analogue

The Step 28 matrix supplies 24 ordered paired synthetic episode seeds per stress cell. For software
and method validation only, each ordered seed is treated as a pseudo-day. The central
`ppo_aggregate - liquidity_aware` paired difference selects the moving-block length using the
frozen autocorrelation rule. The selected engineering block length is five pseudo-days because
absolute autocorrelation is below 0.1 at lags five and six.

The analysis uses 4,096 circular moving-block bootstrap repetitions. Every resample keeps the same
indices for both policies, so the paired-market-path contract is preserved.

Published JSON and CSV floating-point values use 12 significant digits. This is far finer than any
registered decision threshold while removing final-bit differences between supported CPU/NumPy
kernels; the statistical calculations themselves still run in float64 before serialization.

## Effect estimates

Each engineering contrast records:

- paired mean and median cost difference in basis points;
- 95% moving-block bootstrap intervals for mean and median;
- relative change versus the comparator;
- paired standardized effect size;
- a centered block-bootstrap two-sided p-value;
- a non-overlapping block sensitivity interval.

Lower execution cost is better, so a negative policy-minus-comparator difference favours the policy.

## Multiplicity

The Step 28 stress analysis is Tier-3 exploratory evidence. Holm adjustment is nevertheless applied
within each challenger-by-stress-dimension family as a conservative engineering check. These
adjusted values do not convert the synthetic matrix into confirmatory evidence.

## Ranking stability

Within each stress cell, all four competitive policy families are resampled with exactly the same
moving-block indices. The report stores the probability that each policy has the lowest bootstrap
mean cost. A point-estimate winner is labelled stable only when its bootstrap win probability is at
least 0.80. The threshold is descriptive, not a frozen significance test.

## Historical readiness

The code also implements the frozen equal-instrument aggregation rule and Tier-1 completion/CVaR
bootstrap guardrail formulas. Those functions are unit-tested but deliberately not evaluated on the
engineering matrix as if it were historical evidence.

When Gate C eventually opens, the historical path must:

1. aggregate paired episode differences within instrument, side, size and whole day;
2. equal-weight required instruments;
3. select and freeze block length on validation days only;
4. retain every episode in resampled day blocks;
5. run the preregistered Tier-1 contrast unadjusted;
6. apply Holm within each Tier-2 family;
7. evaluate completion and CVaR95 guardrails with the same day-block resamples;
8. preserve failed runs and paired missingness analysis;
9. open the locked test once under the frozen configuration.

IID resampling of individual historical episodes is prohibited for primary inference.
