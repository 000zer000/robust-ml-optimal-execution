# Literature Review — Robust Execution in Limit Order Books

**Step:** 3 — academic literature review and design-evidence synthesis  
**Status:** complete literature baseline; no empirical project result is claimed  
**Review date:** 2026-08-06  
**Central research question (preserved verbatim):**

> Can machine-learning-assisted execution policies improve realised execution quality relative to strong classical baselines, and do those improvements survive latency, liquidity shifts, queue-model errors, market-impact misspecification, changing fees, and out-of-distribution market regimes?

## 1. Review purpose and boundary

This review establishes the academic basis for the full project already specified by Othmane Hassani. It does not replace the project question, reduce the scope, select a venue, choose a final model, or modify the frozen experimental protocol. Its purposes are to:

1. identify the strongest theoretical and empirical foundations for each required component;
2. expose assumptions that the implementation must not conceal;
3. distinguish mature results from recent or preliminary work;
4. define what evidence will later be required before making a claim;
5. identify genuine research gaps that the complete project can investigate.

The review prioritises original peer-reviewed articles, conference proceedings, official journal versions, and official preprints. Surveys are used only for orientation. Recent preprints are labelled as such and do not receive the same evidential weight as peer-reviewed results.

## 2. Optimal execution foundations

### 2.1 Dynamic execution as a control problem

Bertsimas and Lo formulate execution as a dynamic optimisation problem in which the trader divides a parent order over time to minimise expected cost [@BertsimasLo1998]. This supplies the basic state-control structure: inventory evolves as actions are taken, decisions are sequential, and costs depend on the market response. The project inherits that framing but operates at a finer market-microstructure level than their stylised model.

Almgren and Chriss provide the canonical mean–variance framework [@AlmgrenChriss2001]. In its standard form, a schedule trades off expected impact cost against price risk. For an execution trajectory \(x_t\), the objective can be written schematically as

\[
    \min_x \; \mathbb{E}[C(x)] + \lambda\,\mathrm{Var}[C(x)],
\]

subject to initial inventory and terminal completion constraints. Its value to this project is not that it is a realistic order-book simulator. Its value is that it is a transparent, mathematically defined, difficult-to-game baseline. The implementation must therefore preserve the assumptions under which its schedule is derived and avoid presenting it as queue-aware.

Obizhaeva and Wang model liquidity as a resilient limit order book rather than a permanent linear impact coefficient [@ObizhaevaWang2013]. Alfonsi, Fruth, and Schied generalise optimal execution to non-flat book shapes [@AlfonsiFruthSchied2010]. These results show why execution quality can depend on depth, book shape, and resilience after liquidity consumption. They justify the project's market-impact and liquidity-misspecification experiments, but they do not imply that any one parametric resilience model is universally correct.

Gatheral's no-dynamic-arbitrage conditions constrain admissible transient-impact models [@Gatheral2010]. Any synthetic impact mechanism adopted later should be checked for manipulation-like round trips and other pathological behaviour. This is a model-validity requirement, not a claim that the public historical replay can identify true causal impact.

### 2.2 Adaptive and mixed-order execution

Adaptive execution work demonstrates that decisions can respond to realised market states rather than follow a deterministic schedule [@LorenzAlmgren2011]. Research on strategies mixing market and limit orders formalises the trade-off between immediacy, passive fill probability, adverse selection, and terminal risk [@CarteaJaimungal2015; @GueantLehalleFernandezTapia2012]. This supports the full project's action space: urgency, passive/aggressive choice, placement distance, cancellation, replacement, and terminal completion.

The main limitation of these models is also informative. Analytical tractability generally requires simplified price, fill, or arrival dynamics. The project must therefore compare model-based policies under controlled assumptions and then stress those assumptions rather than treating the optimiser as ground truth.

## 3. Limit-order-book dynamics, queues, and market impact

### 3.1 Event-driven book dynamics

Cont, Stoikov, and Talreja model submissions, market orders, and cancellations as stochastic events and derive short-horizon order-book behaviour [@ContStoikovTalreja2010]. Cont and de Larrard develop a Markovian queue model for best-quote dynamics [@ContDeLarrard2013]. These papers support an event-driven simulator, state-dependent queue variables, and explicit event clocks.

