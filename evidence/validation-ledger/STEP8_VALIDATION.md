# Step 8 validation — Execution-policy interface and causal observations

**Status:** PASS, with explicitly recorded environment limitations  
**Date:** 2026-08-06  
**Repository version:** 0.5.0  
**Milestone:** Step 8 only; Step 9 has not started

## 1. Governance

Step 8 implements the approved causal observation, common action, parent accounting, child-order state and terminal-completion interfaces. It does not amend the project question, hypotheses, final scope or experimental protocol.

`python3 scripts/verify_specification_lock.py` reports seven matching frozen files. The proposed Step 5 `AlreadyTerminal` rejection-schema amendment remains unapproved and unapplied.

## 2. Functional acceptance matrix

| Requirement | Evidence | Result |
|---|---|---|
| Exact parent inventory and cash | accounting/state tests | PASS |
| Buy/sell and fee/rebate signs | accounting tests | PASS |
| Overflow-safe rational conversion | accounting tests | PASS |
| Shared child-order lifecycle | state and dispatch tests | PASS |
| Duplicate event/execution/fee protection | state tests | PASS |
| Fill cumulative/leaves conservation | negative state test | PASS |
| Fee-schedule identity | negative state test | PASS |
| Immutable causal observation | observation tests | PASS |
| Delivered-event watermark | observation tests | PASS |
| Crossed-book rejection with rollback | negative observation test | PASS |
| Full environment identity | builder/validator mismatch tests | PASS |
| Top-K depth and bounded trades | observation tests | PASS |
| Deterministic lineage and observation hashes | observation and demo tests | PASS |
| Common no-op/submit/cancel/replace contract | action tests | PASS |
| Equal action constraints across policies | validator tests | PASS |
| Default one-live-child constraint | action tests | PASS |
| Explicit terminal sequence | terminal tests | PASS |
| Terminal event through kernel | integration test | PASS |
| Exact terminal residual accounting | integration test | PASS |
| No-op valid after completion | integration test | PASS |
| Versioned language interchange | four JSON schemas and fixtures | PASS |
| Cross-compiler deterministic demo | GCC/Clang/Release comparison | PASS |
| Installed/exported policy API | separate downstream consumer | PASS |

## 3. Executed validation

### Repository and Python

- frozen specification: **7/7 passed**;
- repository contract: **70 required files passed** before Step 8 reports were added;
- event model: **4 schemas, 9 audit records passed**;
- policy contract: **4 schemas, 4 fixtures and manifest passed**;
- negative JSON-schema control: **passed**;
- Python tests: **48/48 passed**;
- branch-aware Python coverage: **93.69%**;
- JSON, TOML and workflow YAML parsing: **passed**;
- Python bytecode compilation: **passed**;
- deterministic bootstrap, matching, kernel and policy fixtures: **passed**.

### Native C++ matrix

| Configuration | Compiler | Tests | Result |
|---|---|---:|---|
| Debug | GCC 14.2.0 | 30/30 | PASS |
| Debug | Clang 17.0.0 | 30/30 | PASS |
| Release + IPO | GCC 14.2.0 | 30/30 | PASS |
| ASan + UBSan | GCC 14.2.0 | 30/30 | PASS, no findings |

All configurations use warnings as errors.

### Reproducibility and installation

- GCC Debug, Clang Debug and GCC Release policy-demo outputs are byte-identical.
- The output matches `results/sample/step8/policy_demo.txt`.
- Fixture SHA-256: `8c0938a6a4b18dcc7cac48c5a7122c7e6b374f6b9c2cf482892d3690acee7091`.
- Clean CMake installation completed.
- The installed policy demo matches the committed fixture.
- A separate downstream CMake consumer compiled, linked against the installed export, constructed `ExecutionState` and produced `active:10`.
- The project lock was regenerated offline after the repository version changed and now records version `0.5.0`.

## 4. Environment limitations

- Local TSan was not rerun because the unchanged Swift Clang runtime has the previously documented libdispatch/Blocks linker failure. The standard-Ubuntu-Clang CI job remains configured but is not claimed as executed.
- Docker is unavailable locally; the Docker CI job is configured but not executed here.
- `pybind11` headers and package-network access are unavailable in the current environment, so the isolated wheel and manual binding compile were not rerun. Step 8 adds no partial policy binding; the versioned JSON contracts are the current cross-language boundary.
- Ruff, mypy and clang-format are not installed locally. Their pinned hosted checks are configured but not claimed as executed.
- GitHub Actions workflows parse successfully but have not run until the source is pushed.

## 5. Environment

```text
OS: Linux 6.18.35 x86_64
CPU: AMD EPYC 9V74 80-Core Processor
Visible memory: 5.9 GiB
GCC: 14.2.0
Clang: Swift Clang 17.0.0
CMake: 3.31.6
Ninja: 1.12.1
Python: 3.13.5
jsonschema: 4.26.0
```

No performance or execution-quality conclusion is drawn from this environment or demonstration.

## 6. Acceptance decision

Step 8 is complete. Every future schedule, optimiser and learned policy can now receive the same causally available observation, emit the same validated action types, and use the same exact accounting and terminal-completion machinery. No concrete execution strategy or synthetic market process was implemented early.

The next permitted milestone is Step 9: synthetic market generation, calibrated/adversarial regimes, impact/resilience, fees and shocks.
