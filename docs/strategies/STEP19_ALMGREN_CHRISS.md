# Step 19 — Discrete Almgren–Chriss baseline

## Status

Step 19 implements the zero-drift, single-asset, linear-impact Almgren–Chriss schedule as a required classical optimal-execution baseline. It is a schedule model, not a market-prediction model, queue model, or profitability claim.

The implementation follows Almgren and Chriss, *Optimal Execution of Portfolio Transactions*, Journal of Risk 3(2), 5–39. For a monotone liquidation program with interval length `tau`, linear permanent impact `gamma`, linear temporary impact `eta`, volatility `sigma`, and risk aversion `lambda`, define

```text
eta_tilde = eta - gamma * tau / 2
kappa_tilde^2 = lambda * sigma^2 / eta_tilde
```

with the required convexity condition `eta_tilde > 0`.

The discrete first-order condition is

```text
(x[j-1] - 2 x[j] + x[j+1]) / tau^2 = kappa_tilde^2 x[j]
```

with `x[0] = X` and `x[N] = 0`. The equivalent closed form is

```text
x[j] = X * sinh(kappa * (T - t[j])) / sinh(kappa * T)
```

where

```text
2 * (cosh(kappa * tau) - 1) / tau^2 = kappa_tilde^2.
```

## Numerical implementation

The production implementation does not evaluate the hyperbolic expression directly. It solves the strictly diagonally dominant/symmetric positive tridiagonal recurrence for normalized inventory targets using a Thomas solve. This avoids overflow in `sinh(kappa T)` for aggressive parameter settings. The closed-form expression remains an independent validation oracle for moderate parameter values.

The continuous trade weights are converted to integer lots by deterministic largest-remainder apportionment. The implementation:

- conserves the parent quantity exactly;
- breaks equal remainders by earlier slice index;
- rejects numerical states that would make the allocation ambiguous;
- limits this floating apportionment path to at most 2^53 lots for portable exact integer representation.

## Parameter and leakage contract

Every schedule carries:

- `slice_count`;
- risk aversion `lambda`;
- volatility `sigma`;
- temporary impact `eta`;
- permanent impact `gamma`;
- fixed cost `epsilon`;
- timestamp-to-model-time scale;
- execution style;
- a calibration cutoff timestamp;
- a non-empty parameter provenance identifier.

The calibration cutoff must be in the parent clock domain and must be strictly earlier than episode start. This does not claim that the parameters are already empirically calibrated: Step 19 validation uses synthetic oracle parameters only. Future real experiments must estimate/freeze parameters using development data only.

`epsilon` does not change the schedule shape for a monotone one-direction program because total absolute traded quantity is fixed. `gamma` affects the shape through `eta_tilde`. Realized fees, spread, fills, and terminal completion are evaluated by the common Step 17 accounting layer rather than being substituted with the Almgren–Chriss model cost.

## Policy integration

`AlmgrenChrissPolicy` implements the Step 8 `ExecutionPolicy` interface. It releases the cumulative quantity prescribed by the static schedule, waits when a command is pending or a child is live, canonicalizes the exact remaining-quantity fraction, and leaves residual inventory to the common hard-completion mechanism.

The primary classical comparison uses aggressive market/IOC child orders to isolate scheduling behavior. A passive style is available for controlled secondary experiments, but it must not be described as the original Almgren–Chriss execution model because passive queueing and fill uncertainty are outside the classic linear-impact derivation.

## Validation boundaries

The committed validation fixture is synthetic only. It verifies mathematical and software behavior, not market realism or strategy superiority. In particular:

- `lambda = 0` reproduces TWAP exactly;
- zero volatility also removes the risk term and reproduces TWAP;
- increasing `lambda` front-loads the schedule;
- a moderate parameter case matches the closed-form `kappa = ln(2)` oracle;
- the discrete recurrence matches the hyperbolic inventory trajectory;
- `eta_tilde <= 0` and leaked/non-finite parameters are rejected;
- exact integer quantity is conserved after discretization.

No historical parameter estimate or performance result is claimed at Step 19.
