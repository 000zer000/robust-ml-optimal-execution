# Full Project Roadmap

## Document control

- **Version:** 0.5.0
- **Status:** 32-step binding roadmap
- **Current position:** Step 8 complete
- **Last updated:** 2026-08-06

The project proceeds one gated step at a time. A step is complete only when its deliverables and acceptance criteria are satisfied. Advanced work remains in the full final scope but cannot bypass dependencies.

---

## Phase A — Research foundation and repository

### Step 1 — Audit existing work — COMPLETE

Deliverable: `PROJECT_AUDIT.md`.

### Step 2 — Freeze the complete research specification — COMPLETE

Deliverables:

- `PROJECT_CONTEXT.md`;
- `RESEARCH_QUESTIONS.md`;
- `SCOPE.md`;
- revised `RESEARCH_PROTOCOL.md`;
- revised `DECISIONS.md`;
- revised roadmap and README;
- specification-freeze manifest.

Acceptance:

- full scope replaces reduced-v1 assumptions;
- primary estimand/comparator/guardrails fixed;
- two-mode claim boundary fixed;
- IL, RL, deep, robustness, performance, and publication included in final definition;
- Step 1 defects corrected in the new standard;
- unresolved data-dependent fields explicitly listed.

### Step 3 — Academic literature review — COMPLETE

Study primary sources on optimal execution, limit-order-book models, queue dynamics, fill/adverse-selection prediction, decision-focused learning, imitation, RL, robustness, and simulator mismatch.

Deliverables: `LITERATURE_REVIEW.md`, `references.bib`, annotated bibliography, design-evidence matrix.

Acceptance: every major modelling choice is supported, rejected with reason, or labelled an engineering assumption.

### Step 4 — Bootstrap the complete repository — COMPLETE

Create C++/Python packages, CMake, pybind11, tests, CI, Docker, configuration, logging, dependency locks, sanitizers, static analysis, and reproducibility commands.

Acceptance: clean Linux build and test; second platform/compiler path; deterministic sample command.

---

## Phase B — Exact limit-order-book simulator

### Step 5 — Event and market-data model — COMPLETE

Freeze fixed-point types, event schemas, clocks, sequence/order IDs, order states, acknowledgements, fills, fees, latency, and audit-log schema.

### Step 6 — C++ order book and matching — COMPLETE

Implement price-time priority, market/limit orders, partial fills, cancellations, replacements, tick/lot/rejection rules.

### Step 7 — Event-driven kernel and latency — COMPLETE

Implement deterministic scheduler, observation/processing/network/ack latency, seeded logical randomness, replay hashes.

### Step 8 — Execution-policy interfaces — COMPLETE

Implemented causal observations, common action contract, inventory/cash, active-order state, terminal completion.

### Step 9 — Synthetic market generator

Implement calibrated and adversarial regimes, order-flow clustering, liquidity/spread/volatility transitions, impact/resilience, fees, and shocks.

### Step 10 — Simulator validation gate

Hand tapes, invariants, property tests, differential reference, fuzzing, determinism, ASan/UBSan/TSan where practical.

Acceptance: Gate B passes; no data science or RL proceeds earlier.

---

## Phase C — Real data and historical replay

### Step 11 — Select current market-data sources

Verify venue/feed semantics, licensing, historical/current access, sequence recovery, instruments, timestamps, and storage cost using primary sources.

### Step 12 — Raw capture or ingestion

Implement snapshots, incremental updates, reconnects, gap/duplicate detection, raw compression, manifests, checksums.

### Step 13 — Data validation

Validate schema, sequences, timestamps, book states, trades, continuity, invalid spans, and provenance.

### Step 14 — Canonical datasets

Produce raw/interim/processed/sample layers and columnar event datasets with versioned schemas.

### Step 15 — Historical replay

Reconstruct observed books deterministically and expose causal strategy observations.

### Step 16 — Queue models

Implement optimistic, central, pessimistic queue-ahead and cancellation-allocation assumptions; validate sensitivity and metadata.

Acceptance: Gate C passes and minimum instrument/day requirements are met.

---

## Phase D — Metrics and classical execution

### Step 17 — Accounting and metrics

Implement implementation shortfall, completion, inventory, fees, adverse selection, tails, CVaR, latency, throughput, memory, and complete independent audits.

### Step 18 — Basic schedules

Immediate, TWAP, past-only volume-informed, passive/aggressive variants where valid.

### Step 19 — Almgren–Chriss

Derive, implement, calibrate, and test discrete optimal schedules and limiting cases.

### Step 20 — Queue-aware heuristic and MPC

Implement strongest non-ML adaptive baselines under the common action/information contract.

Acceptance: Gate D passes before learned execution comparisons.

---

## Phase E — Supervised learning and decision integration

### Step 21 — Causal targets and features

Implement quote-depletion and adverse-selection labels, feature dictionary, timestamp contract, mutation/leakage tests.

### Step 22 — Interpretable/simple models

Base rate, logistic/GLM, boosted trees, MLP, calibration diagnostics, temporal/instrument slices.

### Step 23 — One serious temporal deep model

Select from literature, train with frozen protocol, compare calibration, decision value, compute, and OOD behaviour.

### Step 24 — ML-assisted MPC

Integrate calibrated predictions into the same MPC; produce deterministic prediction artifacts and controller ablations.

### Step 25 — Prediction versus decision value

Run constant/shuffled/stale/uncalibrated/oracle ablations and identify where predictive improvements do or do not alter execution.

Acceptance: Gates E and F pass before learning-based policy work.

---

## Phase F — Learning-based policies

### Step 26 — Imitation learning

Train behaviour cloning from the teacher, diagnose covariate shift, add DAgger/correction if needed, benchmark quality and speed under ID/OOD states.

### Step 27 — Reinforcement learning

Audit environment/reward, train one primary RL policy over multiple seeds, compare with strong baselines, test unseen synthetic regimes and zero-shot historical replay.

Acceptance: Gates G and H pass; no best-seed or simulator-profit claim.

---

## Phase G — Robustness and performance

### Step 28 — Complete robustness matrix

Latency, decision grid, liquidity, spread, volatility, queue error, fees, size, horizon, impact, prediction degradation, data loss, temporal/instrument shift, simulator mismatch.

### Step 29 — Rigorous statistical analysis

Locked test, paired aggregation, dependence-aware block bootstrap, guardrails, multiplicity, effect sizes, negative results, ranking stability.

### Step 30 — Performance engineering and CUDA decision

Profile, optimise C++ engine and inference, rerun correctness, measure CPU scaling, compiled inference, GPU/CUDA path or measured no-go, inject compute latency into execution.

Acceptance: Gates I and J pass.

---

## Phase H — Report, release, and application outputs

### Step 31 — Technical report and public release

Generate all tables/figures, write report/appendices, clean reproduction, Docker/sample data, release tag, `CITATION.cff`, changelog, archive/DOI.

### Step 32 — Red-team audit and application package

Audit leakage, claims, citations, evidence, reproducibility, installation, limitations, and every CV number. Prepare audience-specific bullets, summaries, interview defence, one-page overview, and professor-paper outreach workflow.

Acceptance: Gate K and the full `SCOPE.md` definition of done pass.

---

## Current next action

**Step 30 — Performance engineering and CUDA decision.** Step 29 engineering statistical
validation is complete; the historical Tier-1 confirmatory analysis remains blocked by Gate C, so
Gate I is not promoted to a historical-statistics pass.
