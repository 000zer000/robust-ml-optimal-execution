# Step 18 — Basic execution baselines

## Scope

Step 18 implements three pre-ML execution baselines under the common Step 8 policy contract and Step 17 accounting contract:

1. **Immediate aggressive execution** — the entire parent quantity is released at the start and submitted aggressively.
2. **TWAP** — the parent quantity is divided as evenly as integer lots permit across equally spaced release times in `[start, end)`.
3. **Past-only volume-informed schedule** — integer lots are allocated across time buckets in proportion to a profile estimated only from observations at or before a declared training cutoff that is strictly earlier than the episode start.

TWAP and the volume-informed schedule support aggressive and passive execution styles. Immediate execution is deliberately defined only as aggressive. Passive children use same-side best, zero tick offset, GTC, post-only placement; they may lag the target schedule if an acknowledged child remains live. The common hard terminal-completion rule remains responsible for residual inventory.

## Quantity allocation

All schedules conserve the parent quantity exactly. Integer-lot allocation uses deterministic largest-remainder apportionment with bucket-index tie breaking. No floating-point proportions are used.

For TWAP, all weights equal one. For the volume-informed schedule, weights are past executed quantities aggregated into predeclared buckets.

## Information boundary

The volume profile is rejected when:

- its provenance identifier is missing;
- a source observation occurs after the declared training cutoff;
- clocks differ;
- a bucket index is invalid;
- all historical volume is zero;
- the training cutoff is at or after the execution episode start.

Therefore the strategy cannot use the realised volume curve of the episode it is executing.

## Common-interface behavior

`ScheduledBaselinePolicy` implements `ExecutionPolicy`. At each observation it computes cumulative scheduled quantity due minus cumulative filled quantity. It does not issue another command while a command is pending or an acknowledged child remains active. Fractions are reduced to canonical rational form before the common action validator sees them.

## Step 18 evidence boundary

The committed validation episode is synthetic and hand-designed. Its prices are intentionally chosen only to prove that the three schedules produce different audited Step 17 implementation-shortfall values under identical exogenous prices. These numbers are **not** evidence that any baseline is superior in a market.

Historical and statistically meaningful baseline comparisons are blocked until real admitted data exists and the locked evaluation protocol is executed later.
