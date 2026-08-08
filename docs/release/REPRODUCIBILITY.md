# Reproduction guide

Python 3.13 on Linux x86-64 with the exact direct dependencies in `requirements/test.lock` is the primary CI reproduction environment. GCC 14 and Clang 18 are exercised in GitHub Actions; macOS and Python 3.11 are also supported for correctness checks. Scikit-learn and Torch fitting can differ across CPUs and ML/BLAS kernels even when those coarse environment identifiers match. The contract therefore requires two byte-identical regenerations on the executing host, verifies every committed artifact's integrity, and applies each step's registered numeric or scientific checks. It deliberately does not claim that fitted-model bytes are portable between machines.

## Fresh-clone setup

Prerequisites are Python 3.11 or 3.13, CMake 3.24 or newer, Ninja, and a C++20 compiler.

```bash
git clone https://github.com/000zer000/robust-ml-optimal-execution.git
cd robust-ml-optimal-execution
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements/test.lock
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`. The native presets and CI are currently validated on Linux and macOS.

## Structural and static checks

```bash
python scripts/verify_specification_lock.py
python scripts/validate_repository.py
python -m compileall -q python/robust_execution scripts tests
ruff check python tests/python scripts
ruff format --check python tests/python scripts
mypy python/robust_execution
```

## Native correctness

Linux:

```bash
cmake --preset gcc-debug
cmake --build --preset gcc-debug
ctest --preset gcc-debug --output-on-failure
```

macOS:

```bash
cmake --preset clang-debug
cmake --build --preset clang-debug
ctest --preset clang-debug --output-on-failure
```

Sanitizer commands, on a supported Clang/GCC installation:

```bash
cmake --preset asan-ubsan
cmake --build --preset asan-ubsan
ctest --preset asan-ubsan --output-on-failure
cmake --preset tsan
cmake --build --preset tsan
TSAN_OPTIONS=halt_on_error=1:second_deadlock_stack=1 ctest --preset tsan --output-on-failure
```

## Python correctness and artifacts

```bash
PYTHONPATH=python python -m pytest \
  --cov=robust_execution --cov-branch --cov-report=term-missing tests/python
PYTHONPATH=python python scripts/validate_step22_simple_models.py
PYTHONPATH=python python scripts/validate_step23_temporal_model.py
PYTHONPATH=python python scripts/validate_step24_ml_mpc.py
PYTHONPATH=python python scripts/validate_step25_prediction_decision_value.py
PYTHONPATH=python python scripts/validate_step26_imitation.py
PYTHONPATH=python python scripts/validate_step27_rl.py
PYTHONPATH=python python scripts/validate_step28_robustness.py
PYTHONPATH=python python scripts/validate_step29_statistics.py
PYTHONPATH=python python scripts/validate_step30_performance.py
python scripts/validate_release.py
```

`scripts/run_bootstrap_validation.sh` is the consolidated Linux validation entry point. The root Dockerfile builds and smoke-tests the distributable CLI; it is intentionally a minimal runtime image, not the full ML reproduction environment.

## Evidence boundaries

- `evidence/performance/STEP30_CUDA_GATE.json`: Tesla T4 CPU/GPU comparison.
- `evidence/performance/STEP30_PYBIND_BOUNDARY_SUPPLEMENT.json`: numeric Python/C++ boundary measurement.
- `evidence/data/TARDIS_SAMPLE_COMPATIBILITY.json`: free sample schema/continuity audit.
- Committed strategy results are controlled simulator evidence, not admitted historical-market results. Gate C remains closed until a qualifying historical dataset is admitted.
