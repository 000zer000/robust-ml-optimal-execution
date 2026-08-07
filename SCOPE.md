# Scope and Definition of Done

## Document control

- **Version:** 0.2.1 — corrected full final scope
- **Status:** Binding
- **Last updated:** 2026-08-06

---

## 1. Scope policy

This project has one final scope. It is not divided into a reduced “real project” and optional keyword extensions. Deep learning, imitation learning, reinforcement learning, robustness research, performance engineering, compiled/GPU inference evaluation, a technical report, and a reproducible public release are all part of the final definition of done.

They are **dependency-gated**, not optional:

- RL cannot begin before environment and baseline validation;
- deep learning cannot bypass causal labels and simple models;
- performance work cannot precede correctness and profiling;
- a paper cannot precede stable experiments;
- public claims cannot precede evidence.

A failed empirical hypothesis is acceptable. A missing required component is not.

## 1.1 Governing research question

> Can machine-learning-assisted execution policies improve realised execution quality relative to strong classical baselines, and do those improvements survive latency, liquidity shifts, queue-model errors, market-impact misspecification, changing fees, and out-of-distribution market regimes?

This exact question is part of the binding scope. A narrower statistical contrast may be pre-specified for rigor, but it cannot replace the full comparison and robustness programme requested here.

---

## 2. Mandatory work products

### 2.1 Governance and research design

- `PROJECT_AUDIT.md`;
- `PROJECT_CONTEXT.md`;
- `RESEARCH_QUESTIONS.md`;
- `SCOPE.md`;
- `RESEARCH_PROTOCOL.md`;
- `DECISIONS.md`;
- `ROADMAP.md`;
- literature review and annotated bibliography;
- references database;
- architecture and data-contract documents;
- claim/evidence ledger;
- experiment registry and final-test access log.

### 2.2 Repository foundation

- C++20 core library;
- Python package with `src` layout;
- pybind11 bindings;
- command-line tools;
- validated configuration system;
- structured logging;
- CMake and CTest;
- Python packaging and pinned lock files;
- Docker or equivalent clean environment;
- GitHub Actions;
- code-format, lint, type, static-analysis, sanitizer, and test jobs;
- reproducible sample fixtures.

### 2.3 Exact matching and event engine

Required functionality:

- bid and ask books;
- multiple price levels;
- price-time priority;
- unique order IDs;
- limit, market, and marketable-limit handling;
- partial fills;
- cancellations and replacements;
- residual quantity;
- tick and lot rules;
- order rejection;
- acknowledgements;
- fees and rebates;
- configurable observation, processing, communication, and acknowledgement latency;
- deterministic event scheduling;
- exact queue position in synthetic mode;
- timestamped audit logs;
- inventory and cash accounting;
- hard terminal completion.

Required validation:

- hand-computed event tapes;
- price-priority and FIFO tests;
- conservation and no-negative-state invariants;
- cancellation and replacement tests;
- crossed-book prevention or documented venue rule;
- latency-ordering tests;
- deterministic replay hashes;
- property-based tests;
- reference/differential implementation tests;
- fuzzing of parsers and order APIs;
- ASan/UBSan; TSan where practical.

### 2.4 Market data and replay

- current primary-source review of candidate venues and feeds;
- licensing and redistribution assessment;
- multi-day capture or historical ingestion;
- raw byte-preserving storage;
- snapshots and incremental updates;
- sequence continuity and gap recovery;
- reconnection and duplicate handling;
- canonical UTC nanosecond timestamps plus original timestamps;
- schema versioning;
- checksums and provenance manifests;
- validation reports;
- canonical columnar datasets;
- lightweight public sample data;
- aggregate historical replay;
- optimistic, central, and pessimistic queue models;
- explicit small-agent ghost assumptions;
- replay determinism and state-reconstruction tests.

Minimum empirical breadth:

- at least two liquid instruments;
- both buy and sell parent orders;
- at least 100 validated whole days per required instrument under the split minimums;
- primary and secondary parent-size/horizon settings;
- non-overlapping sensitivity episodes.

### 2.5 Synthetic regimes

