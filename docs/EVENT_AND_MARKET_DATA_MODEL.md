# Event and Market-Data Model — Step 5

## Status and authority

- **Model version:** 1.0
- **Implementation milestone:** Step 5
- **Research specification:** unchanged
- **Authoritative engine representation:** C++ headers under `cpp/include/robust_execution/model/`
- **Stable interchange representation:** JSON Schema under `schemas/event_model/`
- **Python verification layer:** `python/robust_execution/event_model.py`

This document freezes the venue-neutral representation needed by the exact simulator,
historical replay, policies, metrics, and audit trail. It does **not** choose a venue,
feed, event-order convention, fee schedule, or latency value. Those remain pre-data
fields for Step 11 and later, exactly as required by the frozen specification.

## 1. Exact units

The matching core never compares binary floating-point prices or quantities.

| Concept | C++ type | Representation | Valid absolute value |
|---|---|---|---|
| Price | `PriceTicks` | signed 64-bit integer ticks | strictly positive |
| Price displacement | `TickOffset` | signed 32-bit integer ticks | any representable offset |
| Quantity | `QuantityLots` | unsigned 64-bit integer lots | positive for orders/fills; zero allowed for state fields |
| Cash, fee, rebate | `QuoteAtoms` | signed 64-bit quote atoms | positive fee, negative rebate, zero allowed |
| Tick/lot/quote atom size | `RationalIncrement` | exact positive numerator/denominator | both components positive |

Signed price storage allows checked application of relative tick offsets. Absolute
market prices are validated as positive. Quantity subtraction is checked and cannot
produce a negative result. Overflow-aware addition is provided for prices,
quantities, and quote atoms. Notional multiplication and full cash accounting are
intentionally deferred to Step 17, where wider intermediate arithmetic and explicit
rounding rules will be implemented and independently audited.

Instrument metadata stores exact rational tick, lot, and quote-atom increments plus a
version identifier. Venue-specific conversion and rounding rules cannot be added
without a versioned instrument definition.

## 2. Identifiers

Numerical IDs are distinct strong types and zero is invalid:

- event;
- parent order;
- client order;
- exchange order;
- execution/fill;
- decision;
- normalized trade.

Text identifiers are also distinct strong types:

- run;
- venue;
- instrument;
- source channel;
- external order/trade;
- fee schedule;
- strategy;
- queue model;
- latency model.

External source identifiers are optional because some public feeds do not provide
them. Internal normalized identifiers are mandatory and deterministic.

## 3. Clock contract

`TimestampNs` contains:

1. a clock domain: `unix_utc` or `simulation`;
2. a signed 64-bit nanosecond value.

The model does not compare timestamps from different domains as elapsed time. Each
run and normalized stream must use one domain.

Every event has a canonical `event_time`. For historical or synthetic market events, this is the exchange/source event timestamp; for decisions, timers, and system events it is the timestamp at which that event occurs in its own origin subsystem. It may also have:

- `receive_time`: arrival at the capture process or simulated observer;
- `available_time`: earliest time the causal event may enter a policy observation;
- `original_timestamp`: exact source representation retained for provenance.

For synthetic, strategy, and system events, receive time cannot precede event
time. Historical feeds may exhibit apparent negative transport time because venue
and local clocks are not perfectly synchronized; this is retained as a validation
warning rather than silently repaired. `available_time` must always be at or after
`receive_time` and in the same clock domain.

Decision and action payloads carry their own causal timing fields:

- observation cutoff;
- decision start/end;
- outbound send;
- exchange receive/process;
- acknowledgement send/receive/availability where applicable.

The Step 7 scheduler will populate the full latency path. Step 5 fixes the names,
units, and monotonicity rules.

## 4. Deterministic event ordering

The normalized order key is:

1. canonical event timestamp;
2. adapter-assigned `canonical_sequence`;
3. source subsequence;
4. ingestion sequence;
5. internal event ID.

`canonical_sequence` and `ingest_sequence` are mandatory and non-zero. The raw
`source_sequence` is retained separately when the feed provides one; if
`has_source_sequence` is false, it must be zero. The Step 11 source adapter must
produce `canonical_sequence` from documented venue semantics, snapshot recovery, and
equal-timestamp rules. Until then, synthetic fixtures assign it deterministically.
The generic core therefore stores a total order without inventing how a real feed
should map into that order.

Events from different clock domains must never be mixed in one replay stream. The C++
ordering helper has a deterministic cross-domain fallback only to preserve strict
container ordering; that fallback has no market-time meaning and mixed-domain stream
validation must fail before replay.

## 5. Event envelope

Every event contains:

