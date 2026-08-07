# Research Protocol

## Document control

- **Version:** 0.2.1 — corrected protocol skeleton frozen at Step 2
- **Status:** Binding except explicitly listed pre-data fields
- **Last updated:** 2026-08-06
- **Final-test status:** Not created or opened

This protocol defines the experimental rules before implementation and final results. Fields that depend on the verified venue/feed or the Step 3 literature review are marked **pre-data field**. They must be resolved and committed before the calibration segment is opened. They are not permission to change methodology after seeing final-test outcomes.

---

## 0. Governing research question

> Can machine-learning-assisted execution policies improve realised execution quality relative to strong classical baselines, and do those improvements survive latency, liquidity shifts, queue-model errors, market-impact misspecification, changing fees, and out-of-distribution market regimes?

This exact broad question governs the protocol. The ML-assisted-MPC versus non-ML-MPC comparison is a pre-specified core confirmatory contrast used to test one part of the question; it is not the project’s replacement research question.

---

## 1. Experimental objects

### 1.1 Unit of simulation

The engine operates on events. The policy operates on decision epochs. The statistical unit is an execution episode. Dependence between episodes from nearby times is preserved in the uncertainty procedure.

### 1.2 Episode contract

Each episode records:

- venue and instrument;
- side;
- parent arrival timestamp;
- hard deadline;
- parent quantity and size bucket;
- arrival benchmark;
- strategy name and version;
- queue model;
- latency model;
- fee schedule;
- impact mode;
- random seed where applicable;
- code commit and data hashes;
- every child order, acknowledgement, cancel, rejection, and fill;
- terminal completion;
- complete accounting metrics.

Episodes with engine or data-contract violations fail; they are not silently dropped from one strategy only.

### 1.3 Common information set

All strategies observe the same causal market state after applying the same observation latency. Strategy-specific predictions are allowed only when their generation time and inference latency are included. An oracle may appear only as an explicitly labelled upper-bound ablation.

### 1.4 Common action set

All strategies use the same order types, size buckets, price offsets, active-order limit, rate limits, fees, rejection rules, and terminal completion. A strategy that cannot naturally use an action may ignore it, but no baseline is artificially restricted.

---

## 2. Data protocol

### 2.1 Source selection — pre-data field

Step 11 will freeze:

- venue;
- feed/channel;
- instruments;
- message semantics;
- licence and redistribution rules;
- raw storage format;
- capture or historical acquisition method;
- expected sequence/snapshot recovery procedure.

Only primary-source documentation and legally usable data are accepted.

### 2.2 Minimum data

Each required instrument must have at least 100 validated whole days allocated as:

- training: at least 50;
- validation: at least 20;
- calibration/protocol freeze: at least 10;
- locked test: at least 20.

If this cannot be met, data collection continues or the data source is replaced before final modelling.

### 2.3 Validation before splitting

Exclusion rules are defined before inspecting strategy outcomes. Required checks include:

- schema and type validation;
- original and canonical timestamp validity;
- sequence continuity;
- snapshot/update consistency;
- duplicate and gap detection;
- crossed or locked book policy;
- finite non-negative displayed quantities;
- tick/lot consistency;
- trade/update ordering rules;
- reconnect boundaries;
- source/checksum manifest;
- complete episode horizon.

No interpolation or synthetic repair of missing order-book events is allowed in the primary historical study. Invalid spans are quarantined.

### 2.4 Split algorithm

Whole valid days are ordered chronologically and split 50%/20%/10%/20% into train/validation/calibration/test, subject to minimum counts. Exact dates and hashes are committed before model development.

The locked test is read-protected by process: experiment scripts require an explicit final-test flag and write an access log. Routine development commands must not load test outcomes.

### 2.5 Test invalidation policy

After the final test is opened, only these events permit a corrected rerun:

- a demonstrable software defect affecting the frozen analysis;
- corrupted source data;
- an incorrect implementation of the preregistered protocol.

The issue, affected results, fix, and decision must be documented. The original test result remains archived. When feasible, a new later time period becomes the replacement confirmation set.

Changing a model, threshold, queue assumption, metric, or hypothesis because the result was disappointing does not permit relabelling a rerun as confirmatory.

---

## 3. Episode sampling

### 3.1 Start schedule

Episode starts follow a deterministic schedule frozen before the test, such as every fixed number of minutes within eligible market hours. The interval is a **pre-data field** selected to provide sufficient episodes without excessive duplication.

