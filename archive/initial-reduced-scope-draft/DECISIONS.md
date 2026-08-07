# DECISIONS.md

## Decision log

- **Project:** Robust Execution
- **Version:** 0.1.0
- **Last updated:** 2026-08-06

Major design and research choices are recorded here. A decision can be superseded, but not silently deleted. Each entry states the context, decision, rationale, consequences, and reconsideration trigger.

---

## D-001 — Reduce v1.0 to one complete research loop

**Status:** Accepted  
**Date:** 2026-08-06

### Context

The original specification includes an exact matching engine, historical replay, classical optimal execution, supervised machine learning, deep learning, imitation learning, reinforcement learning, synthetic regimes, performance engineering, a paper, and professor-specific replications. Attempting all components before a stable result creates a high probability of unfinished code, weak baselines, and an indefensible report.

### Decision

v1.0 will include:

- validated synthetic matching engine;
- aggregate historical replay;
- immediate, TWAP, volume-profile, Almgren–Chriss, and non-ML adaptive baselines;
- one decision-relevant prediction target;
- one ML-assisted controller;
- robustness and performance analysis;
- reproducible technical report.

RL, imitation learning, CUDA, second venue, and several deep models are deferred.

### Rationale

A complete and negative-capable study is more credible than a broad collection of partially validated techniques.

### Consequences

The repository will appear less keyword-dense initially, but the central claim will be easier to test and defend.

### Reconsider when

All v1.0 final-evaluation and report acceptance criteria pass.

---

## D-002 — Coinbase Exchange level-2 as provisional primary real-data source

**Status:** Accepted provisionally  
**Date:** 2026-08-06

### Context

The project requires public order-book updates suitable for deterministic capture and aggregate replay. Coinbase documents a public market-data WebSocket and a level-2 channel designed to maintain an order-book snapshot. Binance provides useful public historical trade/aggregate-trade/kline archives and live depth streams, but the standard public archive does not by itself provide the historical full level-2 event stream needed for this project.

### Decision

Use Coinbase Exchange public level-2 data for the initial six-week capture, starting with BTC-USD and ETH-USD. Retain Binance as a secondary or later cross-venue option.

### Rationale

This minimises initial feed synchronisation and data-access complexity while providing real price-level updates for two liquid instruments.

### Consequences

The project depends on self-capture for the core level-2 dataset. Collection must start early, and disconnect handling is a first-class engineering task.

### Reconsider when

- the 72-hour pilot shows unacceptable gaps or unstable semantics;
- storage/throughput is infeasible;
- a legally usable, higher-fidelity order-level dataset becomes available;
- the selected feed changes materially.

---

## D-003 — Separate exact synthetic matching from aggregate historical replay

**Status:** Accepted  
**Date:** 2026-08-06

### Context

Aggregate level-2 updates show quantity at price levels, not complete individual-order identities and FIFO positions. A single simulator pretending to recover exact historical queues would create false precision.

### Decision

Implement two explicit modes:

1. an exact synthetic price-time-priority matching engine;
2. an aggregate historical replay engine with configurable queue-ahead assumptions.

Shared interfaces may be used, but logs and result metadata must identify the mode.

### Rationale

The synthetic engine supports exact validation and controlled stress. Historical replay provides real observed market paths while preserving honest uncertainty.

### Consequences

Some strategy behaviour will differ across modes. Results must be compared within a mode before cross-mode interpretation.

### Reconsider when

Order-level historical data with reliable identifiers and event semantics is obtained.

---

## D-004 — Use a small-agent ghost-execution assumption in historical replay

**Status:** Accepted  
**Date:** 2026-08-06

### Context

A hypothetical order was not present in recorded data. Rewriting subsequent observed events after a simulated fill would invent a counterfactual market response without a calibrated market model.

### Decision

Historical replay will calculate fills against the observed book but will not causally alter the future recorded market path. Parent sizes will be controlled, and larger sizes will be treated as stress tests. Any additional impact penalty must be explicit and sensitivity-tested.

### Rationale

This is more transparent than silently mixing replay data with unvalidated endogenous impact.

### Consequences

The project cannot claim realistic large-order market impact from historical replay. Synthetic mode and stress models handle impact experiments.

### Reconsider when

A validated counterfactual market-response model or agent-based environment is added.

---

## D-005 — Primary ML target is quote depletion, not exact personal fill

**Status:** Accepted provisionally  
**Date:** 2026-08-06

### Context

Exact personal fill labels depend on hidden order identities, queue position, cancellations ahead, and latency. Aggregate level-2 data cannot reveal these perfectly.

### Decision

Predict whether the relevant best quote depletes or is traded through within a short fixed horizon. Convert this prediction to an estimated passive-fill opportunity inside the controller using an explicit queue model.

### Rationale

Quote depletion is closer to observable book evolution and keeps queue uncertainty visible rather than embedding it silently in labels.

### Consequences

The ML output is not described as an exact fill probability. The report must distinguish quote-depletion calibration from simulated fill outcomes.

### Reconsider when

The pilot indicates unstable labels, insufficient positive events, or a better directly observable decision target.

---

## D-006 — Logistic regression and histogram gradient boosting are required; deep learning is gated

