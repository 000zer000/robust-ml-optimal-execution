# Research Questions and Hypotheses

## Document control

- **Version:** 0.2.1
- **Status:** Frozen at Step 2; amendments require a decision entry
- **Project:** Robust Execution Flagship
- **Last updated:** 2026-08-06

---

## 1. Scientific objective

The project studies execution, not directional speculation. A predetermined buy or sell parent order must be completed by a hard deadline. The research question is whether predictions or learned policies improve the cost-risk trade-off relative to strong classical and model-based methods, and whether any improvement survives realistic forms of delay, uncertainty, and distribution shift.

The project is designed to permit three scientifically valid outcomes:

1. learned methods improve execution robustly;
2. learned methods improve only under narrow conditions;
3. strong classical or model-based baselines remain superior.

No method is assumed to win.

---

## 2. Central research question

> **RQ1.** Can machine-learning-assisted execution policies improve realised execution quality relative to strong classical baselines, and do those improvements survive latency, liquidity shifts, queue-model errors, market-impact misspecification, changing fees, and out-of-distribution market regimes?

This is the exact authoritative research question supplied for the project. It governs the complete comparison of classical, model-based, machine-learning-assisted, deep-learning, imitation-learning, reinforcement-learning, and robust execution methods.

### 2.1 Core confirmatory sub-question

> **RQ1a.** On chronologically locked historical episodes, does a calibrated machine-learning prediction layer integrated into a queue-aware model-predictive controller reduce paired mean implementation shortfall relative to the same controller without machine learning, under identical information, action, latency, fee, queue, and terminal-completion rules?

RQ1a tests one mechanism inside RQ1. It does not redefine the project’s central question.

### 2.2 Core confirmatory estimand

For episode \(e\):

\[
\Delta_e=IS^{\mathrm{bps}}_{e,\mathrm{ML\text{-}MPC}}-IS^{\mathrm{bps}}_{e,\mathrm{MPC}}.
\]

The core confirmatory estimand is an equal-instrument-weighted mean of paired episode differences on the locked temporal test. Lower values favour ML-assisted MPC.

### 2.3 Null and alternative

\[
H_{0,1}:\mathbb{E}[\Delta_e]\ge 0
\]

\[
H_{A,1}:\mathbb{E}[\Delta_e]<0.
\]

The project reports a two-sided 95% confidence interval. Superiority for this core contrast is claimed only when the interval is entirely below zero and both risk/completion guardrails pass.

### 2.4 Guardrails

A lower mean cost is not sufficient when it is purchased with unacceptable non-completion or tail loss. ML-assisted MPC must also satisfy:

- lower 95% confidence bound for the completion-rate difference (ML-MPC minus MPC) at least -1 percentage point;
- upper 95% confidence bound for the CVaR95 difference no greater than the larger of 1 basis point or 5% of the absolute MPC CVaR95;
- no violation of common action, latency, or terminal-completion rules.

Failure of a guardrail changes the interpretation from “superior” to “mean-cost/tail-risk trade-off.”

---

## 3. Secondary research questions

### RQ2 — Prediction quality versus decision value

> Do discrimination and calibration improvements translate into lower execution cost, or can a model predict book events better while producing worse execution decisions?

Required comparisons:

- base-rate predictor;
- uncalibrated model;
- calibrated model;
- constant prediction;
- shuffled prediction;
- stale prediction;
- perfect-information oracle upper bound where constructible.

**Hypothesis H2:** calibration and decision-aware integration explain execution value better than headline classification accuracy alone.

A negative result is valid if predictive metrics improve but execution does not.

### RQ3 — Deep temporal model

> Does one compact temporal deep model add decision value beyond linear, tree, and simple neural baselines after accounting for calibration, inference latency, and model complexity?

**Hypothesis H3:** the deep model may improve event prediction, but its execution advantage will be smaller than its predictive advantage after compute and latency are included.

Required falsification:

- equal causal inputs and splits;
- equal controller;
- latency-free comparison;
- measured inference-latency comparison;
- parameter-count and compute disclosure;
- calibration comparison;
- ablation of temporal ordering.

### RQ4 — Latency and stale information

> At what communication, observation, decision, and inference latency does an adaptive or learned strategy lose its advantage?

**Hypothesis H4:** learned and highly adaptive strategies degrade faster than simple schedules as total latency increases, because their actions depend more heavily on short-lived signals.