The queue-reactive model of Huang, Lehalle, and Rosenbaum makes order-flow intensities functions of the current book state [@HuangLehalleRosenbaum2015]. Its importance is methodological:

- event rates should not automatically be treated as independent of depth;
- stationary distributions and conditional event behaviour both matter;
- a simulator should be validated on multiple statistics, not merely on a plausible price chart;
- execution tactics can change the book and therefore alter subsequent order flow in an endogenous simulator.

The project already requires a calibrated synthetic environment. The literature supports a queue-reactive family as an important reference model, but adopting a particular calibration is a later design choice requiring explicit approval and evidence.

### 3.2 Queue position and historical replay

An exact matching engine can track order identifiers, price-time priority, cancellations, and FIFO queue position. Aggregate level-2 data normally cannot reconstruct every historical order identity. The project's required separation between exact synthetic mode and aggregate historical replay is therefore essential.

Historical replay can answer counterfactual questions only under assumptions. For passive execution, the fill outcome depends on how cancellations ahead of the agent, hidden liquidity, unobserved order modifications, and same-timestamp events are treated. The planned optimistic, central, and pessimistic queue models are not three estimates of a known truth; they are explicit sensitivity scenarios. Any result that changes sign across those scenarios is queue-model-dependent and must be reported as such.

### 3.3 Order flow imbalance and impact

Cont, Kukanov, and Stoikov show that short-horizon price changes are strongly related to order-flow imbalance at the best quotes and that the impact coefficient varies inversely with depth [@ContKukanovStoikov2014]. This supports including event-based imbalance, depth, spread, and recent order flow among candidate features and calibration targets. It does **not** justify calling a predictive association causal impact in historical ghost replay.

Bouchaud and co-authors document persistent order-sign dependence and the need for compensating liquidity responses [@BouchaudFarmerLillo2009]. This reinforces two project requirements: temporally dependent train/test handling and stress tests in which order-flow persistence or liquidity response changes.

Impact must be treated differently in the two simulator modes:

1. **Exact interactive synthetic mode:** the agent's orders can consume liquidity and change subsequent simulated dynamics under a declared model.
2. **Aggregate historical replay:** a small-agent assumption can be used, or an external counterfactual impact overlay can be tested, but the replay cannot simultaneously claim faithful historical continuation and fully identified endogenous response.

This distinction must remain visible in code, configuration, output metadata, and the report.

## 4. Classical baselines and fairness

The literature supports the project's required hierarchy:

1. immediate aggressive execution;
2. TWAP;
3. a past-only volume-informed schedule;
4. Almgren–Chriss;
5. passive and urgency heuristics;
6. a non-ML adaptive or model-predictive controller.

A baseline is fair only when it receives the information it is entitled to receive, is calibrated without the locked test set, obeys the same terminal-completion rule, pays the same fees, and is evaluated on the same episodes. A sophisticated policy cannot be compared against a deliberately untuned TWAP and then described as beating “classical execution.”

Almgren–Chriss should be implemented in a way that makes its mapping from estimated volatility, temporary impact, permanent impact, risk aversion, horizon, and inventory explicit. Sensitivity to those estimates is part of the project rather than an implementation nuisance.

The non-ML MPC is especially important. It separates the value of adaptivity and optimisation from the value of machine learning. Without that control, an improvement by an ML-assisted controller could simply come from receding-horizon replanning, richer state information, or more frequent decisions.

## 5. Supervised learning for limit-order books

### 5.1 Strong simple models first

Limit-order-book data are noisy, non-stationary, highly dependent, and sensitive to representation. Logistic or regularised linear models and gradient-boosted trees provide interpretable reference points. They can expose whether imbalance, spread, depth, recent event rates, volatility, and queue proxies carry stable information.

A model's input row must contain only information available at the decision timestamp. Labels that look forward are permitted; features that look forward are leakage. Overlapping prediction horizons also create dependent examples and can exaggerate apparent sample size.

For probabilistic targets such as quote depletion or fill probability, the evaluation should include discrimination and calibration. Expected calibration error alone is insufficient; reliability plots, Brier score, log loss, calibration slope/intercept, and regime slices are more informative [@GuoPleissSunWeinberger2017]. Calibration must be learned on a dedicated development segment, not on the locked test.

