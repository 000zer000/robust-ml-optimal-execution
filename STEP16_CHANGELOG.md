# Step 16 change log

## Added

- C++ aggregate-L2 queue model with optimistic, central, and pessimistic assumptions.
- Passive maker-fill estimates for at-price trades and trade-through events.
- Trade/depth reconciliation that prevents double counting.
- Explicit cancellation-ahead and cancellation-behind accounting.
- Optional additional-initial-ahead sensitivity buffer.
- Exact synthetic FIFO comparison using parallel exact and ghost matching-engine worlds.
- Five deterministic comparison scenarios and a nine-cell sensitivity matrix.
- Three Step 16 JSON Schemas, strict configuration parser, independent verifier, fixture generator, and tamper tests.
- Deterministic queue demo and immutable evidence manifest.

## Changed

- Repository version advanced from 0.12.0 to 0.13.0.
- CMake, installation targets, test registration, local validation commands, and repository contract now include Step 16.
- Removed a duplicated Step 16 validator/demo invocation from the GCC CI job; the intended GCC and Python jobs each retain one complete Step 16 check.

## Unchanged

- Central research question.
- Full project scope and hypotheses.
- Frozen research protocol and specification hashes.
- Historical replay's ghost small-agent and no-endogenous-impact boundaries.
- The prohibition on exact historical FIFO claims.

## Deferred

- Empirical calibration of queue assumptions to live or order-level data.
- Historical execution-quality conclusions, pending admitted real days.
- Fees, implementation shortfall, and strategy metrics, which begin in Step 17.
