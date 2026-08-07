# Decision Log

## Document control

- **Version:** 0.2.0
- **Project:** Robust Execution Flagship
- **Last updated:** 2026-08-06

Decisions are never silently deleted. Superseded choices remain visible so the evolution of the project can be audited.

---

## 1. Superseded initial-scope decisions

The initial starter documents were deliberately reduced to a narrow v1.0. The user subsequently made the full original project the binding target. The following initial decisions are superseded:

| Initial decision | New status | Superseding decision |
|---|---|---|
| Reduce v1.0 to one research loop | Superseded | D-101 |
| Coinbase as provisional primary source | Reopened pending current source review | D-102 |
| Deep learning gated and potentially absent | Superseded for final scope; still dependency-gated | D-111 |
| RL outside v1.0 | Superseded; RL required in final scope | D-113 |
| Imitation learning deferred | Superseded; imitation required in final scope | D-112 |
| CUDA deferred as optional | Superseded; CUDA/GPU decision study required | D-116 |

The archived initial documents are retained under `archive/initial-reduced-scope-draft/`.

---

## D-101 — One complete full-scope flagship project

**Status:** Accepted  
**Date:** 2026-08-06

### Decision

The final project includes the exact simulator, historical replay, classical execution, supervised ML, one deep temporal model, ML-assisted control, imitation learning, RL, robustness, simulator mismatch, performance engineering, compiled/GPU inference evaluation, a technical report, and a public release.

### Rationale

This is the user's explicit project objective. Scientific quality is protected through dependency gates rather than by deleting advanced components.

### Consequences

No partial release or narrow v1 counts as project completion. Negative results do count when the required study is complete.

---

## D-102 — Reopen venue and data-source selection

**Status:** Accepted  
**Date:** 2026-08-06

### Decision

Do not freeze Coinbase or any venue in Step 2. Step 11 will verify current public access, feed semantics, historical coverage, licensing, sequencing, and reliability from primary sources before selection.

### Rationale

Data availability and exchange documentation are time-sensitive. A stale provisional choice is not a rigorous specification.

### Consequences

Venue-independent interfaces are required. Exact instruments, central latency, and queue semantics remain pre-data fields.

---

## D-103 — Separate exact synthetic matching and aggregate historical replay

**Status:** Accepted  
**Date:** 2026-08-06

### Decision

Maintain two explicit modes:

1. exact individual-order price-time-priority simulation;
2. aggregate level-2 historical replay with queue assumptions.

### Rationale

Aggregate data cannot generally reconstruct exact order identity or FIFO position.

### Consequences

Mode is stored in every result. Cross-mode disagreement is analysed rather than averaged away.

---

## D-104 — Small-agent ghost replay for historical data

**Status:** Accepted  
**Date:** 2026-08-06

### Decision

Simulated historical orders may receive counterfactual fills but do not alter the later recorded market path. Primary historical parent sizes remain within a development-data-defined small-agent envelope.

### Rationale

Changing the future recorded path without a validated response model would fabricate causality.

### Consequences

Historical replay does not prove endogenous impact. Larger-size/impact questions are answered in synthetic exact mode or explicit stress studies.

---

## D-105 — Hard terminal completion and common accounting

**Status:** Accepted  
**Date:** 2026-08-06

### Decision

Every strategy must complete residual inventory at the deadline using the same aggressive rule. Reported implementation shortfall includes this transaction and all explicit fees/rebates.

### Rationale

Residual inventory cannot be omitted or represented only by an arbitrary penalty.

### Consequences

Completion, terminal fraction, and forced cost are separately reported.

---

## D-106 — Primary comparator and estimand are fixed

**Status:** Accepted  
**Date:** 2026-08-06

### Decision

The exact central research question remains the broad user-supplied question. ML-assisted MPC minus the same non-ML MPC on paired locked-test episodes is one core confirmatory contrast within that question. Its metric is implementation shortfall in basis points.

### Rationale

Comparing the same controller with and without ML isolates the incremental decision value of the prediction layer better than comparing only with TWAP.

### Consequences

The comparator cannot be selected from final-test results. Other strategies are secondary comparisons.

---

## D-107 — Mean-cost superiority requires guardrails

**Status:** Accepted  
**Date:** 2026-08-06

### Decision

Primary superiority requires a 95% interval for mean shortfall below zero, a lower 95% confidence bound for the completion-rate difference of at least -1 percentage point, and an upper 95% confidence bound for the CVaR95 difference no greater than the larger of 1 basis point or 5% of the absolute comparator CVaR95.

### Rationale