- schema version;
- event ID and run ID;
- venue, instrument, and source channel;
- origin (`historical_feed`, `synthetic_exchange`, `strategy`, or `system`);
- causal timestamps;
- normalized ordering metadata;
- one event kind and matching payload.

Schema major version 1 is the Step 5 compatibility boundary. Unknown major versions
must fail. Minor versions may only add backward-compatible optional fields.

## 6. Payload catalogue

### Market data

- `book_snapshot`: strictly descending bids, strictly ascending asks, no duplicate
  prices, positive displayed quantity, and no locked/crossed best quotes.
- `depth_update`: absolute `set` quantity or `delete` to zero at one side/price.
  The normalized core does not use ambiguous deltas.
- `trade`: normalized trade ID, optional external ID, price, quantity, and aggressor
  side when known.

### Policy and order lifecycle

- `decision`;
- `order_submit`;
- `order_acknowledged`;
- `order_rejected`;
- `cancel_request`;
- `cancel_acknowledged`;
- `cancel_rejected`;
- `replace_request`;
- `replace_acknowledged`;
- `replace_rejected`.

A limit order requires a positive limit price. A market order cannot carry a limit
price or be post-only. Acknowledgement quantities must conserve accepted quantity.
All requests retain the decision link and outbound timing needed to reconstruct
latency and causal behavior.

### Execution and accounting inputs

- `fill`: execution ID, order IDs, side, exact price/quantity, cumulative fill,
  leaves quantity, and maker/taker/unknown role;
- `fee`: one exact signed quote-atom amount linked to an execution and versioned fee
  schedule;
- `terminal_completion`: common deadline completion transaction, exact quantity,
  price, explicit fee, and rule ID.

A negative fee amount represents a rebate. Full implementation-shortfall accounting
is Step 17; Step 5 ensures no required primitive is missing.

### Scheduler

- `timer`: named deterministic scheduler occurrence.

## 7. Order state machine

The frozen states are:

```text
pending_new
live
partially_filled
pending_cancel
cancelled
filled
rejected
expired
replaced
```

Terminal states are `cancelled`, `filled`, `rejected`, `expired`, and `replaced`.
No terminal state may transition back to a live state. Fill-before-ack observations
are representable: `pending_new` may move directly to `partially_filled` or `filled`
when venue messages arrive in that order. A rejected cancel may return
`pending_cancel` to `live` or `partially_filled`; a fill may also arrive while cancel
is pending.

Step 6 will implement stateful enforcement. Step 5 provides the transition predicate
and tests the permitted topology.

## 8. Audit-log contract

The durable audit format is canonical UTF-8 JSON Lines. Each record contains:

- schema version;
- run ID;
- zero-based contiguous append index;
- previous record SHA-256;
- complete event;
- current record SHA-256.

The first record uses 64 zeroes as its previous hash. The current hash covers the
canonical record without the `record_sha256` field, including the previous hash and
event. Canonical JSON uses sorted keys, no insignificant whitespace, UTF-8, and
forbids NaN/Infinity.

`AuditLogWriter` is single-writer and create-only:

- it refuses an existing non-empty file;
- it exposes append but no update, delete, truncate, or rewrite operation;
- it flushes and calls `fsync` after each record;
- the verifier reconstructs the complete chain and revalidates every event.

This is an integrity and reproducibility mechanism, not a claim of protection against
an attacker who can replace the complete file and its external manifest. Final run
artifacts will therefore also be covered by independent manifests and release hashes.
Cross-process locking is deferred until the event kernel has a concrete writer model.

## 9. JSON schemas

The committed Draft 2020-12 schemas are:

- `event-envelope-v1.schema.json`;
- `audit-record-v1.schema.json`;
- `instrument-definition-v1.schema.json`;
- `episode-metadata-v1.schema.json`.

The episode schema contains the metadata required by the research protocol: parent
order, benchmark, strategy/version, queue/latency/fee/impact models, seed, code
commit, and data hashes.

JSON Schema validates structure. C++ and Python validators enforce cross-field and
semantic invariants such as quantity conservation, monotonic causal times, and book
ordering.

## 10. Explicitly unresolved fields

The following are not decided in Step 5:

- selected venue, feed, and instruments;
- source timestamp accuracy and synchronization quality;
- venue sequence/gap-recovery semantics;
- equal-timestamp feed-specific ordering;
- exact tick, lot, minimum-size, and rounding metadata;
- supported venue order instructions;
- central fee and latency values;
- historical queue allocation rules;
- historical trade/order-book reconciliation rules.

They remain governed by Steps 11–16. The model has fields for them but does not
pretend they are known.
