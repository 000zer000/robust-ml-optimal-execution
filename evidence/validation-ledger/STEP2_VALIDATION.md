# Step 2 Validation Report

## Status

**PASS — 2026-08-06**

This report records the checks applied to the full-scope specification before Step 2 was marked complete.

## Checks performed

1. Parsed `SPECIFICATION.yaml` successfully.
2. Verified exact chronological allocation: 50 train, 20 validation, 10 calibration, and 20 locked-test days at the 100-day minimum per instrument.
3. Verified that the active documents require at least two instruments.
4. Verified that ML-MPC versus non-ML MPC is the unique primary contrast.
5. Verified hard terminal completion and fee-inclusive implementation shortfall.
6. Verified that deep learning, imitation learning, RL, robustness, performance engineering, and the CUDA/GPU decision are all in the final scope.
7. Verified that active documents do not contain reduced-v1 headings or statements that RL, imitation, deep learning, or CUDA are outside completion.
8. Verified that historical aggregate replay does not claim exact FIFO reconstruction or endogenous impact.
9. Verified dependence-aware day-block inference and final-test comparator lock.
10. Verified completion/CVaR confidence-bound guardrails.
11. Verified that all internal Markdown links resolve.
12. Generated SHA-256 hashes and file metrics in `STEP2_MANIFEST.json`.

## Specification defects found and corrected during validation

### A. Inconsistent minimum data count

An initial 55-day and then 60-day minimum did not provide a sufficiently credible locked-test period for the planned contiguous-day bootstrap. The binding minimum is now **100 valid whole days per required instrument**, allocated exactly 50/20/10/20.

### B. Guardrails initially used point estimates

The completion and CVaR safeguards were strengthened to confidence-bound non-inferiority checks using the same dependence-aware day-block bootstrap as the primary analysis.

### C. RL seed language was too permissive

The final RL comparison now requires at least ten independent training seeds. The minimum cannot be reduced because of compute inconvenience.

## Result

The active governance package is internally consistent at Step 2. Data-dependent fields remain explicitly identified and must be resolved before the calibration and locked-test stages.
