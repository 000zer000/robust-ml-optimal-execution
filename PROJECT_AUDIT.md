# Project Audit — Robust Execution Flagship

**Audit status:** Complete for Step 1, with material findings and one execution-environment limitation  
**Audit date:** 2026-08-06  
**Auditor:** ChatGPT acting as technical lead and research-methodology reviewer  
**Target project:** *Learning Robust Execution Policies in Limit Order Books: Prediction, Optimisation and Stress Testing under Latency and Regime Shifts*

---

## 1. Purpose of this audit

This document determines what can be inherited from Othmane Hassani's existing work, what must be repaired or redesigned, and what capabilities are still absent before the full flagship project can begin.

The audit covers:

1. the High-Performance Derivatives Pricing & Risk Engine;
2. the European Power Market Research Platform;
3. the current research CV and its evidence boundaries;
4. the initial robust-execution governance documents;
5. the gap between the existing portfolio and the complete intended project, including deep learning, imitation learning, reinforcement learning, robustness research, performance engineering, a technical paper, and release/outreach assets.

This is an audit, not an implementation step. No source code in either existing repository was changed.

---

## 2. Evidence basis and audit limitations

### 2.1 Repository snapshots inspected

The audit is tied to exact default-branch snapshots:

| Repository | Audited commit | Commit date | Latest default-branch CI |
|---|---|---:|---|
| `000zer000/high-performance-derivatives-pricing-risk-engine` | `dca3e357278994e47efbd8b893777c44c3625567` | 2026-08-06 | Successful, run `31104654131` |
| `000zer000/european-power-market-research-platform` | `b54590e78bcf882f30a83b71cab3d2abb16d9a42` | 2026-08-06 | Successful, run `31105128686` |

The audit inspected complete repository trees and reviewed the highest-risk or most reusable files, including build configuration, CI, core numerical code, deterministic random generation, bindings, tests, data ingestion, feature construction, chronological model evaluation, optimisation, backtesting, statistical metrics, validation, and research-artifact contracts.

### 2.2 Tests and execution evidence

The working container could not resolve `github.com`, so it was not possible to clone and rerun the repositories locally during this session. This is an environment restriction, not a repository failure.

Accordingly, evidence is separated into two categories:

- **Directly inspected:** repository source, tests, configuration, documentation, committed outputs, and current GitHub metadata.
- **Externally executed and verified:** successful GitHub Actions runs at the exact audited commits.

No claim in this document should be interpreted as “personally reproduced in the current container.”

### 2.3 Confidentiality boundary

Only public portfolio repositories and user-provided materials were inspected. No employer source code, proprietary market data, credentials, confidential Excel files, or private schemas should enter the new repository.

---

## 3. Executive conclusion

The existing portfolio is a credible foundation for the full robust-execution project. It demonstrates two complementary strengths:

- the derivatives repository provides a strong C++/Python numerical-engineering base;
- the power-market repository provides a strong research-governance, data-validation, leakage-control, optimisation, and evidence-publication base.

However, neither repository contains the central capabilities required for the new project: an event-driven exchange simulator, price-time-priority matching, queue modelling, historical order-book replay, market-impact modelling, optimal execution, microstructure prediction, deep temporal models, imitation learning, reinforcement learning, or simulator-mismatch research.

The correct approach is therefore **selective inheritance**, not codebase fusion. We should reuse proven patterns and a limited number of utilities, while building the market-microstructure core as a new repository with stricter contracts.

The audit also found concrete issues that must not be copied:

1. an incomplete independent state-bound audit in the battery optimiser;
2. final-test selection of the “best” naive comparator before inference;
3. an IID day bootstrap that does not preserve dependence across adjacent days;
4. a coverage percentage that excludes CLI and reporting modules;
5. a research-artifact contract that checks committed-output consistency but does not regenerate the full study;
6. a custom deterministic random generator without a documented formal statistical-quality test suite;
7. initial robust-execution documents that conflict with the user's now-confirmed decision to complete the full project.

These findings do not make the existing projects weak. They define the stronger standard the flagship project must satisfy.

---

## 4. Portfolio and profile audit

### 4.1 Evidence-backed strengths

The current public work supports the following starting capabilities:

