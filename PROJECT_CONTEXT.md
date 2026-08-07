# Project Context — Robust Execution Flagship

## Document control

- **Project:** Robust Execution Flagship
- **Working title:** *Learning Robust Execution Policies in Limit Order Books: Prediction, Optimisation and Stress Testing under Latency and Regime Shifts*
- **Subtitle:** *A reproducible C++/Python comparison of classical, machine-learning-assisted and learning-based optimal-execution strategies*
- **Version:** 0.2.1 — corrected full-scope specification freeze
- **Status:** Step 2 complete; no simulator, model, or empirical result is claimed yet
- **Owner:** Othmane Hassani
- **Last updated:** 2026-08-06
- **Source of truth:** This document, `RESEARCH_QUESTIONS.md`, `SCOPE.md`, `RESEARCH_PROTOCOL.md`, and `DECISIONS.md`

This file preserves the durable purpose, scientific problem, claim boundaries, architecture, completion standard, and current state of the project. Major changes require a dated decision entry. No later implementation may silently weaken the specification.

---

## 1. Mission

The project will build a research-grade C++/Python platform for studying the execution of a predetermined parent order in an electronic limit-order book. It will compare:

1. strong classical schedules;
2. model-based adaptive control;
3. supervised machine-learning-assisted control;
4. a deep temporal prediction model;
5. imitation learning of a model-based teacher;
6. reinforcement-learning execution;
7. robust variants evaluated under latency, regime change, queue uncertainty, fee changes, impact misspecification, and simulator mismatch.

The scientific objective is not to prove that machine learning wins. It is to determine **when**, **why**, and **under which assumptions** an adaptive or learned execution method improves realised execution cost and risk, and when the improvement disappears or reverses.

The engineering objective is to produce a system that withstands inspection of its matching rules, timestamps, queue assumptions, leakage controls, optimisation mathematics, statistical inference, reproducibility, and performance claims.

The project is intended to become Othmane Hassani's strongest public research-and-engineering project and to support applications in quantitative research, quantitative development, market-microstructure research, financial machine learning, HPC/AI infrastructure, and systems software engineering.

## 1.1 Central research question

> Can machine-learning-assisted execution policies improve realised execution quality relative to strong classical baselines, and do those improvements survive latency, liquidity shifts, queue-model errors, market-impact misspecification, changing fees, and out-of-distribution market regimes?

This exact wording is authoritative. No narrower experimental contrast, model choice, or statistical test may replace it. Narrower comparisons exist only to test specific parts of the central question rigorously.

---

## 2. Claim boundary

The repository will support claims about **simulated and replay-based execution research** only.

It will not claim:

- guaranteed or demonstrated live profitability;
- production exchange connectivity;
- institutional order-level data when only aggregate level-2 data are available;
- exact reconstruction of hidden liquidity or historical FIFO position from aggregate data;
- realistic endogenous market impact in historical ghost replay;
- production high-frequency-trading latency;
- generalisation from cryptocurrency microstructure to equities, futures, or all electronic markets;
- safety for deployment with real money;
- authorship or understanding of code that has not been tested and reviewed.

Every public result must identify whether it comes from:

1. **historically observed data**;
2. **aggregate historical replay with explicit queue assumptions**;
3. **calibrated synthetic simulation**;
4. **deliberately adversarial stress testing**.

These categories must never be blended in a table or figure without explicit labels.

---

## 3. Formal execution problem

### 3.1 Episode

An execution episode is defined by:

\[
e=(m,\sigma,t_0,T,Q_0,\mathcal{C}),
\]

where:

- \(m\) is the instrument and venue;
- \(\sigma\in\{+1,-1\}\) is the side, with \(+1\) for a buy and \(-1\) for a sell;
- \(t_0\) is the parent-order arrival time;
- \(T\) is the hard completion deadline;
- \(Q_0>0\) is the parent quantity;
- \(\mathcal{C}\) is the common action, latency, fee, tick, lot, and risk-constraint contract.

The parent order is exogenous. The agent may choose **how** to execute it, not whether it should exist. This avoids converting an execution study into a directional trading strategy.

### 3.2 Inventory and completion

Let \(q_t\in[0,Q_0]\) be remaining inventory. Child fills have non-negative quantities \(x_i\). At the deadline, any residual \(q_T\) is completed using the same documented terminal aggressive-execution rule for every strategy:

\[
\sum_i x_i+q_T=Q_0.
\]

A penalty for terminal inventory may appear in an optimiser or RL reward, but reported implementation shortfall must include an actual terminal-completion transaction. A strategy may not appear cheap by leaving inventory unexecuted.

