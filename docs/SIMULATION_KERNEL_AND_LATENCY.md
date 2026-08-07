# Deterministic simulation kernel and latency contract

**Milestone:** Step 7  
**Repository version:** 0.4.0  
**Research specification:** unchanged  
**Venue/feed semantics:** deliberately unresolved until Step 11

## 1. Purpose and boundary

Step 7 provides the causal event engine used later by execution policies, synthetic
markets, historical replay, accounting, and stress tests. It implements scheduling,
latency, logical randomness, exchange-command dispatch, observer delivery, and replay
hashes. It does not implement a policy, parent-order accounting, a synthetic order-flow
model, a historical feed adapter, fees, impact, or terminal completion. Those remain in
their original roadmap steps.

The kernel uses the Step 5 event schema and the Step 6 exact matching engine without
changing either contract. The proposed Step 5 terminal-cancel rejection amendment is
still unapproved. Consequently, a failed cancel or replace that would require an invalid
`CancelRejected` or `ReplaceRejected` payload is retained as a deterministic
`KernelFailureRecord`; no invalid public event is fabricated.

## 2. Scheduler key

Every task has a total order:

1. timestamp in one clock domain;
2. explicit causal stage;
3. canonical sequence;
4. scheduler task ID.

The causal stages are:

| Stage | Meaning |
|---|---|
| `source` | source-side event creation when explicitly scheduled |
| `exchange_receive` | command reaches the exchange boundary |
| `exchange_process` | matching engine processes the command |
| `exchange_emit` | reserved for explicit exchange emission tasks |
| `observer_available` | event becomes causally visible to a future policy |
| `system` | timer or system event |

The scheduler rejects mixed clock domains, zero canonical sequences, insertion into the
already processed past, and task-ID exhaustion. Equal timestamp behavior is therefore
explicit and deterministic. This stage order is a kernel causality convention, not a
claim about any real venue's undocumented equal-timestamp rules. A Step 11 adapter must
still assign source canonical sequences according to verified venue semantics.

When all latencies are zero, an order follows this order at one timestamp:

```text
exchange_receive -> exchange_process -> observer_available
```

Thus an acknowledgement or fill cannot be observed before the matching operation that
created it.

## 3. Latency path

The latency model contains seven independently configured non-negative integer ranges:

1. market-data network;
2. observation processing;
3. decision processing;
4. outbound order network;
5. exchange processing;
6. acknowledgement network;
7. acknowledgement processing.

For a market event at time `t`:

```text
receive_time   = t + market_data_network
available_time = receive_time + observation_processing
```

For an action whose computation starts at `d`:

```text
decision_end              = d + decision_processing
outbound_send             = decision_end
exchange_receive          = outbound_send + outbound_network
exchange_process          = exchange_receive + exchange_processing
acknowledgement_send       = exchange_process
acknowledgement_receive    = acknowledgement_send + acknowledgement_network
acknowledgement_available  = acknowledgement_receive + acknowledgement_processing
```

Every addition is checked for negative duration and signed 64-bit nanosecond overflow.
The current model is discrete uniform over each inclusive range. Fixed latency is the
special case `minimum == maximum`. Distributional calibration and richer latency
families remain later experimental work; Step 7 does not invent production latency
values.

## 4. Logical randomness

Latency draws use a stateless counter-addressed implementation of Philox4x32-10. The
public address is `(stream_id, logical_index)`, and the run seed is the key. Repeated
access to the same seed/address returns the same four 32-bit words regardless of call
order, thread scheduling, or unrelated draws.

The implementation is checked against the published all-zero Philox4x32-10 known-answer
vector:

```text
6627e8d5 e169c58d bc57ac4c 9b00dbd8
```

Bounded integer draws use rejection sampling. Additional rejection words are obtained
from deterministically key-offset Philox blocks for the same logical address; they do
not consume the next event's logical index. This preserves the logical-address contract.

