# Step 7 validation — Deterministic event-driven kernel and latency

**Status:** PASS, with explicitly recorded local-tool limitations  
**Date:** 2026-08-06  
**Repository version:** 0.4.0  
**Milestone:** Step 7 only; Step 8 has not started

## 1. Scope and governance

Step 7 implements the deterministic scheduler, latency path, logical randomness,
exchange dispatch, observer delivery, and replay hashes required by the approved
32-step roadmap. It does not change the central research question, hypotheses, final
scope, or experimental protocol.

`python3 scripts/verify_specification_lock.py` reported:

```text
{"status": "ok", "checked_files": 7}
```

The proposed Step 5 amendment for terminal cancel/replace rejection payloads remains
unapproved and was not applied. Such failures are retained in the engine-local
`KernelFailureRecord` path instead of fabricating a public event that violates the
current schema.

## 2. Functional acceptance matrix

| Requirement | Evidence | Result |
|---|---|---|
| Deterministic total-order scheduler | stage/sequence/task-order tests | PASS |
| Mixed-clock rejection | scheduler negative test | PASS |
| No scheduling into processed past | scheduler negative test | PASS |
| Seven explicit latency stages | fixed/ranged/overflow tests | PASS |
| Stateless logical RNG | Philox known-answer and call-order tests | PASS |
| Bounded draw correctness contract | range/argument/retry-address tests | PASS |
| Separate exchange receive/process | kernel timing and run-until tests | PASS |
| Causal observer availability | zero-latency and delayed-delivery tests | PASS |
| Step 6 engine integration | submit/cancel/fill/failure tests | PASS |
| Invariant checks after commands | kernel tests invoke engine validation | PASS |
| Hash-chained trace | replay equality/input-change tests | PASS |
| Complete state hash | identical-run and changed-input tests | PASS |
| Cross-compiler sample equality | GCC/Clang/Release versus fixture | PASS |
| Installed executable behavior | installed kernel demo versus fixture | PASS |

## 3. Executed validation

### Python and repository contracts

- specification lock: **7/7 passed**;
- repository structure: **41 required files passed** before Step 7 report creation;
- event-model contract: **4 schemas and 9 audit records passed**;
- Python tests: **47/47 passed**;
- branch-aware Python coverage: **93.69%**, above the 90% gate;
- deterministic bootstrap sample: **passed**;
- matching-engine deterministic hand tape: **passed**;
- kernel fixture validation: **passed**.

### Native C++ matrix

| Configuration | Compiler | Tests | Result |
|---|---|---:|---|
| Debug | GCC 14.2.0 | 21/21 | PASS |
| Debug | Clang 17.0.0 | 21/21 | PASS |
| Release + IPO | GCC 14.2.0 | 21/21 | PASS |
| ASan + UBSan | GCC 14.2.0 | 21/21 | PASS, no findings |

All configurations use warnings-as-errors.

### Reproducibility and installation

- GCC Debug, Clang Debug, and GCC Release kernel-demo outputs were byte-identical.
- Their output matched `results/sample/step7/kernel_demo.txt`.
- Fixture SHA-256:
  `ceff80bedf3f3e43569753d01843614518d180170ea0b3b044c5dd2ee426a12f`.
- Clean CMake installation completed.
- Installed info, matching-demo, and kernel-demo executables ran successfully.
- A separate downstream CMake consumer compiled and linked against the installed
  exported target and exercised both build information and logical randomness.
- The pybind source compiled into a real Python 3.13 shared extension using the locally
  available header copy, imported successfully, and returned deterministic results.

## 4. TSan limitation

The local `tsan` configuration completed, but linking failed before any project test
could run. The installed compiler is a Swift-distributed Clang 17 whose TSan runtime
contains libdispatch interceptors and references unavailable Blocks/libdispatch symbols,
including `_NSConcreteStackBlock`, `_Block_copy`, and `_Block_object_assign`.

This is recorded as a toolchain/runtime limitation, not a passing test and not evidence
of a source race. A hosted CI job now installs the standard Ubuntu Clang toolchain and
runs the existing TSan preset. That job has been configured but has not been executed in
this local session, so no green hosted-TSan claim is made.

The Step 7 scheduler is deliberately single-threaded. TSan remains useful as a build
and future-regression check but is not a substitute for the deterministic scheduler
invariants.

## 5. Other environment limitations

- Docker is unavailable locally; the existing Docker CI job was not executed here.
- Isolated wheel dependency installation is unavailable because package-network access
  is unavailable. The binding source was nevertheless compiled and imported manually.
- `ruff`, `mypy`, and `clang-format` are not installed locally. Their pinned hosted-CI
  jobs/configuration remain present, but are not claimed as executed in this session.
- GitHub Actions workflows were parsed as YAML; they have not been run until the source
  is pushed to GitHub.

## 6. Environment captured

```text
OS: Linux 6.18.35 x86_64
CPU: AMD EPYC 9V74 80-Core Processor
Visible memory: 5.9 GiB
GCC: 14.2.0
Clang: Swift Clang 17.0.0
CMake: 3.31.6
Ninja: 1.12.1
Python: 3.13.5
```

No performance conclusion is drawn from this environment or from the Step 7 demo.

## 7. Acceptance decision

Step 7 is complete because the deterministic kernel, causal latency path, logical
randomness, Step 6 dispatch, replay hashes, tests, cross-compiler reproducibility, and
sanitizer gate are implemented and pass. The TSan local-link limitation is disclosed
and does not invalidate the single-threaded kernel acceptance criteria.

The next permitted milestone is Step 8: immutable causal observations, common policy
actions, active-order state, and parent-order inventory/cash interfaces. No Step 8
implementation is included in this package.