### 5.2 Temporal deep models

DeepLOB combines convolutional feature extraction with temporal recurrence and is an influential benchmark for LOB prediction [@ZhangZohrenRoberts2019]. Sirignano and Cont report evidence of transferable predictive structure across instruments [@SirignanoCont2019]. Kolm, Turiel, and Westray show that order-flow representations can be powerful and emphasise the importance of stationary or normalised features [@KolmTurielWestray2023]. Briola, Bartolucci, and Aste provide a recent microstructure-aware evaluation and report that strong forecasting power does not necessarily correspond to actionable signals [@BriolaBartolucciAste2025].

These studies justify the project's requirement to implement one serious temporal deep model. They do not justify a collection of architectures selected after seeing test performance. The architecture should be frozen after validation, compared to strong simple models, and evaluated on instruments and regimes not used for fitting.

Deep prediction results also require caution:

- class labels can depend strongly on threshold and horizon choices;
- apparent accuracy can be driven by class imbalance or repeated overlapping windows;
- transaction costs, latency, queue position, and action constraints are absent from many prediction benchmarks;
- a better classifier can produce worse execution decisions;
- throughput-oriented batch inference can differ from batch-one decision latency.

The project's contribution is therefore not “we trained DeepLOB.” It is the controlled link between predictive information, executable decisions, and robustness.

## 6. Predict-then-optimise and decision-focused learning

Elmachtoub and Grigas formalise the distinction between prediction error and downstream decision loss [@ElmachtoubGrigas2022]. Donti, Amos, and Kolter and Wilder, Dilkina, and Tambe develop end-to-end or decision-focused methods that differentiate through or relax optimisation components [@DontiAmosKolter2017; @WilderDilkinaTambe2019]. Their central lesson is directly relevant: two predictions with similar statistical error can induce very different decisions, while a less accurate prediction can have lower decision regret.

The project already requires a predict-then-optimise pathway and a comparison between prediction value and decision value. The literature supports the following evaluation decomposition:

1. **Prediction layer:** discrimination, calibration, proper scoring rules, stability, and latency.
2. **Decision interface:** how predicted quantities enter the controller and how sensitive actions are to them.
3. **Execution outcome:** implementation shortfall, tail cost, completion, adverse selection, and operational metrics.
4. **Oracle and corruption studies:** perfect predictions, shuffled predictions, constant predictions, recalibrated predictions, and controlled degradation.

A decision-focused training loss could be a valuable extension, but it has not been silently added to the frozen project. It is recorded as a proposal requiring approval because differentiability, computational expense, and solver stability depend on the final controller.

## 7. Imitation learning

The project's imitation-learning question is whether a learned policy can approximate a stronger but slower optimiser while retaining decision quality and improving inference speed. Plain behavioural cloning trains on states visited by the expert. During deployment, the student may visit different states after its own errors, causing compounding distribution shift.

DAgger addresses this by iteratively collecting states induced by the learner and querying the expert on those states [@RossGordonBagnell2011]. This gives the project a clear methodological hierarchy:

- behavioural cloning is a baseline;
- student rollouts must be evaluated under their own induced state distribution;
- if the expert can be queried affordably, dataset aggregation is the stronger method;
- imitation quality must be measured in execution outcomes as well as action agreement;
- uncertainty or disagreement can be used to identify states where the student should fall back to the optimiser.

No imitation result should be described as acceleration unless end-to-end latency is measured with equivalent input preparation, hardware, batching, and decision frequency.

## 8. Reinforcement learning for execution

Nevmyvaka, Feng, and Kearns provide an early large-scale empirical application of RL to optimised execution [@NevmyvakaFengKearns2006]. Later work continues to study adaptive execution under different market representations. The literature nevertheless exposes recurring risks:

- overfitting to a small collection of historical paths;
- exploiting simulator artifacts;
- reward functions that permit undesirable terminal inventory or risk-taking;
- unstable rankings across training seeds;
- policies that memorise context sequences;
- poor transfer under changed instruments, volatility, depth, fees, or latency.

