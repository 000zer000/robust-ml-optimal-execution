# Step 6 Change Log — C++ Order Book and Matching

**Date:** 2026-08-06  
**Repository version:** 0.3.0  
**Scope status:** Frozen research question and final scope unchanged

## Added

- `cpp/include/robust_execution/exchange/matching_engine.hpp`
- `cpp/include/robust_execution/exchange/exchange.hpp`
- `cpp/src/exchange/matching_engine.cpp`
- `cpp/src/exchange/matching_engine_commands.cpp`
- `cpp/src/exchange/matching_engine_book.cpp`
- `cpp/src/exchange/matching_engine_internal.hpp`
- `cpp/apps/re_matching_demo.cpp`
- six dedicated C++ matching-engine test executables
- deterministic matching hand tape and checker
- `docs/MATCHING_ENGINE.md`
- unimplemented Step 5 schema-amendment proposal

## Implemented

- bid/ask price maps and FIFO order queues;
- market and limit orders;
- GTC, IOC, and FOK;
- post-only rejection;
- maker-price execution;
- partial fills and cumulative quantities;
- cancellations with stable middle-of-queue removal;
- atomic cancel-replace with new IDs and lost priority;
- minimum/maximum quantity validation;
- accepted-client-ID uniqueness;
- deterministic trade, match, execution, exchange-order, and priority sequences;
- complete order history and book queries;
- canonical state serialisation;
- explicit internal invariant validation.

## Corrected governance recovery

The Step 4 specification lock matched the corrected Step 2 package, but the working directory contained the earlier uncorrected Step 2 files. Step 6 restored the seven locked files byte-for-byte from `robust-execution-step2-specification-corrected.zip`. No new research-specification amendment was made.

## Not changed

- central research question;
- research questions or hypotheses;
- final project scope;
- experimental protocol;
- Step 5 event schema or validation;
- data-source or venue selection.

## Not implemented

The Step 7 scheduler, latency, policy interface, fees, market generator, data replay, and performance optimisation are not part of Step 6.
