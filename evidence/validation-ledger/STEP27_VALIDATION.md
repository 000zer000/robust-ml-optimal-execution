# Step 27 Validation — Reinforcement Learning Engineering Gate

**Decision:** PASS for synthetic RL engineering and software validation.  
**Research-result status:** `synthetic_validation_only_non_research`.  
**Historical research activation:** BLOCKED until Gate C admits the required historical data.  
**Research specification changed:** No; the frozen seven-file lock remains unchanged.

## 1. Scope validated

Step 27 implements a versioned reinforcement-learning engineering path without claiming the final
research RL experiment. The engineering candidate is categorical PPO over a six-action finite
execution space. Five preregistered development seeds are trained and all five are reported; no best
seed is selected.

The final `reinforcement_learning_algorithm` pre-data field and final seed count are deliberately not
written into `DECISIONS.md` because that file is part of the frozen specification lock. Final RL
research activation remains blocked by Gate C and requires an explicit later field-resolution step.

## 2. Environment and action contract

The engineering MDP contains twelve decision points for one buy parent order and eleven causal state
features: remaining inventory, time remaining, spread, depth ratio, imbalance, volatility, latency,
fees, impact, recent fills and adverse momentum.

Actions are wait, passive 25%, passive 50%, aggressive 25%, aggressive 50% and aggressive 100%.
Passive/no-op actions are masked at the final decision. Residual inventory is forcibly completed
through an aggressive terminal transaction with the registered terminal-impact multiplier.
Aggressive fills also influence the next synthetic reference state through a temporary-impact term,
so the fixture is interactive rather than a static classification problem.

This is an engineering fixture, not the final exact calibrated synthetic research environment.

## 3. PPO implementation

The fixed engineering configuration uses:

- categorical stochastic policy with action masking;
- two 32-unit tanh hidden layers shared by policy/value heads;
- generalised advantage estimation;
- clipped PPO objective with ratio 0.2;
- gamma 0.99 and GAE lambda 0.95;
- entropy coefficient 0.01 and value coefficient 0.5;
- persistent Adam optimiser state within each seed;
- deterministic CPU seeds and deterministic PyTorch algorithms;
- ten PPO rollout/update rounds with twenty training episodes per update.

There is no Step 27 hyperparameter sweep and no seed selection.

## 4. Reward and anti-exploitation audit

Every transition stores raw execution facts rather than trusting an already summed reward. An
independent reconstruction recomputes execution price cost, participation impact, latency, fee,
adverse momentum, inventory risk, invalid-action penalty and terminal-completion economics.

The committed reward reconstruction absolute error is **0.0**.

Validated safeguards include:

- terminal completion is mandatory;
- residual inventory cannot become negative or disappear;
- executed quantity cannot exceed the parent order;
- invalid actions are masked for PPO and penalised if forced through the lower-level API;
- future RNG draws do not enter the current observation;
- no-op/wait cannot evade terminal economics;
- random and immediate policies remain explicit sanity comparators;
- every registered PPO seed completes every ID and OOD episode;
- locked-test fine-tuning is explicitly rejected.

## 5. Multi-seed engineering results

Five development seeds are reported together: **27, 127, 227, 327, 427**.

| Metric | Five-seed PPO aggregate |
|---|---:|
| ID mean cost | **1.2141 bps** |
| ID mean CVaR95 | **11.9416 bps** |
| OOD mean cost | **7.3328 bps** |
| OOD mean CVaR95 | **26.9607 bps** |
| ID completion | **100% for every seed** |
| OOD completion | **100% for every seed** |
| invalid-action rate | **0% for every seed** |

Seed dispersion is retained rather than hidden. ID mean cost ranges from about **0.20 to 3.34 bps**;
OOD mean cost ranges from about **5.96 to 7.86 bps**.

## 6. Strong-baseline and negative-result preservation

Engineering baselines on the identical registered episode sets are:

| Policy | ID mean | ID CVaR95 | OOD mean | OOD CVaR95 |
|---|---:|---:|---:|---:|
| Immediate | 3.8793 | 6.6492 | 13.4418 | 33.0689 |
| TWAP-like | 2.4883 | 7.2721 | **7.0042** | **17.8209** |
| Liquidity-aware | **0.8203** | 11.0256 | 8.5540 | 23.5587 |
| Random | 3.4201 | 7.3930 | 8.4966 | 27.1104 |
| Wait/no-op | 8.1775 | 22.1171 | 15.9757 | 53.7598 |

