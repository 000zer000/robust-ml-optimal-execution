# Step 2 Specification Freeze

## Completion record

- **Date:** 2026-08-06
- **Status:** Complete
- **Previous state:** Reduced-scope v1-oriented starter documents
- **Current state:** One binding full-scope flagship specification

---

## 1. What changed

The project is no longer defined as a small ML-assisted execution study with imitation learning, RL, and CUDA deferred outside completion.

The final definition now requires:

- exact synthetic matching;
- aggregate historical replay;
- classical and model-based execution;
- supervised ML and one temporal deep model;
- ML-assisted MPC;
- imitation learning;
- reinforcement learning;
- robust control/training and simulator mismatch;
- full statistical stress analysis;
- performance engineering, compiled inference, and an evidence-based CUDA/GPU decision;
- technical report and public release;
- final claim and application package.

Advanced components remain gated by correctness and scientific dependencies.

---

## 2. Corrections made from Step 1

1. **Incomplete state audit corrected:** all independent state audits must verify both lower and upper bounds for start and end states, transitions, inventory, cash, fees, and terminal conditions.
2. **Test-selected comparator prohibited:** the non-ML MPC is fixed as the primary comparator before test access.
3. **IID day bootstrap replaced:** primary inference uses contiguous-day dependence-aware blocks, with block length frozen from validation.
4. **Coverage claims scoped:** every percentage states line/branch denominator and exclusions.
5. **Artifact contract separated from rerun:** cross-file consistency and actual sample-pipeline regeneration are distinct checks.
6. **RNG reuse narrowed:** logical-index determinism is retained, but the random generator must have documented statistical-quality evidence.
7. **Venue choice reopened:** current venue/feed availability will be verified at Step 11 rather than inherited from a provisional stale decision.
8. **Terminal inventory fixed:** all strategies incur a common real terminal completion transaction.
9. **Central question preserved:** the exact user-supplied broad research question remains authoritative; ML-MPC versus MPC is only one pre-specified core confirmatory contrast within it.
10. **RL anti-exploitation rules added:** reward decomposition, action masks, sanity agents, multiple seeds, unseen regimes, and zero-shot historical evaluation are mandatory.

---

## 2.1 Authoritative central research question

> Can machine-learning-assisted execution policies improve realised execution quality relative to strong classical baselines, and do those improvements survive latency, liquidity shifts, queue-model errors, market-impact misspecification, changing fees, and out-of-distribution market regimes?

This wording is preserved verbatim. The narrower ML-MPC versus MPC comparison is a sub-question and confirmatory contrast only.

---

## 3. Frozen scientific choices

- parent-order execution rather than alpha generation;
- implementation shortfall in bps as primary metric;
- exact user-supplied central research question;
- paired ML-MPC minus MPC as a core confirmatory contrast, not a replacement question;
- completion and CVaR guardrails;
- 60-second primary horizon;
- liquidity-relative parent sizing;
- one active child order in the primary contract;
- exact synthetic versus aggregate historical separation;
- small-agent ghost replay;
- quote depletion as primary observable prediction target;
- hard chronological train/validation/calibration/test separation;
- at least two instruments;
- full mandatory method ladder;
- dependence-aware uncertainty;
- complete robustness matrix;
- process-based rather than positive-result-based completion.

---

## 4. Pre-data fields still unresolved

These are deliberately postponed to evidence-producing steps and must be frozen before final evaluation:

- venue/feed and instruments;
- exact valid-day dates and hashes;
- feed-specific timestamp/event ordering;
- queue-allocation formulas;
- central latency values;
- episode-start cadence;
- feature list and deep architecture after literature review;
- selected depletion horizon;
- RL algorithm;
- training-derived robustness thresholds;
- bootstrap block length;
- final RL seed count;
- profiled CUDA candidate.

They are not open-ended scope. Each has a resolution step and deadline in the protocol.

---

## 5. Acceptance check

Step 2 passes because:

- every reduced-scope contradiction was removed from active documents;
- the full original ambition is represented in final completion criteria;
- the exact central research question is preserved, while individual confirmatory contrasts remain focused and falsifiable;
- all mandatory advanced components have dependency gates;
- historical and synthetic claims are separated;
- Step 1 defects were converted into explicit safeguards;
- exact next action is Step 3 literature review.
