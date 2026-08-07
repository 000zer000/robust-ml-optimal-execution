# Step 8 local design decisions

These decisions implement the already approved roadmap. They do not amend the frozen research specification.

## P8-001 — One shared state authority

Inventory, fills, child lifecycle, cash and fees are maintained by `ExecutionState`, not separately by each strategy. This prevents strategy-specific accounting drift.

## P8-002 — Delivered information only

`ObservationBuilder` accepts only canonical events whose availability time has arrived. Kernel audit data that has not been delivered cannot enter an observation.

## P8-003 — Configuration, not hidden constants

Action fractions, tick offsets, rounding, decision interval, depth, history limits and child-order limits are explicit environment fields. Step 8 does not freeze data-dependent experiment values.

## P8-004 — Integer/rational accounting

Notional conversion remains exact in integer quote atoms using instrument rational increments. Floating-point cash state is prohibited.

## P8-005 — No-op after completion

A valid no-op is allowed for a completed parent order. Any state-changing action remains invalid after completion.

## P8-006 — Explicit terminal fallback

If aggressive IOC completion leaves inventory, the kernel requires a named mode-specific fallback price and fee. Step 8 supplies no hidden synthetic or historical pricing assumption.

## P8-007 — Prior schema proposal remains unapproved

Step 8 does not change `CancelRejected` or `ReplaceRejected`. Truthful `AlreadyTerminal` handling stays in the engine-local failure path pending explicit user approval.

## P8-008 — C++ authority with versioned JSON interchange

The C++ contract is executable authority. Draft 2020-12 schemas provide stable language/process interchange without claiming that all Python strategy bindings already exist.