The negative findings are substantive:

- PPO does **not** beat the liquidity-aware heuristic on ID mean cost;
- PPO does **not** beat the TWAP-like baseline on OOD mean or tail cost;
- PPO degrades materially from ID to OOD;
- no seed is promoted as a winner.

These are engineering observations only. They are not simulator-profit or real-market claims.

## 7. OOD and historical-transfer boundary

OOD evaluation changes liquidity, volatility, latency, fees, impact and an instrument scale without
fine-tuning. The same frozen five policies are evaluated across all OOD episodes.

`historical_zero_shot_gate` currently rejects evaluation because Gate C is closed. The same gate
separately rejects fine-tuning on the locked historical test even after the minimum admitted-day
condition is met. Therefore Step 27 makes **no zero-shot historical performance claim**.

## 8. Reproducibility and artifacts

Every seed has a canonical JSON policy artifact containing named model tensors, feature order,
action order and seed. A fresh policy is reconstructed from each artifact during validation.

A clean rerun on the same software/hardware state reproduces byte-identically:

- all five policy JSON artifacts;
- aggregate `report.json`;
- the Step 27 engineering artifact manifest.

The machine-specific inference benchmark is kept outside the deterministic scientific report.
Batch-one greedy PyTorch inference is approximately **40 microseconds p50** for these tiny policies
on the current machine. This is explicitly labelled
`engineering_machine_specific_not_step30_performance_claim`; formal CPU/GPU/compiled-inference work
remains Step 30.

## 9. Executed validation

### Python

- full Python suite: **435/435 passed**;
- dedicated Step 27 suite: **11/11 passed**;
- combined branch-aware repository coverage: **90.8324%** (minimum 90%);
- Step 27 PPO module combined coverage: approximately **93%**;
- Python `compileall`: **passed**;
- Step 27 source/test/script lines over 100 characters: **0**.

The old two-part coverage wrapper exceeded the local execution window after Step 27 added another
PyTorch training suite. It was replaced with three deterministic coverage partitions (temporal,
learning, base), each completed independently, then combined by Coverage.py under the same 90% gate.
No files or branches were exempted.

### Native regression

Step 27 changes no native simulator/controller behaviour, but clean native regressions were rerun:

- GCC Debug: **52/52 passed**;
- Clang Debug: **52/52 passed**;
- GCC Release: **52/52 passed**;
- ASan + UBSan: **52/52 passed**, no findings.

### Packaging and governance

- frozen specification: **7/7 hashes matched**;
- repository contract: **493/493 required files passed**;
- Step 27 JSON/config/schema parsing: **passed**;
- clean Release install: **passed**;
- external `find_package(robust_execution 0.14 CONFIG REQUIRED)` consumer: **passed**.

### Integrated command

The final repository-wide `make test` was attempted on the release tree. It passed the frozen
specification lock, repository contract and every validator through **Step 21**, then the local
execution window terminated the command while Step 22 model regeneration was running. No failing
assertion was reported. Steps **22–27** were then run separately on the identical final source tree
and all passed. No all-in-one green claim is made.

Because the Step 25/26 release manifests intentionally hash shared integration files such as
`Makefile`, `README.md` and `scripts/validate_repository.py`, Step 27 additions made those integration
hashes stale. Their shared-file hash entries were refreshed so the predecessor semantic validators
continue to verify the current repository. No Step 25/26 scientific report, policy, dataset or
research-result field was changed.

### Local tool limitations

Ruff and mypy executables are not installed in this runtime, so no fresh local Ruff/mypy pass is
claimed. The new Step 27 Python files were manually audited for the configured 100-character line
limit and compile successfully.

## 10. Gate decision

**Step 27 engineering gate: PASS.**

Still unresolved by design:

- final research RL algorithm freeze;
- final RL seed count (minimum ten in the research comparison);
- training on the final exact/calibrated synthetic research environment;
- zero-shot historical aggregate replay result;
- comparison against the final selected Step 20/24 research controller stack;
- dependence-aware statistical inference over RL seeds/days;
- any profitability or live-deployment claim.

The exact next milestone is **Step 28 — complete robustness matrix**. Gate C remains closed.