Zhang and co-authors explicitly study generalisation problems in RL execution and show why limited dynamic contexts can lead to memorisation [@ZhangDuanChen2023]. Recent work uses queue-reactive environments, mixed market/limit actions, or knowledge-guided continuous-time actor–critic structures [@EspanaHafsiLilloVittori2025; @CheriditoWeiss2026; @WangGaoLi2026]. The queue-reactive 2025 paper is a preprint; the market/limit-order RL article and the actor–critic article are peer-reviewed 2026 publications.

The literature strongly supports the project's existing RL gates:

1. validate the simulator first;
2. define accounting and terminal completion before reward design;
3. compare against strong classical, MPC, ML-assisted, and imitation baselines;
4. report all final seeds rather than the best seed;
5. evaluate both historical and synthetic OOD conditions;
6. test simulator mismatch deliberately;
7. inspect failure trajectories and reward exploitation;
8. avoid any live-profitability claim.

A negative RL result remains useful if the study identifies the mechanism: variance, reward exploitation, latency sensitivity, weak generalisation, or simulator dependence.

## 9. Simulation, realism, and the sim-to-real gap

### 9.1 Existing simulator architectures

ABIDES demonstrates an agent-based discrete-event architecture with an exchange agent, message latency, background agents, and configurable markets [@ByrdHybinetteBalch2019]. It is useful as an architecture reference, not as a component that must be copied.

JAX-LOB demonstrates that thousands of LOB environments can be processed in parallel on accelerators and that GPU-resident simulation can accelerate RL training [@FreyLiNagy2023]. Its benchmark is chiefly a throughput and massively parallel training result. It does not establish that GPU execution is superior for batch-one live decision latency.

The project's C++ exact engine and Python research layer remain justified because they target transparent exchange logic, deterministic testing, interoperability, and measured performance. GPU or JAX-style batching can be compared later where the workload warrants it.

### 9.2 Realism is multidimensional

Vyetrenko and co-authors catalogue realism metrics for LOB simulations [@VyetrenkoByrdPetosa2020]. LOB-Bench expands evaluation to conditional and unconditional distributions, event statistics, discriminator scores, and response/impact measures [@NagyFreyLi2025]. Recent research continues to focus on the reality gap and richer queue-reactive generators [@BodorCarlier2025; @NobleRosenbaumSouilmi2026]. The 2025/2026 latter works are preprints and should be treated as current research directions rather than settled standards.

A simulator should therefore be evaluated across several layers:

- book validity and conservation invariants;
- spread and depth distributions;
- event-type and order-size distributions;
- inter-arrival times and clustering;
- queue conditional intensities;
- return distribution and volatility clustering;
- order-flow dependence;
- price response and impact under controlled interventions;
- execution-relevant outputs such as fill time, adverse selection, and cost.

Passing a subset does not prove realism. The report should use the phrase “matches the following calibrated statistics” rather than “realistic market simulator” without qualification.

### 9.3 Historical replay versus interactive simulation

Historical replay has high fidelity to the recorded exogenous path but weak counterfactual validity when the agent materially changes the book. Interactive simulation permits counterfactual feedback but depends on a model. The full project deliberately needs both:

- historical replay tests policies against real recorded conditions under explicit small-agent and queue assumptions;
- interactive synthetic simulation tests causal interventions, impact, RL, and controlled misspecification;
- agreement across both is stronger evidence than success in either alone;
- disagreement is a result requiring diagnosis, not something to hide.

## 10. Latency and computational performance

Latency affects execution in at least four places:

1. market-data observation delay;
2. feature and model inference time;
3. policy computation time;
4. order communication and exchange processing delay.

A policy can have better zero-latency decisions but worse realised execution once stale observations and delayed actions are included. The simulator must preserve causal ordering among exchange events, observations, decisions, submissions, acknowledgements, cancellations, and fills.

Performance claims need workload definitions. At minimum:

- single-environment event latency;
- events per second for replay;
- batch-one inference latency distribution;
- batched throughput;
- end-to-end decision latency including feature construction;
- memory consumption;
- scaling versus threads or batch size;
- hardware, compiler, library versions, warm-up, repetitions, and raw measurements.

