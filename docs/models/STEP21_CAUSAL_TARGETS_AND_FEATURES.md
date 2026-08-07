# Step 21 — Causal Targets and Features

## Status

Step 21 freezes the supervised-learning data contract before any model is trained. It does not select a prediction horizon, fit a model, calibrate probabilities, or produce a strategy-performance claim.

The governing research question and Step 2 protocol are unchanged.

## Information-time contract

For a policy decision at local decision time `t`, define the source cutoff

`c = t - observation_latency`.

A market event may enter the feature row only when both conditions hold:

1. `event_time_ns <= c`; and
2. `available_time_ns <= t`.

Rolling windows are right-closed and left-open: `(c - w, c]`.

The implementation records the maximum source event time and maximum availability time used by every row. The verifier rejects a row if either exceeds its causal bound.

The feature builder requires the complete 5-second causal history before a row is emitted. A row whose future coverage does not extend through the complete 5-second candidate label horizon is rejected.

A snapshot/reconnect inside a target horizon invalidates the row rather than pretending that state continuity is known across the reset.

## Row orientation

Each decision checkpoint produces separate `bid` and `ask` passive-side rows. This side-normalizes the features so the same model contract can later serve buy/passive-bid and sell/passive-ask execution decisions.

The row metadata contains the best bid/ask and doubled mid-price (`bid + ask`) for audit and target reconstruction. Those fields are metadata, not part of the 20 frozen model features.

## Primary target — best-quote depletion or trade-through

For passive side `s`, let `p_s(c)` be the best displayed quote at source cutoff `c`.

For candidate horizon `h` in {250 ms, 1 s, 5 s}, the binary target is one when, during `(c, c+h]`, either:

- the original best quote `p_s(c)` disappears from the aggregate L2 book; or
- the same-side best price moves beyond that original quote; or
- a reported trade occurs strictly through the original quote.

Once the event occurs, every longer candidate horizon is also positive.

This target is deliberately called **quote depletion/trade-through**, not exact fill probability. Aggregate L2 does not identify which cancellations occurred ahead of a hypothetical order and does not recover individual FIFO priority.

The selected primary horizon remains the literal marker:

`PRE_DATA_FIELD_BEFORE_CALIBRATION`

Step 21 must not choose among 250 ms, 1 s and 5 s. The frozen protocol performs that selection later using validation support, calibration validity and downstream decision value.

## Secondary target — side-signed adverse selection

Let doubled mid-price be

`mid_x2 = best_bid_ticks + best_ask_ticks`.

For side sign `q = +1` on bid/passive-buy and `q = -1` on ask/passive-sell, define

`adverse_h_half_ticks = q * (mid_x2(c) - mid_x2(c+h))`.

Positive values therefore mean an adverse price move for the passive side:

- passive bid/buy: future mid moves down;
- passive ask/sell: future mid moves up.

The value is stored in exact half-tick units, avoiding floating-point rounding in the data contract.

## Frozen 20-feature dictionary

All features use only the causal history available at the decision checkpoint.

1. `spread_ticks`
2. `same_top1_lots`
3. `opposite_top1_lots`
4. `same_top5_lots`
5. `opposite_top5_lots`
6. `side_imbalance_top1_bps`
7. `side_imbalance_top5_bps`
8. `toward_quote_trade_flow_250ms_lots`
9. `toward_quote_trade_flow_1s_lots`
10. `toward_quote_trade_flow_5s_lots`
11. `trade_count_1s`
12. `trade_count_5s`
13. `side_mid_move_250ms_half_ticks`
14. `side_mid_move_1s_half_ticks`
15. `side_mid_move_5s_half_ticks`
16. `realized_abs_mid_move_1s_half_ticks`
17. `realized_abs_mid_move_5s_half_ticks`
18. `spread_change_1s_ticks`
19. `quote_age_ns`
20. `time_since_last_trade_ns`

The machine-readable formula dictionary is committed beside the sample dataset.

### Side-normalized trade flow

For a passive bid, seller-aggressor quantity is positive because it moves toward the passive bid; buyer-aggressor quantity is negative. For a passive ask, the sign is reversed.

Binance `buyer_is_maker=true` identifies a seller-aggressor trade; `false` identifies a buyer-aggressor trade.

### Imbalance

Imbalance is stored as integer basis points and truncated toward zero:

`10000 * (same_depth - opposite_depth) / (same_depth + opposite_depth)`.

No floating-point tolerance enters the feature contract.

### Realized movement

`realized_abs_mid_move_*` sums absolute changes of doubled mid-price inside the causal trailing window. It is a local variation statistic, not a future-volatility label.

### Quote age and trade recency

Quote age is measured from the last change in the passive-side best price. Trade recency is measured from the last causal trade. If no causal trade exists inside retained history, the latter is deterministically censored at `maximum_feature_window + 1 ns`.

## Explicit exclusions

Step 21 features do not contain:

- future events or labels;
- exact historical queue position;
- optimistic/central/pessimistic queue outcome labels;
- future-day or execution-day volume profiles;
- full-dataset normalization statistics;
- learned embeddings;
- model predictions;
- test-period statistics;
- parent-order outcomes or realised execution cost.

Feature scaling, categorical encoding, imputation and any learned transformation must later be fitted using training data only.

## Physical separation

`prediction_features` and `prediction_labels` are separate immutable tables joined only by `row_id`. This is intentional. A modeling pipeline must explicitly load labels rather than receiving them inside the feature object.

## Research boundary

The committed Step 21 fixture is synthetic validation evidence only. It exists to prove target semantics, causality and leakage barriers. It is not a training dataset and does not open Gate C.
