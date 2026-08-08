# Step 4 Validation — Complete Repository Bootstrap

**Date:** 2026-08-06  
**Step:** 4 of 32  
**Status:** Accepted under the Step 4 roadmap criteria  
**Research specification:** Unchanged; verified by seven SHA-256 locks

## 1. Scope completed

Step 4 created the executable repository foundation required before market-domain
implementation begins:

- C++20 core library and diagnostic executable;
- CMake target separation, install/export rules, and Ninja presets;
- GCC and Clang compiler paths with warnings-as-errors;
- AddressSanitizer and UndefinedBehaviorSanitizer path, plus a TSan preset;
- Python 3.11–3.13 package, strict TOML configuration, JSON logging, CLI, manifests;
- pybind11 binding boundary and scikit-build-core wheel configuration;
- CTest and pytest test layers;
- exact direct build/development tool pins and a project `uv.lock`;
- Docker multi-stage build definition;
- GitHub Actions workflows for C++, Python, quality, wheel, Docker, sanitizers,
  and deterministic reproducibility;
- deterministic sample command explicitly labelled as a bootstrap diagnostic with
  `research_claim: null`;
- frozen-specification hash enforcement;
- repository/data/config/experiment/result directory contracts.

No order-book, strategy, market model, data source, prediction model, or empirical
result was implemented in this step.

## 2. Specification-integrity result

`governance/SPECIFICATION_LOCK.json` covers:

1. `PROJECT_CONTEXT.md`;
2. `RESEARCH_QUESTIONS.md`;
3. `SCOPE.md`;
4. `RESEARCH_PROTOCOL.md`;
5. `DECISIONS.md`;
6. `SPECIFICATION.yaml`;
7. `SPECIFICATION_FREEZE.md`.

Result: **PASS — 7/7 hashes match.**

The exact central research question was found unchanged in:
- `PROJECT_CONTEXT.md`
- `RESEARCH_QUESTIONS.md`
- `README.md`
- `SPECIFICATION.yaml`

Only two existing operational documents changed:

- `README.md`: build/test commands and current status;
- `ROADMAP.md`: current-next-action marker advanced to Step 5.

These changes do not alter the frozen research contract. Details are recorded in
`STEP4_CHANGELOG.md`.

## 3. Executed validation

### 3.1 Python

Command:

```bash
PYTHONPATH=python python3 -m pytest \
  --cov=robust_execution --cov-branch --cov-report=term-missing tests/python
```

Result:

- **29 tests passed**;
- **95.97% combined line/branch-aware coverage** under the configured report;
- strict unknown-key and invalid-value configuration tests passed;
- deterministic artifact and digest tests passed;
- changed/missing specification-file detection tests passed;
- CLI and structured logging tests passed.

The uncovered executable wrapper and defensive CLI branches remain visible in the
coverage report; they were not hidden through broad module exclusions.

### 3.2 GCC build and tests

Environment:

- GCC 14.2.0;
- CMake 3.31.6;
- Ninja 1.12.1;
- C++20;
- warnings treated as errors.

Result:

- configure: PASS;
- build: PASS;
- 2/2 CTest tests: PASS;
- install/export to a clean prefix: PASS;
- installed executable output matched the build-tree executable byte-for-byte.

### 3.3 Independent Clang path

Environment: Clang 17.0.0.

Result:

- configure: PASS;
- build: PASS;
- 2/2 CTest tests: PASS.

### 3.4 Sanitizers

GCC Debug with ASan + UBSan:

- configure: PASS;
- build: PASS;
- 2/2 CTest tests: PASS;
- no sanitizer finding.

TSan is configured as a separate preset because it must not be combined with the
ASan/UBSan path. There is no threaded domain code to justify a TSan execution claim yet.

### 3.5 Deterministic sample

The sample was generated twice from `configs/bootstrap/sample.toml` and compared
byte-for-byte.

Result: **PASS.**

The artifact contains no timestamps, environment-dependent paths, or empirical claim.
Operational timestamps appear only in stderr logs and are not part of the deterministic
artifact.

### 3.6 pybind boundary

Because the exact pinned build packages were not present in the offline package cache,
the isolated wheel could not be built in this container. The binding source was instead
compiled as a real shared extension against locally available pybind11-compatible
headers, imported into Python, and exercised.

Result:

- extension compilation: PASS;
- import: PASS;
- `build_info_json()`: PASS;
- deterministic diagnostic binding: PASS.

This validates the binding source and C++ ABI path, but is not represented as a completed
isolated `scikit-build-core==1.0.3` wheel build.

### 3.7 Syntax and repository contracts

- Python compile-all: PASS;
- TOML parsing: PASS;
- workflow YAML parsing: PASS;
- C++ JSON output parsing: PASS;
- required repository structure: PASS;
- no unexpected file larger than 10 MiB: PASS.

## 4. Environment-limited checks

Two declared CI paths could not be executed here:

1. **Exact isolated wheel:** `uv build --wheel --offline` stopped before compilation
   because `scikit-build-core==1.0.3` and `pybind11==3.0.4` were absent from the local
   cache and DNS/package download is unavailable.
2. **Docker image:** the `docker` executable is not installed in the container.

Ruff and mypy workflows are configured with exact direct versions, but those executables
were also unavailable locally and could not be downloaded. Python compilation, strict
runtime tests, coverage, compiler warnings, and C++ sanitizers were executed instead.
No green GitHub Actions claim is made until the workflows run in GitHub.

## 5. Acceptance criteria

| Step 4 criterion | Result |
|---|---|
| Clean Linux C++ build and tests | PASS — GCC 14 |
| Second compiler/platform path | PASS — Clang 17 locally; macOS CI defined but not yet run |
| Deterministic sample command | PASS — byte-identical rerun |
| Python package/tests | PASS — 29 tests, 95.97% coverage |
| Sanitizer path | PASS — ASan + UBSan |
| pybind11 boundary created | PASS — source and manual extension smoke |
| Docker definition created | PASS — static/syntax review; runtime unavailable |
| CI/static-analysis configuration created | PASS — workflow syntax validated; hosted run pending |
| Frozen specification unchanged | PASS — 7/7 hashes |

**Step 4 decision:** accepted. The roadmap's explicit Step 4 acceptance conditions are
met. Environment-limited hosted checks remain visible and must execute when the repository
is pushed; they are not falsely reported as completed.

## 6. Exact next step

**Step 5 — Event and market-data model.**

Freeze and implement fixed-point market types, event schemas, clocks, sequence and order
identifiers, order state transitions, acknowledgements, fills, fees, latency fields, and
the audit-log contract. No matching algorithm will be implemented before those contracts
are reviewed and tested.
