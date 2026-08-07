# Proposals Requiring Explicit Approval

Nothing in this file is adopted. These are literature-derived possibilities that could strengthen later steps. They will not be added to the specification or implementation unless Othmane explicitly approves them when the relevant step is reached.

## P1 — Queue-reactive model as a named synthetic reference
Use a calibrated Huang–Lehalle–Rosenbaum-style queue-reactive model as one synthetic benchmark, alongside any simpler generator and adversarial stresses.

**Potential value:** interpretable state-dependent event intensities and direct connection to execution probability.  
**Risk:** stationarity and state-space limitations; calibration may not transfer across instruments.

## P2 — LOB-Bench-inspired simulator scorecard
Implement a selected subset of LOB-Bench/Get Real metrics in addition to the project's physical invariants.

**Potential value:** current peer-reviewed basis for conditional/unconditional realism checks.  
**Risk:** metric proliferation and adapting generative-data metrics to an interactive simulator.

## P3 — Decision-focused training ablation
After the normal predict-then-optimise system is stable, train one model using a downstream decision-aware surrogate or differentiable approximation.

**Potential value:** directly tests whether optimisation-aware training improves execution despite worse predictive scores.  
**Risk:** solver differentiability, training instability, and large compute cost.

## P4 — DAgger-style imitation
If the optimiser can be queried cheaply enough, collect expert decisions on states visited by the student rather than relying only on behavioural cloning.

**Potential value:** addresses compounding error and learner-induced distribution shift.  
**Risk:** potentially millions of expensive optimiser calls.

## P5 — Knowledge-guided RL comparator
Include a parsimonious actor–critic policy parameterisation informed by the analytical execution structure, in addition to a flexible deep RL method.

**Potential value:** interpretability, stability, and a bridge between classical control and RL.  
**Risk:** may fit only the strategic trading-rate layer and not the complete market/limit/cancel action space.

## P6 — Stationary-bootstrap sensitivity
Keep the frozen contiguous-day block bootstrap as primary, but compare interval stability with a stationary bootstrap during statistical sensitivity analysis.

**Potential value:** checks dependence on the chosen block construction.  
**Risk:** adds an inference degree of freedom; must be labelled sensitivity, not a way to select the narrowest interval.
