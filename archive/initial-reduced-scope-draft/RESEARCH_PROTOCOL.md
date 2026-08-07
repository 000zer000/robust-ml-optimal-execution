# RESEARCH_PROTOCOL.md

## Document control

- **Protocol version:** 0.1.0
- **Status:** prospective draft; must be frozen before final-test evaluation
- **Last updated:** 2026-08-06
- **Project:** Robust Execution

This document defines the evaluation methodology before final results are examined. Any change made after the locked test period is first accessed must be recorded in `DECISIONS.md`, identified in the report as exploratory or post hoc, and must not silently replace the original protocol.

---

## 1. Research objective

Evaluate whether a calibrated short-horizon quote-depletion prediction improves the decisions of a queue-aware execution controller, compared with the same controller without machine learning and with strong classical baselines, under identical historical episodes and controlled stress conditions.

The protocol distinguishes predictive performance from execution performance. Better AUROC, log loss, or classification accuracy is not sufficient evidence of success. The primary outcome is realised execution cost.

---

## 2. Experimental units

An experimental unit is an **execution episode** defined by:

- venue and instrument;
- start timestamp;
- side: buy or sell;
- parent quantity fixed at episode start;
- execution horizon;
- latency profile;
- fee schedule;
- queue-position model;
- strategy;
- random seed when synthetic components are active.

All compared strategies must receive the same market path, parent order, side, horizon, fees, and stress configuration. This enables paired comparisons.

### 2.1 Initial instruments

- BTC-USD
- ETH-USD

The report must not generalise findings automatically to equities, futures, or other exchanges.

### 2.2 Episode construction

Episodes will be generated mechanically rather than selected by performance.

Provisional rule:

1. divide each eligible day into fixed start-time intervals;
2. create episodes at a predefined cadence, initially every 15 minutes;
3. alternate or deterministically balance buy and sell sides;
4. exclude only episodes failing predeclared data-quality rules;
5. derive parent quantity from information available strictly before episode start;
6. run every eligible strategy on every retained episode.

The final cadence may be adjusted after the pilot solely for computational feasibility. The adjustment must be recorded before model comparison.

### 2.3 Parent-order size

The parent quantity must be predetermined at episode start. A provisional scaling is a fraction of the median visible depth over a trailing pre-episode window, with several size regimes such as small, medium, and large. The exact formula will be fixed after the data pilot.

Requirements:

- no use of future episode volume or future depth;
- identical size for all strategies in an episode;
- size regime reported with every result;
- large regimes treated as stress tests if the small-agent assumption becomes weak.

### 2.4 Horizons

Provisional horizons:

- 60 seconds;
- 300 seconds;
- 900 seconds.

One horizon may be designated primary after pilot diagnostics, before final model selection. The others remain sensitivity analyses.

---

## 3. Data collection and provenance

### 3.1 Primary source

The provisional primary source is Coinbase Exchange's public WebSocket level-2 feed, supplemented by market trades and heartbeat/connection information.

### 3.2 Raw storage

Raw messages must be retained without semantic rewriting in compressed append-only files, for example:

```text
data/raw/coinbase/YYYY/MM/DD/<product>/<connection_id>.jsonl.zst
```

Each capture segment must have a manifest containing:

- venue;
- product;
- channel list;
- capture start and end;
- local software commit;
- host clock information;
- message count;
- byte count;
- checksum;
- disconnects and reconnects;
- sequence or continuity diagnostics;
- parser version.

### 3.3 Canonical representation

Validated data will be converted to an Arrow/Parquet event schema with integer timestamps. Raw, interim, and processed data must remain separate.

Minimum event fields:

- exchange timestamp when available;
- receive timestamp;
- product;
- event type;
- side;
- price in integer ticks or exact decimal representation;
- quantity in fixed-point or exact decimal representation;
- sequence/update identifier when available;
- source file and row offset;
- parser version;
- data-quality flags.

Binary floating-point must not be the authoritative representation of exchange prices or sizes in the matching engine.

### 3.4 Data-quality gates

A capture segment is ineligible if any critical condition cannot be resolved or bounded:

- malformed JSON or schema mismatch;
- unhandled message type affecting book state;
- unrecoverable snapshot/update inconsistency;
- sequence gap or out-of-order state that cannot be repaired;
- crossed or negative-spread book after applying documented recovery logic;
- non-monotonic canonical event ordering without an explicit tie rule;
- missing provenance or checksum.

Non-critical defects may be flagged and retained for sensitivity analysis, but cannot be silently ignored.

---

## 4. Two simulation modes

### 4.1 Synthetic matching-engine mode

