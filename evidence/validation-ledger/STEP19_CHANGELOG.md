# Step 19 changelog — Almgren–Chriss

**Step:** 19 — discrete Almgren–Chriss execution baseline  
**Research specification changed:** No

## Added

- `cpp/include/robust_execution/strategies/almgren_chriss.hpp`
- `cpp/src/strategies/almgren_chriss.cpp`
- `cpp/apps/re_almgren_chriss_demo.cpp`
- `cpp/tests/test_almgren_chriss.cpp`
- `scripts/validate_step19_almgren_chriss.py`
- `docs/strategies/STEP19_ALMGREN_CHRISS.md`
- `docs/strategies/STEP19_ALMGREN_CHRISS_VALIDATION.md`
- deterministic Step 19 sample evidence under `data/sample/almgren_chriss/step19-validation/`

## Build and repository integration

- added the Almgren–Chriss source to `robust_execution_core`;
- added an installed `robust_execution_almgren_chriss_demo` executable;
- added `re_test_almgren_chriss` to CTest;
- added `almgren-chriss-check` to the Makefile and the integrated test dependency chain;
- extended the repository contract to require the Step 18 and Step 19 strategy artifacts.

## Mathematical implementation

The schedule implements the zero-drift, single-asset, linear-impact discrete Almgren–Chriss model with

- `eta_tilde = eta - gamma*tau/2`;
- `kappa_tilde^2 = lambda*sigma^2/eta_tilde`;
- the discrete second-order inventory recurrence;
- deterministic integer-lot apportionment after solving the continuous target trajectory.

The production solver uses the tridiagonal recurrence rather than evaluating hyperbolic functions directly. The hyperbolic closed form is retained as an independent test oracle.

## Leakage and provenance controls

Every parameter set must contain a non-empty provenance identifier and a calibration cutoff strictly earlier than the execution episode. Step 19 does not claim that any parameter has been estimated from real data.

## Defects and issues caught during Step 19

1. A direct vector comparison in the validation executable initially assumed `ScheduleSlice` had equality semantics. The comparison was rewritten explicitly rather than adding an unnecessary global operator.
2. A first portability guard attempted a compile-time `1 << 64` expression on platforms where `long double` has 64 mantissa bits. It was replaced with a platform-independent 2^53 exact-apportionment bound.
3. The frozen `SPECIFICATION.yaml` again drifted externally. It was restored byte-for-byte from the approved corrected Step 2 package; the specification lock itself was not regenerated.
4. Step 13–15 deterministic sidecar hashes had become stale. Those synthetic fixtures were regenerated in dependency order. Their scientific state remained unchanged: Step 13 admitted days = 0, Step 14 rows = 24 and non-research, Step 15 replay events = 10 / observations = 8 and non-research.

## Not added

- no historical Almgren–Chriss calibration;
- no claim that the model's impact parameters represent Binance or any other venue;
- no strategy-superiority claim;
- no Step 20 adaptive/MPC logic;
- no change to the central research question, hypotheses, scope, or protocol.
