# Annotated Bibliography

**Project:** Learning Robust Execution Policies in Limit Order Books  
**Cut-off:** 2026-08-06  
**Evidence labels:** peer-reviewed journal; peer-reviewed conference; official preprint.

## A. Optimal execution and impact

### Bertsimas and Lo (1998) — Optimal control of execution costs
**Status:** peer-reviewed journal.  
**Contribution:** Frames parent-order execution as a sequential stochastic control problem and derives dynamic strategies under explicit impact assumptions.  
**Use here:** Foundation for inventory state, sequential decisions, and cost minimisation.  
**Limit:** Stylised market and impact dynamics; no full order-book queues.

### Almgren and Chriss (2001) — Optimal execution of portfolio transactions
**Status:** peer-reviewed journal.  
**Contribution:** Mean–variance trade-off between expected impact and execution risk; canonical deterministic schedule.  
**Use here:** Mandatory strong classical baseline and parameter-misspecification study.  
**Limit:** Does not model detailed limit-order placement, queueing, or nonlinear state-dependent liquidity.

### Obizhaeva and Wang (2013) — Optimal trading strategy and supply/demand dynamics
**Status:** peer-reviewed journal.  
**Contribution:** Models a resilient limit order book and transient liquidity recovery.  
**Use here:** Supports resilience and impact stress tests.  
**Limit:** Parametric idealisation; calibration and cross-venue stability are empirical questions.

### Alfonsi, Fruth, and Schied (2010) — General LOB shape functions
**Status:** peer-reviewed journal.  
**Contribution:** Shows how non-flat book shape and resilience affect optimal execution.  
**Use here:** Supports depth-shape and resilience scenarios.  
**Limit:** Analytical model is not a full event-driven exchange.

### Gatheral (2010) — No-dynamic-arbitrage and market impact
**Status:** peer-reviewed journal.  
**Contribution:** Derives restrictions on transient-impact models to avoid manipulation.  
**Use here:** Validation check for synthetic impact models.  
**Limit:** Conditions apply within a model class and do not identify real causal impact.

### Lorenz and Almgren (2011) — Adaptive execution
**Status:** peer-reviewed journal.  
**Contribution:** Studies updating an execution strategy as information arrives.  
**Use here:** Supports receding-horizon and adaptive non-ML controls.  
**Limit:** Adaptivity is not necessarily queue-aware.

### Cartea and Jaimungal (2015) — Market and limit order execution
**Status:** peer-reviewed journal.  
**Contribution:** Formalises tactical use of market and limit orders under fill and adverse-selection trade-offs.  
**Use here:** Supports mixed action space and passive/aggressive comparisons.  
**Limit:** Fill and price processes require modelling assumptions.

### Guéant, Lehalle, and Fernandez-Tapia (2012) — Liquidation with limit orders
**Status:** peer-reviewed journal.  
**Contribution:** Provides stochastic-control treatment of passive liquidation.  
**Use here:** Supports limit-order baselines and terminal penalty/completion logic.  
**Limit:** Simplified arrival model.

## B. Order-book dynamics and queue modelling

### Cont, Stoikov, and Talreja (2010) — Stochastic order-book dynamics
**Status:** peer-reviewed journal.  
**Contribution:** Event-based stochastic model for submissions, market orders, and cancellations.  
**Use here:** Reference for simulator event taxonomy and calibration.  
**Limit:** Independence/Poisson assumptions can miss clustering and state dependence.

### Cont and de Larrard (2013) — Markovian limit-order market
**Status:** peer-reviewed journal.  
**Contribution:** Queue-based best-quote model with analytically tractable price dynamics.  
**Use here:** Reference for queue-state validation and short-horizon dynamics.  
**Limit:** Reduced Level-I representation.

### Huang, Lehalle, and Rosenbaum (2015) — Queue-reactive model
**Status:** peer-reviewed journal.  
**Contribution:** Makes event intensities functions of current queue state and validates simulation behaviour.  
**Use here:** Leading candidate family for calibrated synthetic regimes and execution-probability studies.  
**Limit:** The exact state and stationarity assumptions may be insufficient across regimes.

### Cont, Kukanov, and Stoikov (2014) — Price impact of order-book events
**Status:** peer-reviewed journal.  
**Contribution:** Relates short-horizon price changes to order-flow imbalance and depth.  
**Use here:** Supports OFI/depth features, market-state slices, and impact calibration targets.  
**Limit:** Predictive/explanatory association is not a complete structural counterfactual model.

