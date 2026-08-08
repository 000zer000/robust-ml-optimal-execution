# Step 15 change log

**Repository version:** 0.12.0  
**Step:** 15 — Historical aggregate-L2 replay  
**Research specification changed:** No

## Added

- A C++ historical replay module for aggregate snapshots, depth updates, trades, reconnects, sequence synchronization, and causal policy observations.
- An explicit-timing market-event path in the deterministic kernel that preserves exchange event time, collector receive time, and policy availability time separately.
- Snapshot-bootstrap suppression until the first sequence-bridging depth update.
- Explicit reconnect boundaries that clear stale book and trade state immediately at connection start and suppress policy observations until the new sequence bridge.
- Deterministic replay, kernel-state, observation-lineage, table, configuration, and manifest hashes.
- A Python canonical-dataset adapter and independent historical replay verifier.
- Three immutable replay tables: events, observations, and connection integrity.
- Strict rejection of sequence gaps, stale updates, crossed books, causal timestamp violations, unsupported source datasets, output overwrites, and weakened scientific claims.
- Two JSON schemas, sample and processed configuration contracts, CLI commands, deterministic fixtures, validation scripts, and Python/C++ tests.
- A direct kernel test for explicit historical event, receive, and availability timing.
- Historical replay documentation and an additive snapshot-timestamp metadata proposal.
- CI and local reproducibility integration.

## Correctness defect caught before freeze

The final audit found that a pre-bridge trade on a new connection could otherwise be combined with the previous connection's stale book. Both C++ and Python paths now reset market-state readiness at connection start, clear stale book/trade state, retain only causally observed trades from the new connection, and suppress decisions until synchronization. Dedicated reconnect tests cover this failure mode.

## Scientific boundaries retained

The replay explicitly states and machine-checks that:

- exact historical FIFO queue position is not reconstructed;
- aggregate L2 quantities are price-level quantities, not individual orders;
- simulated child orders do not alter the recorded future path;
- endogenous market impact is not modelled in historical replay;
- the committed fixture is synthetic and non-research;
- Step 16 must introduce explicit optimistic, central, and pessimistic queue assumptions.

## Compatibility updates

The repository version advanced from 0.11.0 to 0.12.0. Step 12, Step 13, and Step 14 deterministic fixture metadata was regenerated because those manifests record the software version. The underlying raw fixture messages, Step 13 admission decision, Step 14 canonical rows, and scientific interpretation did not change.

## Not changed

- the exact central research question;
- secondary research questions or hypotheses;
- final project scope;
- the chronological split or Gate C requirements;
- Binance Spot, BTCUSDT, or ETHUSDT selection;
- the prohibition on repairing missing market events;
- the research-admission status of any day;
- the unapproved Step 5 rejection-schema proposal.

## Pending external evidence

No research historical replay has been produced. It remains blocked until the live 72-hour pilot succeeds, exact snapshot request/response timestamps are captured, whole live days pass Step 13, Step 14 produces verified processed Parquet tables, and Step 16 queue models are implemented.
