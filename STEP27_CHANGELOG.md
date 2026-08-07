# Step 27 Changelog — Reinforcement Learning

**Step:** 27 of 32  
**Status:** Engineering implementation complete; final research RL activation blocked by Gate C  
**Research specification changed:** No

## Added

- categorical PPO engineering implementation with masked finite actions and GAE;
- interactive synthetic execution MDP with fees, latency, impact, inventory risk and forced completion;
- five preregistered development seeds with no best-seed selection;
- immediate, TWAP-like, liquidity-aware, random and no-op engineering baselines;
- ID/OOD evaluation over liquidity, volatility, latency, fees, impact and instrument-scale shifts;
- raw-transition reward decomposition and independent economic reconstruction;
- action-mask, residual-inventory, terminal-completion, future-observation and pathological-policy tests;
- canonical JSON policy artifacts for every seed and deterministic rerun verification;
- historical zero-shot gate that blocks Gate C and prohibits locked-test fine-tuning;
- machine-specific batch-one policy inference benchmark;
- Step 27 config, JSON schemas, generator, validator, tests and methodology documents;
- predecessor Step 25/26 release-manifest shared integration hashes refreshed after the Step 27
  Makefile/README/repository-contract additions; predecessor scientific artifacts were unchanged.

## Explicitly not changed

- the seven frozen specification files;
- the final `reinforcement_learning_algorithm` pre-data field;
- final RL seed count;
- selected prediction horizon/model family/controller weight;
- Gate C status;
- locked historical test state.

## Negative results retained

The engineering PPO policies are not presented as universally superior. The liquidity-aware baseline
has lower mean ID cost than the five-seed PPO aggregate, while the TWAP-like baseline has lower OOD
mean and CVaR95 cost. PPO also degrades materially from ID to OOD. No best seed is promoted.
