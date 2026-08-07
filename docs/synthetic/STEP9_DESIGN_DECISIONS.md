# Step 9 design decisions

## Accepted implementation decisions

### S9-D01 — Designed synthetic and adversarial evidence are distinct

Every regime, shock and scenario carries an evidence class. Step 9 never labels a parameter set
"calibrated" because no historical data calibration has occurred.

### S9-D02 — Discrete self-exciting Bernoulli grid

The first generator uses integer per-step probabilities and bounded excitation. This is reproducible,
inspectable and calibration-ready. It is not described as a Hawkes process estimate.

### S9-D03 — Exact book mechanics remain authoritative

The generator submits orders to the Step 6 matching engine rather than maintaining a separate
approximate book. This prevents divergence between synthetic generation and exchange semantics.

### S9-D04 — Counter-addressed randomness

Each event category has a stable stream ID and uses the global grid step as its logical index. Adding
a diagnostic draw to one process cannot shift all later random outcomes.

### S9-D05 — Impact is explicit and transient

Aggressive filled quantity updates an integer microtick impact state. The state decays each step and
influences the placement reference for future liquidity. This is a modelling assumption exposed in
configuration, not a causal estimate.

### S9-D06 — Resilience is deficit-sensitive

Passive arrival probability increases when visible depth is below the regime target. Replenishment
still occurs through valid post-only orders and remains subject to exchange rules.

### S9-D07 — Shocks are half-open and composable

Shock intervals are `[start, start + duration)`. Active multipliers compose deterministically and are
bounded. One-time price jumps occur only at the start step.

### S9-D08 — Exact fee atoms

Maker rebates and taker fees are integer quote atoms per lot. The output records both sides of every
match and validates aggregate accounting independently.

### S9-D09 — One-sided books are permitted in adversarial stress

A severe liquidity-vacuum scenario may temporarily remove all visible liquidity from one side. This
is retained as an explicit stress outcome rather than silently repaired. Policies must handle missing
best quotes safely in later steps.

### S9-D10 — No early venue semantics

The generator remains venue-neutral. Step 11 will select and verify public data sources and adapters.
No current synthetic parameter is presented as a Coinbase, equity or futures rule.

## Deferred—not removed

- historical parameter estimation;
- goodness-of-fit testing against real event streams;
- richer marked point-process alternatives;
- cross-asset or cross-venue coupling;
- hidden-liquidity models;
- simulator mismatch experiments;
- policy training and evaluation.

These remain in the full project and enter at their approved roadmap stages.