- calibrated base regime;
- varying spread, depth, volatility, order-flow intensity, clustering, and cancellation behaviour;
- exact individual-order queues;
- configurable impact and resilience;
- latency and fee models;
- regime transitions;
- adversarial shocks;
- reproducible seeds and manifests;
- calibration diagnostics against development historical data;
- explicit distinction between calibration fit and held-out validation.

### 2.6 Metrics and accounting

- implementation shortfall in quote currency and basis points;
- average execution price;
- completion and terminal cost;
- passive/aggressive fractions;
- time-to-fill and inventory trajectory;
- adverse selection;
- fees/rebates;
- variance, tail quantiles, VaR/CVaR;
- strategy actions and cancellations;
- inference/controller latency;
- event throughput and memory;
- independent accounting reconstruction;
- complete state-bound checks, including both lower and upper bounds for every state.

### 2.7 Classical and adaptive strategies

- immediate aggressive execution;
- TWAP;
- past-only volume-informed schedule;
- Almgren–Chriss;
- queue/liquidity-aware heuristic;
- non-ML model-predictive controller;
- documented mathematics, assumptions, calibration, tests, and common evaluation conditions.

### 2.8 Supervised prediction

- causal feature dictionary;
- observable target definitions;
- exact timestamp contract;
- mutation/leakage tests;
- base-rate and simple-rule baselines;
- logistic/generalised linear model;
- gradient-boosted trees;
- simple MLP;
- one compact temporal deep model;
- calibration on a separate chronological segment;
- prediction uncertainty where justified;
- temporal, instrument, regime, and latency evaluation;
- saved model cards and inference contracts.

### 2.9 ML-assisted execution

- predictions integrated into the same MPC action/constraint framework;
- primary paired comparison against non-ML MPC;
- constant, shuffled, stale, uncalibrated, and oracle ablations;
- prediction-versus-decision analysis;
- controller threshold and sensitivity analysis;
- inference latency injected into execution timing;
- negative-result preservation.

### 2.10 Imitation learning

- validated teacher policy;
- logged teacher dataset with provenance;
- behaviour-cloning policy;
- covariate-shift diagnostic;
- DAgger or another corrective method if required by the diagnostic;
- teacher-relative execution and tail-risk metrics;
- latency/throughput benchmark;
- uncertainty/fallback study;
- unseen-regime evaluation.

### 2.11 Reinforcement learning

- audited environment API;
- finite action space or rigorously bounded continuous action space;
- action masking;
- reward decomposition;
- terminal completion;
- multiple seeds;
- random, no-op, and scripted sanity agents;
- one selected RL algorithm with justified hyperparameter search;
- training curves and instability logs;
- held-out synthetic regimes;
- domain-randomised or robust training variant;
- zero-shot historical aggregate replay;
- comparison against immediate, TWAP, Almgren–Chriss, MPC, and ML-MPC;
- simulator-exploitation and reward-hacking tests.

### 2.12 Robustness and statistics

- locked test protocol;
- paired episode evaluation;
- dependence-aware block or cluster bootstrap;
- effect sizes and confidence intervals;
- multiple-seed aggregation;
- equal-instrument weighting for primary estimand;
- multiplicity control for secondary families;
- latency, liquidity, spread, volatility, queue, fee, impact, data-loss, prediction, size, horizon, instrument, and simulator-shift matrix;
- worst-case, CVaR, and ranking-stability analysis;
- failed and contradictory results retained.

### 2.13 Performance engineering

- correctness baseline;
- profiling evidence;
- memory and allocation analysis;
- single-thread baseline;
- multithread scaling;
- repeated raw timings;
- hardware/compiler/software metadata;
- Python/C++ boundary benchmark;
- model batch-one latency and batched throughput;
- compiled inference path;
- CPU/GPU comparison;
- resolved CUDA decision with either a justified implementation and profiler evidence or a measured no-go conclusion;
- end-to-end execution impact of compute latency.

### 2.14 Publication and release