- Python research pipelines;
- modern C++ numerical implementation;
- CMake and CTest;
- pybind11 interoperability;
- OpenMP shared-memory parallelism;
- deterministic experiment seeds;
- Monte Carlo simulation;
- confidence intervals and convergence studies;
- numerical validation against independent formulas and finite differences;
- chronological model evaluation;
- data provenance and checksums;
- strict configuration validation;
- mixed-integer optimisation with SciPy/HiGHS;
- post-solver auditing;
- pytest, branch coverage, strict mypy, and Ruff;
- GitHub Actions, ASan, UBSan, secret scanning, and link checking;
- committed machine-readable result evidence;
- explicit limitations and narrow claim wording.

These are directly relevant to the intended project and reduce the amount of infrastructure that must be invented from nothing.

### 4.2 Capabilities not yet evidenced

The current portfolio does **not** yet establish competence in:

- exchange matching-engine design;
- limit-order-book invariants;
- event-time simulation;
- exact FIFO queue state;
- historical level-2/level-3 replay;
- WebSocket capture with gap recovery;
- market microstructure and queue-reactive models;
- Almgren–Chriss or stochastic-control implementation;
- fill-probability and adverse-selection modelling;
- deep order-book architectures;
- PyTorch training systems;
- imitation learning;
- reinforcement learning;
- off-policy evaluation;
- simulator calibration and sim-to-real error;
- CUDA, GPU profiling, or compiled neural inference;
- high-throughput columnar event storage;
- fuzzing, mutation testing, or formal property-based testing of a C++ engine;
- research-paper production in LaTeX with automatically generated tables.

These are project work items, not résumé claims that may be made in advance.

### 4.3 Internship experience

The public CV describes valuable experience with heterogeneous data, explicit validation, anomaly detection, and monitoring. Those experiences support the project's engineering mindset, but employer-specific code and data must not be reused. Only general lessons—such as “missing is not zero,” explicit reconciliation, and auditable transformations—may be inherited.

---

# 5. Repository audit: derivatives pricing and risk engine

## 5.1 Overall assessment

**Status:** Strong reusable engineering reference; not a base repository to copy wholesale.

The repository is compact, modular, and correctness-oriented. Its strongest contribution to the new project is not option-pricing code, but its engineering discipline around deterministic simulation, numerical validation, C++/Python separation, CI, sanitizers, benchmarks, and evidence-bounded claims.

## 5.2 Architecture

The current architecture separates:

- public headers under `include/derivatives`;
- implementations under `src`;
- a static `pricing_core` library;
- a CLI executable;
- optional pybind11 bindings;
- tests;
- benchmarks;
- convergence experiments;
- architecture, mathematics, reproducibility, and evidence documentation.

This general separation is suitable for adaptation. The new project should similarly keep:

- the C++ engine independent of Python;
- Python bindings thin;
- experiments outside core implementation;
- raw benchmark evidence separate from summaries;
- documentation and claim evidence versioned with the code.

## 5.3 Build and CI quality

The repository uses C++20, warnings including conversion and shadow warnings, optional OpenMP, optional pybind11, CTest, Debug/Release builds on Linux and macOS, sanitizer builds, and a benchmark-smoke job.

This is a strong baseline. For the flagship repository it should be expanded with:

- a package manager or reproducible dependency mechanism for C++ dependencies;
- Clang and GCC coverage rather than only runner-default compilers;
- `clang-tidy` or equivalent static analysis;
- C++ coverage reporting;
- property/fuzz test jobs;
- deterministic replay artifact checks;
- benchmark baselines separated from correctness CI;
- an optional Windows portability job after the Linux/macOS core is stable.

## 5.4 Deterministic simulation pattern

The Monte Carlo implementation uses path-indexed random draws and fixed-size blocks combined in a fixed order. This allows serial and OpenMP execution to produce identical aggregate results for a fixed binary and toolchain.

This is highly relevant to the execution simulator. The transferable principles are:

1. randomness must be indexed by stable logical identifiers, not by thread scheduling;
2. event ordering must be deterministic under a fixed configuration;
3. parallel work must not change reduction order when exact reproducibility is claimed;
4. result records must contain seed, configuration, thread count, software version, and hardware metadata.

