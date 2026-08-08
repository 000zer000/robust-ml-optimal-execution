# Reinforcement-learning method and evaluation

## Status and claim boundary

The reinforcement-learning analysis evaluates the complete software path in the registered
controlled simulator. Historical Gate C remains closed, so the result does not constitute a
historical-market comparison or open a locked historical test.

The controlled study uses categorical PPO over five registered development seeds, complete reward
auditing, unseen-regime transfer, and explicit baseline comparisons. The smaller seed count and
absence of zero-shot historical evaluation are reported limitations rather than historical claims.

## Engineering algorithm candidate

The implemented candidate is categorical PPO with a finite masked action space. PPO is appropriate
for this engineering contract because:

- the action space is finite and naturally represented by a categorical stochastic policy;
- the environment is interactive and non-differentiable;
- clipped policy-ratio updates constrain destructive policy changes;
- multiple optimisation epochs can reuse one on-policy rollout;
- the project explicitly requires one policy-gradient family rather than a broad algorithm sweep.

This is the registered algorithm for the controlled study; it is not presented as a universal or
historically validated execution policy.

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
`configs/rl/ppo_engineering.json`; the analysis does not conduct a final-test hyperparameter sweep.

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
engineering comparators for the RL harness; they do not replace the final adaptive-control analysis/24 controller
comparison once Gate C is open.

## OOD transfer

The OOD matrix changes liquidity, volatility, latency, fees, impact, and an instrument scale. The
same frozen policies are evaluated without fine-tuning. The fixture intentionally preserves any
performance degradation rather than tuning against the OOD set.

## Historical boundary

`historical_zero_shot_gate` rejects the current Gate-C-blocked state and separately rejects any
request to fine-tune on the locked historical test. Once the required admitted historical breadth
exists, the adapter may permit zero-shot evaluation only.