Reference design: Salmon, Moraes, Dror, and Shaw, *Parallel Random Numbers: As Easy as
1, 2, 3*, SC11, and the D. E. Shaw Research Random123 documentation. The project does
not claim that this local reimplementation has independently repeated the complete
upstream statistical test campaign. Step 9 must still validate the distributions and
simulation outputs actually used by the market generator.

## 5. Exchange command lifecycle

The kernel currently schedules three command payloads:

- `OrderSubmit`;
- `CancelRequest`;
- `ReplaceRequest`.

The kernel stamps command timestamps from the sampled action path. At
`exchange_receive`, it records the inbound event and schedules a separate
`exchange_process` task. At processing time it invokes the Step 6 matching engine and
checks all matching-engine invariants.

Generated responses use their causal timestamps:

- acknowledgements and rejections originate at `acknowledgement_send`;
- trades and fills originate at `exchange_process`;
- all become observer-visible at `acknowledgement_available`.

For one match, output order is deterministic:

1. trade;
2. maker fill;
3. taker fill.

An accepted order acknowledgement is emitted before same-availability execution events.
This is an explicit simulator convention and is covered by a zero-latency test.

No fee event is generated in Step 7. Fee calculation and independent cash accounting
remain Step 17.

## 6. Observation boundary

`delivered_events()` contains only events whose `available_time` has been reached. This
is the future Step 8 policy-observation boundary. `exchange_received_events()` is kept
separately for audit and cannot be treated as policy-visible data.

Step 8 must build immutable causal observations exclusively from delivered events and
must not expose pending scheduler tasks, exchange-process state, or future event
metadata.

## 7. Replay trace and hashes

Every schedule, dispatch, and engine failure appends a trace record containing:

- append index;
- action;
- task ID;
- timestamp;
- stage;
- task kind;
- event ID;
- detail string;
- previous SHA-256;
- record SHA-256.

The record hash covers a length-delimited canonical serialization of every event header
and payload plus the previous hash. `replay_hash()` is the final trace-chain hash.
`state_hash()` additionally covers:

- pending scheduler state;
- exact matching-engine canonical state;
- delivered events;
- exchange-received events;
- engine failure records.

The SHA-256 implementation is checked against the empty-string and `abc` standard test
vectors. Hash equality is evidence of deterministic replay for the same code and input;
it is not proof that the market model is realistic or that two different implementations
are semantically equivalent.

## 8. Deterministic sample

`robust_execution_kernel_demo` runs a non-empirical tape with:

- one resting sell limit order;
- one marketable buy order;
- one timer;
- fixed latency at every stage.

Its committed output is `results/sample/step7/kernel_demo.txt`. The validation script
runs the executable twice and compares both outputs byte-for-byte with the committed
fixture.

## 9. Step 7 acceptance evidence

Required tests cover:

- SHA-256 vectors;
- Philox known-answer vector;
- call-order-independent logical draws;
- inclusive bounded draws and invalid arguments;
- fixed and ranged latency;
- timestamp overflow;
- scheduler stage, sequence, and task-ID ordering;
- mixed-clock and past-insertion rejection;
- partial execution with deterministic acknowledgements/trades/fills;
- run-until semantics;
- replay and state hash equality across identical runs;
- hash change after an input change;
- zero-latency causality;
- duplicate-order rejection;
- successful cancellation;
- already-terminal cancellation retained as an internal failure without emitting an
  invalid Step 5 event;
- matching invariants after every exchange command;
- GCC, Clang, ASan, and UBSan execution.

## 10. Explicit limitations

- Single-threaded deterministic scheduler only; parallel execution is not needed for
  correctness and is not claimed.
- No wall-clock or real-time mode.
- No queue-aware policy interface yet.
- No external market-data replay adapter yet.
- No stochastic market generator yet.
- No calibrated latency distributions yet.
- No fee, inventory, cash, or terminal-completion accounting yet.
- No performance claim from the demo or test suite.
- No exact historical queue claim.
