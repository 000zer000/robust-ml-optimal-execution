# Step 16 validation report

**Repository version:** 0.13.0  
**Step:** 16 — Aggregate-L2 queue models  
**Status:** Engineering pass; historical calibration and real-data execution results pending  
**Research specification changed:** No  
**Specification lock regenerated:** No

## Acceptance decision

The optimistic, central, and pessimistic aggregate-L2 queue models pass their engineering gate. Exact historical FIFO reconstruction remains explicitly false.

Step 16 may feed passive maker-fill estimates into Step 17 accounting and metrics. No historical strategy result may be treated as robust unless it is evaluated under all three queue assumptions.

## Model semantics

- All displayed quantity present when the child joins is initially ahead.
- Later displayed additions are behind the child.
- Eligible at-price trades consume estimated quantity ahead before filling the child.
- Trade-through fills the residual child when enabled.
- The next level update attributes matching displayed reduction to prior trade volume before treating any remainder as cancellation/deletion volume.
- Cancellation-only sequences cannot fill the child.
- Optimistic allocates unexplained reductions ahead.
- Central allocates them proportionally to estimated queue ahead over displayed quantity.
- Pessimistic allocates them behind.

## Exact synthetic comparison

The validation runs two Step 6 exact matching engines for each scenario:

1. an exact FIFO world containing the passive child;
2. a ghost world without the child, used to generate the public aggregate tape.

Five exact comparison scenarios passed:

| Scenario | Exact FIFO | Optimistic | Central | Pessimistic |
|---|---:|---:|---:|---:|
| No cancellation | 10 | 10 | 10 | 10 |
| Cancellation ahead | 20 | 20 | 0 | 0 |
| Cancellation behind | 0 | 20 | 0 | 0 |
| Mixed cancellation | 10 | 20 | 10 | 0 |
| Addition only | 0 | 0 | 0 | 0 |

For all five scenarios:

- optimistic fill ≥ central fill ≥ pessimistic fill;
- optimistic fill ≥ exact FIFO fill ≥ pessimistic fill.

These are controlled validation properties, not universal claims for arbitrary historical paths.

## Sensitivity matrix

The mixed-cancellation scenario was evaluated under all three assumptions and additional initial-ahead buffers of 0, 2,500, and 5,000 basis points.

- nine sensitivity cells passed;
- estimated fills were non-increasing as the hidden-ahead buffer increased;
- estimated residual quantity ahead was non-decreasing.

The buffers are stress parameters, not calibrated hidden-liquidity estimates.

## Python validation

- 242/242 tests passed;
- branch-aware coverage: 90.18%;
- strict queue-model configuration tests passed;
- schema validation passed for the contract, report, and evidence manifest;
- artifact hash and immutable-manifest verification passed;
- report, CSV, and semantic tampering tests passed;
- deterministic fixture regeneration passed.

## Native validation

- GCC Debug: 44/44 tests passed;
- Clang Debug: 44/44 tests passed;
- GCC Release with IPO: 44/44 tests passed;
- GCC ASan + UBSan: 44/44 tests passed, no findings;
- queue demo output was byte-identical under GCC Debug, Clang Debug, and GCC Release;
- queue demo SHA-256: `f05feff3c80a426872f3dc256868e229ed7c55a06fd73fce70cf72bc772d2092`;
- clean Release installation passed;
- external `find_package(robust_execution 0.13)` consumer compiled, linked, and ran the queue validation API.

## Fixture compatibility regeneration

The repository version advanced from 0.12.0 to 0.13.0. Steps 12–15 deterministic fixture manifests embed the software version, so those synthetic fixtures and their downstream hashes were regenerated.

The following scientific content did not change:

- Step 12 raw fixture messages and feed semantics;
- Step 13 structural-validity and non-admission decision;
- Step 14 canonical row counts and sample-only classification;
- Step 15 replay event and observation counts, queue boundary, and non-research status.

## Scientific claim boundary

The committed evidence states:

```text
historical_exact_fifo_reconstructed = false
ghost_small_agent_assumption = true
research_status = synthetic_validation_only_non_research
```

Step 16 does not identify real cancellations ahead or behind, recover hidden liquidity, or establish that the central model is empirically correct.

## Tool limitations

Ruff and mypy were unavailable locally, so no fresh local result is claimed for them. Python compilation, executable tests, independent compilers, optimized builds, sanitizers, installation, downstream consumption, schema validation, and deterministic evidence checks passed. Hosted CI remains configured for the pinned quality tools.

## Decision

**Step 16 engineering gate: PASS.**  
**Historical queue calibration: PENDING.**  
**Real-data strategy evaluation: PENDING admitted live days and Step 17 metrics.**