This is tested across absolute and relative latency settings. A crossing point in strategy ranking is a central result.

### RQ5 — Queue uncertainty

> How sensitive are strategy rankings to optimistic, central, and pessimistic queue-ahead assumptions and to cancellation-allocation error?

**Hypothesis H5:** passive and learned strategies exhibit materially larger queue-model sensitivity than immediate or aggressive schedules.

No historical result may be reported without its queue model.

### RQ6 — Impact misspecification and parent size

> How do nominal and robust strategies respond when the impact model, parent size, or liquidity differs from development assumptions?

**Hypothesis H6:** robust control sacrifices some nominal mean performance but improves worst-case and tail outcomes under impact and liquidity misspecification.

Historical ghost replay is not used to claim causal endogenous impact. Impact questions are answered primarily in calibrated synthetic exact mode.

### RQ7 — Imitation learning

> Can an imitation policy approximate a validated model-based teacher while materially lowering decision latency, and where does covariate shift cause it to fail?

**Hypothesis H7:** imitation can retain most teacher performance in-distribution at lower inference cost, but behaviour cloning alone will show larger error under shifted regimes; dataset aggregation or a safe fallback may reduce that gap.

Required outcomes:

- teacher-relative cost gap;
- action agreement;
- state-conditional errors;
- latency and throughput;
- OOD performance;
- fallback frequency if uncertainty gating is used.

### RQ8 — Reinforcement learning

> Can an RL execution agent trained in calibrated synthetic environments outperform strong classical, MPC, and ML-assisted baselines without exploiting simulator artefacts, and does any advantage transfer to unseen synthetic regimes and historical replay?

No directional superiority hypothesis is imposed. The confirmatory comparison is symmetric:

\[
H_{0,8}: \text{RL has no practically meaningful paired advantage over the predeclared comparator.}
\]

RL succeeds scientifically if it is evaluated honestly, even if it loses.

Mandatory anti-exploitation tests include:

- reward-component accounting;
- action-mask validation;
- terminal-completion enforcement;
- no negative or duplicated inventory;
- no use of future events;
- random-policy and no-op sanity checks;
- adversarial environment tests;
- performance after environment-parameter randomisation;
- zero-shot historical evaluation.

### RQ9 — Simulator mismatch

> Which conclusions are stable across exact synthetic matching and aggregate historical replay, and which depend on simulator assumptions?

**Hypothesis H9:** strategy ranking will not be invariant across modes; methods trained aggressively in one simulator may lose under queue or impact mismatch.

A disagreement is reported explicitly and is not averaged away.

### RQ10 — Computational trade-offs

> What execution-quality improvement remains after accounting for model inference, controller solve time, engine latency, memory, and hardware cost?

Required outputs:

- per-decision p50/p95/p99 latency;
- batch-one inference latency;
- batched throughput;
- engine events per second;
- peak memory;
- CPU scaling;
- compiled inference comparison;
- GPU/CUDA decision based on measured end-to-end benefit.

**Hypothesis H10:** the best offline strategy may not be the best latency-constrained strategy.

---

## 4. Prediction questions

### PQ1 — Quote depletion

Can the probability that the relevant best quote depletes or is traded through within a short horizon be predicted and calibrated out of sample?

Candidate horizons are 250 ms, 1 s, and 5 s. One primary horizon is selected using validation data and frozen before final calibration/test.

Required metrics include:

- log loss;
- Brier score;
- calibration error and reliability plots;
- ROC-AUC and PR-AUC with class-balance context;
- precision/recall at controller-relevant thresholds;
- temporal and instrument slices;
- inference cost.

Accuracy alone is not a primary metric.

### PQ2 — Adverse selection

Can the side-signed post-event mid-price change be predicted sufficiently to improve passive/aggressive order choice?

Required evaluation includes scale-sensitive error or proper scoring rules, calibration where probabilistic, and downstream decision value.

### PQ3 — Uncertainty

Can model uncertainty identify states where the prediction layer should be ignored or the policy should fall back to a conservative controller?

This may use ensembles, conformal methods, predictive entropy, calibration residuals, or another literature-supported method. The exact method is frozen after Step 3.

---

## 5. Engineering research questions

### EQ1 — Matching correctness

Can the engine enforce price-time priority, exact quantity conservation, deterministic event ordering, latency semantics, rejection rules, and terminal accounting across hand-computed, property-based, differential, and fuzz tests?

