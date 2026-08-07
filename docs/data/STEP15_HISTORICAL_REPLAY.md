# Step 15 — Historical Aggregate-L2 Replay

**Status:** Engineering complete on deterministic non-research fixtures. Real research replay remains blocked by the live-data and snapshot-timestamp requirements described below.

## 1. Purpose

Step 15 converts validated Step 14 canonical tables into a deterministic historical aggregate-L2 replay. It has two implementations with deliberately overlapping responsibilities:

1. a C++ replay engine that schedules historically observed market events through the Step 7 deterministic kernel and exposes Step 8 causal policy observations;
2. a Python canonical adapter that reconstructs immutable replay events, aggregate-book states, causal validation observations, connection integrity records, and a hash-verified replay manifest.

The replay answers: *what would a policy have observed on this recorded aggregate market path, given explicit receive and processing timing?* It does not answer exact FIFO position or endogenous impact.

## 2. Scientific boundary

The following statements are mandatory and machine-checked:

- `exact_fifo_reconstructed = false`;
- `queue_position_semantics = not_reconstructed_until_step16`;
- `endogenous_impact_modelled = false`;
- `market_impact_semantics = ghost_small_agent_no_endogenous_impact`;
- the historical path is not altered by simulated child orders;
- aggregate L2 quantities are observed price-level quantities, not individual order identities.

Step 16 will add separate optimistic, central, and pessimistic queue assumptions. It will not retroactively turn aggregate data into exact order-level history.

## 3. Input contract

The adapter accepts only a Step 14 manifest that:

- passes independent canonical verification;
- contains `source_records`, `book_snapshots`, `book_deltas`, and `trades`;
- exactly matches the configured venue instruments and order;
- has no repaired missing events;
- preserves message, row, connection, timestamp, and payload-hash provenance.

A research replay additionally requires a research-admissible Step 14 dataset. The committed fixture is synthetic and remains non-research.

## 4. Snapshot bootstrap and synchronization

A REST snapshot is a bootstrap state, not a normal exchange event. Every reconnect also creates an internal reset boundary at the captured connection-start timestamp: stale book state and stale recent-trade history are cleared immediately, and policy readiness remains false until the replacement stream bridges its snapshot. The current Step 12/14 contracts retain the connection start time and snapshot sequence ID but do not retain the exact snapshot response receive timestamp.

The sample replay therefore uses the conservative contract:

```text
snapshot_timestamp_semantics =
connection_start_proxy_suppressed_until_sequence_bridge
```

The snapshot is made internally available at the first depth message that bridges `lastUpdateId + 1`. Policy observations are suppressed until that bridge has been applied. Consequently, the connection-start proxy is never exposed as a policy-ready historical observation.

This is sufficient for deterministic fixture validation, but it is not accepted for a real research replay. Exact snapshot request/response timestamps must be added before the live pilot is treated as research input.

## 5. Ordering and causality

For every canonical market message:

```text
exchange event time <= collector receive time <= policy available time
```

Policy available time is:

```text
collector receive time + configured observation-processing delay
```

The C++ kernel now has an additive explicit-timing scheduling path for observed market data. The existing synthetic-latency method remains unchanged.

Within each instrument, replay events are ordered by:

1. available timestamp;
2. snapshot before depth before trade when availability is equal;
3. canonical message sequence;
4. source subsequence for individual depth levels in C++.

The Python fixture emits an observation after each delivered event only for validation. This is explicitly not the primary 100 ms strategy decision grid. Later execution experiments will query the same C++ state on the common decision grid frozen in the research protocol.

## 6. Book reconstruction

- Snapshot: replace the aggregate bid and ask maps.
- Depth set: set the exact displayed quantity at `(side, price)`.
- Depth delete: remove the price level.
- Trade: append the trade to bounded causal history; do not infer hidden book changes beyond recorded deltas.
- Reconnect: at connection start, clear stale book and prior-connection trade history, retain only causally received new-connection trades, load the new snapshot at synchronization, and wait for the sequence bridge before exposing observations.

After every policy-ready event, the adapter checks:

- non-empty bid and ask sides;
- strictly positive stored quantities;
- best bid below best ask;
- causal lineage times;
- deterministic book and lineage hashes.

## 7. Outputs

The immutable replay dataset contains:

1. `replay_events` — snapshot, depth-batch, and trade envelopes with causal timestamps and payload hashes;
2. `replay_observations` — top-of-book/depth summaries and causal lineage hashes;
3. `connection_integrity` — sequence bridge, batch counts, gap counts, crossed-book counts, and timestamp semantics;
4. `replay-manifest.json` and its SHA-256 sidecar.

The committed fixture contains two instrument connections, 10 events, and 8 synchronized observations.

## 8. Failure policy

The replay fails rather than repairing or guessing when it encounters:

- an unverified canonical source;
- symbol mismatch;
- missing connection snapshot;
- no bridging depth batch;
- overlapping or non-monotone connection intervals;
- stale or gapped depth sequences;
- event time after receive time;
- receive time after available time;
- a locked or crossed reconstructed book;
- conflicting replay output already present;
- weakened FIFO or impact claims;
- any manifest or table hash mismatch.

## 9. Reproducibility commands

```bash
PYTHONPATH=python python scripts/generate_step15_fixture.py
PYTHONPATH=python python scripts/validate_step15_replay.py
cmake --preset gcc-debug
cmake --build --preset gcc-debug
ctest --preset gcc-debug -R historical
python scripts/check_historical_demo.py
```

## 10. Gate status

Step 15 engineering passes on deterministic fixtures. Historical empirical readiness remains conditional on:

- the Step 12 72-hour live pilot;
- exact snapshot request/response timing metadata;
- Step 13 admitted whole days;
- Step 14 research-processed Parquet datasets;
- Step 16 queue-model implementation;
- the full Gate C minimum of 100 admitted days per instrument.