Eligibility uses only information available by the start:

- valid reconstructed book;
- required causal feature history;
- no known feed gap within already observed history;
- venue open/active status;
- spread/depth conditions if a preregistered liquidity filter is used.

Later outcomes cannot determine eligibility.

### 3.2 Side assignment

Every eligible start produces both a buy and sell episode when the historical/synthetic environment supports symmetric execution. If duplication would create an invalid counterfactual assumption, side assignment follows a deterministic balanced schedule independent of future prices.

### 3.3 Horizon and size

Primary horizon: 60 seconds. Secondary horizons: 30 and 300 seconds.

Primary size: 25% of training-period median top-five opposite-side depth in the relevant instrument/time bucket. Secondary sizes: 10%, 50%, and 100%. The 100% historical setting is labelled a stress case.

Exact lot rounding is deterministic and documented.

### 3.4 Overlap

The primary dataset may include overlapping episodes. Statistical resampling operates on contiguous day blocks, not independent episodes. A non-overlapping episode analysis is required as sensitivity.

---

## 4. Historical queue protocol

Historical L2 replay uses three queue-ahead models:

1. **Optimistic:** cancellations/depletions are allocated to quantity ahead as rapidly as defensibly possible.
2. **Central:** allocation parameters are calibrated on development data or selected from literature/venue semantics before the test.
3. **Pessimistic:** displayed reductions are allocated behind the simulated order unless execution ahead is directly supported.

The exact formulas are **pre-data fields** because they depend on feed semantics. All are implemented and tested before final evaluation.

The central queue model is used for the primary result. Optimistic and pessimistic models are mandatory sensitivity analyses. Queue-model identity is stored in every result row.

---

## 5. Latency protocol

Total action delay is decomposed into:

- market-data transport/observation latency;
- policy scheduling delay;
- feature and inference time;
- optimiser or policy compute time;
- outbound order latency;
- exchange processing/acknowledgement latency.

The central values are **pre-data fields**, calibrated or justified after venue selection. Required stress values include zero latency, central latency, and at least 0.5x, 2x, and 5x central end-to-end latency, plus absolute values that span 1–100 ms where meaningful.

Measured inference and controller times are injected, not merely discussed.

---

## 6. Baseline calibration

All hyperparameters, risk aversion, impact coefficients, thresholds, and controller weights are selected on training/validation only.

Fairness rules:

- identical episode origins;
- identical parent orders;
- identical action and latency constraints;
- identical fee/rebate schedule;
- identical terminal completion;
- no baseline uses future volume or test-period profiles;
- no baseline is tuned less carefully than learned methods;
- all failed or unstable configurations remain in the experiment log.

The predeclared primary comparator is the non-ML MPC. It cannot be replaced after seeing test results.

---

## 7. Prediction protocol

### 7.1 Timestamp contract

For a feature row at decision time \(t\), every source event must satisfy:

\[
t_{\mathrm{source}}\le t-t_{\mathrm{observation\ latency}}.
\]

Rolling windows are closed on the past. Labels begin strictly after the decision cutoff. Events at equal timestamps follow a venue-specific deterministic ordering frozen in the data contract.

Mutation tests must prove that changing future data cannot change earlier features or predictions.

### 7.2 Target selection

Candidate quote-depletion horizons: 250 ms, 1 s, 5 s.

Selection on validation uses this ordered rule:

1. minimum positive and negative event support in every required instrument;
2. valid calibration and no timestamp leakage;
3. best mean validation decision value in the fixed non-final controller;
4. if values are practically tied, select the longer horizon for stability.

The selected horizon is frozen before calibration/test.

### 7.3 Models

Required models:

- constant/base-rate;
- logistic/generalised linear;
- gradient-boosted trees;
- simple MLP;
- one compact temporal deep model.

Hyperparameters are selected on validation. Probability calibration is fitted only on the calibration segment. Test labels are not used for early stopping, calibration, threshold choice, or feature selection.

### 7.4 Prediction metrics

Primary prediction metrics are log loss and Brier score. Calibration plots and expected calibration error are required. ROC-AUC and PR-AUC are secondary and must be interpreted with class prevalence.

The final prediction model is not selected solely on AUC. Controller-relevant validation decision value is part of the predeclared selection rule.

---

## 8. ML-assisted controller protocol