### 3.3 Primary cost metric

Let \(p_0\) be the arrival benchmark, \(p_i\) the price of child fill \(i\), \(p_T^{\mathrm{term}}\) the terminal-completion price, and \(F\) total explicit fees minus rebates. Quote-currency implementation shortfall is:

\[
IS_e = \sigma\left(\sum_i x_i p_i + q_Tp_T^{\mathrm{term}} - Q_0p_0\right)+F.
\]

Normalised implementation shortfall in basis points is:

\[
IS^{\mathrm{bps}}_e=10^4\frac{IS_e}{Q_0p_0}.
\]

Lower is better. The formula is symmetric for buys and sells under the stated side convention.

One pre-specified core confirmatory estimand is the paired difference:

\[
\Delta_e=IS^{\mathrm{bps}}_{e,\mathrm{ML\text{-}MPC}}-IS^{\mathrm{bps}}_{e,\mathrm{MPC}},
\]

on identical locked-test episodes. This estimand tests one central mechanism—whether ML adds decision value beyond the same controller without ML. It is not a replacement for the broader project question, which also covers classical baselines, deep learning, imitation learning, reinforcement learning, robustness, regime shifts, latency, fees, queue error, and impact misspecification.

### 3.4 Secondary outcomes

Secondary execution outcomes include:

- median and mean implementation shortfall;
- 95% and 99% tail cost;
- CVaR of implementation shortfall;
- cost variance and downside semideviation;
- terminal aggressive-completion fraction;
- passive and aggressive fill fractions;
- fill rate before deadline;
- time-weighted residual inventory;
- cancellation and replacement counts;
- post-fill adverse selection;
- explicit fee and rebate contribution;
- decision latency and model inference latency;
- events processed per second;
- peak memory use;
- CPU scaling and, where justified, GPU throughput/latency.

Every metric must have a mathematical or algorithmic definition before final evaluation.

---

## 4. Common information and action contract

### 4.1 Information available to a strategy

At decision time \(t\), a strategy may use only information whose exchange event time is no later than the strategy's latency-adjusted observation cutoff. The common observation may contain:

- the visible top \(K\) bid and ask levels;
- spread, mid-price, microprice, and depth imbalance;
- recent trades and order-flow summaries computed only from past events;
- elapsed time and time remaining;
- remaining parent inventory;
- the strategy's own acknowledged active orders and fills;
- model predictions generated from the same causal observation;
- fee, tick, lot, latency, and risk parameters known before the episode.

A strategy may not use future trades, later book updates, hidden order identities absent from the dataset, final-period labels, or an oracle queue position in aggregate historical replay.

### 4.2 Decision clock

The exchange processes every market event in event time. Strategy actions occur on a common configurable decision grid. The primary grid is **100 milliseconds**; 10, 50, 250, and 1,000 milliseconds are stress or sensitivity settings where data resolution and compute permit.

A policy does not receive an advantage from being called more frequently than another policy unless the experiment is explicitly a decision-frequency study.

### 4.3 Action space

The common action interface supports:

- no action;
- cancel one or more acknowledged active child orders;
- submit a passive or marketable limit order;
- submit an aggressive market order when the venue model supports it;
- choose child quantity from a predeclared set of fractions of remaining inventory;
- choose limit placement from a predeclared set of tick offsets relative to the relevant best quote.

The default research contract permits at most one live child order for the parent order at a time. A multi-order extension is allowed only as a separately identified experiment because multiple simultaneous orders change queue, cancellation, and action-comparison complexity.

All strategies share the same order-size, tick-size, rate-limit, latency, fee, rejection, and terminal-completion rules.

---

## 5. Two simulation modes

### 5.1 Synthetic exact mode

Synthetic exact mode contains individual orders and exact price-time priority. It is used for:

- matching-engine validation;
- exact queue-position tests;
- calibrated synthetic regimes;
- controlled market-impact experiments;
- imitation-learning data generation;
- reinforcement-learning training;
- domain randomisation;
- simulator-exploitation tests;
- adversarial stress experiments.

Required properties include exact order IDs, FIFO within price, partial fills, cancellations, acknowledgements, rejection rules, fees, latency, deterministic replay, and conservation invariants.

### 5.2 Historical aggregate mode

Historical aggregate mode replays observed level-2 book updates and trades. It is used for:

- real observed market paths;
- causal feature and label generation;
- supervised model development;
- execution comparisons under a small-agent ghost assumption;
- temporal and cross-instrument evaluation;
- queue-model sensitivity.

