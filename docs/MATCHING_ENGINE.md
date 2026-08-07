# C++ Price-Time-Priority Matching Engine — Step 6

## 1. Status and claim boundary

Step 6 implements the deterministic exchange-mechanics core for the project's **synthetic exact mode**. It does not claim to reproduce the rules of any named real venue. Venue-specific feed semantics, order types, fees, throttles, auction rules, and timestamp behaviour remain unresolved until Step 11 verifies a current data source from primary documentation.

The matching engine does not implement the Step 7 event scheduler, network latency, policy observations, market generation, historical replay, or execution accounting. It accepts already canonical Step 5 command objects and returns structured exchange outcomes. Step 7 will assign event times and wrap those outcomes in complete event envelopes and audit records.

The frozen research question and scope are unchanged.

## 2. Public interface

The public C++ API is defined in:

- `cpp/include/robust_execution/exchange/matching_engine.hpp`;
- `cpp/include/robust_execution/exchange/exchange.hpp`.

The implementation is split by responsibility:

- `cpp/src/exchange/matching_engine.cpp` — public façade and lifetime;
- `cpp/src/exchange/matching_engine_commands.cpp` — submit/cancel/replace validation and processing;
- `cpp/src/exchange/matching_engine_book.cpp` — price levels, matching, queries, invariants, and canonical state;
- `cpp/src/exchange/matching_engine_internal.hpp` — private implementation contract.

The principal operations are:

```cpp
SubmitResult submit(const model::OrderSubmit& command);
CancelResult cancel(const model::CancelRequest& command);
ReplaceResult replace(const model::ReplaceRequest& command);
```

Read-only queries expose:

- best bid and ask;
- aggregate displayed quantity at a price;
- bounded or complete price-level views;
- complete accepted-order history by client order ID;
- active-order count;
- crossing and fillability checks;
- a deterministic canonical state;
- explicit invariant validation.

The C++ engine owns its state, is movable but not copyable, and exposes no mutable internal iterators or containers.

## 3. Canonical units and tick/lot enforcement

Prices enter the engine as `PriceTicks` and quantities as `QuantityLots`. Therefore, fractional values that violate the instrument tick or lot increment cannot exist inside the matching engine. Raw decimal-to-canonical conversion and explicit `TickViolation` or `LotViolation` rejection belong to the venue adapter and ingestion boundary implemented after Step 11 selects a feed.

The engine itself enforces:

- positive limit prices;
- positive quantities;
- the instrument's minimum order quantity;
- the optional maximum order quantity;
- level aggregate overflow protection;
- unique accepted client order IDs;
- valid command identifiers and causal action timestamps.

This division is deliberate: a canonical integer type is stronger than repeatedly testing divisibility after conversion, but the raw adapter must still preserve and report malformed venue input.

## 4. Book representation

The bid and ask books use ordered price maps:

- bids are ordered from highest to lowest price;
- asks are ordered from lowest to highest price.

Each price level contains a linked FIFO sequence of resting orders and a checked aggregate displayed quantity. Active order indices map both exchange and client IDs to the exact resting-order location. A separate immutable-use history maps every accepted client order ID to its assigned exchange order ID and latest terminal or active state.

The implementation favours correctness and cancellation stability over premature low-level optimisation. `std::list` preserves iterators for other orders when one order is cancelled or filled. Performance and alternative memory layouts are explicitly deferred to Step 30, after profiling.

## 5. Price-time priority

Eligible prices are consumed before worse prices. At a price, the lowest `priority_sequence` executes first. The priority sequence is assigned once when an order is accepted by the synthetic exchange.

For a buy aggressor:

1. select the lowest ask;
2. stop if a limit price exists and the ask is above it;
3. consume the FIFO front order;
4. continue until the incoming quantity is exhausted or no eligible ask remains.

For a sell aggressor, the symmetric rule consumes the highest bid first.

A partially filled resting order retains its original FIFO position. A cancelled order is removed. A replacement is a new accepted order and always loses time priority, even if it keeps the same price or reduces quantity. This is an explicit synthetic-venue rule, not a claim about every real venue.

## 6. Execution-price rule

Every match executes at the resting maker's limit price. One match produces:

- one synthetic `Trade` record;
- one maker `Fill` with `LiquidityRole::Maker`;
- one taker `Fill` with `LiquidityRole::Taker`.

The two fills have the same price, quantity, and synthetic match identifier, but distinct execution IDs. Cumulative and remaining quantities are updated independently for both sides.

## 7. Supported order semantics

### 7.1 Good-til-cancelled limit orders

A GTC limit order first executes against eligible opposite-side liquidity. Any remainder rests at its limit price. Its final stored state is:

- `Live` if it received no fill;
- `PartiallyFilled` if it received at least one fill and has remaining quantity;
- `Filled` if no quantity remains.

### 7.2 Immediate-or-cancel orders

IOC is supported for limit and market orders. The accepted order executes immediately against eligible liquidity. Any remainder is cancelled automatically and returned in `automatic_cancellation`; it never rests.

The result sequence is logically:

1. acceptance acknowledgement;
2. zero or more matches;
3. automatic cancellation of any remainder.

Step 7 will assign scheduler timestamps to those outcomes.

### 7.3 Fill-or-kill orders

FOK is supported for limit and market orders. Before any mutation, the engine walks eligible levels and verifies that the entire requested quantity is available. If not, the command is rejected and the complete canonical engine state remains unchanged. If sufficient liquidity exists, the order executes in full under normal price-time priority.

### 7.4 Market orders

Market orders are allowed only with IOC or FOK. A market GTC order is rejected because the synthetic engine never rests an unpriced order.