Purpose:

- test exact exchange mechanics;
- create controlled market regimes;
- measure policy behaviour when individual order identity and FIFO queue position are known;
- stress latency and model misspecification.

Required mechanics:

- multiple bid and ask levels;
- price-time priority;
- limit and market orders;
- cancellations;
- partial fills;
- order acknowledgements and rejects;
- deterministic tie-breaking;
- configurable fees/rebates;
- exact queue position;
- reproducible random event generation.

### 4.2 Aggregate historical-replay mode

Purpose:

- evaluate strategies against real observed price-level dynamics;
- preserve the observed exogenous market path;
- study robustness under transparent fill assumptions.

Limitations:

- public level-2 price-level updates do not expose individual order identities;
- cancellations and executions may not always be separable perfectly;
- the user's hypothetical order did not exist in the recorded market;
- future market events are not causally changed by simulated user actions.

The historical mode therefore uses a **small-agent ghost-execution assumption**. Aggressive child orders consume the visible book for fill-price calculation, but the recorded future market path is not rewritten. Passive fills are estimated using a declared queue-ahead model.

At minimum, three queue models must be evaluated:

- **optimistic:** a larger fraction of displayed depletion benefits the simulated order;
- **neutral:** a documented central queue-ahead rule;
- **pessimistic:** cancellations ahead are limited and depletion behind is not credited.

The exact formulas must be frozen before final evaluation.

---

## 5. Event timing and latency

All timestamps in the engine use integer nanoseconds or another documented integer unit.

Latency is decomposed into:

1. market-data transport latency;
2. policy decision/inference latency;
3. outbound order latency;
4. exchange processing latency;
5. acknowledgement latency.

The scheduler must define deterministic precedence for events sharing a timestamp. A proposed order is:

1. exchange market event;
2. market-data delivery;
3. policy timer;
4. decision completion;
5. outbound order arrival;
6. exchange matching/validation;
7. acknowledgement/fill delivery.

This ordering is provisional until tested against hand-computed scenarios.

Latency scenarios will include a base case and predefined stresses, for example 0, 10, 50, 100, and 250 milliseconds of additional decision-to-exchange delay. Values must be justified as experimental scenarios rather than claims about a specific firm's infrastructure.

---

## 6. Strategies

### S0 — Immediate execution

Execute the full parent quantity aggressively at episode start, subject to visible depth and the declared terminal/impact rule.

Purpose: lower-variance, high-immediacy reference.

### S1 — TWAP

Split the parent order into equal target quantities over equal time intervals. Child execution rules must be fixed and reported.

### S2 — Historical volume-profile schedule

Allocate target quantity using a volume profile estimated only from training-period or pre-episode history. For 24/7 markets, hour-of-week or another stable periodic grouping may be used if supported by pilot diagnostics.

### S3 — Almgren–Chriss schedule

Implement the discrete Almgren–Chriss trajectory under clearly stated volatility, risk-aversion, and impact parameters. Parameters must be calibrated without final-test information. The schedule controls target inventory through time; a documented child-order rule maps schedule targets to book actions.

### S4 — Non-ML queue-aware controller

Use observable state variables and fixed/calibrated rules, without a learned predictor. Candidate inputs include:

- spread;
- top-level and multi-level imbalance;
- queue ahead;
- remaining inventory;
- time remaining;
- recent volatility;
- recent trade intensity;
- short-term order-flow imbalance.

This is the most important baseline for isolating the value of machine learning.

### S5 — ML-assisted receding-horizon controller

Use the same action set, constraints, cost function, and state as S4, but add the calibrated quote-depletion probability. The controller may solve a short-horizon discrete optimisation or evaluate a finite action set under expected cost.

The ML strategy is not allowed extra future information, a weaker completion constraint, or more favourable fees/latency.

### Neutral-prediction ablation

Run S5 with a constant base-rate prediction. This distinguishes controller architecture gains from predictive-information gains.

---

## 7. Prediction target and labels

### 7.1 Primary target

For side-specific best quote at decision time `t`, define:

```text
Y(t, h) = 1
```

when the displayed queue at that quote is depleted or the market trades through that price within horizon `h`; otherwise `Y(t, h) = 0`.

The exact treatment of temporary quote disappearance, reconnect boundaries, price improvement, and crossed updates must be specified in the label implementation and tested.

### 7.2 Prediction horizons

Candidate short horizons, chosen before final training:

- 250 ms;
- 1 s;
- 5 s.

The pilot will determine which horizon has sufficient event support and decision relevance. At most one horizon is primary in v1.0; others are sensitivity analyses.

