# Step 28 Validation — Complete Robustness Matrix

**Decision:** PASS for the Step 28 engineering robustness-matrix gate.  
**Research-result status:** `synthetic_validation_only_non_research`.  
**Gate C:** BLOCKED; no admitted historical research dataset.  
**Gate I:** PENDING Step 29 dependence-aware statistics and historical activation.  
**Research specification changed:** No; the frozen specification remains locked.

## 1. Matrix coverage

Step 28 registers every robustness dimension required by `RESEARCH_PROTOCOL.md`: latency, decision
grid, liquidity, spread, volatility, queue assumptions, fees/rebates, parent size, horizon, impact,
prediction degradation, data quality, distribution shift and compute, plus explicit simulator
mismatch.

The interactive synthetic panel contains **43 cases**. Every comparable policy/case cell uses the
same **24 deterministic episode seeds**. Competitive policies are immediate, TWAP-like,
liquidity-aware, and the equal-seed aggregate of all five Step 27 PPO policies.

Physical-time values that are not calibrated in the Step 27 engineering MDP are labelled as proxies.
The exact 10/50/100/250/1000 ms and 30/60/300 s research grids remain the frozen future research
contract rather than being silently fabricated from normalized simulator steps.

## 2. Negative-result-preserving ranking evidence

Central engineering ranking:

1. liquidity-aware heuristic;
2. five-seed PPO aggregate;
3. TWAP-like;
4. immediate execution.

Across all 43 cells:

- liquidity-aware first: **35**;
- PPO aggregate first: **5**;
- TWAP-like first: **3**;
- immediate first: **0**.

The ordering changes in **16 of 42 non-central cases**. This directly supports the project thesis that
strategy rankings can be regime-dependent, while also showing that PPO is not uniformly superior.

Worst observed mean-cost increases relative to each policy's central reference were approximately:

- immediate: **+28.56 bps**;
- liquidity-aware: **+9.95 bps**;
- PPO aggregate: **+15.53 bps**;
- TWAP-like: **+10.24 bps**.

These are descriptive engineering values only. Step 28 does not attach confidence intervals or
p-values.

## 3. Prediction, queue and compute panels

Prediction robustness hashes and reuses the Step 25 calibrated, uncalibrated, stale,
training-base-rate and shuffled modes. The perfect event oracle remains an upper-bound diagnostic.

Queue robustness preserves Step 16's optimistic/central/pessimistic exact-synthetic comparison and
adds Step 28 passive-fill-assumption perturbations. Exact historical FIFO reconstruction remains
false and the central historical queue model is still uncalibrated.

The compute panel reuses existing machine-specific p95 timings. On this machine, the 0.025 ms budget
admits the NumPy imitation student but not PPO, the temporal deep models or the MPC teacher; the
0.05 ms budget admits the Step 27 PPO policies but not temporal prediction or MPC. These are
engineering feasibility observations only. Step 30 owns formal profiling and CPU/GPU/CUDA claims.

## 4. Python validation

The final repository test partitions contain **450 Python tests**:

- temporal deep model: 15/15;
- simple models: 16/16;
- imitation learning: 22/22;
- Step 27 RL: 11/11;
- Step 28 robustness: 15/15;
- all remaining Python tests: 371/371.

Combined branch-aware coverage is **91%**, above the unchanged 90% gate. The Step 28 robustness module
is **90% branch-aware covered**. The expensive full byte-identical matrix regeneration test is run
normally and inside the Step 28 semantic validator; the coverage job uses faster generator-path tests
to avoid the local execution-window limit.

## 5. Native regression

Step 28 changes no C++ semantics, but the complete native platform was rerun:

- GCC Debug: **52/52 PASS**;
- Clang Debug: **52/52 PASS**;
- GCC Release: **52/52 PASS**;
- ASan + UBSan: **52/52 PASS**, no findings.

Clean Release installation passed. An external CMake consumer successfully used
`find_package(robust_execution 0.14 CONFIG REQUIRED)`, included the installed adaptive-strategy API,
linked `robust_execution::core`, built and ran.

## 6. Reproducibility and integrity

The independent Step 28 validator checks JSON schemas, config/artifact hashes, all required semantic
boundaries, 100% completion and zero invalid-action rate in every interactive cell, and byte-identical
regeneration of the report, CSV, ranking artifact and artifact manifest from copied dependencies.

The Step 27 default numerical path remains unchanged despite the two optional robustness knobs. The
Step 27 scientific report and policy artifacts therefore remain intact; predecessor release-manifest
hashes are refreshed only for legitimate shared integration-file changes.

## 7. Integrated-run limitation

On the final release tree, the repository-wide sequential `make test` passed every integrated gate
through Step 21 and was then terminated by the local execution window while Step 22 simple-model
regeneration was running. No assertion or validator failure was reported. Steps 22–28 were executed
separately on the identical final source state and all passed. Therefore no combined-green claim is
made for the single `make test` invocation.

Ruff and mypy remain unavailable locally. No fresh local Ruff/mypy-green claim is made.

## 8. Scientific boundary and decision

Step 28 proves that the complete robustness machinery is implemented and deterministic on the
engineering fixture, and that strategy rankings change under controlled stresses. It does **not**
prove historical robustness, statistical significance, or a final strategy winner.

**Step 28 engineering gate: PASS.**  
**Next milestone:** Step 29 — rigorous dependence-aware statistical analysis.
