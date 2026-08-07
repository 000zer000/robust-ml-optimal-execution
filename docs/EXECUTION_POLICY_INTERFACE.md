# Step 8 — Execution-policy interface and causal observation contract

## 1. Scope

Step 8 defines one execution interface for every later baseline, optimiser and learned policy. It does not implement a trading strategy, market generator, queue model, fee model, impact model or empirical experiment.

The executable C++ source of truth is `cpp/include/robust_execution/policy/`. Versioned JSON interchange schemas are under `schemas/policy/`.

## 2. Parent-order contract

A parent order fixes:

- parent-order ID;
- side;
- total quantity in integer lots;
- start and terminal timestamps in one clock domain;
- positive arrival price in integer ticks;
- terminal-completion rule ID.

The parent snapshot reports cumulative fill, residual inventory, signed gross cash flow, explicit fees, net cash flow, fill count and status. Status is derived as pending, active, terminal-completion pending or completed.

### Cash sign convention

- Buy executions produce negative gross cash flow.
- Sell executions produce positive gross cash flow.
- Positive fees reduce net cash flow.
- Negative fees represent rebates and increase net cash flow.
- `net_cash_flow = gross_cash_flow - explicit_fees`.

Price, quantity and quote-atom conversion uses exact rational instrument increments with overflow checks. No floating-point notional is used.

## 3. Causal observation boundary

A policy may observe only events that have reached observer availability in the Step 7 kernel. Exchange-received events and future market events are audit data, not policy inputs.

`ObservationBuilder` enforces:

- canonical event validation;
- matching venue and instrument;
- an available timestamp not later than delivery;
- monotonically non-decreasing delivery time;
- an uncrossed visible book;
- top-K depth truncation;
- bounded recent-trade history;
- a rolling SHA-256 lineage over delivered canonical events.

The immutable `PolicyObservation` includes:

- decision ID and time;
- maximum causal market-event cutoff;
- strategy, fee-schedule and latency-model IDs;
- parent-order accounting state;
- top-K bid and ask levels;
- recent delivered trades;
- acknowledged active child orders;
- pending-command count;
- delivered-event lineage;
- elapsed time and time remaining;
- deterministic canonical representation and hash.

The observation does not claim that the visible book is current at exchange time. It is exactly the possibly stale state causally available to the strategy.

## 4. Child-order state

`ExecutionState` is the shared accounting and lifecycle authority. Strategies do not maintain independent inventory or cash ledgers.

It tracks:

- pending submits, cancels and replacements;
- acknowledgement and exchange IDs;
- requested, filled and leaves quantities;
- live, partially filled and terminal child states;
- exact parent fill and cash effects;
- fees matched to known execution IDs and the configured fee schedule;
- explicit terminal completion.

Unknown unrelated market events do not mutate owned-order state. Duplicate event, execution and fee IDs are rejected. Fill increments, cumulative quantity and leaves must conserve the tracked requested quantity.

The unapproved Step 5 `AlreadyTerminal` schema amendment remains unapplied. Engine-local failure objects resolve truthful terminal cancel/replace outcomes without emitting a contradictory canonical rejection event.

## 5. Common action contract

Every policy emits one of:

1. no action;
2. submit a child order;
3. cancel acknowledged active children;
4. replace one acknowledged active child.

Submit and replace quantities are selected from predeclared rational fractions of residual parent inventory and converted using the configured lot-rounding rule. Limit prices are expressed relative to same-side or opposite-side best quote with a predeclared integer tick offset.

`ActionValidator` enforces the same constraints for all strategies:

- decision ID/time consistency;
- matching policy environment;
- parent activity and residual inventory;
- unique client IDs;
- allowed quantity fractions and tick offsets;
- non-zero rounded quantity;
- live-child and commands-per-decision limits;
- market, marketable-limit and post-only permissions;
- valid time-in-force combinations;
- no command while another child command is pending.

A no-op remains valid after parent completion so a finished policy can be called safely without creating a false validation failure.

## 6. Explicit experiment configuration

Step 8 does not silently choose final experimental values. The following are explicit `PolicyEnvironment` fields and remain versioned experiment choices:

- decision interval;
- top-K depth;
- recent-trade capacity;
- maximum live children;
- maximum commands per decision;
- allowed quantity fractions;
- allowed tick offsets;
- lot-rounding rule;
- market-order, marketable-limit and post-only permissions;
- strategy, fee and latency configuration IDs.

The default research constraint remains at most one acknowledged live child order. Sensitivities can change the configuration later without changing the interface.

## 7. Terminal completion

Hard completion is a controlled sequence:

1. wait for commands already in flight;
2. cancel acknowledged live children;
3. submit the full residual as a market IOC;
4. after the configured aggressive-attempt budget is exhausted, require an explicit mode-specific completion price and fee;
5. deliver a canonical `TerminalCompletion` system event through the kernel;
6. apply the event to the shared parent accounting state.

The fallback never invents a price. Synthetic exact mode and historical aggregate replay must supply their own documented price and fee rule in later steps.

## 8. Current limitations

- Step 9 has not yet generated endogenous market events or impact.
- Historical replay and queue assumptions do not exist yet.
- Fee IDs are checked, but fee calculation belongs to later venue/model configuration.
- No concrete execution policy is implemented beyond the interface test double and terminal controller.
- The JSON schemas define interchange fields; complete production pybind serialization is deferred until Python policy implementations are introduced.
- No performance or execution-quality claim is made.