Aggregate level-2 data generally do not reveal individual historical order identities or exact FIFO position. Therefore, historical replay must expose separate optimistic, central/calibrated, and pessimistic queue-ahead models. Results must report the queue model used.

A simulated order does not alter the later recorded market path. Historical replay therefore does not establish endogenous impact. Parent sizes must be kept within a training-data-defined small-agent envelope for the primary historical study. Larger parent sizes belong to synthetic or explicit stress studies.

### 5.3 Cross-mode interpretation

Historical and synthetic results answer different questions:

- historical replay tests behaviour on real observed paths under explicit counterfactual fill assumptions;
- synthetic exact simulation tests causal engine behaviour and controlled misspecification;
- agreement across modes strengthens a conclusion;
- disagreement is a finding, not an error to hide.

---

## 6. Data and episode design

### 6.1 Venue decision

The venue and feed are not frozen in Step 2. They will be selected in Step 11 after current data availability, licensing, message semantics, sequence recovery, and historical coverage are verified from primary sources.

The final study must include at least two liquid instruments from the same well-documented electronic venue. A third instrument may be added as an external transfer test. Exact instrument names are frozen before model development.

### 6.2 Minimum usable data

The primary empirical study requires enough complete, validated whole days to create four chronological segments and dependence-aware uncertainty intervals. The minimum is:

- 50 usable whole days for training;
- 20 for model and controller validation;
- 10 for calibration and protocol finalisation;
- 20 locked final-test days;
- for each required instrument.

This is a minimum quality gate, not a target. If data are inexpensive to capture or obtain, the project should use materially more.

### 6.3 Chronological split rule

After removing invalid days using rules defined without outcome inspection, remaining whole days are ordered chronologically and allocated:

- first 50%: training;
- next 20%: validation and hyperparameter selection;
- next 10%: probability calibration, robustness-threshold selection, and final protocol freeze;
- final 20%: locked test.

Rounding occurs at whole-day boundaries while preserving the minimum counts above. No random row-level split is permitted.

### 6.4 Episode origins

Episode start times are generated by a deterministic schedule fixed before final evaluation. Starts must not be selected because later prices or fills look favourable. Eligibility uses only information available at or before the start and may exclude:

- feed gaps;
- invalid or crossed reconstructed books;
- venue maintenance periods;
- insufficient prehistory for causal features;
- episodes whose full horizon crosses an invalid interval.

Overlapping episodes may be retained for computational efficiency, but dependence must be handled in inference. A non-overlapping sensitivity analysis is required.

### 6.5 Parent-order design

The primary execution horizon is **60 seconds**. Secondary horizons are 30 and 300 seconds.

Parent-order size is defined relative to training-period visible liquidity, not future test liquidity. The primary historical size is 25% of the training-period median opposite-side top-five-level depth for the relevant instrument and local time bucket. Sensitivities use 10%, 50%, and 100%. The 100% setting is explicitly a stress case under ghost replay.

Buy and sell episodes are both required. Their scheduled origins and quantities must be symmetric except where venue constraints make symmetry impossible.

---

## 7. Required strategy ladder

All strategies are mandatory in the final project unless an implementation is scientifically invalid for the selected data; any replacement requires a decision entry.

### 7.1 Classical and model-based strategies

1. **Immediate aggressive execution** — completes at episode start.
2. **TWAP** — deterministic equal-time schedule with documented rounding and terminal handling.
3. **Volume-informed schedule** — uses only training-period or past-only intraday volume profiles.
4. **Almgren–Chriss** — calibrated only on development data, with documented impact and risk parameters.
5. **Queue/liquidity-aware heuristic** — reacts to spread, depth, imbalance, urgency, and fills without learned predictions.
6. **Model-predictive controller (MPC)** — receding-horizon optimisation using non-ML state estimates.

### 7.2 Supervised ML-assisted strategy

7. **ML-assisted MPC** — the same controller and action constraints as MPC, augmented with calibrated short-horizon predictions. This is the primary learned strategy and the primary confirmatory comparison is against the non-ML MPC.

### 7.3 Deep prediction strategy

8. **Deep-model-assisted MPC** — replaces the tabular prediction layer with one compact temporal architecture selected and justified during the literature-review step. It must be compared with simpler models on prediction, calibration, decision value, inference cost, and robustness.

### 7.4 Imitation learning

9. **Imitation policy** — learns to approximate the validated MPC or robust MPC teacher. Behaviour cloning is required; dataset aggregation or another covariate-shift correction is required if validation demonstrates compounding error.

