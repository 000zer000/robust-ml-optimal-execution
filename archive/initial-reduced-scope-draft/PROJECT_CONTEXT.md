# PROJECT_CONTEXT.md

## Document control

- **Project:** Robust Execution
- **Working title:** *Learning Robust Execution Policies in Limit Order Books: Prediction, Optimisation and Stress Testing under Latency and Regime Shifts*
- **Version:** 0.1.0 — scope baseline
- **Status:** Phase 0, specification and repository bootstrap
- **Last updated:** 2026-08-06
- **Owner:** Othmane Hassani

This file is the durable source of truth for the project's purpose, scope, assumptions, current state, and next action. It must be updated whenever a major decision changes the research question, experimental protocol, architecture, or claims that may later appear on the CV, GitHub, or in professor outreach.

---

## 1. Owner profile and intended use

Othmane Hassani is an ESILV engineering student in Paris, expected to graduate in June 2028 with a Financial Engineering major and an HPC-AI track. His relevant completed background includes probability and statistics, linear algebra, statistical modelling, machine learning, algorithms, Python, C++, SQL, numerical optimisation, Monte Carlo simulation, testing, continuous integration, and reproducible time-series evaluation. He was ranked first in an approximately 70-student cohort at EIGSI.

Existing evidence relevant to this project includes:

1. A C++/Python derivatives pricing and risk engine with Black–Scholes, Monte Carlo estimators, variance reduction, numerical validation, CMake, pybind11, CTest, OpenMP, sanitizers, and fixed-hardware benchmarking.
2. A European power-market research platform with provenance checks, timestamp validation, chronological model development, an isolated test period, optimisation, bootstrap intervals, sensitivity analysis, automated tests, and reproducible outputs.
3. Internship work involving Python reconciliation of heterogeneous financial reports, infrastructure monitoring and anomaly detection, and ELK/SIEM analysis.

The project has two linked objectives:

- **Research objective:** produce a controlled, reproducible study of whether a calibrated short-horizon limit-order-book signal improves execution decisions and whether any improvement survives realistic forms of misspecification.
- **Career objective:** demonstrate research judgement, quantitative methodology, C++ systems design, Python experimentation, optimisation, testing, and performance analysis for professor outreach, quantitative research/development, hedge-fund software engineering, and systems-oriented Big Tech roles.

This is not a live-trading system, a profitability claim, or an attempt to imitate institutional production infrastructure.

---

## 2. Concise project definition

The project will build and validate a deterministic C++/Python execution-research platform that compares strong classical execution strategies with a machine-learning-assisted queue-aware controller. The central experiment asks whether a calibrated prediction of near-term quote depletion improves realised execution quality on held-out limit-order-book data, and whether any advantage remains under latency, liquidity shifts, fee changes, queue-position error, degraded predictions, and synthetic regime stress.

The project deliberately separates:

- an **exact synthetic matching-engine mode**, where individual orders, FIFO priority, cancellations, and fills are known;
- an **aggregate historical-replay mode**, where public level-2 updates are replayed and queue position must be approximated honestly.

That separation prevents the repository from claiming exact queue reconstruction from data that does not contain order identifiers.

---

## 3. v1.0 scope

### 3.1 In scope

#### Markets and data

- Primary venue: Coinbase Exchange public level-2 market data.
- Initial instruments: BTC-USD and ETH-USD.
- Raw capture: level-2 updates, trades, heartbeats, connection metadata, and sequence diagnostics.
- Minimum research dataset target: six usable calendar weeks after a successful pilot capture.
- Historical mode: aggregate price-level replay with explicit queue and small-agent assumptions.
- Synthetic mode: event-driven price-time-priority matching with exact order identities.

#### Execution problem

- Predetermined parent buy or sell order.
- Finite liquidation horizon.
- Child actions limited to a controlled set such as:
  - wait;
  - submit or retain a passive order at the best quote;
  - cancel/replace;
  - execute an aggressive child order;
  - force terminal completion.
- Parent size fixed at episode start using only pre-episode information.
- Episode horizons and size regimes varied through predefined sensitivity grids.

#### Strategies

1. Immediate aggressive execution.
2. TWAP.
3. A volume-profile schedule using only past data.
4. Almgren–Chriss schedule.
5. Non-ML queue-aware adaptive controller.
6. ML-assisted queue-aware receding-horizon controller.

All strategies run on identical episodes, latency settings, fees, queue assumptions, and terminal-completion rules.

#### Machine-learning layer

The v1.0 supervised target is:

> The probability that the relevant best-quote queue depletes, or the market trades through that quote, within a fixed short horizon.

The target is observable from aggregate level-2 replay more honestly than an exact personal fill label. The controller combines this probability with queue-ahead and latency assumptions to estimate whether passive placement is worthwhile.

Models included in v1.0:

- logistic regression;
- a regularised linear alternative if justified;
- histogram gradient-boosted trees;
- probability calibration where needed.

