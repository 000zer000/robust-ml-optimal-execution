# Synthetic Market Generator — Step 9

## Status

Step 9 implements a deterministic, configuration-driven synthetic limit-order-book environment.
It is **not historically calibrated yet**. Its outputs are designed synthetic evidence or deliberately
adversarial stress evidence, never historical evidence.

The generator uses the real Step 6 price-time-priority matching engine. Limit additions,
aggressive orders, cancellations, partial fills, queue depletion, trades, maker/taker roles and
book invariants therefore follow the same exact synthetic exchange mechanics used elsewhere in the
repository.

## Model structure

### Time and randomness

- Time advances on an integer nanosecond grid.
- Every stochastic decision is addressed by `(seed, stream_id, global_step)` through the Step 7
  Philox counter-based generator.
- No mutable random stream is consumed conditionally.
- Probabilities and multipliers are integer parts-per-million values.
- Identical source and configuration must generate byte-identical tapes across supported compilers.

### Order-flow processes

At each grid step the generator evaluates four marked processes:

1. passive limit-order addition;
2. aggressive IOC market-order submission;
3. cancellation of a live synthetic order;
4. exogenous reference-price movement.

The occurrence model is a discrete self-exciting Bernoulli grid. Each event class has:

- a base per-step probability;
- an excitation increment following an occurrence;
- deterministic excitation decay;
- an excitation cap.

This creates controllable clustering without claiming that the current parameters estimate a Hawkes
process or any venue's true arrival law.

### Liquidity and resilience

Each regime specifies:

- half spread;
- visible levels per side;
- target lots per level;
- order-size range;
- passive-add probability;
- resilience boost cap.

When visible depth is below the regime target, the passive-add probability receives a bounded
resilience boost. Replenishment is generated as actual post-only orders; it is not inserted directly
into a summary book.

### Reference price and impact

The reported synthetic reference price has two components:

```text
reference ticks = fundamental ticks + transient impact microticks / 1,000,000
```

The fundamental component follows bounded, discrete exogenous moves. The transient component changes
only after actual aggressive fills and decays each grid step. `impact_microticks_per_lot` and
`impact_decay_ppm` are explicit synthetic assumptions. They are not empirical market-impact estimates.

### Fees

Each generated match records:

- maker quantity and maker fee;
- taker quantity and taker fee;
- fee-schedule identifier;
- exact integer quote atoms.

Negative maker fees are permitted to represent rebates. Fee arithmetic is checked for overflow.

## Regimes and shocks

A scenario contains one or more sequential regimes. A shock is active on the half-open interval
`[start_step, start_step + duration_steps)` and can alter:

- liquidity target;
- spread;
- reference-move probability;
- aggressive-flow probability;
- cancellation probability;
- directional buy probability;
- a one-time reference-price jump.

Shock effects are multiplicative in integer ppm units and bounded to 10x per aggregate runtime
multiplier. A scenario containing an adversarial regime or adversarial shock must be classified
`adversarial_stress`.

The repository ships two contracts:

- `configs/stress_tests/synthetic_normal.json`;
- `configs/stress_tests/synthetic_adversarial_liquidity_vacuum.json`.

These are examples and test fixtures, not final research calibration.

## Outputs

`SyntheticMarketGenerator::generate()` returns a `SyntheticTape` containing:

- the complete configuration and its SHA-256;
- every generated action with causal sequence, step and time;
- every exact trade and fee record;
- per-step reference price, visible depth, best quotes and excitation state;
- aggregate counts and accounting;
- canonical deterministic text;
- tape SHA-256;
- a machine-readable manifest and manifest SHA-256.

The manifest explicitly contains:

```json
"calibration_status": "not_calibrated_step9"
```

The committed sample can be regenerated with:

```bash
cmake --preset gcc-debug
cmake --build --preset gcc-debug
./build/gcc-debug/robust_execution_synthetic_demo --output-dir /tmp/step9
python3 scripts/validate_synthetic_market.py
```

## Invariants and rejection controls

Generation fails rather than silently repairing when:

- configuration values are invalid;
- identifiers or timestamps can overflow;
- prices become non-positive;
- fees, quantities or impact arithmetic overflow;
- the matching engine reports an invariant violation;
- a crossed book appears;
- initial liquidity is rejected;
- stored hashes or summary counts disagree with regenerated values.

`validate_tape()` independently reconstructs action counts, trade quantities, fee totals, sequence
continuity, step ordering and hashes.

## Boundaries

Step 9 does not claim:

- historical calibration;
- realistic hidden liquidity;
- a universal order-arrival model;
- venue-specific market impact;
- exact empirical spread/depth distributions;
- real-market profitability;
- that a strategy trained on this simulator will transfer to live markets.

Historical calibration, goodness-of-fit diagnostics and simulator-to-data validation enter later
data and replay steps. Step 10 will validate the simulator as an engineered system before any policy
comparison begins.
