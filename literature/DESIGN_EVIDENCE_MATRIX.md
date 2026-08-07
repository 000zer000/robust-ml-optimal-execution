# Design–Evidence Matrix

This matrix maps the user's already-required project components to the literature. **“Supported” does not mean implemented.** “Proposal” means the idea has not been adopted and requires explicit user approval.

| Project component | Evidence base | What the evidence supports | Constraint / failure mode | Project status |
|---|---|---|---|---|
| Parent-order control formulation | Bertsimas–Lo; Almgren–Chriss | Inventory state, sequential decisions, expected-cost/risk objectives | Stylised impact and price dynamics | Required, supported |
| Immediate/TWAP/volume schedule | Classical execution literature | Transparent reference policies | Must use past-only profiles and same completion rule | Required, supported |
| Almgren–Chriss baseline | Almgren–Chriss | Strong mathematical schedule baseline | Parameters and assumptions must be exposed and stressed | Required, supported |
| Non-ML adaptive MPC | Adaptive execution and stochastic control | Replanning based on current state | Must isolate adaptivity from ML value | Required, supported |
| Exact C++ matching engine | Exchange mechanics; event-driven models | Price-time priority, partial fills, cancellations, deterministic replay | Correctness precedes optimisation | Required, supported |
| Aggregate historical replay | Microstructure/data limitations | Real-path evaluation under explicit queue assumptions | Cannot reconstruct exact FIFO or causal impact from aggregate L2 | Required, supported |
| Queue-position scenarios | Queue models and passive execution | Fill outcomes are sensitive to priority/cancellation assumptions | Scenario labels must not imply known truth | Required, supported |
| Queue-reactive synthetic generator | Huang–Lehalle–Rosenbaum; recent hybrids | State-dependent event intensities and calibrated book behaviour | Regime stationarity and overfitting | Candidate only; approval later |
| Impact/resilience module | Obizhaeva–Wang; Alfonsi et al.; Gatheral | Transient response, book shape, no-manipulation checks | Structural model is not identified by ghost replay | Required stress family; exact model TBD |
| OFI/depth features | Cont–Kukanov–Stoikov | Short-horizon supply/demand state | Association is not causal impact | Required feature candidates |
| Interpretable ML baselines | Standard statistical learning | Transparent discrimination/calibration baseline | Temporal leakage and dependence | Required, supported |
| One serious temporal deep model | DeepLOB; Sirignano–Cont; Kolm et al. | Spatial/temporal representation learning | Benchmark accuracy may not produce execution value | Required, supported |
| Probability calibration | Guo et al.; proper scoring literature | Reliability, Brier/log loss, post-hoc calibration | Calibration can shift across regimes | Required, supported |
| Predict-then-optimise integration | SPO; task-based learning | Prediction error and decision error can diverge | Solver sensitivity and discontinuous actions | Required, supported |
| Decision-focused loss | SPO+; differentiable optimisation | Potentially train for downstream execution regret | May be inapplicable/unstable for final controller | Proposal P3; not adopted |
| Behavioural cloning | Imitation-learning baseline | Fast approximation of optimiser | Learner-induced distribution shift | Required, supported |
| DAgger-style aggregation | Ross et al. | Reduces compounding error by expert querying on learner states | Expensive optimiser queries | Proposal P4; not adopted |
| Reinforcement learning | Nevmyvaka et al.; recent execution RL | Adaptive policy learning in controlled environments | Seed variance, reward hacking, overfitting, simulator exploitation | Required and dependency-gated |
| Multi-seed and OOD RL | Zhang et al.; recent theory-guided RL | Generalisation must be tested across contexts/simulators | Best-seed reporting is invalid | Required, supported |
| ABIDES-style architecture review | ABIDES | Message passing, exchange agents, latency | Framework realism must be separately validated | Reference only |
| Accelerator simulation | JAX-LOB | Large batched throughput and RL training speed | Not proof of low batch-one latency | Required performance question, outcome open |
| Simulator realism battery | Get Real; LOB-Bench | Multiple conditional/unconditional and response metrics | Stylised-fact matching is not full counterfactual validity | Required, supported |
| Historical/synthetic cross-validation | Simulation literature | Complementary strengths of replay and interactive models | Disagreement must be reported | Required, supported |
| Latency stress | Execution and simulator literature | Signal/action value can decay under delay | All latency stages must be modelled causally | Required, supported |
| Block-bootstrap uncertainty | Politis–Romano | Preserve dependence in resampling | Block length and nonstationarity sensitivity | Required, supported |
| Multiplicity controls | White; Romano–Wolf | Prevent broad comparison search from creating false wins | Families must be defined before testing | Required, supported |
| CVaR/tail analysis | Risk-measure literature | Tail cost can rank policies differently from mean | Needs adequate effective sample size | Required, supported |
| Profiling before CUDA | Performance methodology; JAX-LOB evidence | Separate latency, throughput, transfer, and batching | Keyword-driven GPU work is invalid | Required, supported |

## Evidence gaps to close experimentally

| Gap | Why literature cannot decide it | Project step that must resolve it |
|---|---|---|
| Public venue/data source | APIs, licences, schemas, and continuity change | Step 11 |
| Exact event schema | Depends on selected feed and exchange rules | Steps 5 and 11–14 |
| Queue central assumption | Aggregate data do not reveal all order identities | Steps 15–16 |
| Target/horizon | Depends on data quality and decision sensitivity | Steps 21–22 |
| Deep architecture | Validation and latency trade-off are empirical | Step 23 |
| Final MPC objective | Depends on accounting, action space, and solver | Step 20 |
| Imitation expert-query method | Depends on optimiser speed | Step 26 |
| RL algorithm/action distribution | Depends on environment and reward diagnostics | Step 27 |
| Synthetic generator family | Must match selected market statistics | Steps 9 and 28 |
| Bootstrap block length | Depends on episode-level dependence | Step 29 |
| CUDA target | Must follow profiling | Step 30 |
