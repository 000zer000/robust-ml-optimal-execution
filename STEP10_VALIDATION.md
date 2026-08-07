# Step 10 validation — Simulator Gate B

**Date:** 2026-08-06  
**Repository version:** 0.7.0  
**Decision:** PASS — Step 11 may begin

## 1. Governance

The central research question, hypotheses, final scope, data split and research protocol were not
changed. `scripts/verify_specification_lock.py` reports seven matching files. The lock was not
regenerated.

The Step 5 terminal-rejection amendment remains unapproved and unapplied.

## 2. Gate result

| Evidence class | Workload | Result |
|---|---:|---|
| Hand matching oracle | 1 exact three-level tape | PASS |
| Hand latency oracle | 7 fixed latency stages | PASS |
| Reproducibility | same and changed seeds | PASS |
| Failure injection | invalid config and tape tamper | PASS |
| Randomized generator properties | 64 seeds, 16,384 steps | PASS |
| Differential reference | 32 seeds, 64,000 commands | PASS |
| Structured mutation | 2,048 corrupted artifacts | PASS |
| Directional sensitivities | 4 comparisons × 32 paired seeds | PASS |

All seven report checks and all four sensitivity checks passed. The committed JSON report validates
against `simulator-validation-report-v1.schema.json`.

## 3. Sensitivity evidence

| Sensitivity | Control | Treatment | Criterion | Result |
|---|---:|---:|---|---|
| Market-order probability | 13.375 | 167.46875 | treatment > control + 50 | PASS |
| Target visible depth | 40.06591796875 | 217.523193359375 | treatment > 1.5 × control | PASS |
| Volatility/impact | 2.03125 | 34.0 | treatment > control + 10 ticks | PASS |
| Liquidity shock | 64.5625 | 0.0 | treatment < control | PASS |

## 4. Test matrix

| Configuration | Compiler | C++ tests | Result |
|---|---|---:|---|
| Debug | GCC 14.2.0 | 36/36 | PASS |
| Debug | Clang 17.0.0 | 36/36 | PASS |
| Release + IPO | GCC 14.2.0 | 36/36 | PASS |
| ASan + UBSan | GCC 14.2.0 | 36/36 | PASS, no findings |

For the sanitizer configuration, the first 35 tests passed in the complete CTest run and the
long-running Gate B test passed in a separate verbose CTest invocation after the surrounding tool
window expired. No failed or interrupted test is counted as a pass.

Additional validation:

- Python tests: **52/52 passed**;
- Python branch-aware coverage: **93.69%**;
- frozen specification: **7/7 passed**;
- repository contract: **108 required files passed**;
- event, policy, synthetic and validation schemas/fixtures: passed;
- GCC Debug, Clang Debug and GCC Release Gate B reports: byte-identical;
- clean Release install: passed;
- installed validation executable: passed and matched the fixture;
- clean external `find_package(robust_execution 0.7)` consumer: built, linked and ran successfully.

## 5. Reproducibility hashes

Canonical in-process report hash:

```text
d59b06d19b7af478b98974c34d335501cefbcb8d4e771beb058564c2562567cf
```

Committed JSON file hash, including its final newline:

```text
5f43e3b0a8b51fae04ef32954b38d8a156d16ab2b9f92cc7ac202b398d70e769
```

The JSON file hash is identical under GCC Debug, Clang Debug and GCC Release.

## 6. Defects found during the gate

1. The installed target export lacked a CMake package config, so `find_package` failed. Corrected
   and independently retested.
2. The initial mutation workload was unnecessarily expensive under sanitizers. It was reduced in
   baseline tape size without reducing the 2,048 cases or mutation categories.
3. The Release build had no named CTest preset. Validation now uses the actual build directory and
   does not claim a nonexistent preset.

## 7. Scientific boundary

Gate B validates exact synthetic mechanics and designed-process response. It does not validate:

- historical distributional fit;
- venue-specific semantics;
- hidden liquidity;
- aggregate historical queue position;
- real-data market impact;
- strategy quality;
- real or simulated profitability.

The synthetic generator remains explicitly uncalibrated. Gate B authorizes real-data source
selection; it does not authorize skipping later historical-replay, queue-model, baseline or RL
gates.

## 8. Environment limitations

- Local TSan retains the documented Swift-Clang libdispatch/Blocks linker incompatibility.
- Coverage-guided libFuzzer/AFL++ was not run; the 2,048-case structured mutation campaign is labelled
  accurately.
- Docker, hosted CI, wheel construction, Ruff and mypy were not rerun locally because their required
  tools or package access were unavailable. Configurations are present but not claimed green.

## 9. Final decision

**Gate B passes.** The exact synthetic simulator is sufficiently validated to proceed to Step 11:
verify and select current market-data sources using primary venue documentation, licensing/access
rules and feed semantics.
