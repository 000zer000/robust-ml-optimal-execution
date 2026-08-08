# Step 29 Validation — Rigorous Statistical Analysis

**Decision:** PASS for statistical-method engineering validation.  
**Research-result status:** `synthetic_validation_only_non_research`.  
**Historical Tier-1 activation:** BLOCKED by Gate C.  
**Locked historical test opened:** No.  
**Research specification changed:** No; the frozen specification lock remains 7/7.

## 1. Frozen statistical contract implemented

Step 29 implements the protocol's paired aggregation, moving-block uncertainty, effect-size,
multiplicity, guardrail and ranking-stability machinery without substituting the synthetic matrix
for the locked historical Tier-1 analysis.

The engineering analogue uses the 24 ordered paired Step 28 episode seeds as pseudo-days only to
validate method behavior. The final historical unit remains whole trading days with every episode
inside a selected day block retained.

## 2. Block-length selection

The central engineering diagnostic is PPO aggregate minus liquidity-aware cost. Applying the frozen
rule—first lag with absolute autocorrelation below 0.1 for two consecutive lags, clamped to 2–7—
selects **block length 5** because lags 5 and 6 satisfy the threshold.

This is an engineering oracle only. The historical block length remains an unresolved pre-data field
that must be selected on admitted validation days and frozen before the locked test.

## 3. Engineering inference

The committed matrix contains 43 stress cases and four competitive policy families. Step 29 forms
129 paired challenger-minus-liquidity-aware contrasts and uses 4,096 deterministic circular
moving-block bootstrap repetitions per contrast.

Key engineering findings:

- **85/129** 95% mean-difference intervals cross zero;
- Holm-significant exploratory cells: PPO aggregate 4, TWAP-like 8, immediate 15;
- **21/43** point-estimate winners have bootstrap win probability at least 0.80;
- **22/43** point winners are therefore labelled ranking-unstable;
- central liquidity-aware point winner probability is **0.87841796875**;
- central PPO aggregate minus liquidity-aware mean difference is **+0.28198 bps**, with a 95%
  interval crossing zero.

These are Tier-3 synthetic engineering diagnostics, not historical significance claims.

## 4. Tier-1 and guardrail boundary

The preregistered Tier-1 contrast remains ML-assisted MPC minus the same non-ML MPC on locked
historical episodes. Step 29 implements the equal-instrument aggregation and the frozen completion
and CVaR95 block-bootstrap guardrail formulas, and unit-tests them, but records:

- Tier-1 status: `blocked_gate_c`;
- Tier-1 p-value: not evaluated;
- completion guardrail: not evaluated;
- CVaR95 guardrail: not evaluated;
- locked historical test access: false.

No synthetic strategy is promoted into the Tier-1 slot.

## 5. Multiplicity and negative-result preservation

Holm correction is implemented and applied within challenger-by-stress-dimension engineering
families. The adjustment is deliberately conservative but does not change the evidence class from
Tier 3 to confirmatory.

Intervals crossing zero and bootstrap-unstable point winners remain first-class release artifacts.
No strategy is declared universally superior from the robustness matrix.

## 6. Executed validation

### Python

- repository test total represented by the complete partitions: **465/465 passed**;
- dedicated Step 29 tests: **15/15 passed**;
- branch-aware repository coverage: **91%** (required minimum 90%);
- Step 29 statistics module branch-aware coverage: **90%**;
- Step 29 semantic artifact validator: passed;
- Python `compileall`: passed;
- Step 29 source/test/script lines over 100 characters after formatting: **0**.

### C++ regression

Step 29 changes no native behavior, but the complete native platform was rerun:

- GCC Debug: **52/52 passed**;
- Clang Debug: **52/52 passed**;
- GCC Release: **52/52 passed**;
- ASan + UBSan: **52/52 passed**, no findings.

### Packaging/integration

- frozen research specification: **7/7 hashes matched**;
- repository required-file contract: **531/531** after Step 29 integration;
- Step 29 JSON config/schema/artifact parsing: passed;
- clean Release CMake install: passed;
- external `find_package(robust_execution 0.14 CONFIG REQUIRED)` consumer: passed;
- Step 29 report/CSV/ranking/manifest regeneration: byte-identical.

## 7. Tool limitations

Ruff and mypy are not installed locally, so no fresh local Ruff/mypy pass is claimed. The repository
line-length contract is checked directly for the new/touched Step 29 Python files.

The complete integrated `make test` passed every gate through Step 22 and was terminated by the
local execution window while Step 23 temporal-model validation was running. No failing assertion
had occurred. Steps 22–29 were also executed separately on the identical final source state and
all passed, so the single long command is not labelled fully green.

## 8. Gate decision

**Step 29 engineering gate: PASS.**

**Gate I remains pending historical activation.** The statistical machinery and full robustness
matrix exist, but the locked historical test, historical block-length freeze, Tier-1 estimate and
completion/CVaR guardrails cannot be evaluated until Gate C admits the required historical data.

**Next milestone:** Step 30 — performance engineering and evidence-based CUDA decision.
