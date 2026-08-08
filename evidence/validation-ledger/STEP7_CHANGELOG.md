# Step 7 change log — Deterministic event-driven kernel and latency

**Date:** 2026-08-06  
**Repository version:** 0.4.0  
**Research specification:** unchanged; specification lock verified 7/7  
**Step 5 terminal-rejection amendment:** not approved and not applied

## Added

### C++ simulation and utility APIs

- `cpp/include/robust_execution/util/sha256.hpp`
- `cpp/include/robust_execution/simulation/logical_rng.hpp`
- `cpp/include/robust_execution/simulation/latency.hpp`
- `cpp/include/robust_execution/simulation/scheduler.hpp`
- `cpp/include/robust_execution/simulation/canonical_event.hpp`
- `cpp/include/robust_execution/simulation/kernel.hpp`
- `cpp/include/robust_execution/simulation/simulation.hpp`

### C++ implementations

- `cpp/src/util/sha256.cpp`
- `cpp/src/simulation/logical_rng.cpp`
- `cpp/src/simulation/latency.cpp`
- `cpp/src/simulation/scheduler.cpp`
- `cpp/src/simulation/canonical_event.cpp`
- `cpp/src/simulation/kernel.cpp`
- `cpp/src/simulation/kernel_exchange.cpp`
- `cpp/src/simulation/kernel_internal.hpp`

### Executable, fixtures, tests, and documentation

- `cpp/apps/re_kernel_demo.cpp`
- seven Step 7 C++ test executables plus SHA-256 tests;
- `cpp/tests/simulation_test_support.hpp`;
- `results/sample/step7/kernel_demo.txt`;
- `scripts/check_kernel_demo.py`;
- `docs/SIMULATION_KERNEL_AND_LATENCY.md`;
- `docs/simulation/STEP7_DESIGN_DECISIONS.md`.

## Implemented behavior

1. Deterministic total-order scheduling by timestamp, causal stage, canonical sequence, and task ID.
2. Explicit source, exchange-receive, exchange-process, exchange-emit, observer-availability, and system stages.
3. Seven-stage non-negative latency path for observations, decisions, outbound commands, exchange processing, and acknowledgements.
4. Stateless Philox4x32-10 logical randomness keyed by run seed and `(stream_id, logical_index)`.
5. Rejection-sampled bounded integers without consuming an adjacent event's logical index.
6. Exchange dispatch for submit, cancel, and replace commands through the Step 6 matching engine.
7. Causal observer delivery: future policies may consume delivered events only.
8. SHA-256 hash-chained schedule/dispatch/failure traces and complete state hashes.
9. Deterministic generated IDs and canonical sequences.
10. Internal truthful retention of terminal cancel/replace failures while the Step 5 public schema amendment remains unapproved.

## Corrections made during implementation

- Rejection sampling initially risked borrowing another logical event's random address. It now derives retry blocks by deterministic key offsets within the same logical address.
- Generic event timing was kept as the already-correct Step 5 `event_time`; no false universal exchange-time interpretation was introduced.
- The seven frozen specification files were restored byte-for-byte from the approved corrected Step 2 package after an external working-directory state regression. The lock file was not regenerated.
- A hosted standard-Clang TSan job was added because the local Swift Clang 17 TSan runtime cannot link without unavailable libdispatch/Blocks symbols.

## Deliberately not implemented

- execution-policy APIs or observations beyond the delivered-event boundary;
- parent-order inventory or cash accounting;
- fees, rebates, terminal completion, or implementation shortfall;
- synthetic order-flow generation, impact, or resilience;
- historical feed adaptation;
- calibrated latency values;
- throughput or latency optimisation.

Those remain in their original roadmap steps.
