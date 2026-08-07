# Step 17 — Exact accounting and execution metrics

## Status

Step 17 defines and implements the accounting contract used by every later strategy. The committed evidence is synthetic validation only. It is not a historical strategy result, a performance benchmark, or a profitability claim.

## 1. Exact ledger

Every child execution enters the metric engine with:

- execution identifier;
- parent side;
- integer price ticks;
- integer quantity lots;
- fill timestamp;
- maker, taker, or unknown liquidity role;
- explicit fee in quote atoms;
- continuous or terminal-completion source.

Fees use one convention throughout the project:

- positive amount = cost;
- negative amount = rebate.

All quote notionals are reconstructed exactly from the instrument tick size, lot size, and quote-atom size. A metric calculation fails if a product is not exactly representable or exceeds the signed 64-bit quote-atom range.

## 2. Cash accounting

For execution price `p_i`, quantity `q_i`, and exact quote notional `N_i`:

- buy gross cash flow is `-sum(N_i)`;
- sell gross cash flow is `+sum(N_i)`;
- net cash flow is `gross cash flow - explicit fees`.

The independent audit reconstructs these values from the raw execution ledger and does not trust the reported cash fields.

## 3. Implementation shortfall

Let `s = +1` for a buy parent and `s = -1` for a sell parent. Let `N_exec` be total execution notional, `N_bench` the benchmark notional for the full parent quantity, and `F` total explicit fees and rebates.

```text
implementation shortfall = s * (N_exec - N_bench) + F
```

A positive value is worse execution for both buy and sell parents. A negative value is improvement relative to the benchmark.

Basis points are:

```text
shortfall_bps = shortfall_quote_atoms / benchmark_notional_quote_atoms * 10,000
```

The arrival price is mandatory. Additional externally defined benchmarks may be supplied, but they use the same ledger, completion, fee, and side convention.

### Completion rule

Final implementation shortfall is undefined for an incomplete parent order. The engine records completion and residual inventory, but it withholds final shortfall until every lot is accounted through ordinary fills or the explicit terminal-completion rule. Aggregate tail summaries reject incomplete episodes.

## 4. Terminal completion

Terminal fills are classified separately. Their directional cost is measured against the arrival price for the terminal quantity and includes the terminal fee:

```text
terminal cost = s * (terminal notional - arrival notional for terminal quantity)
                + terminal fees
```

This prevents forced liquidation from disappearing inside total implementation shortfall.

## 5. Average price and fill composition

The system reports:

- exact gross execution notional;
- quantity-weighted average execution price in ticks;
- average price in quote units;
- passive maker quantity and fraction;
- aggressive taker quantity and fraction;
- quantity with unknown liquidity classification.

Maker and taker fractions are quantity weighted and sum with the unknown fraction to one whenever any quantity is filled.

## 6. Inventory and completion

The inventory trajectory begins at the full parent quantity at parent start, decreases only when fills occur, records the parent deadline explicitly, and ends at the exact residual.

Every inventory point is audited for:

- the parent clock domain;
- non-decreasing timestamps;
- lower bound zero;
- upper bound parent quantity;
- non-increasing remaining inventory;
- agreement with ledger fills.

The report includes time to first fill and time to full completion. Completion after the nominal deadline remains visible rather than being clipped.

## 7. Adverse selection

For fill price `p_fill`, future markout mid-price `p_mark`, quantity `q`, and side sign `s`:

```text
adverse-selection cost = s * (p_fill - p_mark) * q
```

Positive cost means that the post-fill price moved against the parent side. Results are grouped by markout horizon, and every horizon reports observed quantity and coverage. Missing markouts are never silently treated as zero.

## 8. Actions, latency, throughput and memory

The episode report records decision, submit, cancel, replace, rejected-action, and invalid-action counts. Cancellation activity is reported as cancels divided by submits when defined.

Latency summaries cover:

- observation staleness;
- controller duration;
- model-inference duration when present;
- decision-end to action-dispatch duration.

Each summary reports count, minimum, maximum, mean, and empirical nearest-rank p50, p95, and p99.

Throughput is calculated only from an externally measured event count and wall-clock duration:

```text
events_per_second = events_processed * 1e9 / wall_time_ns
```

Peak RSS is stored as raw measured bytes. The Step 17 fixture validates accounting only and makes no speed or scalability claim.