### Bouchaud, Farmer, and Lillo (2009) — Long-memory order flow and impact
**Status:** peer-reviewed book chapter/research synthesis based on original empirical work.  
**Contribution:** Connects persistent order signs, liquidity response, and impact.  
**Use here:** Supports dependence-aware evaluation and order-flow-regime shifts.  
**Limit:** Results vary with market, era, and data definition.

### Gould et al. (2013) — LOB survey
**Status:** peer-reviewed survey.  
**Contribution:** Organises order-book mechanics, models, and empirical stylised facts.  
**Use here:** Orientation and terminology cross-check.  
**Limit:** Secondary source; design claims should trace to original work.

## C. Supervised and deep LOB prediction

### Zhang, Zohren, and Roberts (2019) — DeepLOB
**Status:** peer-reviewed journal.  
**Contribution:** CNN/inception/LSTM architecture for extracting spatial and temporal LOB features.  
**Use here:** Architecture reference for the required serious temporal model.  
**Limit:** Prediction benchmark performance does not by itself establish executable value under fees, queues, and latency.

### Sirignano and Cont (2019) — Universal features of price formation
**Status:** peer-reviewed journal.  
**Contribution:** Studies deep models trained across instruments and transferable short-horizon structure.  
**Use here:** Supports cross-instrument tests and shared-versus-local models.  
**Limit:** Transferability is data- and target-dependent.

### Kolm, Turiel, and Westray (2023) — Deep order-flow imbalance
**Status:** peer-reviewed journal.  
**Contribution:** Emphasises order-flow representations and stationary transformations for prediction.  
**Use here:** Supports simple stationary feature baselines and representation ablations.  
**Limit:** Prediction gains still need downstream execution evaluation.

### Briola, Bartolucci, and Aste (2025) — Deep LOB forecasting: a microstructural guide
**Status:** peer-reviewed journal.  
**Contribution:** Microstructure-aware evaluation across NASDAQ stocks; highlights that high forecasting power need not create actionable signals.  
**Use here:** Current support for transaction-aware and decision-level evaluation rather than accuracy-only claims.  
**Limit:** Uses licensed LOBSTER data and addresses forecasting rather than the complete execution-control problem.

### Guo et al. (2017) — Calibration of modern neural networks
**Status:** peer-reviewed conference.  
**Contribution:** Documents neural miscalibration and evaluates post-hoc calibration methods.  
**Use here:** Calibration diagnostics and development-only recalibration.  
**Limit:** Generic classification setting; financial temporal shift requires extra tests.

## D. Prediction-to-decision learning

### Elmachtoub and Grigas (2022) — Smart Predict, then Optimize
**Status:** peer-reviewed journal.  
**Contribution:** Defines decision loss and a tractable SPO+ surrogate.  
**Use here:** Theoretical basis for prediction-versus-decision value and a possible decision-focused ablation.  
**Limit:** Direct applicability depends on the final optimisation structure.

### Donti, Amos, and Kolter (2017) — Task-based end-to-end model learning
**Status:** peer-reviewed conference.  
**Contribution:** Trains predictive components through a downstream optimisation objective.  
**Use here:** Reference for differentiable decision pipelines.  
**Limit:** Differentiability and solver stability may be difficult for discrete order actions.

### Wilder, Dilkina, and Tambe (2019) — Decision-focused combinatorial optimisation
**Status:** peer-reviewed conference.  
**Contribution:** Shows that standard accuracy can be poorly aligned with solution quality.  
**Use here:** Supports reporting both predictive and execution metrics.  
**Limit:** Domains and optimisation structures differ from LOB execution.

## E. Imitation learning

### Ross, Gordon, and Bagnell (2011) — DAgger
**Status:** peer-reviewed conference.  
**Contribution:** Addresses compounding error by collecting expert labels on learner-induced states.  
**Use here:** Stronger imitation method than behavioural cloning when the optimiser can be queried.  
**Limit:** Expert querying can be computationally expensive; convergence theory does not guarantee market robustness.

## F. Reinforcement learning and execution

### Nevmyvaka, Feng, and Kearns (2006) — RL for optimised trade execution
**Status:** peer-reviewed conference.  
**Contribution:** Early large-scale empirical RL execution study.  
**Use here:** Historical foundation and baseline-design reference.  
**Limit:** Market/data setting and simulator assumptions require modern re-evaluation.