- all tables and figures generated automatically;
- 10–12-page technical report excluding appendices/references;
- appendices with mathematics, tests, additional results, and reproducibility details;
- real academic references only;
- public README and architecture diagrams;
- sample data and quick reproduction;
- clean-environment verification;
- tagged GitHub release;
- changelog, license, `CITATION.cff`;
- archival bundle and Zenodo DOI when appropriate;
- claim/evidence audit;
- CV and outreach materials only after final evidence.

---

## 3. Explicitly out of scope

The following are not required and should not be silently added:

- live order submission or brokerage/exchange credentials;
- real-money deployment;
- market making, alpha generation, portfolio selection, or signal-based parent-order creation;
- smart order routing across many venues;
- options or derivatives execution;
- hidden-order and dark-pool reconstruction;
- full exchange certification or production operational resilience;
- co-location, kernel bypass, FPGA, or sub-microsecond networking;
- distributed multi-node RL training merely for scale;
- many deep or RL algorithms without a research reason;
- causal claims about endogenous historical market response under ghost replay;
- universal claims across asset classes;
- peer-review or publication acceptance guarantees.

These may become separate future projects only after the flagship is complete.

---

## 4. Non-negotiable methodological constraints

1. No final-test model or strategy selection.
2. No random row-level train/test split.
3. No future event in features, labels, queue state, or policy observation.
4. No exact historical FIFO claim from aggregate level-2 data.
5. No incomplete inventory omitted from implementation shortfall.
6. No baseline receives worse information or constraints to help ML.
7. No primary comparator chosen after seeing final results.
8. No IID observation bootstrap for serially dependent episodes.
9. No performance claim without repeated fixed-hardware evidence.
10. No coverage percentage without stating scope and exclusions.
11. No artifact-consistency check described as a full pipeline rerun.
12. No custom random stream used for scientific work without deterministic tests and statistical-quality evaluation.
13. No RL before simulator and reward audits pass.
14. No CUDA keyword without a measured end-to-end question.
15. No manually typed paper result that is not linked to generated evidence.
16. No confidential employer data or logic.

---

## 5. Stage gates

### Gate A — Specification

Passes when the audit, questions, scope, protocol, decisions, and roadmap are internally consistent and contain no reduced-scope contradiction.

### Gate B — Simulator

Passes only after all exact-engine invariants, hand tapes, differential tests, fuzz tests, determinism checks, and sanitizers pass.

### Gate C — Data

Passes only after continuity, schema, timestamp, provenance, replay, and sample-reproduction checks pass for the required instruments and days.

### Gate D — Classical strategies

Passes when every classical/adaptive strategy has mathematics, tests, fair calibration, and valid accounting.

### Gate E — Supervised learning

Passes when target and feature contracts, split isolation, leakage tests, simple baselines, calibration, and locked prediction artifacts are valid.

### Gate F — ML-assisted execution

Passes when primary-controller integration, ablations, common constraints, and development-period stress tests are stable.

### Gate G — Imitation learning

Passes when teacher data, policy training, covariate-shift analysis, and OOD fallback evaluation are complete.

### Gate H — RL

Passes when environment/reward audits, sanity agents, multi-seed training, strong baselines, unseen regimes, and historical zero-shot tests are complete.

### Gate I — Robustness/statistics

Passes when the test lock is respected, dependence-aware intervals and multiplicity controls are applied, and the full stress matrix is generated.

### Gate J — Performance

Passes when profiling, raw timings, correctness-after-optimisation, compiled inference, CPU/GPU comparison, and CUDA decision are documented.

### Gate K — Release

Passes when clean reproduction, artifact regeneration, report, limitations, claim audit, release tag, and archival package are complete.

No later gate can retroactively excuse failure of an earlier gate.

---

## 6. Definition of done

The project is complete only when every mandatory work product and Gate A–K criterion is satisfied.

A method may fail to outperform. A model may be unhelpful. RL may lose. CUDA may be slower. These are valid findings.

The project is **not** complete if any required component is absent, if the final test was contaminated, if results cannot be regenerated, if historical queue/impact claims exceed the data, or if Othmane cannot defend the implemented assumptions and evidence.