### 7.5 Post-only orders

Post-only is supported only for GTC limit orders. If the order would execute immediately, it is rejected without assigning an exchange order ID or mutating the book. A non-crossing post-only order rests normally.

## 8. Cancellation semantics

A cancellation must provide a valid client/exchange-order pair and causal timestamps. It succeeds only while the order is active. Success:

- removes the exact FIFO node;
- subtracts its remaining quantity from the price-level aggregate;
- preserves cumulative fills;
- sets remaining quantity to zero;
- stores terminal state `Cancelled`;
- returns the cancelled quantity.

Failures distinguish:

- unknown client order;
- client/exchange ID mismatch;
- already-terminal order;
- malformed command.

The engine-local failure object may report the true terminal state. The existing Step 5 `CancelRejected` event cannot currently express this truthfully because its validator forbids terminal `resulting_state`; no Step 5 schema was silently changed. The proposed amendment is isolated in `docs/proposals/STEP5_CANCEL_REJECT_STATE_AMENDMENT.md`.

## 9. Replacement semantics

Replacement is implemented as an atomic cancel-and-new operation:

1. validate the original active order;
2. validate the new client ID, quantity, price, timestamps, and capacity;
3. only after all checks pass, remove and mark the original order `Replaced`;
4. allocate a new exchange order ID and priority sequence;
5. acknowledge the replacement;
6. execute the replacement if it crosses;
7. rest any remainder with new time priority.

A rejected replacement leaves the original order completely unchanged.

`new_quantity` means the total quantity of the new replacement order, not the original order's old total and not an incremental change to remaining quantity. The replacement inherits the original parent order and side, is a GTC limit order, and is not post-only because the Step 5 replacement command does not contain a post-only field.

## 10. Client-order-ID policy

An accepted client order ID can never be reused, including after fill, cancellation, or replacement. A command rejected before acceptance does not consume the client ID; it may be corrected and resubmitted. This behaviour is tested by rejecting an insufficient FOK order and accepting a corrected command with the same client ID.

## 11. Rejection and failure model

Submit failures return both:

- a Step 5 `OrderRejected` payload where the existing enumeration is expressive enough;
- an engine-local `EngineFailure` with a more precise code and optional current state.

The engine-local codes distinguish insufficient FOK liquidity, unsupported order/TIF combinations, identifier mismatch, quantity bounds, price errors, post-only crossing, and internal sequence exhaustion. The broad Step 5 rejection reason is retained for future event compatibility; it is not allowed to erase the more precise engine diagnosis.

## 12. Determinism

No randomness, wall clock, hash-table iteration order, or memory address enters matching decisions. IDs and priority are monotonic. Price maps and FIFO levels define all execution order.

`canonical_state()` serialises:

- next deterministic ID counters;
- bid and ask levels in matching order;
- FIFO orders at each level;
- all accepted orders sorted by exchange order ID.

The same command tape must produce byte-identical canonical state. A deterministic 400-command invariant test and a committed hand tape enforce this requirement.

## 13. Invariants

`validate_invariants()` checks at least:

1. best bid is strictly below best ask;
2. each price level has positive price and aggregate quantity;
3. each level contains at least one resting order;
4. each resting order has positive leaves quantity;
5. side and limit price agree with the containing level;
6. only `Live` or `PartiallyFilled` orders rest;
7. FIFO priority sequences increase strictly within a level;
8. aggregate level quantity equals the checked sum of order leaves;
9. active client and exchange indices agree;
10. locators agree with stored order fields;
11. active history equals the live node;
12. used client-ID history remains internally consistent.

Tests call the invariant validator after deterministic and generated command sequences, not only at the end of one happy-path example.

## 14. Complexity

With `P` price levels and `M` maker orders touched by a command:

- best bid/ask: `O(1)` from the ordered-map front;
- insertion into a level: `O(log P)` plus constant-time FIFO append;
- cancellation by exchange ID: expected `O(1)` index lookup plus `O(log P)` level lookup and constant-time list erase;
- matching: `O(M + K log P)` where `K` is the number of emptied price levels;
- FOK precheck: `O(L)` eligible levels until sufficient quantity is found;
- complete book view: `O(P)`;
- invariant validation: `O(N + P)` for `N` active orders.

These are algorithmic properties, not benchmark claims. No latency or throughput claim is made in Step 6.

## 15. Explicit exclusions

Step 6 does not implement:

- self-trade prevention or account ownership;
- hidden, iceberg, pegged, stop, discretionary, or auction orders;
- maker/taker fees or rebates;
- venue rate limits and throttling;
- amend-in-place priority variants;
- network, gateway, processing, or acknowledgement latency;
- feed publication and market-data fan-out;
- endogenous impact or order-flow response;
- historical aggregate queue reconstruction;
- concurrency or lock-free structures.

These omissions are explicit rather than silently approximated.

## 16. Validation assets

C++ tests cover:

- price priority across levels;
- FIFO priority at one level;
- partial-fill priority retention;
- maker-price execution;
- maker/taker fill symmetry;
- GTC, IOC, FOK, market, and post-only behaviour;
- minimum and maximum quantities;
- missing/unexpected price rejection;
- duplicate IDs;
- disabled configuration features;
- cancel success, unknown, mismatch, and terminal failure;
- replacement atomicity and lost priority;
- crossing replacement behaviour;
- bounded and complete book views;
- both-side fillability checks;
- output compatibility with Step 5 event validation;
- deterministic generated command sequences;
- canonical hand-tape reproduction;
- all documented invariants.

The matching engine is compiled under GCC and Clang with warnings as errors and under AddressSanitizer plus UndefinedBehaviorSanitizer.
