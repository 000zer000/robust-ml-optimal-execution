# Step 19 validation — Discrete Almgren–Chriss

**Decision:** PASS for Step 19 engineering and mathematical acceptance.  
**Research status:** synthetic validation only; no historical performance claim.

## Mathematical acceptance

The implementation follows the discrete zero-drift linear-impact Almgren–Chriss first-order condition. The following independent oracles pass:

1. `lambda = 0` produces exactly `25 / 25 / 25 / 25` for a 100-lot, four-period parent and therefore exactly matches Step 18 TWAP.
2. `sigma = 0` also removes the risk penalty and reproduces TWAP.
3. For `lambda = 0.5`, `sigma = eta = tau = 1`, `gamma = 0`, the discrete relation gives `cosh(kappa)=1.25`, hence `kappa = ln(2)`. The implementation matches this value to numerical tolerance.
4. The tridiagonal inventory solution matches the independent hyperbolic closed form at every inventory node in the moderate-risk oracle.
5. Increasing risk aversion from 0 to 0.5 to 2.0 increases first-slice quantity from 25 to 51 to 73 lots.
6. The moderate-risk schedule has lower `E + lambda*V` than TWAP when both are evaluated at the same `lambda = 0.5` under the Almgren–Chriss model.
7. An extreme-risk 64-slice case remains finite and approaches immediate execution, validating the stable recurrence solver rather than a potentially overflowing direct `sinh(kappa*T)` implementation.
8. `eta_tilde <= 0`, non-finite parameters, leaked calibration cutoffs, invalid horizons, and invalid provenance are rejected.

## Integer schedules and synthetic realized-cost oracle

The committed 100-lot schedules are:

| Case | lambda | Integer schedule | AC expected cost units | AC variance units | Synthetic realised shortfall |
|---|---:|---|---:|---:|---:|
| Risk neutral | 0.0 | 25 / 25 / 25 / 25 | 2500 | 8750 | 0 bps |
| Moderate risk | 0.5 | 51 / 26 / 14 / 9 | 3554 | 3011 | +37 bps |
| High risk | 2.0 | 73 / 20 / 5 / 2 | 5758 | 782 | +68 bps |

The realised-shortfall path is deliberately constructed so that stronger front-loading performs worse ex post. This is a negative control: optimality under the Almgren–Chriss model does not imply superiority on an arbitrary realised price path.

Every realised metric is produced through the common Step 17 metric calculator and passes the independent Step 17 audit.

## Leakage and claim controls

- calibration cutoff must be strictly before parent start;
- calibration provenance must be non-empty;
- the committed parameters are synthetic validation parameters, not estimates;
- fixed cost `epsilon` enters model diagnostics but does not change the monotone schedule shape;
- historical calibration and sensitivity remain future experimental work;
- no real-market, profitability, or strategy-ranking conclusion is permitted at Step 19.

## Regression matrix

- frozen specification: 7/7 hashes passed;
- Python: 308/308 tests passed;
- Python branch-aware coverage: 90.07%;
- GCC Debug: 50/50 C++ tests passed;
- Clang Debug: 50/50 passed;
- GCC Release with IPO: 50/50 passed;
- ASan + UBSan: 50/50 passed, no findings;
- GCC, Clang, and Release Step 19 output: byte-identical;
- Step 19 deterministic report verifier: passed;
- clean CMake installation: passed;
- separate downstream `find_package(robust_execution 0.14)` consumer using the installed Almgren–Chriss API: passed;
- Step 13–15 deterministic fixture regeneration and verification: passed with unchanged scientific status/counts.

## Source verification

The implementation was checked against Almgren and Chriss, *Optimal Execution of Portfolio Transactions*, Journal of Risk 3(2), 5–39. In the paper's linear model, expected cost contains the effective temporary-impact coefficient `eta_tilde = eta - gamma*tau/2`; minimizing `E + lambda V` yields the discrete second-order inventory equation and hyperbolic solution used as the independent oracle here.

**Exact next step:** Step 20 — implement and validate a non-ML adaptive queue/liquidity-aware controller and a receding-horizon/MPC baseline under the same causal observation and accounting contracts.