There is no empirical shortcut: failure of core invariants blocks all later claims.

### EQ2 — Replay fidelity

Can a recorded level-2 stream be reconstructed without sequence gaps, silent repair, time inversion, or impossible books, with every exclusion documented?

### EQ3 — Determinism

Which outputs are bitwise deterministic, numerically reproducible within tolerance, or statistically reproducible? These categories must be stated separately.

### EQ4 — Performance

Which components dominate end-to-end cost, and do optimisations preserve correctness? No speedup may be claimed without raw repeated timings and fixed-hardware metadata.

---

## 6. Confirmatory analysis hierarchy

### Tier 1 — Primary

- ML-assisted MPC versus non-ML MPC;
- mean implementation shortfall;
- locked temporal test;
- central queue and latency assumptions;
- completion and CVaR guardrails.

### Tier 2 — Secondary families

1. calibrated versus uncalibrated prediction;
2. deep versus best simple prediction model;
3. robust versus nominal controller;
4. imitation versus teacher;
5. RL versus MPC and ML-MPC;
6. compiled/GPU versus Python or native baseline inference.

Multiplicity is controlled within each family.

### Tier 3 — Exploratory

- fine-grained regime slices;
- alternative feature sets;
- interpretability diagnostics;
- extra instruments;
- additional horizons;
- unplanned stress cases;
- post-hoc hypotheses.

Tier 3 results must be labelled exploratory.

---

## 7. Falsification and negative-result criteria

The project must preserve evidence that contradicts its preferred narrative. Examples include:

- simple baselines match or beat ML;
- a deep model improves AUC but worsens cost;
- calibration does not change actions;
- latency erases the signal;
- queue assumptions reverse the ranking;
- robust methods cost too much in normal conditions;
- imitation is fast but unsafe under shift;
- RL exploits a reward defect or fails to transfer;
- GPU execution has worse batch-one latency;
- synthetic results do not reproduce in historical replay.

None of these is a reason to hide a run. They are reasons to improve the interpretation.

---

## 8. Forbidden claim transformations

The following transformations are prohibited:

- “Lower simulated shortfall” → “profitable trading strategy.”
- “Historical ghost replay” → “realistic market impact.”
- “Quote depletion” → “exact fill probability.”
- “L2 queue model” → “known FIFO queue position.”
- “One venue/two instruments” → “universal market result.”
- “GPU training used” → “implemented CUDA systems.”
- “CI passed” → “formally verified.”
- “Many tests” → “bug free.”
- “RL wins in simulator” → “RL would win live.”
- “Technical report” → “peer-reviewed paper.”

---

## 9. Claim-to-evidence matrix

| Candidate claim | Minimum evidence required |
|---|---|
| Correct matching engine | hand tapes, invariants, property tests, differential tests, sanitizers, fuzzing, deterministic replay |
| Historical L2 replay | sequence and snapshot validation, gap policy, canonical timestamps, reconstruction checks, queue-model disclosure |
| Leakage-safe prediction | timestamp contract, mutation tests, chronological splits, feature provenance, locked test |
| ML improves execution | paired locked-test contrast, 95% interval, guardrails, ablations, common action/information contract |
| Deep model adds value | simple baselines, calibration, equal controller, compute/latency accounting, multiplicity control |
| Imitation accelerates control | teacher-relative execution gap and measured latency/throughput under ID and OOD states |
| RL is robust | strong baselines, anti-exploit tests, multiple seeds, unseen regimes, historical zero-shot evaluation |
| Robust strategy improves worst case | predeclared stress matrix, tail/worst-case metrics, nominal-performance trade-off |
| Performance speedup | profiler evidence, raw repeated timings, fixed hardware/software metadata, correctness rerun |
| CUDA is useful | end-to-end CPU comparison including transfer/launch overhead and numerical consistency |

---

## 10. Research completion criterion

The questions are considered answered when:

- every mandatory method has been implemented and passed its technical gate;
- the primary test has been opened only after protocol freeze;
- primary and secondary findings include appropriate uncertainty;
- stress and simulator-mismatch studies are complete;
- negative results and failed hypotheses are retained;
- conclusions match the evidence boundary;
- all principal tables and figures regenerate from saved outputs.

No positive result is required. Complete and defensible answers are required.