The non-ML MPC and ML-MPC share:

- horizon;
- optimiser;
- action space;
- constraints;
- objective structure;
- queue model;
- latency model;
- terminal handling.

The only intended difference is the prediction-derived state or cost term. Additional code-path differences require an audit.

Required ablations:

- ML prediction replaced by its training base rate;
- shuffled predictions within day/instrument;
- stale predictions;
- uncalibrated predictions;
- perfect-event oracle;
- prediction term weight set to zero.

---

## 9. Imitation-learning protocol

### 9.1 Teacher

The teacher is the validated MPC or robust MPC selected before imitation training. Teacher actions and full states are logged from training/development environments only.

### 9.2 Behaviour cloning

A compact policy is trained to predict the teacher action. Class imbalance, invalid actions, and state normalisation are handled using training data only.

### 9.3 Covariate shift

Validation measures divergence between teacher-state and learner-state distributions. If rollout error compounds materially, dataset aggregation, corrective labels, or a conservative fallback is required.

### 9.4 Evaluation

The imitation policy is compared with the teacher on identical episodes for:

- mean and tail implementation shortfall;
- completion;
- action agreement;
- invalid-action rate;
- per-decision latency;
- OOD regimes;
- fallback/abstention behaviour.

---

## 10. RL protocol

### 10.1 Start gate

RL work starts only after:

- exact engine Gate B;
- data/replay Gate C;
- classical Gate D;
- supervised Gate E;
- stable reward and terminal-completion tests.

### 10.2 Environment

The RL environment uses synthetic exact mode for training. State, action, transition, reward, termination, and truncation semantics are versioned. Observation normalisation is fitted on training environments only.

### 10.3 Algorithm

One primary policy-gradient algorithm is selected after Step 3 based on action space and literature. Algorithm choice is a **pre-data field** frozen before RL experiments. A small sanity algorithm or tabular environment may be used for environment validation but does not count as the final RL method.

### 10.4 Seeds and selection

At least five independent seeds are required during development and at least ten independent training seeds are required for the final RL comparison. Additional seeds may be added based on a pre-test precision analysis, but the minimum may not be reduced.

No best-seed reporting. Results aggregate every preregistered seed.

### 10.5 Reward audit

Each reward component is saved separately. The following must pass:

- reward equals independently reconstructed economics within tolerance;
- residual inventory cannot disappear;
- duplicate fills cannot occur;
- terminal completion is charged;
- invalid actions are masked or penalised consistently;
- no future state enters the observation;
- random/no-op policies behave as expected;
- pathological actions cannot create reward through bookkeeping defects.

### 10.6 Transfer tests

Final RL evaluation includes:

- unseen synthetic seeds;
- unseen regime combinations;
- changed latency, fees, impact, and liquidity;
- at least one instrument not used for RL training where feasible;
- zero-shot historical aggregate replay;
- simulator-parameter mismatch.

No fine-tuning on locked historical test episodes.

---

## 11. Robustness matrix

Every strategy is evaluated on a common matrix. Central values and exact grids are frozen on training/calibration.

| Dimension | Required settings |
|---|---|
| Latency | zero, 0.5x, 1x, 2x, 5x central; absolute latency checks |
| Decision grid | 10, 50, 100, 250, 1000 ms when supported |
| Liquidity | training low/median/high quantiles plus adversarial thin case |
| Spread | training quantiles plus widened case |
| Volatility | training quantiles plus shock case |
| Queue | optimistic, central, pessimistic; cancellation-allocation perturbation |
| Fees/rebates | central, zero, adverse change, favourable change |
| Parent size | 10%, 25%, 50%, 100% depth scale |
| Horizon | 30, 60, 300 s |
| Impact | central, coefficient shifts, functional-form misspecification |
| Prediction | calibrated, uncalibrated, stale, constant, shuffled, degraded |
| Data quality | dropped/delayed update scenarios in synthetic mode |
| Distribution | later dates, second instrument, unseen synthetic regimes |
| Compute | measured model/controller latency and constrained budgets |

Historically observed, calibrated synthetic, and adversarial stress results are separated.

---

## 12. Statistical analysis

### 12.1 Primary aggregation

Within each instrument, side, size, and day, paired episode differences are averaged. The primary pooled estimate weights required instruments equally, preventing a higher-event-rate instrument from dominating.

### 12.2 Dependence-aware uncertainty