The exact random-number implementation should not be copied without further validation. It uses a custom SplitMix64-based key construction followed by Box–Muller transformation. The source is deterministic, but the repository does not document a formal battery of statistical-quality tests for the generated streams. The new project should use a well-established counter-based generator or subject any custom generator to dedicated statistical testing before relying on it for research conclusions.

## 5.5 Numerical validation and tests

The derivatives test suite covers:

- input validation;
- independent Black–Scholes values;
- put-call parity;
- analytical Greeks;
- central finite-difference comparisons;
- Monte Carlo confidence-interval construction;
- deterministic edge cases;
- variance-reduction behaviour;
- serial/OpenMP equality;
- CLI failures and valid outputs;
- Python bindings;
- running-statistics merging.

This is a good model for layered validation. For the new matching engine, the equivalent must include:

- hand-computed event tapes;
- FIFO and price-priority properties;
- conservation of quantity and cash;
- deterministic replay hashes;
- invalid event/order rejection;
- queue-position invariants;
- cancellation and partial-fill properties;
- latency ordering;
- differential tests against a simple reference implementation;
- randomized state-machine tests;
- fuzzing and sanitizer execution.

The existing custom “one executable plus test-case name” harness is manageable for a small engine but will become difficult to maintain in a large simulator. The flagship project should use a mature C++ test framework and explicit property-testing support.

## 5.6 Performance methodology

The repository records raw timings, fixed hardware and compiler metadata, warm-ups, repeated runs, medians, and limitations. It also profiles before parallelising.

This workflow should be inherited directly:

1. correctness baseline;
2. profile;
3. identify bottleneck;
4. change one component;
5. rerun correctness tests;
6. benchmark repeatedly;
7. save raw outputs;
8. report environment and uncertainty.

The reported speedups remain hardware- and workload-specific. No generic performance multiplier should be transferred to the new project.

## 5.7 Reuse decision

### Reuse after adaptation

- CMake target separation and warning policy;
- optional OpenMP pattern;
- thin pybind11 binding pattern;
- deterministic logical-index random design;
- fixed-order reduction concept;
- Welford/mergeable running-statistics pattern;
- sanitizer configuration;
- benchmark evidence format;
- evidence-log and claim-gating philosophy;
- raw timing and convergence artifact conventions.

### Do not copy directly

- financial-pricing domain classes;
- custom CLI parser;
- custom test-dispatch harness;
- custom RNG without an additional validation decision;
- assumptions that bitwise equality is cross-platform;
- benchmark thresholds unrelated to event processing.

---

# 6. Repository audit: European power-market research platform

## 6.1 Overall assessment

**Status:** Strong reusable research-pipeline and governance reference; several statistical and validation details require correction before reuse.

This repository is the stronger of the two for prospective research discipline. It explicitly separates model selection from final evaluation, records provenance, checks feature availability, settles decisions against realised outcomes, validates committed evidence, and states limitations.

## 6.2 Data engineering and provenance

Strong existing patterns include:

- raw response caching;
- atomic writes;
- exact source URLs and parameters;
- retrieval timestamps;
- SHA-256 hashes;
- canonical UTC timestamps;
- explicit market timezone;
- schema validation;
- rejection of invalid or missing data rather than silent repair;
- raw/processed/artifact separation;
- deterministic offline fixtures.

These should be reused in the new market-data layer. The execution project must extend them with:

- sequence numbers;
- snapshot/update linkage;
- channel and product identifiers;
- receive, exchange, and processing timestamps;
- reconnect boundaries;
- gap intervals;
- duplicate-message identifiers;
- compression and file-part metadata;
- checksums per capture segment;
- capture-software commit hash;
- exchange schema version;
- clock source and synchronisation metadata.

CSV is adequate for small evidence tables, but not for high-volume order-book events. The new project should use Arrow/Parquet or another justified binary columnar format for canonical event data, while keeping small summaries in CSV/JSON.

## 6.3 Configuration

The Pydantic configuration layer is a strong pattern:

- unknown keys are rejected;
- models are frozen;
- dates and physical bounds are validated;
- configuration is separate from code.

The new project should adopt this pattern for Python-facing experiment configuration. C++ configuration must be generated or validated against the same schema to prevent Python/C++ interpretation drift.

