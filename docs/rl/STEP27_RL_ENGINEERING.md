# Step 27 — Reinforcement-learning engineering gate

## Status and claim boundary

Step 27 validates the reinforcement-learning software path while historical Gate C remains closed.
The committed result is therefore `synthetic_validation_only_non_research`; it is not the final RL
research comparison and it does not open the locked historical test.

The frozen protocol requires one policy-gradient algorithm, at least five development seeds, at
least ten final research seeds, complete reward auditing, unseen-regime transfer, and zero-shot
historical evaluation. This engineering gate implements all machinery that can be validated before
Gate C, but deliberately leaves the final algorithm field and final seed count unresolved because
`DECISIONS.md` is part of the seven-file specification lock.

## Engineering algorithm candidate

The implemented candidate is categorical PPO with a finite masked action space. PPO is appropriate
for this engineering contract because:

- the action space is finite and naturally represented by a categorical stochastic policy;
- the environment is interactive and non-differentiable;
- clipped policy-ratio updates constrain destructive policy changes;
- multiple optimisation epochs can reuse one on-policy rollout;
- the project explicitly requires one policy-gradient family rather than a broad algorithm sweep.

This is an engineering candidate, not a frozen final research-field resolution. Freezing the
`reinforcement_learning_algorithm` pre-data field requires a later explicit specification-lock
resolution before the real RL experiment.

## Environment

The versioned engineering MDP uses one buy parent order and twelve decision points. State features
are causal and contain only information available at the decision:

1. remaining inventory fraction;
2. time remaining fraction;
3. scaled spread;
4. depth ratio;
5. book imbalance;
6. volatility scale;
7. latency scale;
8. fee scale;
9. impact scale;
10. recent fill fraction;
11. adverse-momentum proxy.

The finite action set is:

- wait;
- passive 25%;
- passive 50%;
- aggressive 25%;
- aggressive 50%;
- aggressive 100%.

Passive/no-op actions are masked at the final decision. If a policy nevertheless submits an invalid
index or masked action through a lower-level call, the environment fails closed or applies the
registered invalid-action penalty. Residual inventory is forcibly completed at the horizon.

The fixture contains interactive temporary impact: aggressive fills alter the next reference state.
Market randomness is seeded and future random draws are not part of the observation contract.

## PPO implementation

The policy/value network has two 32-unit tanh hidden layers. The configuration is fixed in
`configs/rl/step27_ppo_engineering.json`; Step 27 does not conduct a hyperparameter sweep.

The implementation uses:

- categorical masked policy;
- generalised advantage estimation;
- clipped PPO objective;
- value regression;
- entropy regularisation;
- gradient-norm clipping;
- deterministic CPU seeds;
- persistent Adam optimiser state within a seed.

Five independent development seeds are trained and every registered seed is reported. There is no
best-seed selection.

## Baselines

The engineering comparison includes immediate aggressive execution, a TWAP-like urgency policy, a
liquidity-aware adaptive heuristic, a random policy, and a wait/no-op sanity policy. These are
engineering comparators for the RL harness; they do not replace the final Step 20/24 controller
comparison once Gate C is open.

## OOD transfer

The OOD matrix changes liquidity, volatility, latency, fees, impact, and an instrument scale. The
same frozen policies are evaluated without fine-tuning. The fixture intentionally preserves any
performance degradation rather than tuning against the OOD set.

## Historical boundary

`historical_zero_shot_gate` rejects the current Gate-C-blocked state and separately rejects any
request to fine-tune on the locked historical test. Once the required admitted historical breadth
exists, the adapter may permit zero-shot evaluation only.
