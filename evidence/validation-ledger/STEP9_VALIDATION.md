# Step 9 validation — Synthetic market generator

**Date:** 2026-08-06  
**Repository version:** 0.6.0  
**Milestone:** Step 9 only; Step 10 has not started  
**Decision:** PASS

## 1. Governance

Step 9 implements the synthetic market generator required by the approved roadmap. It does not
change the central research question, hypotheses, final scope, data split, inference plan or research
protocol.

`python3 scripts/verify_specification_lock.py` reports seven matching frozen files. The lock was not
regenerated during Step 9.

The generator explicitly distinguishes:

- `designed_synthetic` scenarios;
- `adversarial_stress` scenarios;
- future historical calibration, which is not claimed at Step 9.

Every Step 9 manifest contains `calibration_status=not_calibrated_step9`.

## 2. Functional acceptance matrix

| Requirement | Evidence | Result |
|---|---|---|
| Deterministic synthetic event generation | same seed/config reruns | PASS |
| Counter-addressed randomness | Step 7 Philox logical addresses | PASS |
| Passive limit additions | generator and matching-engine tests | PASS |
| Aggressive market orders | exact IOC submissions and trades | PASS |
| Cancellations of live orders | generator tests | PASS |
| Partial fills and queue depletion | Step 6 engine integration | PASS |
| Clustered arrivals | independent versus self-exciting test | PASS |
| Sequential liquidity/volatility regimes | regime transition test | PASS |
| Liquidity resilience | depth-deficit probability boost | PASS |
| Transient synthetic impact | fill-driven microtick state and decay | PASS |
| Fee schedules and rebates | exact maker/taker atom accounting | PASS |
| Temporary and adversarial shocks | liquidity-vacuum fixture | PASS |
| One-time price jumps | shock-start test | PASS |
| No crossed-book state | every generated step checked | PASS |
| Matching-engine invariants | checked after every grid step | PASS |
| Exact action/trade/fee summaries | independent `validate_tape()` | PASS |
| Canonical tape and manifest hashes | SHA-256 checks | PASS |
| Machine-readable contracts | two JSON schemas | PASS |
| Configurable stress environments | two committed configurations | PASS |
| Cross-compiler reproducibility | GCC/Clang/Release byte comparison | PASS |
| Installed/exported API | downstream CMake consumer | PASS |

## 3. Executed validation

### Repository and Python

- frozen specification: **7/7 passed**;
- repository contract: **74 required files passed** before Step 9 reports were added;
- event model: **4 schemas and 9 audit records passed**;
- policy contracts: **4 schemas and 4 fixtures passed**;
- synthetic contracts: **2 schemas and 2 scenario configurations passed**;
- deterministic synthetic fixture regeneration: **passed**;
- Python tests: **50/50 passed**;
- branch-aware Python coverage: **93.69%**;
- Python bytecode compilation: **passed**;
- JSON, TOML and workflow YAML parsing: **passed**.

### Native C++ matrix

| Configuration | Compiler | Tests | Result |
|---|---|---:|---|
| Debug | GCC 14.2.0 | 35/35 | PASS |
| Debug | Clang 17.0.0 | 35/35 | PASS |
| Release + IPO | GCC 14.2.0 | 35/35 | PASS |
| ASan + UBSan | GCC 14.2.0 | 35/35 | PASS, no findings |

All configurations compile with warnings as errors.

### Reproducibility fixture

The committed adversarial demonstration has:

- 200 grid steps;
- 336 generated actions;
- 132 trades;
- 256 executed lots;
- one explicit liquidity-vacuum shock;
- zero rejected commands;
- exact maker rebates of -256 quote atoms;
- exact taker fees of 768 quote atoms.

Hashes:

```text
summary:  c55988cb261bfbc03b71e9266be1ef263ce77b27edb6b9cc6c022e3be098b4ba
tape:     568987023c495fcd3f4f4ea938da0457a0f72830441e73a62b8c32ec9d30dba2
manifest: cf9c899d77b584451359897f671062a4e4c6f1928b73fede8fb53d772d8c895f
```

GCC Debug, Clang Debug and GCC Release produced byte-identical versions of all three artifacts.

### Installation

- clean CMake install from the Release build: **passed**;
- installed `robust_execution_synthetic_demo`: **passed and matched the fixture**;
- separate downstream CMake consumer: **compiled, linked and generated a 10-step tape with a
  64-character SHA-256**.

## 4. Defects caught before completion

### S9-F01 — Invalid defaulted equality operator

GCC accepted a defaulted equality operator for `SyntheticMarketConfig`, while Clang correctly
reported that it was implicitly deleted because `InstrumentDefinition` has no equality operator.
The invalid public operator was removed. No compiler-specific warning suppression was added.

### S9-F02 — Insufficient output provenance

The first manifest summarized the run but did not contain a configuration hash or explicit regime
and shock identifiers. It now records:

- `config_sha256`;
- ordered `regime_ids`;
- ordered `shock_ids`;
- explicit calibration status and limitations.

### S9-F03 — Missing safety bounds

Validation was strengthened to reject:

- regime quantities outside instrument limits;
- unsafe impact magnitudes;
- identifier ranges that could overflow;
- more than 100 million grid steps;
- adversarial regimes incorrectly labelled as designed synthetic.

### S9-F04 — Weak clustering test

The initial excitation test checked only that excitation remained bounded. It was replaced with a
stronger deterministic control using the same seed: the self-exciting process must generate at least
three times as many passive additions as the independent-grid process under the specified fixture.

## 5. Scientific boundaries

Step 9 outputs cannot be used as evidence that:

- the process is calibrated to a real venue;
- its point-process parameters match empirical order flow;
- its impact parameters are causal estimates;
- a strategy that performs well here will perform well in historical or live markets;
- one-sided or liquidity-vacuum behavior has a particular empirical frequency.

A one-sided visible book is intentionally permitted in an adversarial liquidity-vacuum stress. It is
not silently replenished solely to make later policies easier to implement.

## 6. Environment limitations

- Local TSan was not rerun because the unchanged Swift Clang runtime has the documented
  libdispatch/Blocks linker incompatibility. Hosted standard-Clang TSan remains configured but is not
  claimed as executed.
- Docker is unavailable locally. Its CI build remains configured but is not claimed as executed.
- `pybind11` is not installed and package-network access is unavailable, so the isolated wheel and
  manual binding build were not rerun. Step 9's public C++ API and JSON contracts were validated.
- Ruff and mypy were unavailable from the offline package cache. Their pinned hosted jobs remain
  configured and are not claimed as executed.
- GitHub Actions workflow files parse, but hosted jobs have not run until the source is pushed.

## 7. Environment

```text
OS: Linux 6.18.35 x86_64
CPU: AMD EPYC 9V74 80-Core Processor
GCC: 14.2.0
Clang: 17.0.0
CMake: 3.31.6
Ninja: 1.12.1
Python: 3.13.5
jsonschema: 4.26.0
```

No execution-quality, latency, throughput or real-market conclusion is drawn from the demonstration.

## 8. Acceptance decision

Step 9 is complete. The repository now has a deterministic, auditable synthetic environment capable
of normal designed scenarios and deliberately adversarial regimes, while retaining exact matching,
fees, order-flow clustering, resilience and explicit impact assumptions.

The next permitted milestone is Step 10: simulator validation gate. It must test invariants,
hand-calculated scenarios, statistical generator diagnostics, sensitivity, reproducibility and
failure controls before any baseline strategy is implemented.
