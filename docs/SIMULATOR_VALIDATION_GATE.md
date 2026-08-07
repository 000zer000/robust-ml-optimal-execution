# Simulator validation gate — Gate B

**Repository version:** 0.7.0  
**Status:** Passed on 2026-08-06  
**Scope:** exact synthetic matching, event scheduling, latency composition, policy-state contracts,
synthetic-market accounting and designed-process response

## Decision

Gate B is **PASS**. The repository may proceed to Step 11, selection of current real-market data
sources.

This decision does not certify historical realism. It establishes that the exact synthetic mode is
internally consistent enough to serve as an engineering and controlled-stress foundation while real
data, venue semantics, historical replay and queue assumptions are developed under later gates.

## Required evidence

A pass requires every item below to pass:

1. Manual FIFO, price-priority and partial-fill oracle.
2. Manual seven-stage latency arithmetic oracle.
3. Same-seed byte determinism and changed-seed separation.
4. Invalid-configuration and tape-tamper detection.
5. Sixty-four-seed randomized tape and book-invariant campaign.
6. Independent reference-book differential test after every command.
7. Structured mutation campaign over configuration, sequence, accounting, hashes and book state.
8. Directional response to market-order frequency, target depth, volatility/impact and liquidity
   shock parameters.
9. GCC, Clang, Release/IPO and ASan/UBSan execution.
10. Byte-identical validation reports across GCC Debug, Clang Debug and GCC Release.
11. Installed-package and clean downstream-consumer validation.
12. Frozen research-specification hash verification.

## Executed workload

- 64 generated seeds;
- 16,384 generated grid steps;
- 32 independent differential seeds;
- 64,000 valid reference-comparison commands;
- 2,048 deterministic structure-aware mutations;
- four 32-seed paired sensitivity comparisons.

The differential reference is deliberately implemented with independent standard-library maps and
FIFO deques. It compares production-engine fills and complete visible-book state after every limit,
market or cancellation command.

## Directional sensitivity results

| Test | Control mean | Treatment mean | Required direction | Result |
|---|---:|---:|---|---|
| Market-order arrival | 13.375 | 167.46875 | treatment > control + 50 | PASS |
| Visible depth | 40.06591796875 | 217.523193359375 | treatment > 1.5 × control | PASS |
| Volatility/impact displacement | 2.03125 | 34.0 | treatment > control + 10 ticks | PASS |
| Liquidity-vacuum minimum depth | 64.5625 | 0.0 | treatment < control | PASS |

These are designed-process response checks. They show that parameters influence outputs in the
intended direction; they are not empirical estimates, causal market-impact findings or calibration
results.

## Failure and mutation controls

The structured mutation campaign changes one supported contract field per case, including:

- action sequence and grid index;
- summary step and trade counts;
- seed/configuration identity without recomputing provenance;
- tape and configuration hashes;
- manifest bytes;
- maker-fee accounting;
- crossed best bid and ask.

All 2,048 mutations were rejected by independent tape validation. This is not described as
coverage-guided fuzzing. A future libFuzzer or AFL++ harness remains useful, but its absence does not
block Gate B because the current campaign is deterministic, reproducible and paired with sanitizers,
differential testing and invariant checks.

## Claim boundary

Gate B supports these claims:

- exact synthetic FIFO and price-time mechanics passed the stated tests;
- event and latency arithmetic is causal under the defined model;
- generated tapes are deterministic and independently auditable;
- the designed generator responds directionally to its declared parameters;
- the tested source state is portable across GCC and Clang and clean under ASan/UBSan.

Gate B does not support these claims:

- a real venue follows the current generic assumptions;
- the generator matches historical order-flow distributions;
- synthetic impact coefficients are causal estimates;
- aggregate historical FIFO queue position can be reconstructed exactly;
- hidden liquidity is represented;
- any execution strategy is profitable or even superior;
- the simulator is ready for RL before the later baseline, reward and mismatch gates.

## Remaining limitations

- TSan cannot link locally because the installed Swift Clang runtime expects unavailable
  libdispatch/Blocks symbols. The standard Ubuntu-Clang hosted job remains configured but unexecuted
  until pushed.
- The mutation campaign is structure-aware, not coverage-guided.
- Historical replay, venue adaptation and queue models are not part of Gate B.
- The Step 9 process remains explicitly `not_calibrated_step9`.
- Docker, hosted CI and isolated-wheel jobs remain configured but are not claimed as executed here.