### Zhang et al. (2023) — Generalizable RL for trade execution
**Status:** peer-reviewed conference.  
**Contribution:** Analyses overfitting to dynamic contexts and proposes compact representations.  
**Use here:** Supports OOD regimes, held-out contexts, and representation diagnostics.  
**Limit:** Results depend on its simulator and data construction.

### Wang, Gao, and Li (2026) — Continuous-time actor–critic with error analysis
**Status:** peer-reviewed journal.  
**Contribution:** Knowledge-guided actor–critic under an Almgren–Chriss structure, with convergence/error analysis and several simulators.  
**Use here:** Important recent comparator for theory-informed RL and terminal completion.  
**Limit:** Strategic trading-rate layer and market-order-only action space differ from the full tactical problem.

### España, Hafsi, Lillo, and Vittori (2025) — RL in queue-reactive models
**Status:** official preprint.  
**Contribution:** Applies deep RL to execution in a queue-reactive simulator with transient impact.  
**Use here:** Current reference for queue-based RL and simulator-dependence questions.  
**Limit:** Not yet treated as settled peer-reviewed evidence.

### Cheridito and Weiss (2026) — RL with market and limit orders
**Status:** peer-reviewed journal article.  
**Contribution:** Continuous allocation across market and limit actions in simulated LOBs.  
**Use here:** Reference for action parameterisation.  
**Limit:** Conclusions remain simulation-specific and preprint-stage.

## G. Simulation and performance

### Byrd, Hybinette, and Balch (2019) — ABIDES
**Status:** official preprint; widely used open simulator.  
**Contribution:** Message-driven agent-based exchange with configurable latency and background agents.  
**Use here:** Architecture and event-ordering reference.  
**Limit:** A simulator framework is not automatically a validated market model.

### Frey et al. (2023/2024) — JAX-LOB
**Status:** peer-reviewed conference version plus official preprint.  
**Contribution:** GPU-vectorised LOB simulation and high-throughput RL training.  
**Use here:** Benchmark reference for accelerator throughput and environment batching.  
**Limit:** Does not prove GPU superiority for batch-one decision latency.

### Vyetrenko et al. (2020) — Get Real
**Status:** peer-reviewed conference.  
**Contribution:** Catalogues realism metrics across returns, volumes, orders, and microstructure.  
**Use here:** Multi-metric simulator validation.  
**Limit:** Matching stylised facts is necessary but not sufficient for counterfactual validity.

### Nagy et al. (2025) — LOB-Bench
**Status:** peer-reviewed conference.  
**Contribution:** Benchmark for conditional/unconditional statistics, event distributions, discriminator scores, and response metrics.  
**Use here:** Current validation reference and possible metric implementation source.  
**Limit:** Designed for message-data generation; some metrics require adaptation to interactive simulators.

### Bodor and Carlier (2025) — Multidimensional deep queue-reactive model
**Status:** official preprint.  
**Contribution:** Neural state-dependent intensities and richer order-size/cross-queue dependence.  
**Use here:** Current hybrid-generator reference.  
**Limit:** Added flexibility increases calibration and overfitting risk.

### Noble, Rosenbaum, and Souilmi (2026) — Bridging the reality gap
**Status:** official preprint.  
**Contribution:** Practical projected-state simulator with timing and impact feedback.  
**Use here:** Current evidence that latency-scale event timing and intervention response matter.  
**Limit:** Recent preprint and large-tick focus.

## H. Statistical inference

### Politis and Romano (1994) — Stationary bootstrap
**Status:** peer-reviewed journal.  
**Contribution:** Dependence-preserving resampling through random-length blocks.  
**Use here:** Foundation for block-based uncertainty and sensitivity checks.  
**Limit:** Block-length choice and nonstationarity still require judgement.

### White (2000) — Reality Check
**Status:** peer-reviewed journal.  
**Contribution:** Tests whether the best result among many models exceeds a benchmark while accounting for data snooping.  
**Use here:** Multiplicity/data-mining caution for broad strategy comparisons.  
**Limit:** Can be conservative and does not replace pre-registration.

### Romano and Wolf (2005) — Stepwise multiple testing
**Status:** peer-reviewed journal.  
**Contribution:** Dependence-aware stepdown control of multiple hypotheses.  
**Use here:** Candidate method for families of secondary comparisons.  
**Limit:** Requires careful definition of the hypothesis family and resampling scheme.