A compact temporal neural model is a gated stretch task, not a v1.0 requirement.

#### Evaluation

- Chronological train, validation, and locked final-test periods.
- Paired evaluation on the same episodes.
- Implementation shortfall as the primary execution metric.
- Tail cost, completion, residual inventory, fill behaviour, adverse selection, cancellation rate, and computational latency as secondary metrics.
- Paired bootstrap confidence intervals, effect sizes, sensitivity analysis, ablations, and explicit negative results.
- Stress tests for latency, spread, depth, volatility, fees, queue-ahead error, prediction degradation, and synthetic regime shifts.

#### Engineering

- Modern C++ core and Python research layer.
- CMake, CTest plus a C++ test framework, pybind11, pytest, type checking, formatting, linting, GitHub Actions, ASan, and UBSan.
- Integer timestamps and deterministic event ordering.
- Configuration-driven experiments.
- Raw experiment outputs retained; tables and figures generated automatically.
- One-command fast test and reproducibility path.

### 3.2 Explicitly out of scope for v1.0

- Reinforcement learning.
- Imitation learning.
- Several deep-learning architectures.
- CUDA.
- Multi-agent market ecology as the primary simulator.
- Cross-venue smart order routing.
- Equities/futures generalisation claims.
- Exact queue reconstruction from aggregate level-2 data.
- Endogenous market impact claims from ghost historical replay.
- Live order submission or real-money deployment.
- A publication claim before stable experiments and external review.

These may become later extensions only after the v1.0 acceptance criteria are met.

---

## 4. Research questions

### Primary research question

Does a calibrated short-horizon quote-depletion model, integrated into a queue-aware receding-horizon execution controller, reduce paired implementation shortfall relative to the same controller without machine learning and to strong static baselines on locked out-of-sample episodes?

### Secondary research questions

1. Does any in-distribution improvement survive latency, liquidity, spread, fee, and queue-position misspecification?
2. Are probability calibration and decision-aware diagnostics more informative about execution value than discrimination metrics such as AUROC alone?
3. What computational-latency and throughput costs are introduced by the prediction layer, and at what point do they erase its execution benefit?

---

## 5. Principal hypotheses

- **H1 — Decision value:** the ML-assisted controller has lower mean paired implementation shortfall than the non-ML adaptive controller on the locked test set.
- **H2 — Fragility:** the ML advantage decreases, and may reverse, as latency and queue-model error increase.
- **H3 — Calibration:** lower calibration error and better decision-conditional performance are more strongly associated with execution improvement than raw classification accuracy.
- **H4 — Baseline competitiveness:** TWAP, Almgren–Chriss, and the non-ML adaptive controller remain competitive in at least some instruments, horizons, or stress regimes.

These are hypotheses, not expected conclusions. Mixed or negative results are valid.

---

## 6. Minimum viable and stretch contributions

### Minimum viable contribution

A defensible v1.0 exists when the repository contains:

1. a validated deterministic synthetic matching engine;
2. a validated aggregate historical replay path with documented queue assumptions;
3. identical-episode comparisons of the six defined strategies;
4. one calibrated prediction target that enters a real execution decision;
5. chronological development and a locked final test;
6. paired uncertainty analysis and stress tests;
7. automated figures and tables from saved outputs;
8. a reproducible technical report with substantive limitations.

A result showing that ML fails to improve execution can still satisfy the minimum contribution if the study reveals why and under which regimes.

### Stretch contribution

Only after v1.0 is stable:

- compiled or ONNX inference inside the C++ loop;
- a compact temporal model;
- a second venue or higher-fidelity dataset;
- cross-simulator validation using ABIDES or another independent environment;
- imitation of a slower optimiser;
- carefully scoped reinforcement learning under simulator mismatch.

---

## 7. Architecture summary

```text
                         ┌──────────────────────────┐
                         │ Raw market-data capture  │
                         │ JSONL/Zstd + manifests   │
                         └─────────────┬────────────┘
                                       │
                         ┌─────────────▼────────────┐
                         │ Validation and conversion│
                         │ sequence/gap/schema/DST  │
                         └─────────────┬────────────┘
                                       │
                         ┌─────────────▼────────────┐
                         │ Canonical event store    │
                         │ Arrow/Parquet + metadata │
                         └───────┬─────────┬────────┘
                                 │         │
                 ┌───────────────▼──┐   ┌──▼────────────────┐
                 │ Feature/label     │   │ Historical replay │
                 │ generation        │   │ aggregate L2      │
                 └──────────┬────────┘   └──┬────────────────┘
                            │               │
                 ┌──────────▼────────┐      │
                 │ Model training and │      │
                 │ calibration        │      │
                 └──────────┬────────┘      │
                            │ precomputed    │
                            │ predictions    │
                     ┌──────▼───────────────▼──────┐
                     │ C++ event scheduler and     │
                     │ execution simulation        │
                     ├──────────────────────────────┤
                     │ synthetic matching engine   │
                     │ aggregate historical book   │
                     │ latency + queue models       │
                     │ policy interface             │
                     │ account, fills, metrics      │
                     └──────────────┬───────────────┘
                                    │
                          ┌─────────▼─────────┐
                          │ Experiment runner │
                          │ configs/manifests │
                          └─────────┬─────────┘
                                    │
                          ┌─────────▼─────────┐
                          │ Statistical eval. │
                          │ tables/figures    │
                          └───────────────────┘
```