A strategy should not be called superior if it lowers average cost by accepting materially worse completion or tail risk.

### Consequences

Guardrail failure produces a trade-off conclusion.

---

## D-108 — Chronological four-segment split

**Status:** Accepted  
**Date:** 2026-08-06

### Decision

Use whole-day 50% train, 20% validation, 10% calibration/protocol-freeze, and 20% locked-test segments, with minimum 50/20/10/20 valid days per required instrument.

### Rationale

A separate calibration segment prevents probability calibration and final threshold selection from contaminating the test.

### Consequences

More data must be collected if minima are not met. Random row-level mixing is prohibited.

---

## D-109 — Primary parent-order contract

**Status:** Accepted  
**Date:** 2026-08-06

### Decision

Primary horizon is 60 seconds. Primary historical size is 25% of training-period median top-five opposite-side depth in an instrument/time bucket. Required sensitivities are 30/300 seconds and 10%/50%/100% sizes.

### Rationale

Relative sizing creates comparable difficulty across instruments without using future test liquidity.

### Consequences

The 100% historical setting is labelled stress under the ghost assumption.

---

## D-110 — Observable depletion target, not exact fill label

**Status:** Accepted  
**Date:** 2026-08-06

### Decision

Primary supervised target is best-quote depletion or trade-through at a selected short horizon. The controller combines this observable prediction with an explicit queue model.

### Rationale

Exact personal fill labels are not directly observable in aggregate level-2 data.

### Consequences

Outputs are described as depletion probabilities, not exact fill probabilities.

---

## D-111 — Required model complexity ladder

**Status:** Accepted  
**Date:** 2026-08-06

### Decision

The final project requires base-rate/rule models, linear probabilistic models, boosted trees, a simple MLP, and one compact temporal deep model. Simple models are completed first.

### Rationale

This permits an evidence-based complexity comparison while avoiding a superficial architecture zoo.

### Consequences

The deep model is mandatory in the final scope but cannot start before causal labels and simple baselines pass.

---

## D-112 — Imitation learning is required and teacher-gated

**Status:** Accepted  
**Date:** 2026-08-06

### Decision

Train an imitation policy after the MPC teacher is validated. Behaviour cloning is required; a covariate-shift correction is added if diagnostics show compounding error.

### Rationale

The research question is whether learned inference can approximate expensive control, not merely whether actions can be classified offline.

### Consequences

Teacher-relative execution and OOD rollout metrics are mandatory.

---

## D-113 — RL is required but cannot be foundational

**Status:** Accepted  
**Date:** 2026-08-06

### Decision

Implement one primary RL policy after simulator, data, baseline, supervised, reward, and terminal-completion gates pass.

### Rationale

RL is scientifically meaningful only in an audited environment with strong comparators.

### Consequences

RL failure does not invalidate the project. Reward hacking, best-seed selection, or test fine-tuning invalidates the RL claim.

---

## D-114 — RL trains in synthetic exact mode and transfers zero-shot

**Status:** Accepted  
**Date:** 2026-08-06

### Decision

RL training uses calibrated synthetic exact environments with domain randomisation. Final transfer includes unseen synthetic regimes and zero-shot aggregate historical replay.

### Rationale

Interactive historical data cannot reveal the causal market response to counterfactual orders, while exact synthetic mode can support controlled RL transitions.

### Consequences

No historical-test fine-tuning. Simulator mismatch becomes a principal analysis.

---

## D-115 — Precomputed predictions for primary scientific replay; compiled path for systems study

**Status:** Accepted  
**Date:** 2026-08-06

### Decision

Primary scientific experiments consume timestamp-keyed prediction artifacts for deterministic comparison. A separate systems phase integrates compiled inference and measures real batch-one latency, which is injected into execution timing.

### Rationale

This separates model/decision effects from integration noise while still answering end-to-end compute questions.

### Consequences

Precomputed inference is not described as production deployment. Compiled inference is mandatory later.

---

## D-116 — Resolve CUDA by profiling and end-to-end evidence

**Status:** Accepted  
**Date:** 2026-08-06

### Decision

The final project must evaluate a CUDA/GPU path. A custom CUDA component is implemented only if profiling identifies a suitable bottleneck; otherwise a measured no-go result must show why CPU or compiled inference is better for the relevant latency/throughput regime.

### Rationale

Forcing an irrelevant kernel is less credible than a rigorous CPU/GPU decision.

### Consequences

The project cannot simply omit CUDA discussion or claim CUDA because PyTorch used a GPU.

---

## D-117 — Fixed-point market quantities in the C++ core