## 6.4 Leakage prevention

The feature pipeline uses explicit lags, chronological splits, a feature-availability manifest, and a mutation test proving that changing future targets does not alter earlier features.

The principle is directly reusable, but the new project needs a more precise event-time contract. Every feature must define:

- source event timestamp;
- exchange timestamp;
- local receive timestamp;
- decision timestamp;
- publication/availability delay;
- latency applied before the policy observes the value;
- target horizon;
- embargo or purging requirement.

For order-book data, simple row shifting is insufficient. Availability must be proven under event ordering and latency.

## 6.5 Chronological model evaluation

The platform selects hyperparameters on a validation year and uses a monthly expanding-window evaluation on the final year. This is a defensible pattern and should inform the new project.

The execution project will need stronger controls:

- date- or episode-level splits;
- purging around overlapping label horizons;
- an embargo where appropriate;
- no tuning on stress-test outcomes;
- a separate final lockbox period or instrument;
- explicit policies for model retraining;
- experiment-family registration before opening final results.

## 6.6 Optimisation and independent audit

The battery module correctly separates optimisation from realised-price evaluation and reconstructs the solver objective independently. It also prevents simultaneous charge and discharge through binary mode variables.

This separation—optimiser output followed by an independent physical/economic audit—is an excellent pattern for optimal execution.

### Finding PA-001 — incomplete state-bound audit

**Severity:** Medium  
**Impact on existing results:** No automatic invalidation; solver bounds still constrain all state variables.  
**Impact on claims:** The phrase “independently verify every returned physical constraint” is too strong for the current implementation.

The `audit_schedule` function checks:

- `start >= min_soc`;
- `end <= max_soc`;

but omits:

- `start <= max_soc`;
- `end >= min_soc`.

The current optimiser supplies bounded states, so a normal solver-produced schedule should still obey all bounds. However, `evaluate_schedule` accepts a DataFrame and relies on `audit_schedule`; a manually modified schedule could violate an omitted bound without being rejected.

**Required control for the new project:** Every independent audit must test both sides of every bound, and adversarial tests must inject each individual violation to prove detection.

## 6.7 Statistical inference

### Finding PA-002 — final-test comparator selection

**Severity:** High for confirmatory inference  
**Impact:** The reported raw test metrics remain descriptive, but inference against a comparator selected using the same final-test outcomes is not fully prospective.

The metrics code determines the “best naive” baseline by comparing final-test MAE and then computes bootstrap intervals for each ML model against that selected baseline.

This introduces a post-selection issue: the comparator is chosen using the test set being used for inference. The new project must instead:

- predeclare the primary comparator using training/validation evidence or research rationale;
- report comparisons against all required baselines;
- define one primary contrast before opening final results;
- address multiple comparisons for secondary contrasts.

### Finding PA-003 — IID day bootstrap under serial dependence

**Severity:** Medium in the existing daily study; potentially high in high-frequency execution research.

The current bootstrap resamples complete local days independently. This preserves within-day dependence but assumes sampled days are exchangeable and independent. Adjacent market days may remain serially dependent or share regimes.

For the new project, uncertainty methods must be chosen prospectively and may include:

- moving-block bootstrap;
- stationary bootstrap;
- date/week clustering;
- episode-level paired bootstrap with dependence-sensitive block lengths;
- seed-level hierarchical analysis for synthetic experiments;
- sensitivity to the resampling unit.

The correct method will depend on the final experimental unit and data-generating process.

## 6.8 Test and coverage quality

The repository has unit, integration, leakage, physical-property, and offline end-to-end tests. CI checks Python 3.11 and 3.12, strict typing, formatting, branch coverage, secret leaks, documentation links, and committed research artifacts.

### Finding PA-004 — scoped coverage percentage

**Severity:** Low, transparency issue.

The coverage configuration omits `cli.py` and `reporting.py`. Therefore, the reported 91.47% branch coverage is coverage of the configured core package scope, not the entire repository.

The new project should report:

- overall core-library coverage;
- exclusions with justification;
- separate integration coverage for CLI/reporting paths;
- C++ and Python coverage independently;
- coverage as a diagnostic, never as proof of correctness.