The literature on JAX-LOB supports a GPU-throughput hypothesis, not a predetermined CUDA conclusion. The project's mandatory accelerator study can correctly conclude that CPU is better for the selected online workload, that GPU is better only for batched RL training, or that transfer/launch overhead dominates. The conclusion must follow profiling.

## 11. Statistical methodology

Execution episodes are temporally dependent and strategies are paired on the same market paths. The primary estimator should therefore use episode-level paired differences, with a resampling unit that preserves relevant serial dependence.

The stationary bootstrap of Politis and Romano is a foundational dependence-aware method [@PolitisRomano1994]. The project's frozen contiguous-day block bootstrap is compatible with the same principle: do not pretend that overlapping or adjacent market observations are independent. Block length should be chosen using development data and subjected to sensitivity analysis.

Multiple strategy, model, instrument, regime, latency, fee, and stress comparisons create a substantial multiplicity problem. White's Reality Check and Romano–Wolf stepdown methods illustrate approaches for controlling data-snooping or family-wise error in collections of dependent comparisons [@White2000; @RomanoWolf2005]. The project does not need to force every exploratory table into one correction family, but it must distinguish:

- a small number of predeclared confirmatory contrasts;
- secondary predeclared analyses;
- exploratory findings requiring cautious language.

Tail metrics such as CVaR need enough independent blocks to estimate meaningfully. Point estimates, intervals, sample counts, and sensitivity to the tail threshold should be reported together. No claim should be based only on the best day, instrument, regime, or RL seed.

## 12. Synthesis against the exact research question

The literature does not answer the project's central question in advance. It establishes that each side of the question is plausible:

- classical scheduling is mathematically strong but stylised;
- adaptive and queue-aware policies can exploit state information;
- LOB prediction models can extract short-horizon information;
- predictive accuracy need not equal decision value;
- passive execution introduces queue and adverse-selection risk;
- latency can destroy the value of a signal;
- simulator assumptions can dominate RL results;
- rankings can change under liquidity, impact, fee, and regime shifts.

The project's defensible contribution is the **controlled integration and stress testing** of these components within one reproducible platform. It should not claim theoretical novelty merely for combining known methods. Potential novelty must come from the experimental design, the separation of exact and aggregate replay, the prediction-to-decision decomposition, the simulator-mismatch matrix, and any stable empirical findings.

## 13. Literature-backed requirements already present in the project

The review supports, without altering, the following existing requirements:

- exact synthetic matching and honest aggregate historical replay;
- strong classical and non-ML adaptive baselines;
- one interpretable and one serious temporal prediction family;
- calibration and decision-value analysis;
- imitation and RL only after foundation gates;
- multi-seed RL evaluation;
- latency, liquidity, queue, impact, fee, and OOD stress tests;
- simulator realism measured by a battery of statistics;
- dependence-aware paired inference;
- profiling before optimisation or CUDA claims;
- public limitations and negative findings.

## 14. Unresolved questions that require later evidence

The literature cannot decide these implementation choices without data or profiling:

1. final venue and instruments;
2. event schema and data quality achievable from public feeds;
3. the most defensible queue-depletion/fill/adverse-selection target;
4. the correct horizon and episode length;
5. whether a queue-reactive, Hawkes-like, agent-based, or hybrid synthetic generator best matches the selected data;
6. the exact MPC formulation and solver;
7. the deep architecture that wins validation without excessive latency;
8. whether decision-focused training is worth its complexity;
9. whether DAgger-style expert querying is computationally feasible;
10. the RL action representation and algorithm;
11. the required block length and effective sample size;
12. whether CUDA/GPU work is justified for simulation, training, inference, or none of them.

These are not defects in the current specification. They are questions assigned to later project steps.

## 15. Conclusion

The full project is ambitious but academically coherent. Its strongest research angle is not “AI beats TWAP.” It is the careful separation of prediction, optimisation, execution mechanics, model assumptions, latency, and robustness. The literature repeatedly shows why simple point-estimate comparisons are inadequate and why strong baselines, counterfactual caution, simulator validation, temporal generalisation, and decision-level metrics are necessary.

No central project instruction has been changed by this review. Suggestions that would add a new method or alter a future design choice are isolated in `PROPOSALS_REQUIRING_APPROVAL.md` and remain unadopted.
