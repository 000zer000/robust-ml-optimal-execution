# ROADMAP.md

## Project roadmap

- **Version:** 0.1.0
- **Last updated:** 2026-08-06
- **Planning principle:** complete a defensible research loop before adding sophistication.

No phase is complete because files exist or code compiles. A phase is complete only when its acceptance criteria pass and the evidence is recorded.

---

## Phase 0 — Audit, scope freeze, and repository bootstrap

### Objectives

- inspect the two existing repositories;
- identify reusable engineering and research components;
- freeze v1.0 scope;
- create the repository scaffold;
- establish quality gates and documentation.

### Deliverables

- component-reuse inventory;
- top-level repository structure;
- `PROJECT_CONTEXT.md`;
- `RESEARCH_PROTOCOL.md`;
- `ROADMAP.md`;
- `DECISIONS.md`;
- `README.md`;
- build/test/lint/type-check configuration;
- minimal C++ library and Python package;
- CI matrix with debug/release and sanitizer jobs;
- initial issue backlog.

### Acceptance criteria

- clean configure/build on the reference machine;
- one C++ test and one Python test pass locally and in CI;
- formatting, linting, and type checking execute in CI;
- no copied code without provenance and compatibility review;
- protocol identifies primary outcome and final-test lock;
- v1.0 exclusions are explicit.

### Gate

Do not start full simulator implementation until existing code reuse has been inspected rather than assumed.

---

## Phase 1 — Exact synthetic matching engine

### Objectives

Implement a deterministic event-driven C++ matching engine for controlled validation and synthetic experiments.

### Core components

- fixed-point `Price`, `Quantity`, `OrderId`, and timestamp types;
- side and order-type enums;
- price-level containers;
- FIFO order queues;
- add, cancel, replace where justified, and market order handling;
- partial fills;
- acknowledgements and rejects;
- fee/rebate model;
- account/inventory ledger;
- event scheduler;
- structured execution log.

### Deliverables

- public C++ interfaces;
- matching-engine implementation;
- unit scenarios and invariants;
- small Python bindings;
- architecture note with ownership/lifetime rules;
- deterministic sample tape.

### Acceptance criteria

- all hand-computed scenarios match exactly;
- price and FIFO priority tests pass;
- quantity, cash, inventory, and fee invariants pass;
- same seed/configuration yields identical event/fill output;
- ASan/UBSan jobs pass;
- parser-independent engine benchmark established without optimisation claims.

### Gate

No strategy comparison may use synthetic results until the invariant suite passes.

---

## Phase 2 — Market-data pilot, validation, and historical replay

### Objectives

Capture public level-2 data, validate it, define a canonical event schema, and replay aggregate book states deterministically.

### Tasks

1. Implement reconnecting Coinbase capture client.
2. Preserve raw JSON messages and connection metadata.
3. Build manifest and checksum generation.
4. Implement schema and continuity validation.
5. Convert to Arrow/Parquet.
6. Build aggregate book reconstruction.
7. Check book snapshots at deterministic checkpoints.
8. Run a 72-hour pilot on BTC-USD and ETH-USD.
9. Fix storage-rate, disconnect, and timestamp issues.
10. Begin six-week core capture only after the pilot report passes.

### Deliverables

- capture CLI;
- raw-data directory contract;
- manifest schema;
- validation report;
- canonical schema;
- replay reader;
- sample anonymisation/redaction review;
- lightweight sample tape for CI.

### Acceptance criteria

- capture survives reconnects and records them;
- every raw segment has checksum and metadata;
- book reconstruction passes sequence/state checks on the pilot;
- malformed or incomplete segments fail loudly;
- deterministic replay generates identical checkpoint hashes;
- storage and compute estimates support the planned collection period;
- no secret or authentication material is required for the public feed path.

### Gate

Do not define final model labels until actual feed semantics and data defects are understood from the pilot.

---

## Phase 3 — Historical fill model and latency framework

### Objectives

Create an honest execution overlay for aggregate replay and a deterministic latency model.

### Tasks

- define small-agent ghost-execution semantics;
- implement aggressive fill against visible depth;
- define terminal-completion rule;
- implement optimistic/neutral/pessimistic queue-ahead models;
- define passive fill from displayed depletion;
- implement market-data, decision, order, and acknowledgement latency;
- create hand-computed latency/queue scenarios;
- document what cannot be inferred from level-2 data.

### Deliverables

- queue-model interfaces;
- latency scheduler integration;
- fill and terminal rules;
- validation scenarios;
- assumptions document section;
- sensitivity configuration.

### Acceptance criteria

- queue models produce expected fills on manual tapes;
- no strategy receives events before its latency-adjusted availability;
- terminal completion reconciles inventory exactly;
- all queue assumptions are configurable and logged;
- historical mode never mutates the exogenous future path silently;
- result metadata identifies the active fill and latency model.

---

## Phase 4 — Classical execution baselines

### Objectives

Implement fair, tested baselines before machine learning.

### Strategies

- immediate execution;
- TWAP;
- past-only volume-profile schedule;
- Almgren–Chriss schedule;
- non-ML queue-aware adaptive controller.

### Deliverables

- mathematical definitions;
- implementations;
- strategy unit tests;
- parameter-calibration scripts;
- identical-episode experiment harness;
- baseline result sanity report on development data only.

### Acceptance criteria