A key design choice is to precompute model predictions for core experiments and feed them to the C++ replay by timestamp. This preserves deterministic replay, avoids a Python callback on every event, and lets model inference latency be measured separately before a later compiled-inference extension.

---

## 8. Reusable assets from existing projects

### From the derivatives pricing engine

Likely reusable directly or by pattern:

- CMake project organisation;
- pybind11 binding layout;
- CTest integration;
- deterministic random seeds;
- OpenMP benchmark harness;
- fixed-hardware metadata capture;
- ASan/UBSan CI jobs;
- numerical reference testing;
- repeated-seed convergence analysis;
- Python/C++ cross-checks.

Not reusable without redesign:

- pricing-domain classes;
- payoff hierarchy;
- assumptions tied to independent Monte Carlo paths;
- performance claims measured for the old workload.

### From the power-market platform

Likely reusable directly or by pattern:

- raw/interim/processed data separation;
- provenance and checksum manifests;
- timestamp and missing-data validation;
- chronological split utilities;
- locked-test discipline;
- bootstrap analysis;
- sensitivity-analysis runner;
- optimisation-result validation;
- automatic table and figure generation;
- experiment metadata and CI conventions.

Not reusable without redesign:

- hourly feature definitions;
- battery model formulation;
- day-ahead forecast labels;
- assumptions specific to DE-LU electricity prices.

---

## 9. Greatest current risks and controls

### Risk 1 — Aggregate data cannot reveal exact queue position

**Control:** separate exact synthetic matching from historical aggregate replay; label the historical queue model as an assumption; report sensitivity across optimistic, neutral, and pessimistic queue-ahead rules; never call aggregate replay exact.

### Risk 2 — Scope expands before a result exists

**Control:** no RL, CUDA, second venue, or deep model until the v1.0 gates in `ROADMAP.md` are met. New ideas enter `DECISIONS.md` and require a stated research benefit and cost.

### Risk 3 — Simulator bugs create convincing but false results

**Control:** deterministic hand-computed scenarios, invariants, property tests, differential tests between simple reference Python logic and C++, replay checksums, and acceptance criteria before strategy experiments.

### Risk 4 — Temporal leakage or contaminated labels

**Control:** causal feature timestamps, purged chronological splits, scalers fitted on training data only, model selection on validation only, final-test lock, and automated leakage assertions.

### Risk 5 — ML metric gains do not create execution gains

**Control:** make execution cost the primary outcome; compare the ML-assisted controller to the same controller with neutral/uninformative predictions; include calibration and decision curves; retain negative findings.

---

## 10. Current milestone and next action

### Current phase

Phase 0 — Project audit and specification.

### Completed

- Initial project objective defined.
- Original scope audited and reduced.
- v1.0 research question, hypotheses, architecture, and protocol baseline defined.
- Primary data-source direction selected provisionally.
- Initial governance documents created.

### Not completed

- Existing repositories have not yet been inspected at file level.
- No market-data pilot has been run.
- No repository scaffold or executable code has been created.
- No acceptance test has been executed.

### Exact next action

Upload or connect the complete derivatives-pricing and power-market repositories, including hidden CI/config files. The first implementation task is then a reuse audit that produces a component inventory and an initial repository scaffold without copying domain-specific code blindly.

---

## 11. Files to obtain first

For each existing project, provide the repository or a zip containing:

1. top-level `README.md`;
2. complete source directories;
3. complete test directories;
4. `CMakeLists.txt`, `pyproject.toml`, requirements/lock files, and build scripts;
5. `.github/workflows/`;
6. benchmark scripts and raw benchmark outputs;
7. configuration files;
8. sample data or a manifest explaining how data is obtained;
9. generated reports only when needed to trace claims;
10. any current `PROJECT_CONTEXT.md`, roadmap, decisions, or research-protocol files.

Do not upload secrets, API keys, private employer data, or large proprietary datasets.

---

## 12. Source notes for the initial specification

- Coinbase Exchange WebSocket overview and level-2 documentation: public market data and level-2 update semantics.
- Binance public-data repository and Spot WebSocket documentation: useful as a secondary source and for trades, but its standard public archive is not by itself a historical full-depth event dataset.
- Almgren and Chriss, *Optimal Execution of Portfolio Transactions*.
- Cont, Kukanov, and Stoikov, *The Price Impact of Order Book Events*.
- Zhang, Zohren, and Roberts, *DeepLOB*.
- ABIDES official repository and paper, used only as a potential later comparison, not as the v1.0 core.