### 7.3 Features

All features must be causal and use only information available by the decision timestamp after applying market-data latency.

Candidate feature groups:

- spread and mid-price;
- level-1 to level-10 depth;
- signed depth imbalance;
- microprice;
- recent order-flow imbalance;
- trade sign/intensity proxies;
- queue growth/depletion rates;
- short-horizon realised volatility;
- time since last price change;
- time-of-week;
- instrument identifier where a pooled model is used.

Every feature must have a timestamp contract and an automated causality test.

### 7.4 Models

Required:

- logistic regression;
- histogram gradient-boosted classifier;
- calibration layer when validation diagnostics justify it.

Optional after the baseline gate:

- one compact temporal model.

No model family is selected using the locked final test.

### 7.5 Predictive metrics

- log loss;
- Brier score;
- expected calibration error with binning sensitivity;
- calibration curve;
- AUROC;
- precision-recall metrics when class imbalance is material;
- inference time distribution;
- feature and model ablations.

Prediction metrics are secondary to execution outcomes.

---

## 8. Data splitting

### 8.1 Chronological split

After the pilot and capture period, use contiguous time blocks:

- training period;
- validation/model-selection period;
- purge gap at least as long as the maximum label and feature horizon;
- locked final-test period.

No random event-level split is permitted.

### 8.2 Final-test lock

Before accessing final-test strategy results:

- feature list frozen;
- label definition frozen;
- model classes frozen;
- calibration method frozen;
- strategy parameters frozen;
- episode generation frozen;
- primary metric frozen;
- stress grid frozen;
- analysis script hash recorded.

Any later change produces a new protocol version and labels the previous final test as used.

### 8.3 Scaling and preprocessing

- fit scalers/imputers on training data only;
- transform validation and test without refitting;
- do not forward-fill across capture gaps unless explicitly justified;
- derive periodic features without using future observations;
- preserve missingness indicators when informative.

---

## 9. Execution metrics

Let:

- `s = +1` for a buy parent order and `s = -1` for a sell;
- `Q` be the intended parent quantity;
- `q_i` be fill quantity;
- `p_i` be fill price including fee treatment as declared;
- `P_0` be the arrival mid-price;
- `Q_f = Σ_i q_i` be executed quantity.

### 9.1 Primary metric — implementation shortfall

For a completed episode:

```text
IS_bps = 10,000 × s × ((Σ_i q_i p_i) / Q - P_0) / P_0
```

A positive value is worse for both buys and sells under this sign convention.

Terminal residual inventory is force-completed under the same declared rule for all strategies. The primary metric includes forced completion so incomplete strategies cannot appear artificially cheap.

### 9.2 Secondary metrics

- mean and median implementation shortfall;
- standard deviation;
- 95% and 99% cost quantiles;
- CVaR at 95%;
- completion before terminal time;
- residual inventory before forced completion;
- forced-liquidation cost;
- passive fill fraction;
- aggressive-order fraction;
- cancellation count/rate;
- time to specified completion fractions;
- adverse selection after passive fills;
- realised spread/capture where definable;
- decision latency;
- model inference latency;
- replay throughput;
- events per second;
- peak memory;
- CPU scaling for selected workloads.

Every metric must have a mathematical or algorithmic definition in the report.

---

## 10. Statistical analysis

### 10.1 Primary comparison

Primary paired contrast:

```text
Δ_e = IS_bps(S5, episode e) - IS_bps(S4, episode e)
```

Negative values favour the ML-assisted controller.

Report:

- mean paired difference;
- median paired difference;
- 95% paired bootstrap confidence interval;
- standardised effect size where meaningful;
- fraction of episodes improved;
- distribution plots, not only averages.

Bootstrap resampling must preserve dependence. The default unit should be a day or another block longer than short-term autocorrelation, not individual events. Block choice will be determined from pilot dependence diagnostics and frozen before final evaluation.

### 10.2 Baseline family

S5 will also be compared with S0-S3. These are secondary family comparisons. Report all predefined contrasts. Do not highlight only favourable strategies or instruments.

### 10.3 Multiple comparisons

The report will distinguish:

- one primary S5-versus-S4 contrast;
- secondary predefined baseline contrasts;
- exploratory subgroup analyses.

Confidence intervals and, where used, adjusted p-values must be interpreted with the number of comparisons in mind. Statistical significance is not a substitute for economic or operational magnitude.

### 10.4 Heterogeneity

Report results by:

- instrument;
- side;
- parent-size regime;
- horizon;
- spread/liquidity regime;
- volatility regime;
- time period.