Primary confidence intervals use a stationary or moving-block bootstrap over ordered whole days within instrument. Block length is selected on validation using this rule:

1. compute the autocorrelation of daily paired mean differences;
2. choose the smallest lag at which absolute autocorrelation remains below 0.1 for two consecutive lags;
3. use at least two days and at most seven days;
4. freeze the value before final test.

All episodes in selected day blocks are retained. A cluster-by-day and non-overlapping-episode sensitivity analysis is also reported.

IID resampling of individual episodes is prohibited for primary inference.

### 12.3 Confidence and effect sizes

Report:

- paired mean and median difference;
- 95% confidence interval;
- bps effect size;
- relative change versus comparator;
- per-instrument and per-side results;
- completion and CVaR guardrails;
- number of days and episodes.

Guardrails use the same dependence-aware day-block bootstrap. Completion passes when the lower 95% bound for `completion_rate_ML-MPC - completion_rate_MPC` is at least -0.01. CVaR passes when the upper 95% bound for `CVaR95_ML-MPC - CVaR95_MPC` is no greater than `max(1 bps, 0.05 * abs(CVaR95_MPC))`.

### 12.4 Multiple comparisons

The single Tier-1 contrast is unadjusted but preregistered. Tier-2 families use Holm correction. Exploratory analyses report raw intervals and are labelled exploratory.

### 12.5 Missing and failed runs

A run that fails due to strategy logic, solver failure, numerical error, or timeout is recorded. A uniform failure policy is defined before test. Strategies may not receive different episode sets without a paired missingness analysis.

### 12.6 Practical significance

Statistical significance is not enough. Effects are interpreted relative to:

- baseline shortfall;
- fees;
- tail risk;
- completion;
- model/controller latency;
- queue-model uncertainty;
- instrument variability.

---

## 13. Performance protocol

### 13.1 Correctness before optimisation

Every optimised implementation must produce identical discrete events or documented numerical tolerance against the reference path. Correctness tests rerun after each optimisation.

### 13.2 Benchmark method

Benchmarks record:

- code commit;
- compiler and flags;
- Python/runtime/library versions;
- CPU/GPU model;
- core/thread count;
- memory;
- operating system;
- power mode where relevant;
- workload definition;
- warm-up;
- every repetition;
- median, dispersion, and outliers.

At least five timed repetitions are required after warm-up; more are used for unstable workloads.

### 13.3 CUDA decision

A profiler identifies candidate bottlenecks. One of three outcomes is allowed:

1. implement and validate a useful CUDA path;
2. use framework/compiled GPU inference and show end-to-end benefit;
3. demonstrate that transfer/launch overhead makes GPU/CUDA inferior for the relevant batch-one workload.

The decision must be supported by end-to-end latency and throughput, not kernel time alone.

---

## 14. Reproducibility protocol

Required commands:

- environment setup;
- formatting/lint/type checks;
- unit/integration/fuzz tests;
- quick deterministic sample;
- standard reproducibility run;
- full experiment run;
- artifact-consistency validation;
- paper table/figure regeneration.

Experiment manifests contain data hashes, code commit, configuration, seeds, runtime versions, and hardware metadata.

A committed artifact contract checks cross-file consistency. A separate clean-environment job reruns the sample pipeline from raw/sample inputs. These are not described as the same thing.

---

## 15. Frozen fields and amendment process

Frozen now:

- execution problem and primary metric;
- primary comparator and contrast;
- hard terminal completion;
- two-mode simulator distinction;
- historical ghost assumption;
- minimum instruments and days;
- chronological split algorithm;
- primary horizon and parent-size rule;
- common action/information contract;
- mandatory strategy/model ladder;
- full IL/RL/performance scope;
- primary guardrails;
- dependence-aware inference requirement;
- completion definition.

Pre-data fields to resolve before calibration/test:

- venue/feed/instruments;
- exact split dates and data hashes;
- feed-specific event ordering;
- central queue formula;
- central latency values;
- episode-start interval;
- exact feature set;
- selected prediction horizon;
- deep architecture;
- RL algorithm;
- robustness grid values derived from training data;
- bootstrap block length;
- final seed count after compute/precision analysis.

Every resolution is committed to `DECISIONS.md`. After the calibration period is opened, changes require an amendment with rationale. After the final test is opened, changes invalidate confirmatory status unless they correct a documented defect under the test-invalidation policy.
