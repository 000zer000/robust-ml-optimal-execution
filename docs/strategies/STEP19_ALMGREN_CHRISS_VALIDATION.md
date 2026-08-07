# Step 19 Almgren–Chriss validation methodology

The validation uses a 100-lot synthetic buy parent over four equal intervals. `sigma = 1`, `eta = 1`, `gamma = 0`, and the interval length is one model-time unit.

Three risk settings are fixed before the synthetic episode:

| Case | lambda | Integer schedule | Purpose |
|---|---:|---|---|
| risk-neutral | 0.0 | 25 / 25 / 25 / 25 | must equal TWAP |
| moderate | 0.5 | 51 / 26 / 14 / 9 | closed-form `kappa = ln(2)` oracle |
| high | 2.0 | 73 / 20 / 5 / 2 | stronger front-loading |

For the moderate case, the recurrence solution is independently compared with the hyperbolic closed form at every inventory node. Its model objective is also checked to be lower than the TWAP objective when both are evaluated using `lambda = 0.5`.

The schedules are then passed through the Step 17 realized metric engine on one deliberately falling/rising synthetic ask path. This path is chosen so that stronger front-loading is *worse* in realized shortfall: 0 bps for the risk-neutral/TWAP schedule, +37 bps for the moderate schedule, and +68 bps for the high-risk schedule. This is a negative-control oracle showing that mathematical optimality under the Almgren–Chriss impact/risk model does not imply ex-post superiority on an arbitrary price path.

The validation report is regenerated from the C++ executable and must match byte-for-byte. A Python verifier independently checks the payload SHA-256, leakage cutoff, quantity conservation, expected allocations, closed-form `kappa`, and monotone front-loading.