**Status:** Accepted  
**Date:** 2026-08-06

### Context

The scientific question concerns decision value and robustness, not architecture novelty. A deep model added immediately increases tuning, leakage, compute, and explanation risk.

### Decision

v1.0 requires an interpretable linear probabilistic model and a strong non-linear tree baseline. A compact temporal neural model is permitted only after:

- labels and splits pass validation;
- simple models show non-trivial signal;
- the controller integration is stable;
- there is a precise hypothesis that the temporal model tests.

### Rationale

This creates a meaningful complexity ladder and protects the project from superficial deep-learning claims.

### Consequences

A v1.0 release may contain no neural network and still be complete.

### Reconsider when

Baseline results and dataset scale justify the added model.

---

## D-007 — Reinforcement learning is not part of v1.0

**Status:** Accepted  
**Date:** 2026-08-06

### Context

RL introduces reward-design risk, simulator exploitation, unstable training, and a larger comparison burden. It is especially weak when the simulator and terminal-inventory rules are not already validated.

### Decision

No RL implementation before the v1.0 report. Later RL work requires a new protocol and simulator-mismatch evaluation.

### Rationale

The project already has a strong research question through predict-then-optimise execution. RL is not necessary to demonstrate ML, optimisation, market microstructure, or systems ability.

### Consequences

Time is redirected to baseline strength, uncertainty analysis, and engine correctness.

### Reconsider when

The exact and historical simulators, baselines, ML-assisted controller, and robustness suite are stable.

---

## D-008 — Precompute predictions for core execution experiments

**Status:** Accepted  
**Date:** 2026-08-06

### Context

Calling Python inference from C++ at each event complicates determinism, creates binding overhead, and confounds strategy results with runtime integration effects.

### Decision

Core experiments will use prediction artifacts keyed by timestamp and configuration. The C++ runner consumes them deterministically. Inference latency is measured separately and injected into latency scenarios. Compiled inference is a later extension.

### Rationale

This cleanly separates model quality, decision logic, and systems latency while keeping the replay loop fast and reproducible.

### Consequences

The first version does not demonstrate in-process production inference. It does demonstrate correct latency accounting and a path to later compiled inference.

### Reconsider when

Core results are stable and end-to-end inference integration becomes a research or performance question.

---

## D-009 — Use fixed-point/integer representations in the C++ core

**Status:** Accepted  
**Date:** 2026-08-06

### Context

Exchange prices, ticks, and quantities require exact ordering and conservation. Binary floating-point can produce comparison and reconciliation errors.

### Decision

Represent prices in integer ticks and quantities in an instrument-specific fixed-point integer scale. Conversions occur at validated boundaries.

### Rationale

This supports exact priority, deterministic logs, and reliable accounting.

### Consequences

Instrument metadata must define tick and quantity scales. Conversion overflow and invalid precision require explicit handling.

### Reconsider when

Never for core matching semantics unless a formally equivalent exact-decimal approach is adopted.

---

## D-010 — C++20 core with Python research layer

**Status:** Accepted provisionally  
**Date:** 2026-08-06

### Context

The project must demonstrate systems quality and support large event replays while retaining a productive environment for data science, statistics, optimisation, and visualisation.

### Decision

Use:

- C++20 for event types, books, scheduler, fills, strategies, and performance-critical replay;
- CMake and CTest with Catch2 or an equivalent test framework;
- pybind11 for selected interfaces;
- Python 3.12-compatible code for capture orchestration, data conversion, features, models, optimisation research, evaluation, and plots;
- Arrow/Parquet for canonical columnar data;
- pytest, strict typing, formatting, linting, and GitHub Actions.

### Rationale

This reuses demonstrated skills while creating clear architecture boundaries.

### Consequences

The build system and Python packaging must be integrated carefully. Not every class should be exposed through bindings.

### Reconsider when

The existing repository audit identifies a stronger compatible foundation or platform constraint.

---

## D-011 — Primary outcome is paired implementation shortfall including terminal completion

**Status:** Accepted  
**Date:** 2026-08-06

### Context

A strategy can appear cheap by leaving inventory unexecuted. Predictive metrics can improve without helping execution.

### Decision

The primary comparison is paired implementation shortfall between ML-assisted and non-ML adaptive controllers on the same episodes, including a common forced terminal-completion rule.

### Rationale

This measures the actual decision objective and prevents incomplete execution from creating artificial gains.

### Consequences

Terminal rules and fee treatment become critical protocol components and must be sensitivity-tested.

### Reconsider when

Only through a versioned protocol change before the final-test lock.

---

## D-012 — Negative results remain first-class outputs

**Status:** Accepted  
**Date:** 2026-08-06

### Context

The project is vulnerable to cherry-picking if ML is assumed to win.

### Decision

Failed models, neutral results, reversed strategy rankings, and robustness failures will be retained and reported when methodologically valid.

### Rationale

The project's credibility depends more on honest controlled evidence than on a positive headline.

### Consequences

The final CV claim may focus on the platform and discovered robustness boundary rather than an ML performance gain.

### Reconsider when

Never; only the presentation detail changes with evidence.