Subgroup analyses are descriptive unless predeclared and adequately powered.

---

## 11. Robustness and stress tests

### 11.1 Historical replay stresses

- added market-data/order latency;
- optimistic/neutral/pessimistic queue model;
- fee and rebate perturbation;
- increased terminal penalty;
- reduced visible depth;
- widened spread;
- degraded prediction probabilities;
- calibration shift;
- missing/deferred market-data packets where recoverable.

### 11.2 Synthetic stresses

- thin liquidity;
- high and low volatility;
- clustered arrivals;
- temporary liquidity shock;
- changing order-flow imbalance;
- queue cancellation shock;
- impact coefficient misspecification;
- adverse-selection regime shift;
- fee/rebate changes;
- latency shift;
- unseen combinations of generator parameters.

Synthetic regimes must be labelled as calibrated, stylised, or adversarial. They must not be presented as observed market facts.

### 11.3 Model ablations

- constant prediction;
- uncalibrated versus calibrated probability;
- remove order-flow features;
- remove deep-level features;
- remove time-of-week;
- single-instrument versus pooled model;
- increased inference delay without changing predictions;
- corrupted/noisy probability stress.

---

## 12. Simulator validation protocol

No strategy result is considered valid until all applicable engine gates pass.

### 12.1 Unit scenarios

- price priority;
- FIFO time priority;
- partial fill;
- full fill;
- cancellation before and after partial fill;
- invalid cancellation;
- market order sweeping levels;
- fee/rebate calculation;
- tick and size validation;
- crossed-book prevention;
- reject behaviour;
- queue-ahead accounting;
- residual inventory;
- terminal completion;
- deterministic replay.

### 12.2 Invariants

- non-negative resting quantity;
- no order filled above remaining quantity;
- executed buy quantity equals executed sell quantity in synthetic matching;
- inventory change equals signed fills;
- cash change reconciles with fills and fees;
- best bid below best ask outside explicitly modelled auctions/crosses;
- total child execution never exceeds parent quantity except in a deliberate rejection test;
- fixed configuration and seed produce byte-identical core logs where feasible.

### 12.3 Differential and reference tests

- manually calculated event tapes;
- simple Python reference book for small scenarios;
- Python/C++ metric cross-checks;
- aggregate replay snapshots compared at checkpoints;
- parser round-trip tests.

### 12.4 Fuzz/property tests

Generate valid and invalid event sequences to test invariants, determinism, and reject handling. Fuzzing is a support tool, not a replacement for explicit scenarios.

---

## 13. Performance protocol

Performance optimisation occurs only after correctness.

For each benchmark:

- record CPU, core count, memory, OS, compiler, build type, flags, commit, and dependency versions;
- use warm-up runs;
- report repeated measurements and distribution summaries;
- retain raw timings;
- separate parsing, replay, policy, model, and output costs;
- rerun correctness tests after changes;
- compare fixed workloads on fixed hardware.

The initial performance target is sufficient throughput to run the predefined experiment suite reproducibly, not an unsupported low-latency-trading claim.

---

## 14. Decision rules and interpretation

### 14.1 Evidence supporting H1

H1 receives support only if:

- the primary paired mean difference favours S5;
- its confidence interval excludes a practically negligible or adverse region defined before final testing;
- completion and tail cost do not degrade materially;
- the finding is not driven by a tiny subgroup or data defect.

The practical-equivalence margin will be chosen after pilot cost-scale diagnostics and before final testing.

### 14.2 Evidence against H1

H1 is not supported when:

- confidence intervals include material harm or negligible benefit;
- gains vanish after forced completion;
- gains rely on optimistic queue assumptions only;
- gains disappear under modest latency;
- gains result from an unfair parameter or information advantage.

### 14.3 Valid negative contribution

A negative result is still publishable as a technical report when the project shows, for example, that:

- prediction improvements do not translate into execution value;
- simple adaptive rules dominate under latency;
- queue uncertainty overwhelms model gains;
- calibration matters more than ranking metrics;
- strategy rankings are regime-dependent.

---

## 15. Reproducibility requirements

The repository must provide:

- a pinned environment;
- one-command unit tests;
- one-command small deterministic example;
- a separate full-experiment command;
- saved experiment configs;
- saved code/data/model hashes;
- automatic table/figure generation;
- lightweight sample data for CI;
- no manual copying of result numbers into the report;
- provenance for every reported table and figure.

---

## 16. Protocol change log

| Version | Date | Change | Final test accessed? |
|---|---:|---|---|
| 0.1.0 | 2026-08-06 | Initial scope and prospective methodology | No |
