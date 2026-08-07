# Step 20 — Queue-aware heuristic and non-ML MPC

## Status

Step 20 implements the strongest non-learned adaptive opponents required before any ML-assisted execution comparison. The research question and frozen scope are unchanged.

The committed parameters and evidence are **synthetic validation only**. Historical activation is blocked until Gate C supplies admitted real data and the same parameters are calibrated only on the permitted development segment.

## Shared information boundary

Both controllers consume only the immutable `PolicyObservation` delivered by the Step 8 interface. They do not receive future events, hidden individual order IDs, exact historical queue position, future realized volume, future mid-price changes, or learned predictions.

Displayed same-side best quantity is treated as a **liquidity/competition proxy**, not as exact queue-ahead. Actual historical passive fills remain governed by the Step 16 optimistic/central/pessimistic queue models.

## Shared non-ML calibration

The controllers share a versioned calibration object containing:

- maker and taker fee assumptions;
- a bounded parametric passive-fill model;
- a passive adverse-selection penalty;
- an insufficient-visible-depth penalty;
- a calibration cutoff strictly before the execution episode;
- a non-empty provenance identifier.

The Step 20 fixture values are deliberately labelled synthetic. In research use these values must be frozen from the development/calibration segment before test episodes are opened.

### Parametric passive-fill score

For current same-side best displayed quantity `Q_s`, opposite-side best quantity `Q_o`, and recent trade-flow pressure `F` in `[0,1]`,

`queue_share = Q_s / (Q_s + Q_o)`

and

`p_fill = clip(p0 + w_q*(0.5 - queue_share) + w_t*(F - 0.5), 0, 1)`.

For a buy parent, `F` is the fraction of known recent aggressor volume that is sell-initiated; for a sell parent it is buy-initiated. Unknown aggressor-side trades are excluded from that ratio. This is a transparent parametric rule, not machine learning.

## Queue/liquidity-aware heuristic

The heuristic computes:

- elapsed fraction of the horizon;
- filled and remaining parent fractions;
- progress lag relative to linear time progress;
- spread;
- same/opposite best displayed depth;
- the rule-based passive-fill score.

It:

1. keeps a current passive child when the order is still at the predeclared same-side placement and urgency is low;
2. cancels stale passive children or children that conflict with urgent catch-up;
3. submits a passive child when fill conditions satisfy the predeclared threshold;
4. submits aggressively when schedule lag exceeds the threshold or the terminal-aggressive window is reached;
5. otherwise waits or catches up according to the same explicit rule.

There is no fitted price forecast.

## Non-ML receding-horizon MPC

The MPC is a genuine finite-horizon controller. At every policy observation it rebuilds and solves a local action tree over a bounded planning horizon, executes only the first action, and re-solves when the next observation arrives.

Candidate controls are:

- no action;
- passive post-only placement at the predeclared same-side offset for allowed fractions;
- aggressive IOC market execution for allowed fractions.

For computational and execution discipline, passive placement is capped at a predeclared fraction of residual inventory (`1/2` in the validation configuration). Full residual aggressive execution remains available.

### Local cost model

For each candidate plan the controller combines:

- visible-book aggressive sweep cost relative to current midpoint;
- configured taker fee;
- an explicit penalty for quantity beyond currently visible depth;
- expected passive execution at same-side best using the non-ML fill score;
- maker fee and transparent adverse-selection penalty;
- quadratic inventory-risk cost at every planning stage;
- forced aggressive terminal cost;
- linear and quadratic residual-inventory terminal penalties.

The local forecast assumes the **currently observable book and parametric fill conditions remain fixed within that local planning horizon**. This is intentionally simple and auditable. It is not claimed to be a true market forecast. Re-solving on each new observation is what makes the policy receding-horizon/adaptive.

## Deterministic tie breaking and bounds

- MPC planning horizon: at most four decisions.
- Candidate action fractions: at most four canonical reduced fractions.
- Search tree size is therefore explicitly bounded.
- Exact ties retain the earlier deterministic candidate order rather than using randomness.
- All action fractions and tick offsets must be predeclared in the common `PolicyEnvironment`.
- The action set must include full-residual execution.

## Active-child behavior

Because the primary research environment permits one acknowledged live child, an active passive child is retained only when the MPC still wants passive execution and the child remains at the current predeclared same-side price. Otherwise the controller issues a cancel first; it does not silently submit a second child.

## Research claim boundary

Step 20 does not show that either adaptive controller outperforms TWAP, Almgren–Chriss, or any later ML method. The committed realized-cost path is only an accounting/action-interface fixture. No ranking should be inferred from its shortfall numbers.