- each strategy satisfies inventory and timing constraints;
- no strategy uses future data;
- AC implementation matches independent formula/reference cases;
- volume profile uses training or pre-episode data only;
- all strategies run through the same execution API;
- identical episodes and costs are enforced by the runner;
- baseline behaviour is qualitatively sensible on hand-designed regimes.

### Gate

ML work does not begin until S4 is a credible adaptive baseline. A weak rule-based baseline would invalidate the claimed value of ML.

---

## Phase 5 — Labels, causal features, and supervised models

### Objectives

Build one decision-relevant prediction layer with leakage-safe evaluation.

### Tasks

- finalise quote-depletion label;
- define label horizon;
- implement feature timestamp contracts;
- implement causal features;
- freeze chronological split plan;
- train logistic regression;
- train histogram gradient boosting;
- evaluate and calibrate probabilities;
- benchmark feature generation and inference;
- document failed features/models.

### Deliverables

- label generator and tests;
- feature registry;
- split manifest;
- model-training pipeline;
- calibration report;
- saved model artifacts and metadata;
- precomputed prediction files keyed by timestamp.

### Acceptance criteria

- leakage assertions pass;
- labels match manual cases;
- train/validation/test periods are disjoint and purged;
- preprocessing is fit on training only;
- predictive metrics regenerate from saved artifacts;
- model choice uses validation data only;
- probabilities and metadata align exactly with replay timestamps;
- no final-test execution result has been viewed.

---

## Phase 6 — ML-assisted execution and ablations

### Objectives

Measure whether predictions improve decisions, not merely labels.

### Tasks

- integrate precomputed probabilities into S5;
- implement neutral/base-rate prediction ablation;
- tune controller on development periods only;
- compare S5 with S4 on paired development episodes;
- evaluate uncalibrated versus calibrated predictions;
- evaluate feature-family ablations;
- freeze final strategy/configuration.

### Deliverables

- ML-assisted controller;
- decision-cost formulation;
- ablation configs;
- development-only decision report;
- final-test lock manifest.

### Acceptance criteria

- S4 and S5 differ only by predictive input and unavoidable model latency;
- constant-prediction S5 reproduces the expected no-information behaviour;
- controller constraints are identical;
- all hyperparameters are frozen before final test;
- final lock manifest includes code, config, data, and model hashes.

---

## Phase 7 — Locked final evaluation and robustness

### Objectives

Run the predefined final comparison once, then execute the frozen stress grid.

### Tasks

- verify lock manifest;
- run all strategies on all eligible test episodes;
- compute paired primary contrast;
- block-bootstrap uncertainty;
- run secondary baselines;
- run latency, queue, fee, liquidity, and prediction-degradation stresses;
- run synthetic out-of-distribution regimes;
- inspect failures and data-quality flags;
- preserve all outputs.

### Deliverables

- immutable run manifests;
- raw episode-level outputs;
- statistical summary;
- automatic tables and figures;
- deviations log;
- negative-results log.

### Acceptance criteria

- every reported result traces to a run manifest;
- no missing strategy/episode cells without an explained failure;
- primary and all predefined secondary contrasts are reported;
- confidence intervals use the frozen dependence-aware resampling unit;
- forced completion is included consistently;
- conclusions match uncertainty and robustness evidence;
- no test-driven model retuning is hidden.

---

## Phase 8 — Performance engineering

### Objectives

Improve measured bottlenecks without weakening correctness.

### Tasks

- profile parser, replay, strategy, metrics, and output paths;
- identify dominant bottlenecks;
- optimise one component at a time;
- examine memory layout and allocation patterns;
- add batching where useful;
- measure scaling on fixed workloads;
- optionally investigate compiled model inference.

### Deliverables

- baseline and post-change profiles;
- raw benchmark files;
- hardware/software manifests;
- correctness regression results;
- performance section for the report.

### Acceptance criteria

- optimisation is motivated by profiler evidence;
- correctness suite passes after every accepted change;
- repeated measurements and variability are reported;
- no cross-hardware speedup claim is presented as a controlled comparison;
- model latency is included in end-to-end decision timing.

---

## Phase 9 — Technical report, release, and outreach package

### Objectives

Turn stable evidence into a defensible public research artifact.

### Deliverables

- 10–12 page Technical Report — Version 1.0;
- automatic figures and tables;
- limitations section;
- reproducibility guide;
- release changelog;
- `CITATION.cff`;
- tagged GitHub release;
- optional Zenodo archival package;
- one-page research overview;
- tailored CV bullets;
- 50/100/200-word summaries;
- professor-specific outreach framework;
- interview question bank.

### Acceptance criteria

- every numerical claim is generated from saved results;
- every citation is real and checked;
- repository quick start works on a clean environment;
- sample reproduction does not require massive data;
- limitations include aggregate queue uncertainty, small-agent replay, crypto generalisation, and synthetic-regime assumptions;
- CV bullets are supported by code, tests, and result artifacts;
- Othmane can explain the architecture, mathematics, assumptions, and evidence.

---

## Deferred Phase 10 — Advanced learning extensions

Not part of v1.0. Consider only after release-quality evidence exists.

Possible order:

1. compact temporal model;
2. compiled inference;
3. independent simulator comparison;
4. imitation learning of a costly controller;
5. reinforcement learning with explicit simulator-mismatch tests.

Each extension requires a new research question. It must not be added only for keywords.

---

## Session close-out template

At the end of each substantial work session, record:

- current phase;
- completed work;
- files created or changed;
- tests run and exact results;
- important findings;
- unresolved risks;
- protocol or decision changes;
- exact next action.
