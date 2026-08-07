# Step 15 Causal Replay Contract

## Invariants

1. The replay uses only Step 14 canonical rows.
2. Exchange event time, capture receive time, and policy availability remain separate.
3. No event is visible before its `available_time`.
4. At every reconnect, policy readiness and stale market state are reset at connection start; a policy-ready book remains unavailable until the new snapshot sequence is bridged.
5. Snapshot bootstrap timing is never represented as an exact exchange timestamp unless the capture contains such evidence.
6. Equal-time events use deterministic canonical ordering.
7. Replay does not submit historical data into the exact matching engine as individual orders.
8. Trades do not imply unrecorded depth changes.
9. Simulated orders do not modify the recorded future path.
10. No exact queue-ahead quantity or FIFO position is produced in Step 15.

## C++ execution path

`HistoricalReplayEngine` converts snapshots, depth batches, and trades into model events. Internal reconnect boundaries are merged with delivered-event time: they replace the observation builder before any new-connection event is ingested, clear stale book/trade state, and set synchronization false. It uses `SimulationKernel::schedule_market_event_with_timing`, which preserves observed receive time and adds only explicitly configured policy-processing delay. At checkpoints the kernel runs inclusively, newly delivered events are passed to `ObservationBuilder`, and a `PolicyObservation` is built only after sequence synchronization.

## Python evidence path

The Python adapter independently reconstructs aggregate state from the canonical tables and writes hash-verified event, observation, and connection-integrity tables. This is not a substitute for C++ execution; it is an independent artifact and provenance check.

## Interpretation labels

Every output must retain all of these labels:

- `aggregate_historical_replay`;
- `ghost_small_agent_no_endogenous_impact`;
- `not_reconstructed_until_step16` for queue position;
- `sample_only_non_research` or `research_processed` inherited from Step 14;
- explicit snapshot timestamp semantics.
