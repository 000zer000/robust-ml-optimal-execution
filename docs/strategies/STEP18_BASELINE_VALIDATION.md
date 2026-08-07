# Step 18 baseline validation

The gate requires:

- exact parent-quantity conservation;
- deterministic integer allocation;
- evenly spaced TWAP releases;
- strict past-only volume-profile cutoff;
- future-observation rejection;
- aggressive and passive schedule construction where valid;
- policy-level market-action generation through the common `ExecutionPolicy` interface;
- Step 17 metric calculation and independent metric audit;
- deterministic byte-identical validation output;
- cross-compiler and sanitizer regression of the entire C++ platform.

The committed synthetic validation path uses arrival price 100 and the same exogenous ask sequence for all scheduled baselines. Its implementation-shortfall values are test oracles only.