## 6.9 Research-artifact contract

The artifact validator is valuable because it recomputes published metrics and checks cross-file consistency, accounting identities, date coverage, strategy coverage, and perfect-foresight gaps.

### Finding PA-005 — consistency check is not full reproduction

**Severity:** Low if accurately described; medium if presented as a complete reproducibility test.

The script explicitly validates committed outputs rather than rerunning ingestion, feature generation, training, optimisation, and reporting from raw data. This is useful but narrower than end-to-end reproduction.

The new project should have both:

1. a fast artifact-consistency contract for CI;
2. a lightweight end-to-end reproducibility run from sample raw data;
3. a full-experiment command that regenerates all final artifacts from manifests and locked dependencies;
4. stored hashes linking raw input segments, configurations, model artifacts, simulator build, and result tables.

## 6.10 Reuse decision

### Reuse after adaptation

- strict Pydantic configuration;
- provenance manifests and SHA-256 checksums;
- canonical timestamp handling;
- no-silent-repair validation philosophy;
- raw/interim/processed/artifact separation;
- deterministic offline fixture pattern;
- feature-availability manifests;
- future-target mutation tests;
- chronological model selection and expanding-window concept;
- decision-value evaluation rather than prediction-only evaluation;
- optimisation/output-audit separation;
- independent objective reconstruction;
- research-artifact contract concept;
- Ruff, strict mypy, pytest branch coverage, Gitleaks, and link checks;
- committed machine-readable outputs and generated figures;
- explicit limitations and claim boundaries.

### Reuse only after correction

- physical audit logic;
- bootstrap and uncertainty code;
- comparator-selection logic;
- coverage reporting language.

### Do not copy directly

- power-market domain models;
- battery MILP formulation as an execution controller;
- CSV as the main high-frequency event store;
- hourly feature assumptions;
- daily terminal-state assumptions;
- the existing final-test comparator selection.

---

# 7. Audit of the initial robust-execution starter documents

## 7.1 Current state

The existing starter documents are internally coherent for a deliberately reduced first release. They define one prediction target, one ML-assisted controller, strong baselines, historical/synthetic separation, and explicit deferral of imitation learning, reinforcement learning, CUDA, and multiple deep architectures.

## 7.2 Governance conflict

The user has now made a new controlling decision:

> The complete project—including deep learning, imitation learning, reinforcement learning, broad robustness work, and performance engineering—must remain within the final project scope and will be completed sequentially.

The following current decisions are therefore obsolete as final-scope decisions:

- `DECISIONS.md` D-001, which reduces v1.0 to one complete research loop;
- `DECISIONS.md` D-007, which excludes RL from v1.0;
- the `PROJECT_CONTEXT.md` out-of-scope list;
- the `README.md` statement that RL is outside v1.0;
- the deferred advanced-learning phase in `ROADMAP.md`.

### Finding GOV-001 — scope documents no longer reflect user intent

**Severity:** Blocking for Step 2.  
**Control:** Do not silently patch isolated sentences. Step 2 must rewrite the research specification and decision log so the complete project is the final scope while retaining gated dependencies.

The correct replacement is not “do everything simultaneously.” It is:

- all major components remain in the final definition of done;
- each component has entry gates;
- RL cannot begin before simulator, data, baselines, and supervised-learning validation;
- CUDA cannot begin before profiling identifies a suitable workload;
- a component can produce a negative result and still be complete;
- no advanced component is included solely for a keyword.

## 7.3 Status of existing starter files

| File | Step-1 status |
|---|---|
| `README.md` | Retain as historical draft; rewrite in Step 2/4 |
| `PROJECT_CONTEXT.md` | Must be replaced with full-scope source of truth in Step 2 |
| `RESEARCH_PROTOCOL.md` | Useful foundation; must be expanded and prospectively corrected |
| `ROADMAP.md` | Superseded by the agreed 32-step full roadmap |
| `DECISIONS.md` | Preserve history, but mark reduced-scope decisions superseded |
| `PROJECT_AUDIT.md` | New authoritative Step-1 output |

---

# 8. Reuse matrix

Legend:

- **A — Reuse substantially:** architecture/pattern is already suitable.
- **B — Reuse after adaptation:** valuable but requires redesign for market microstructure.
- **C — Reuse concept only:** do not copy implementation.
- **D — Do not reuse:** wrong abstraction or methodology for the new project.

| Existing component | Source | Rating | Decision for flagship |
|---|---|---:|---|
| CMake library/CLI/bindings separation | Derivatives | A | Generalise names and targets |
| Warning-as-error policy | Derivatives | A | Keep; add static analysis |
| Linux/macOS Debug/Release CI | Derivatives | A | Keep and expand |
| ASan/UBSan job | Derivatives | A | Keep; add fuzz targets |
| Thin pybind11 wrapper | Derivatives | A | Keep; no duplicated simulation logic |
| Path-indexed randomness | Derivatives | B | Keep logical-index principle |
| Fixed-order parallel reduction | Derivatives | B | Reuse where exact aggregation matters |
| Custom SplitMix64/Box–Muller RNG | Derivatives | C | Replace or validate formally |
| RunningStatistics merge pattern | Derivatives | B | Generalise to experiment statistics |
| Custom CTest dispatch harness | Derivatives | D | Replace with mature test framework |
| Raw benchmark evidence | Derivatives | A | Keep and extend |
| Evidence log / claim gate | Derivatives | A | Make project-wide |
| Strict Pydantic configuration | Power market | A | Adopt for Python config contract |
| Raw/interim/processed/artifact layout | Power market | A | Adopt, using Parquet for events |
| SHA-256 provenance manifests | Power market | A | Extend to capture segments/builds/models |
| Atomic raw writes and bounded retry | Power market | B | Extend for streaming/reconnections |
| No-silent-repair validation | Power market | A | Mandatory |
| UTC canonical timestamps | Power market | A | Extend to exchange/receive/decision times |
| Future-target mutation leakage test | Power market | A | Adapt to event-time features |
| Chronological expanding evaluation | Power market | B | Add purging, embargo, lockbox rules |
| Prediction-to-decision evaluation | Power market | A | Core research principle |
| Solver/audit separation | Power market | A | Keep, with complete invariant checks |
| Current battery audit implementation | Power market | C | Correct pattern; do not copy bug |
| Current IID day bootstrap | Power market | D | Redesign for dependence |
| Test-selected comparator | Power market | D | Predeclare contrasts |
| Artifact consistency validator | Power market | A | Keep plus true regeneration test |
| Ruff + strict mypy + pytest | Power market | A | Keep |
| Gitleaks and link checking | Power market | A | Keep |
| CSV canonical event storage | Power market | D | Use Parquet/Arrow for LOB events |
| Generated result figures/tables | Power market | A | Keep and expand to paper pipeline |

---

# 9. Capability-gap map for the complete project

## 9.1 C++ exchange and simulation

Missing work:

- strongly typed price, quantity, order, event, and timestamp types;
- order ownership and lifetime model;
- bid/ask books and price-level containers;
- exact price-time priority;
- order ID index;
- limit, market, cancel, and replace semantics;
- partial fills and trade generation;
- exchange acknowledgements and rejects;
- event scheduler;
- communication and processing latency;
- deterministic replay;
- structured binary or columnar event logs;
- exact synthetic queue position;
- aggregate historical queue approximations;
- market-impact and small-agent assumptions;
- throughput, allocation, cache, and memory profiling.

## 9.2 Market data

Missing work:

- source and licence evaluation;
- streaming capture daemon;
- snapshot plus incremental update reconstruction;
- sequence-gap detection;
- reconnect/recovery protocol;
- exchange/receive timestamps;
- multi-asset capture;
- canonical level-2 event schema;
- historical replay fixtures;
- calibrated synthetic regime parameters;
- data-quality dashboards and manifests.

## 9.3 Optimal execution

Missing work:

- formal parent-order problem;
- arrival price and implementation shortfall definitions;
- immediate, TWAP, and volume-informed baselines;
- Almgren–Chriss derivation and tests;
- queue-aware adaptive controller;
- model-predictive controller;
- residual-inventory and forced-completion logic;
- fees, rebates, adverse selection, and impact accounting;
- fair calibration rules shared across strategies.

## 9.4 Machine learning

Missing work:

- causal microstructure feature contract;
- fill, depletion, movement, adverse-selection, volatility, or regime targets;
- label-overlap and purging analysis;
- probability calibration;
- interpretable baselines;
- one justified temporal neural architecture;
- inference-latency measurement;
- prediction-to-decision integration;
- oracle, neutral, shuffled, and degraded-signal ablations;
- unseen-date, instrument, and regime evaluation.

## 9.5 Imitation learning and reinforcement learning

Missing work:

- expert-policy dataset generation;
- behavioural cloning and distribution-shift evaluation;
- uncertainty or abstention mechanisms;
- Markov decision process definition;
- action space and constraints;
- reward definition with terminal inventory;
- anti-reward-hacking tests;
- RL algorithm selection based on action/state properties;
- seed and hyperparameter protocol;
- strong-baseline comparison;
- simulator-mismatch evaluation;
- offline/online distinction and no-live-profitability claims.

## 9.6 Statistical methodology

Missing work:

- prospective primary contrast;
- experiment-family registry;
- dependence-aware uncertainty;
- hierarchical analysis over dates, instruments, and seeds;
- multiple-comparison policy;
- effect-size reporting;
- tail-risk inference;
- robust-rank comparisons across stress dimensions;
- negative-result preservation;
- lockbox opening procedure.

## 9.7 Release and paper

Missing work:

- LaTeX paper structure;
- automated table/figure inclusion;
- bibliographic database;
- architecture diagrams;
- reproducible sample dataset;
- Docker or equivalent environment;
- tagged releases;
- `CITATION.cff` and changelog;
- archival package and possible Zenodo DOI;
- one-page research overview;
- CV variants and professor-specific outreach material.

---

# 10. Mandatory engineering and research standards inherited from the audit

The new repository must enforce the following from the beginning.

## 10.1 Claim classes

Every claim must be labelled internally as one of:

- **implementation claim** — code exists and tests pass;
- **numerical claim** — independently validated on defined cases;
- **empirical claim** — supported by a registered experiment and uncertainty analysis;
- **performance claim** — tied to hardware, compiler, workload, repetitions, and raw data;
- **generalisation claim** — supported across held-out dates/instruments/regimes;
- **limitation or hypothesis** — not presented as evidence.

## 10.2 Reproducibility levels

The project must distinguish:

1. deterministic replay under the same build/configuration;
2. numerically equivalent results across supported platforms;
3. statistically consistent stochastic results;
4. complete regeneration from raw/sample data;
5. artifact-internal consistency.

These are not interchangeable.

## 10.3 Testing layers

Required layers:

- unit tests;
- hand-computed scenario tests;
- property/invariant tests;
- differential tests;
- randomized state-machine tests;
- fuzz tests;
- sanitizer tests;
- integration tests;
- deterministic replay tests;
- sample end-to-end reproduction;
- research-artifact consistency tests;
- performance-regression smoke tests.

## 10.4 Experimental controls

Required controls:

- all timestamps and information availability documented;
- final comparator declared before final evaluation;
- no selection on final-test outcomes;
- overlapping labels handled explicitly;
- dependence-aware uncertainty;
- all required baselines run under identical conditions;
- no best-seed or best-day reporting;
- failed and negative experiments retained;
- stress-test definitions separated from historical observations;
- model and policy latency measured and injected;
- final claims generated from saved machine-readable outputs.

---

# 11. Initial risk register

