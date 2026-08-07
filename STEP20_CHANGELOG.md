# Step 20 Changelog — Non-ML Adaptive Baselines and MPC

**Step:** 20 of 32  
**Status:** Engineering complete; Gate D engineering pass, historical activation blocked by Gate C  
**Repository version:** 0.14.0  
**Research specification changed:** No

## Added

- `cpp/include/robust_execution/strategies/adaptive.hpp`
  - shared non-ML calibration contract;
  - adaptive signal calculation;
  - queue/liquidity-aware heuristic policy;
  - bounded finite-horizon non-ML MPC interface and diagnostics.
- `cpp/src/strategies/adaptive.cpp`
  - causal fill-pressure and visible-queue features;
  - heuristic decision logic;
  - bounded action-tree MPC solver;
  - expected passive/aggressive cost models;
  - terminal and action-contract guards.
- `cpp/tests/test_adaptive_strategies.cpp`
  - favorable/urgent heuristic oracles;
  - buy/sell symmetry checks;
  - MPC passive-to-aggressive regime switch;
  - leakage, fraction, NaN, horizon, and terminal-state failures.
- `cpp/apps/re_adaptive_demo.cpp`
  - deterministic Step 20 validation evidence.
- `configs/strategies/step20_non_ml_adaptive.json`
  - synthetic-only calibration and frozen engineering-test parameters.
- `scripts/validate_step20_adaptive.py`
  - machine-checkable evidence and configuration validation.
- `docs/strategies/STEP20_ADAPTIVE_BASELINES.md`
  - controller equations, action semantics, assumptions, and limitations.
- `docs/strategies/STEP20_GATE_D.md`
  - formal classical/adaptive baseline gate decision.
- `data/sample/adaptive/step20-validation/report.json`
  - deterministic synthetic validation fixture.
- `results/validation/step20/adaptive_cross_compiler.sha256`
  - GCC/Clang/Release output identity evidence.

## Modified

- `cpp/include/robust_execution/strategies/strategies.hpp`
  - exports the Step 20 adaptive API.
- `CMakeLists.txt`
  - builds/installs adaptive implementation and validation executable.
- `cpp/tests/CMakeLists.txt`
  - registers the Step 20 C++ test target.
- `Makefile`
  - adds `adaptive-baselines-check` and includes it in the project test gate.
- `scripts/validate_repository.py`
  - requires Step 20 public source, evidence, documentation, and governance artifacts.

## Corrections made during Step 20

1. Restored a drifted `SPECIFICATION.yaml` byte-for-byte from the approved corrected Step 2 package; the specification lock itself was not regenerated.
2. Limited passive MPC child orders to a predeclared maximum fraction (validation default 1/2), while retaining full residual aggressive execution for completion.
3. Added explicit no-action behavior when `ParentOrderStatus::TerminalCompletionPending`, preserving Step 8 as the only terminal-completion owner.
4. Moved calibration-cutoff leakage validation into shared adaptive-signal calculation so direct solver calls cannot bypass it.
5. Made horizon ceiling arithmetic overflow-safe.
6. Calculated spread in `long double` to avoid signed integer subtraction overflow at extreme tick values.
7. Required canonical reduced fractions and the full `1/1` aggressive action in the MPC action set.
8. Regenerated stale deterministic Steps 13–17 provenance sidecars in dependency order; their scientific content, admission status, replay counts, queue results, and metric values did not change.
9. Added the Step 20 Makefile target to `.PHONY` and the help surface.

## Scope deliberately not added

Step 20 contains no learned model, future information, exact historical queue state, Step 21 features/labels, or historical strategy ranking. The adaptive calibration parameters are synthetic engineering-test values only until Gate C admits real data.
