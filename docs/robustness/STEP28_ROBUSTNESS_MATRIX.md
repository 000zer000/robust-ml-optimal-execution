# Step 28 — Complete robustness matrix

## Status and purpose

Step 28 generates the complete **registered engineering robustness matrix** required before the
formal Step 29 statistical analysis. Gate C remains closed, so the result is explicitly
`synthetic_validation_only_non_research`: no historical robustness claim is made and the locked
historical test is not opened.

The matrix deliberately separates three evidence classes:

1. interactive synthetic execution stresses evaluated on paired episode seeds;
2. prediction/controller degradation evidence inherited from Step 25 and independently hashed;
3. historical-required cells that remain blocked until admitted real-market days exist.

## Interactive policy panel

The common interactive environment evaluates the same competitive policies in every supported cell:

- immediate execution;
- TWAP-like schedule;
- liquidity-aware heuristic;
- all five frozen Step 27 PPO engineering policies, with PPO reported as an equal-seed aggregate.

Random and wait/no-op agents remain Step 27 sanity controls and are not promoted into the competitive
ranking.

Every interactive cell uses the same 24 deterministic episode seeds for every policy. Step 28 stores
mean, median, p95, CVaR95, completion, invalid-action rate, action counts, and episode-level costs.
Formal confidence intervals, dependence-aware resampling, and multiplicity correction remain Step 29.

## Registered dimensions

The engineering matrix covers latency multipliers, decision-grid opportunity count, liquidity,
spread, volatility, queue/fill assumptions, fees/rebates, parent size, horizon-time proxies, impact
coefficient and functional-form misspecification, dropped/delayed observations, temporal and
instrument-scale shifts, unseen combined regimes, and joint simulator mismatch.

The exact research values in `RESEARCH_PROTOCOL.md` remain authoritative. Where the Step 27
engineering MDP has no calibrated millisecond or second mapping, Step 28 labels values as proxies
rather than silently relabelling normalized simulator steps as physical time.

## Prediction and queue panels

Prediction robustness reuses the exact Step 25 calibrated, uncalibrated, stale, constant/base-rate,
and shuffled artifacts. Their committed report hash is verified before inclusion. The perfect event
oracle remains an upper bound rather than a degradation setting.

Queue robustness has two layers: Step 16 already validates optimistic, central, and pessimistic
aggregate-L2 assumptions against exact synthetic FIFO worlds; Step 28 additionally perturbs passive
fill assumptions inside the interactive execution MDP. Neither layer claims exact historical FIFO.

## Main engineering finding

The central engineering ranking is:

1. liquidity-aware heuristic;
2. five-seed PPO aggregate;
3. TWAP-like;
4. immediate execution.

Across the complete interactive matrix, rankings switch repeatedly. The heuristic wins most cells,
PPO wins a smaller subset, and TWAP-like wins several coarse-grid/narrow-spread/pessimistic-queue
cells. Volatility and combined distribution shocks can materially worsen PPO relative to simple
baselines. This is a negative-result-preserving engineering observation, not a confirmatory result.

## Compute boundary

Existing machine-specific p95 inference measurements from Steps 23, 26, and 27 are checked against a
registered budget grid. This is a feasibility diagnostic only. Formal profiling, compiled inference,
CPU/GPU comparison, latency injection from measured production paths, and any CUDA decision remain
Step 30.

## Gate boundary

Step 28 completes the engineering stress-matrix generation requirement. **Gate I does not pass yet.**
Step 29 must apply the frozen dependence-aware statistical protocol, and historical cells cannot be
activated until Gate C admits real data.