| ID | Risk | Probability | Impact | Initial control |
|---|---|---:|---:|---|
| R-01 | Incorrect matching or queue accounting | High | Critical | Reference model, hand tapes, properties, differential tests, fuzzing |
| R-02 | Historical replay implies false exact queue position | High | Critical | Separate exact synthetic mode from aggregate historical queue models |
| R-03 | Future information leaks through timestamps or labels | High | Critical | Availability contracts, event-time tests, purging/embargo |
| R-04 | ML metrics improve but execution does not | High | High | Decision-value primary outcome and neutral/oracle ablations |
| R-05 | RL exploits simulator/reward artifacts | High | Critical | Delayed entry gate, anti-exploit tests, mismatch stress tests |
| R-06 | Public market data are incomplete or licence-incompatible | Medium | Critical | Data-source audit before capture; fallback design |
| R-07 | Project scope produces many shallow components | High | High | Gated sequential roadmap; acceptance criteria per component |
| R-08 | Statistical significance is inflated by dependence or selection | High | High | Predeclared contrasts, dependence-aware inference, multiple-comparison policy |
| R-09 | Performance optimisation changes results | Medium | Critical | Correctness rerun and replay-hash gates after every optimisation |
| R-10 | Reproducibility claims exceed actual guarantees | Medium | High | Explicit reproducibility levels and artifact contracts |
| R-11 | Data volume exceeds local storage/compute | Medium | High | Capture pilot, compression, partitioning, retention policy |
| R-12 | Advanced model complexity exceeds available signal | High | Medium | Strong simple baselines, learning curves, architecture entry gates |
| R-13 | CUDA/GPU work is performative rather than useful | Medium | Medium | Profile first; CPU comparison and transfer-cost accounting |
| R-14 | Existing starter documents create conflicting instructions | Certain | High | Full specification rewrite in Step 2 |
| R-15 | User cannot defend AI-generated code | Medium | Critical | Decision log, code review gates, no unexplained component enters release |

---

# 12. Step-1 findings register

| Finding | Severity | Disposition |
|---|---:|---|
| PA-001 incomplete battery state-bound audit | Medium | Correct pattern in new project; add adversarial tests |
| PA-002 final-test selection of best naive comparator | High | Prohibit; predeclare primary comparator |
| PA-003 IID day bootstrap under serial dependence | Medium/High | Replace with dependence-aware method |
| PA-004 branch coverage excludes CLI/reporting | Low | Report scope explicitly and add integration tests |
| PA-005 artifact contract is not full regeneration | Low/Medium | Keep plus sample/full reproduction workflows |
| DR-001 custom RNG lacks documented formal quality battery | Medium | Replace or validate before reuse |
| DR-002 custom test dispatch will not scale | Medium | Use mature C++ test/property framework |
| GOV-001 starter documents conflict with full-scope decision | Blocking | Rewrite in Step 2 |
| ENV-001 local clone/rerun unavailable in audit container | Informational | Current public CI verified; rerun during repository bootstrap |

---

# 13. Step-1 acceptance criteria

| Criterion | Result |
|---|---|
| Existing public repositories identified | Pass |
| Exact audited commits recorded | Pass |
| Repository structures inspected | Pass |
| Core numerical and research code reviewed | Pass |
| Build, test, CI, and reproducibility mechanisms reviewed | Pass |
| Current public CI verified at audited commits | Pass |
| Reusable components classified | Pass |
| Material defects and methodological weaknesses documented | Pass |
| Missing capabilities mapped to full project | Pass |
| Confidentiality boundary documented | Pass |
| Local clean-clone reproduction performed in this session | Not performed — environment DNS restriction |
| Existing repositories modified | No |

**Step-1 decision:** Complete, with the execution limitation explicitly recorded. The audit is sufficient to proceed to specification freeze because repository source and exact-commit CI evidence were available, and no unresolved ambiguity about reusable architecture blocks Step 2.

---

# 14. Files created or changed in Step 1

Created:

- `PROJECT_AUDIT.md`

Not changed:

- either existing GitHub repository;
- `README.md`;
- `PROJECT_CONTEXT.md`;
- `RESEARCH_PROTOCOL.md`;
- `ROADMAP.md`;
- `DECISIONS.md`.

Those governance documents remain historical drafts until Step 2 replaces the reduced-scope assumptions.

---

# 15. Exact next action

**Step 2 — Freeze the complete research specification.**

Step 2 must:

1. replace the reduced v1-only scope with the complete final definition of done;
2. define the parent-order problem, observation model, action spaces, exchange assumptions, historical and synthetic claim boundaries, and all entry gates;
3. define primary and secondary research questions and hypotheses;
4. predeclare the primary comparator and inference principles;
5. create a corrected, versioned `PROJECT_CONTEXT.md`, `SCOPE.md`, `RESEARCH_QUESTIONS.md`, and `DECISIONS.md`;
6. preserve all advanced components in the final scope while enforcing dependency order.

Step 2 must not begin until the user says **go**.
