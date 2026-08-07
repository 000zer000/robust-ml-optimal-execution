# Step 16 — Aggregate-L2 queue models

## Status

Step 16 implements and validates three explicit passive-fill assumptions for historical aggregate level-2 replay. It does **not** reconstruct individual historical order identities or exact FIFO position.

The three models are:

1. **Optimistic:** every unexplained reduction in displayed quantity is allocated ahead of the simulated child order, up to the remaining estimated quantity ahead.
2. **Central:** unexplained reductions are allocated ahead proportionally to the estimated quantity ahead as a share of the displayed historical level before the update.
3. **Pessimistic:** unexplained reductions are allocated behind the simulated child order; only eligible trade prints reduce estimated quantity ahead.

All three models use identical trade, timing, order-side, and trade-through rules. Only the allocation of unexplained aggregate depth reductions differs.

## Placement semantics

A passive child order is treated as joining behind all displayed quantity present at its price when the order becomes active. The order is a ghost small agent and is not inserted into the historical aggregate book.

Later increases in displayed quantity at the same price are placed behind the child and do not increase estimated quantity ahead. This is an assumption, not an observable historical fact.

The optional `additional_initial_ahead_bps` parameter adds a sensitivity buffer for hidden or otherwise unobserved quantity ahead. The default is zero. Values of 2,500 and 5,000 basis points are included in the deterministic sensitivity matrix; they are not calibrated estimates.

## Trade handling

A trade is relevant only when its aggressor side consumes the child order's resting side.

For a resting buy child:

- sell-aggressor trade above the child price: no queue effect;
- sell-aggressor trade at the child price: consumes estimated quantity ahead, then fills the child as maker if volume remains;
- sell-aggressor trade below the child price: trade-through, so the residual child is filled.

For a resting sell child, the inequalities reverse.

Trade-at-price volume is recorded as pending displayed depletion. The next absolute level update first attributes any matching reduction to that trade volume, preventing the trade and subsequent depth update from being counted twice. Any remaining reduction is treated as unexplained cancellation/deletion volume and passed to the selected queue assumption.

A cancellation or deletion alone never creates a fill. It may move estimated queue position to the front, but a trade at the price or a trade-through is still required.

## Central model equation

For an unexplained displayed reduction `R`, displayed quantity before the update `D`, and estimated quantity ahead `A`, the central allocation is:

```text
cancellation_ahead = floor(R × min(A, D) / D)
```

when `D > 0`; otherwise the allocation is zero. The estimate is bounded by `A`.

This corresponds to a proportional allocation across visible historical quantity. It is a modelling convention, not a statement that real cancellations are uniformly distributed.

## Exact synthetic comparison

The validation uses the Step 6 exact price-time-priority engine in two parallel worlds:

- **Exact world:** historical orders, the passive child, later historical orders, cancellations, and an aggressive order are all inserted into the exact FIFO book. The child's maker fill is the exact synthetic reference.
- **Ghost world:** the same historical orders, cancellations, and aggressive order are replayed without the passive child. The resulting public trade tape and aggregate displayed quantities are supplied to each queue model.

This design avoids constructing the aggregate tape from the model being tested. Five deterministic scenarios cover no cancellation, cancellation ahead, cancellation behind, mixed cancellation, and addition-only behavior.

For the designed scenarios, the validation requires:

```text
optimistic fill >= exact FIFO fill >= pessimistic fill
optimistic fill >= central fill >= pessimistic fill
```

These are validation properties for the controlled scenarios, not universal mathematical guarantees for every possible aggregate message sequence.

## Sensitivity matrix

The mixed-cancellation scenario is evaluated across:

- optimistic, central, and pessimistic assumptions;
- 0, 2,500, and 5,000 basis points of additional initial quantity ahead.

Estimated fills must be non-increasing as the hidden-ahead buffer rises, while estimated residual quantity ahead must be non-decreasing.

## Accounting boundary

Every estimated passive fill contains:

- client order ID;
- maker fill price;
- incremental quantity;
- cumulative filled quantity;
- residual quantity;
- maker liquidity role;
- fill reason (`trade_at_price` or `trade_through`);
- event time.

Step 16 does not calculate monetary fees or implementation shortfall. Those enter Step 17 through the common accounting and metric layer.

## Scientific limitations

The historical models cannot observe:

- individual order IDs;
- exact placement within a price level;
- hidden or iceberg quantity;
- whether a cancellation occurred ahead or behind;
- exchange-internal matching details not exposed by the feed;
- counterfactual endogenous impact of the simulated order.

Therefore:

```text
historical_exact_fifo_reconstructed = false
ghost_small_agent_assumption = true
```

The three queue models must be carried together in historical strategy evaluation. A strategy result that changes materially across the three assumptions is queue-model-sensitive and cannot be presented as robust.
