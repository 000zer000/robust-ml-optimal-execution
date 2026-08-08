# Step 28 Changelog — Complete Robustness Matrix

**Step:** 28 of 32  
**Status:** Engineering robustness matrix complete; historical activation and Gate I remain blocked  
**Research specification changed:** No

## Added

- `python/robust_execution/robustness/matrix.py`
  - 43 paired interactive synthetic stress cases;
  - common 24-episode seed schedule per comparable cell;
  - five-seed PPO aggregate plus immediate, TWAP-like and liquidity-aware baselines;
  - rank-switch and worst-degradation summaries;
  - inherited Step 25 prediction-degradation panel;
  - inherited Step 16 queue-assumption evidence;
  - machine-specific compute-budget feasibility panel;
  - explicit blocked historical cells and Step 29/30 boundaries.
- Step 28 configuration and JSON schemas.
- Deterministic report, CSV stress table, ranking-stability artifact and manifest.
- Step 28 generator, independent validator and Python tests.
- Robustness methodology and claim-boundary documentation.

## Backward-compatible Step 27 environment extensions

The Step 27 synthetic environment now accepts optional `market_time_scale` and `impact_exponent`
arguments for Step 28 horizon and functional-form stresses. Defaults preserve the original Step 27
arithmetic path exactly; the committed Step 27 scientific report and policy artifacts are unchanged.

## Main engineering findings retained

- central ranking: liquidity-aware > PPO aggregate > TWAP-like > immediate;
- strategy ranking changes in 16 of 42 non-central interactive cases;
- liquidity-aware wins 35/43 cells, PPO aggregate 5/43, TWAP-like 3/43;
- no immediate-execution win in the engineering matrix;
- PPO is particularly weak under the registered volatility-shock case;
- PPO wins selected small-size, short-horizon, instrument-scale and simulator-mismatch cells;
- existing prediction-quality/decision-value divergence from Step 25 remains visible;
- compute feasibility results remain machine-specific and are not Step 30 performance claims.

## Explicitly not changed

- frozen research question or hypotheses;
- Gate C status;
- historical queue central calibration;
- final prediction horizon/model/weight;
- final RL algorithm or seed count;
- locked historical test status;
- formal statistical inference or multiplicity policy;
- formal CPU/GPU/CUDA performance conclusions.
