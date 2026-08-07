# Step 4 Bootstrap Architecture

## Boundaries

- `robust_execution_core` is a dependency-light C++20 library.
- Python orchestration lives under `python/robust_execution`.
- `cpp/bindings/module.cpp` is the only pybind11 boundary at bootstrap.
- Configuration is strict TOML and rejects unknown keys.
- JSON logging is operational telemetry and is kept out of deterministic artifacts.
- `governance/SPECIFICATION_LOCK.json` protects the frozen research contract.
- The diagnostic sequence and bootstrap artifact are build/reproducibility checks only;
  neither is a simulator, model, random-number generator, or empirical result.

## Test layers

1. one CTest executable per bootstrap contract, with no custom test dispatcher;
2. pytest unit/integration tests for configuration, logging, artifacts, CLI, and governance;
3. GCC and Clang native builds;
4. ASan+UBSan path;
5. wheel build with the pybind11 extension in network-enabled CI;
6. deterministic sample rerun and byte comparison;
7. Docker build in CI.

A richer C++ testing framework and property/fuzz testing enter with the simulator
validation work, when there are domain invariants large enough to justify them.
