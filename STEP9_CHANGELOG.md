# Step 9 change log — Synthetic market generator

## Added

- C++ synthetic-market configuration, validation and generator APIs.
- Discrete self-exciting order-flow processes for adds, market orders and cancellations.
- Discrete exogenous reference moves.
- Liquidity-deficit resilience.
- Transient fill-driven impact with decay.
- Sequential regime definitions and composable adversarial shocks.
- Exact maker/taker fee accounting.
- Canonical tapes, manifests and SHA-256 provenance.
- Independent tape consistency validation.
- Five C++ test executables.
- Two JSON Schema Draft 2020-12 contracts.
- Normal and adversarial scenario configuration examples.
- Deterministic committed tape, manifest and summary fixtures.
- Native validation script and Python schema tests.
- Installed `robust_execution_synthetic_demo` executable.

## Correctness controls

- Specification lock retained without regeneration.
- No historical-calibration claim added.
- No policy, learning or performance result introduced.
- No venue-specific rule selected early.
- No Step 10 simulator-validation conclusion claimed.

## Version

Repository version advanced from `0.5.0` to `0.6.0` for the Step 9 API addition.