**Status:** Accepted  
**Date:** 2026-08-06

### Decision

Represent prices in integer ticks and quantities in integer lots or another exact fixed-point type. Floating point may be used for analytics and model outputs outside matching comparisons.

### Rationale

Book ordering and quantity conservation require exact comparison and arithmetic.

### Consequences

Conversions are checked and venue-specific tick/lot metadata are versioned.

---

## D-118 — Logical-index deterministic RNG with quality evaluation

**Status:** Accepted  
**Date:** 2026-08-06

### Decision

Synthetic randomness is keyed by experiment seed and logical event identity, not worker scheduling. The selected generator must have documented statistical-quality testing or be a well-established counter-based generator.

### Rationale

The prior path-indexed pattern is valuable, but a custom stream without a documented test battery should not be copied blindly.

### Consequences

Bitwise, numerical, and statistical reproducibility claims are separated.

---

## D-119 — Dependence-aware statistical inference

**Status:** Accepted  
**Date:** 2026-08-06

### Decision

Primary intervals resample contiguous day blocks within instrument. IID episode or IID day resampling is not used for primary inference.

### Rationale

Nearby market episodes and adjacent days may be serially dependent.

### Consequences

Block length is selected on validation by a frozen autocorrelation rule. Non-overlapping sensitivity is required.

---

## D-120 — No final-test baseline selection

**Status:** Accepted  
**Date:** 2026-08-06

### Decision

All primary comparators, thresholds, models, and aggregation rules are frozen before test access. The “best” test baseline may be described only exploratorily and cannot define a confirmatory interval.

### Rationale

Selecting a comparator on the test and testing against it on the same data creates selection bias.

### Consequences

The primary MPC comparator is fixed now.

---

## D-121 — Complete independent state and accounting audits

**Status:** Accepted  
**Date:** 2026-08-06

### Decision

Independent audits must check both lower and upper bounds for every state, transitions, action exclusivity, inventory, cash, fees, terminal conditions, and objective reconstruction.

### Rationale

The existing battery project omitted complementary state-bound checks in its independent audit. The new project will not repeat that defect.

### Consequences

Solver success alone is insufficient evidence.

---

## D-122 — Coverage and artifact claims must state scope

**Status:** Accepted  
**Date:** 2026-08-06

### Decision

Coverage reports state branch/line scope and every excluded module. Artifact consistency and full regeneration are separate CI jobs and separate claims.

### Rationale

A scoped percentage and a cross-file consistency check must not be overstated.

### Consequences

CLI/reporting exclusions require explicit justification or testing through integration/end-to-end jobs.

---

## D-123 — Final-test access and amendment ledger

**Status:** Accepted  
**Date:** 2026-08-06

### Decision

Loading locked outcomes requires an explicit command flag and writes an access record. Post-open changes follow the test-invalidation policy and retain original results.

### Rationale

A locked test is a process, not only a date range.

### Consequences

Repeated hidden tuning cannot be presented as confirmation.

---

## D-124 — One active child order in the primary contract

**Status:** Accepted  
**Date:** 2026-08-06

### Decision

The primary strategy interface permits at most one live child order for the parent at a time. A multi-order study is a separately labelled extension within the repository.

### Rationale

This keeps queue and action comparisons interpretable across classical, MPC, imitation, and RL policies.

### Consequences

The engine still supports many orders from market participants and can later support multiple agent child orders.

---

## D-125 — Full completion is process-based, not result-based

**Status:** Accepted  
**Date:** 2026-08-06

### Decision

The project is complete when every mandatory component, audit, comparison, stress study, reproducibility path, and report is complete. No method is required to win.

### Rationale

Forcing a positive result creates cherry-picking risk.

### Consequences

Negative ML, RL, deep-learning, or CUDA findings remain publishable project results.

---

## D-121 — Restore the exact central research question

**Date:** 2026-08-06  
**Status:** Accepted; corrective amendment

### Decision

The authoritative central research question is restored verbatim:

> Can machine-learning-assisted execution policies improve realised execution quality relative to strong classical baselines, and do those improvements survive latency, liquidity shifts, queue-model errors, market-impact misspecification, changing fees, and out-of-distribution market regimes?

The ML-assisted-MPC versus non-ML-MPC comparison remains a pre-specified core confirmatory contrast only. It must never be presented as a replacement for the broader question.

### Rationale

The Step 2 draft improperly replaced the user-supplied broad question with a narrower one. That violated the project instruction to preserve the exact research objective.

### Consequences

All active governance documents must state the exact central question and distinguish it from narrower sub-questions, hypotheses, and statistical contrasts.