### 7.5 Reinforcement learning

10. **RL policy** — trained only after the environment, baselines, reward, terminal treatment, and action masking pass their gates. The default design is one policy-gradient algorithm with a finite discrete or multi-discrete action space, rather than a large algorithm sweep. It is evaluated against all relevant baselines under unseen synthetic regimes and zero-shot historical replay.

### 7.6 Robust variants

11. **Robust controller or robustly trained policy** — incorporates uncertainty sets, domain randomisation, distributionally robust objectives, risk-sensitive loss, or another method justified by the literature review. Its purpose is to trade some in-distribution mean performance for better worst-case or tail behaviour.

---

## 8. Prediction tasks

### 8.1 Primary observable target

The primary supervised target is side-specific best-quote depletion or trade-through within a fixed future horizon. Candidate horizons are 250 milliseconds, 1 second, and 5 seconds. The primary horizon is chosen on validation data using a predeclared combination of event support, calibration, and decision value, then frozen before the calibration and locked-test periods.

This target is an observable market event. It is not described as an exact personal fill probability.

### 8.2 Secondary target

The required secondary target is post-event adverse selection: the side-signed change in mid-price over a fixed interval after the relevant quote event. It may be modelled as regression, ordinal classification, or a calibrated probability of adverse movement. The formulation is frozen after Step 3 and before final model development.

### 8.3 Required model ladder

The final project includes:

- constant/base-rate and simple rule baselines;
- logistic or generalised linear models;
- gradient-boosted trees;
- a simple multilayer perceptron;
- one compact temporal deep model;
- calibration methods evaluated on the separate calibration segment;
- uncertainty or confidence estimates where justified.

The project will not add many deep architectures merely for breadth. One well-justified deep model is stronger than an unprincipled architecture sweep.

---

## 9. Learning-based policy design

### 9.1 Imitation learning question

The imitation study asks whether a learned policy can retain the teacher's execution quality while materially reducing per-decision compute. Required evaluation includes:

- action agreement;
- state-conditional error;
- implementation shortfall gap to teacher;
- tail-risk gap;
- inference latency;
- out-of-distribution degradation;
- uncertainty and abstention or fallback behaviour.

### 9.2 Reinforcement-learning question

The RL study asks whether an agent trained in calibrated synthetic environments can outperform strong non-learning and ML-assisted baselines without exploiting simulator defects, and whether any advantage transfers to unseen synthetic regimes and historical aggregate replay.

The RL reward must be derived from execution economics and include:

- realised execution cost;
- inventory risk through time;
- fees and rebates;
- adverse selection if used by the environment;
- terminal aggressive-completion cost;
- explicit penalties only where they correspond to a documented constraint or risk preference.

Reward components must be logged separately. Reward clipping, normalisation, and discounting must be documented. An agent that earns reward by violating intended economics fails the environment audit.

### 9.3 Training/evaluation separation

RL and imitation training may use synthetic exact data and development historical episodes. Locked historical test episodes may be used only for final zero-shot evaluation. No policy fine-tuning, replay-buffer construction, reward redesign, or hyperparameter selection may use the locked test.

---

## 10. Robustness programme

The final project must contain a structured robustness matrix rather than isolated hand-picked perturbations.

Required dimensions are:

- communication latency;
- market-data latency;
- processing and inference latency;
- decision frequency;
- visible liquidity;
- spread;
- volatility;
- order-flow intensity and clustering;
- queue-ahead error;
- cancellation-allocation assumptions;
- fee and rebate changes;
- parent-order size and horizon;
- impact coefficient and functional-form misspecification;
- degraded, miscalibrated, stale, constant, and shuffled predictions;
- instrument and temporal distribution shift;
- synthetic-to-historical simulator mismatch;
- observation noise and dropped market-data messages;
- model compute budget.

Stress settings are defined using training/calibration statistics or explicit adversarial values, never chosen because they produce a preferred final ranking.

---

## 11. Confirmatory and exploratory layers

### 11.1 Core pre-specified confirmatory contrast

The project’s central research question remains the exact broad question stated in Section 1.1. One core confirmatory contrast tests whether ML-assisted MPC reduces paired mean implementation shortfall relative to the same MPC without ML on the locked temporal test, under the central queue and latency assumptions.

Superiority requires:

- a two-sided 95% confidence interval for the paired mean difference entirely below zero;
- the lower bound of the 95% confidence interval for the completion-rate difference (ML-MPC minus MPC) is at least -1 percentage point;
- the upper bound of the 95% confidence interval for the 95% CVaR difference is no greater than the larger of 1 basis point or 5% of the absolute non-ML MPC 95% CVaR.

If mean cost improves but a guardrail fails, the result is reported as a trade-off, not as unqualified superiority.

### 11.2 Secondary confirmatory families

Secondary families cover:

- simple versus deep prediction;
- calibrated versus uncalibrated predictions;
- robust versus nominal control;
- imitation policy versus teacher;
- RL versus MPC and ML-assisted MPC;
- CPU versus compiled/GPU inference.

Within each family, multiplicity is controlled using Holm's procedure or a more appropriate preregistered method.

### 11.3 Exploratory analyses

Regime slicing, feature interpretation, architecture diagnostics, alternative parent sizes, and extra stress conditions may be exploratory. They must be labelled exploratory and may not be used to rewrite the central research question or any pre-specified hypothesis after the test is opened.

---

## 12. Reproducibility and software standard

The final repository must provide:

- modern C++ with explicit ownership, RAII, fixed-point market quantities, and clean interfaces;
- Python with a packaged `src` layout and strict typing for production modules;
- CMake, CTest, a C++ unit-test framework, pybind11, pytest, Ruff, and static type checking;
- pinned Python and C++ dependencies;
- Linux CI and at least one second operating-system/compiler path;
- ASan and UBSan; TSan where practical;
- property and fuzz tests for parser and matching-engine surfaces;
- deterministic replay hashes for small fixtures;
- structured logs and versioned schemas;
- raw/interim/processed/sample data separation;
- checksums and provenance manifests;
- experiment manifests containing code commit, data hashes, configuration, seeds, software versions, and hardware metadata;
- a fast artifact-consistency check;
- a genuine clean-environment sample pipeline rerun;
- separate commands for quick, standard, and full experiments;
- automatic table and figure generation from raw experiment outputs;
- paper tables imported or generated from machine-readable results rather than typed manually.

Coverage percentages must state their denominator and exclusions. Passing tests are evidence for tested paths, not proof of correctness.

---

## 13. Performance and CUDA scope

Performance work is part of the final project, but every optimisation must follow correctness and profiling.

Required performance studies include:

- event-engine throughput and latency distributions;
- memory allocation and cache behaviour;
- single-thread versus multithread scaling;
- Python/C++ boundary overhead;
- model inference latency at batch size one;
- batched inference throughput;
- ONNX or another compiled inference path;
- CPU-versus-GPU training and inference where hardware permits;
- end-to-end latency injection into execution results.

CUDA is an **evaluated engineering path**, not a forced positive claim. After profiling, the project must identify the best candidate among feature extraction, batched simulation, or neural inference. If transfer and launch overhead make CUDA inappropriate, the project must demonstrate that with measurements. If a suitable bottleneck exists, one justified CUDA implementation is required and must include numerical-consistency tests and profiler evidence.

The full project is not complete until this decision has been resolved by evidence; merely omitting CUDA or adding an unused kernel is not acceptable.

---

## 14. Final deliverables

The completed project includes:

1. validated C++ matching and event engine;
2. historical capture/ingestion and aggregate replay;
3. calibrated synthetic environment and stress generator;
4. complete classical and adaptive strategy ladder;
5. supervised and deep prediction models;
6. ML-assisted controller;
7. imitation-learning policy;
8. RL policy with simulator-mismatch evaluation;
9. robustness matrix and statistical analysis;
10. performance, compiled-inference, and CUDA decision study;
11. automatically generated figures and tables;
12. a 10–12-page technical report plus appendices;
13. a clean public repository, sample dataset, Docker/reproducibility path, release tag, `CITATION.cff`, and archival package;
14. evidence-bounded CV, interview, and professor-outreach materials.

Negative or mixed empirical findings do not make the project incomplete. Missing required systems, comparisons, audits, or reproducibility evidence do.

---

## 15. Current state

Completed:

- Step 1: audit of both existing repositories and current project materials;
- Step 2: full-scope scientific and engineering specification freeze;
- correction of the reduced-scope v1 framing;
- formal primary estimand, guardrails, split rules, action contract, full strategy ladder, and completion criteria.

Not completed:

- literature review;
- repository implementation;
- venue and data-source selection;
- simulator or data pipeline;
- any model, strategy, experiment, result, performance benchmark, paper, or release.

The next step is **Step 3 — academic literature review and design-evidence matrix**. No implementation should precede that review except trivial storage of these governance documents.
