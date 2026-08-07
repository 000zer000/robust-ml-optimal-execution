# Step 18 changelog — Basic execution baselines

## Added

- `cpp/include/robust_execution/strategies/baselines.hpp`
- `cpp/include/robust_execution/strategies/strategies.hpp`
- `cpp/src/strategies/baselines.cpp`
- `cpp/tests/test_basic_baselines.cpp`
- `cpp/apps/re_baseline_demo.cpp`
- `scripts/validate_step18_baselines.py`
- deterministic Step 18 baseline validation report
- Step 18 strategy and validation documentation
- `baselines-check` Make target

## Behavior

Implemented:

1. immediate aggressive execution;
2. aggressive or passive TWAP;
3. aggressive or passive past-only volume-informed schedules;
4. deterministic integer-lot largest-remainder allocation;
5. timestamped past-volume profile construction with hard leakage rejection;
6. `ScheduledBaselinePolicy` through the common Step 8 `ExecutionPolicy` interface;
7. Step 17 metric calculation and independent audit for the deterministic oracle.

## Corrections made during the step

- canonicalized mathematically equivalent action fractions such as `25/100` to `1/4` before common action validation;
- removed `assert`-dependent Step 18 tests after Release/IPO correctly showed that `NDEBUG` would disable them; Step 18 tests now use always-on requirements in every build configuration;
- replaced non-standard `__int128` arithmetic with checked portable C++20 integer arithmetic after the warnings-as-errors gate rejected the extension.

## Scope and claim boundary

The frozen research specification was not modified. The committed shortfall values are synthetic test oracles on one hand-designed price path, not strategy-performance evidence. No historical result or baseline ranking is claimed.

The repository semantic version remains 0.14.0 at this intermediate research milestone; no upstream version-bearing fixture was rewritten solely for metadata churn.
