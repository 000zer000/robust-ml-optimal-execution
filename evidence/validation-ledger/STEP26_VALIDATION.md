# Step 26 Validation — Imitation Learning

**Decision:** PASS for the engineering imitation-learning gate.  
**Research-result status:** `synthetic_validation_only_non_research`.  
**Historical research activation:** BLOCKED until Gate C admits the required real market-data days.  
**Research specification changed:** No.

## 1. Scope validated

Step 26 implements the complete engineering path required before reinforcement learning:

- exact C++ teacher queries through the already-validated shared MPC solver;
- deterministic teacher-labelled train, validation, correction, engineering-holdout and OOD splits;
- compact behavior cloning with training-only normalization;
- validation-only model selection;
- sequential learner rollouts;
- covariate-shift diagnostics;
- validation-triggered one-round DAgger correction;
- conservative confidence/feature-distance teacher fallback;
- teacher-relative mean and tail implementation-shortfall diagnostics;
- deterministic policy and dataset artifacts;
- separate machine-specific latency benchmarking.

The final historical teacher is **not** selected in this step.

## 2. Teacher choice and rejected shallow fixture

The first engineering attempt used the Step 20 non-ML MPC directly. A broad controlled state sweep
showed its first solver action was `passive_50` throughout the tested engineering surface. Training a
student on that one-action fixture would have allowed trivial near-perfect imitation without validating
meaningful policy learning.

The accepted engineering fixture therefore uses the **same shared MPC optimizer path validated in
Step 24**, with a causal synthetic prediction-risk input and a fixed 10,000-bps engineering-only weight.
This creates a non-degenerate action surface while preserving the exact solver implementation.

This choice is explicitly limited to software/research-pipeline validation. It does not select:

- the final research teacher;
- the final prediction horizon;
- the final prediction model family;
- a research ML-MPC prediction weight;
- any historical execution result.

The committed training teacher contains four action classes:

- `passive_50`: 297 rows;
- `aggressive_100`: 162 rows;
- `aggressive_50`: 19 rows;
- `aggressive_25`: 2 rows.

## 3. Data and leakage contract

The committed deterministic teacher dataset contains physically distinct split tables for:

- 80 training episodes;
- 30 validation episodes;
- 30 correction episodes;
- 30 engineering-holdout episodes;
- 30 OOD episodes.

Each episode has at most six decisions. The initial teacher-labelled row counts are 480 train,
180 validation, 95 engineering holdout and 118 OOD. DAgger adds 87 learner-visited correction rows from
the dedicated correction pool.

Teacher tables exclude machine timing so that the scientific dataset is byte-reproducible. A separate
manifest records provenance, row counts and SHA-256 hashes for every split.

Training-only information is used for the scaler. Validation alone selects the behavior-cloning
hyperparameters and fallback thresholds. The correction pool is queried only after the validation
trigger fires. Engineering holdout and OOD are evaluation-only and cannot select hyperparameters,
DAgger data, fallback thresholds or the final engineering policy.

## 4. Behavior cloning and corrective learning

The student is a compact one-hidden-layer MLP over the exact adaptive-signal state plus the synthetic
engineering prediction-risk input. The selected validation-only configuration is:

- hidden units: 8;
- L2 alpha: 0.0001.

Hyperparameters are frozen before correction.

The initial sequential validation rollout reaches **97.7011%** raw action agreement. The predeclared
98% agreement threshold therefore triggers exactly one DAgger round. After adding 87 exact teacher
labels on learner-visited correction states, validation rollout agreement rises to **98.8372%**.

A useful negative result is retained: the standardized validation mean-state-shift statistic does not
improve, moving from **0.5956** to **0.6167**. DAgger improves action agreement here; it is not claimed
to eliminate distribution shift by every diagnostic.

## 5. Engineering holdout

On the untouched engineering holdout:

- raw student action agreement: **100%**;
- completion: **100%**;
- invalid-action rate: **0%**;
- mean shortfall delta versus teacher: **0 bps**;
- p95 shortfall delta versus teacher: **0 bps**.

The validation-selected fallback fires on 2.1053% of holdout decisions and retains exact teacher
behavior. These values are fixture diagnostics, not historical performance claims.

## 6. OOD negative result and fallback

The deliberately shifted OOD evaluation exposes a material weakness in the raw behavior clone:

| Metric | Teacher | Raw student | Student + teacher fallback |
|---|---:|---:|---:|
| Action agreement | — | 69.30% | 94.78% |
| Completion | 100% | 100% | 100% |
| Mean shortfall (bps) | -39.20 | -115.87 | -27.27 |
| p95 shortfall (bps) | 281.45 | 455.00 | 287.50 |
| Fallback rate | — | 0% | 82.61% |

The raw student looks better than the teacher on **mean** shortfall in this fixture while being much
worse on tail shortfall and action fidelity. That is deliberately preserved as a warning against using
one mean metric as proof of imitation quality.

The validation-selected fallback substantially restores action fidelity and tail behavior, but it is
not perfect and falls back to the teacher on roughly 82.6% of OOD decisions. Therefore it also erodes
much of the potential inference-speed advantage. No OOD threshold is tuned on the OOD set.

## 7. Artifact and reproducibility contract

The final policy is stored as canonical JSON containing the scaler, class order and named neural
weights. A NumPy implementation reconstructs the policy exactly.

The committed deterministic artifacts have these SHA-256 values:

- report: `ee139ac7b95e7224f8b5f6170e414416372feb963adc3a63ad8235709f5df425`;
- policy: `a0f00710e76e4d94d97cda6690e4a83a5c3194e67f804a662367ba9b456b4575`;
- teacher-dataset manifest: `b481658161c7d1fa43770c328839d0abd6828185e711ebfb6848d4904f9e8241`.

The independent Step 26 validator regenerates the report, policy, teacher manifest and all five teacher
split tables and requires byte identity.

GCC Debug, Clang Debug and GCC Release teacher oracles independently regenerate these same scientific
artifacts byte-for-byte.

## 8. Latency engineering diagnostic

The separate benchmark contains 150 batch-one measurements on the current machine:

- C++ shared MPC teacher: p50 **199,407 ns**, p95 **262,686.9 ns**;
- NumPy student: p50 **12,428.5 ns**, p95 **13,856.05 ns**.

The benchmark is explicitly labelled
`engineering_machine_specific_not_step30_performance_claim`. Formal hardware comparisons, compiled
inference, batching, CPU/GPU decisions and execution-latency injection remain Step 30 responsibilities.

## 9. Executed validation

### Python

- temporal partition: **15/15 passed**;
- non-temporal partition: **409/409 passed**;
- total repository Python tests: **424/424 passed**;
- combined branch-aware coverage: **90.6395%** (minimum 90%);
- Step 26 imitation module coverage: **91.05%**;
- dedicated Step 26 tests: **22/22 passed**;
- independent Step 26 semantic/artifact validator: passed.

### Native regression

- GCC Debug: **52/52 passed**;
- Clang Debug: **52/52 passed**;
- GCC Release: **52/52 passed**;
- ASan + UBSan: **52/52 passed**, no findings.

The imitation oracle is an application target, not a separate CTest; its solver behavior and artifact
outputs are exercised by the Step 26 integration/semantic tests.

### Packaging/integration

- clean GCC Release install: passed;
- installed `robust_execution_imitation_oracle`: present and executable;
- external `find_package(robust_execution 0.14 CONFIG REQUIRED)` consumer: built and ran successfully.

## 10. Claim boundaries

Step 26 does **not** establish:

- historical imitation quality;
- real-market OOD generalization;
- production abstention/fallback behavior;
- a final teacher policy;
- a final horizon, model family or prediction weight;
- a formal latency advantage;
- profitability.

The high OOD fallback rate is a limitation, not a success metric.

## 11. Tool and integrated-run limitations

Ruff and mypy are not installed in the local execution environment, so no fresh local Ruff/mypy-green
claim is made. New/touched Step 26 source is manually checked against the repository's 100-character
line convention.

The repository-wide sequential `make test` command was executed on the final source tree. It passed
the specification/repository checks and every validator through Step 21, then the local execution
window terminated the command while the Step 22 model regeneration was running. No failing assertion
was reported. Steps 22, 23, 24, 25 and 26 were then run separately on the identical final source state
and all passed. Therefore no combined-green claim is made for the all-in-one command.

## 12. Gate decision

**Step 26 engineering gate: PASS.**

Step 27 may implement the engineering reinforcement-learning environment/policy machinery under the
frozen RL start-gate contract. Historical research activation remains blocked by Gate C, and no final
research teacher or empirical claim may be selected from this Step 26 synthetic fixture.
