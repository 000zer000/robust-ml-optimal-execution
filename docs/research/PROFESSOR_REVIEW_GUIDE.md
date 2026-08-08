# Professor Review Guide

This repository is a research system for a deliberately narrow but consequential question:

> When a causal limit-order-book forecast is inserted into an execution controller, does a better
> prediction produce a different decision and, ultimately, a lower execution cost?

The main finding is a negative-but-informative one. In the registered controlled environment,
forecast quality, controller response, execution cost, robustness, and hardware performance are
not monotone proxies for one another. That result is supported by matched-controller ablations,
strong deterministic baselines, multi-seed sequential learning, paired stress tests, block
bootstrap inference, and end-to-end timing measurements.

## Ten-minute evaluation path

1. Read the [research paper](../../paper/Robust_ML_Optimal_Execution_Research_Paper.pdf), especially
   the abstract, experimental-design section, decision-value results, and threats to validity.
2. Use [claim traceability](../../paper/CLAIM_TRACEABILITY.md) to map every headline number to its
   committed JSON report and validation rule.
3. Inspect the exact C++ market and control boundary in `cpp/`, the causal ML stack in `python/`,
   and the staged validators in `scripts/`.
4. Run `python scripts/validate_paper_claims.py`, then `python scripts/validate_release.py`.
5. For a complete Linux validation, run `bash scripts/run_bootstrap_validation.sh`; for the paper,
   install Tectonic and run `make paper-build`.

Historical implementation records and their artifact hashes remain available in the
[validation ledger](../../evidence/validation-ledger/), but are archived away from the project
root so that they do not obscure the scientific entry points above.

## What is novel here

- **Decision-value diagnosis.** Forecasts are evaluated through a matched MPC rather than treated
  as useful merely because their log loss improves. Neutral, shuffled, stale, uncalibrated,
  perfect-label-oracle, and zero-weight controls expose where prediction and execution objectives
  diverge.
- **One accounting path across policies.** Classical schedules, non-ML MPC, ML-assisted MPC,
  imitation learning, and PPO share the same implementation-shortfall and terminal-completion
  rules.
- **Model risk is an experimental variable.** Queue assumptions, latency, liquidity, spread,
  volatility, fees, impact misspecification, information loss, distribution shift, compute budget,
  and simulator mismatch are registered stress dimensions rather than afterthoughts.
- **Statistics and systems are part of the claim.** Paired block bootstrap and ranking stability
  temper point-estimate winners, while CPU, language-boundary, and transfer-inclusive CUDA timing
  prevent microbenchmarks from standing in for a real decision path.

The project does not claim a new neural architecture, a universal best execution policy, or a
production trading strategy. Its research contribution is the integrated methodology and the
empirical demonstration that common proxy objectives can disagree.

## Evidence boundary

| Evidence tier | What is measured | What may be concluded |
|---|---|---|
| Registered controlled simulator | Forecast, decision, cost, OOD, robustness, and statistical comparisons | Causal and comparative statements within the committed generator, controller, and stress assumptions |
| Direct hardware measurements | C++ throughput, Python/C++ boundary, CPU inference, and Tesla T4 CUDA inference | Workload- and hardware-specific performance conclusions |
| Historical/live market data | Ingestion, admission, sequence, replay, and queue-assumption contracts only | Engineering readiness; no historical strategy-performance conclusion |

Historical Gate C is intentionally closed because no qualifying paid or licensed historical feed
was admitted. All manuscript strategy findings are therefore labeled controlled-simulator
evidence. This is a scientific limitation, not a hidden substitution of synthetic data for market
data.

## Reproducibility contract

- Python 3.11 and 3.13 are covered in CI; the native core is tested with GCC, Clang, and
  AppleClang.
- Native correctness is exercised under debug/release builds, ASan/UBSan, and ThreadSanitizer.
- The Python suite enforces branch-aware coverage, and scientific stages have semantic validators
  in addition to unit tests.
- Committed deterministic artifacts carry hashes. Model fitting must reproduce byte-for-byte
  twice on the executing host; cross-hardware weight-byte identity is not claimed.
- Paper figures are regenerated from committed reports, and the manuscript's headline values are
  checked automatically against those reports.

Detailed fresh-clone commands are in [the reproduction guide](../release/REPRODUCIBILITY.md).

## Best directions for a university research extension

The clearest next study is to admit a licensed multi-day historical L2/L3 dataset under the frozen
Gate-C protocol and repeat the matched decision-value experiment without changing the primary
metric or hypothesis. Other defensible extensions include uncertainty-aware or decision-focused
forecast training, calibrated latent queue models from L3 data, cross-venue external validation,
and statistically powered comparisons of multiple policy architectures. Those are future research
questions; none is presented here as completed evidence.
