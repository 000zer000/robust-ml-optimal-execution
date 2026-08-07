# Reproduction guide

## Fast structural check

```bash
python scripts/verify_specification_lock.py
python scripts/validate_repository.py
python -m compileall -q robust_execution scripts tests
```

## Python tests

Use the repository's partitioned test targets to keep expensive PyTorch regeneration from exceeding short CI shells. The release threshold remains >=90% branch-aware repository coverage.

## Native correctness

```bash
cmake --preset gcc-debug
cmake --build --preset gcc-debug -j2
ctest --preset gcc-debug --output-on-failure
```

Repeat with the Clang, Release, and sanitizer presets documented in the step validation reports.

## Scientific artifacts

Step-specific validators regenerate deterministic JSON/CSV/model artifacts. Expensive Steps 22-30 should be run separately if the shell has a short wall-clock limit.

## Docker

The root `Dockerfile` provides a clean environment for the software/reproduction path. Large external historical datasets are intentionally not embedded in the source image.

## External evidence

- `evidence/performance/STEP30_CUDA_GATE.json`: Tesla T4 CPU/GPU comparison.
- `evidence/performance/STEP30_PYBIND_BOUNDARY_SUPPLEMENT.json`: numeric Python/C++ boundary measurement.
- `evidence/data/TARDIS_SAMPLE_COMPATIBILITY.json`: free sample schema/continuity audit.
