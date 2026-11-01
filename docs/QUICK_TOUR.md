# Quick tour and interview route

## Run

Requirements: Python 3.11+, CMake 3.24+ and a C++20 compiler. From the repository:

```bash
python3 scripts/quick_demo.py
```

Open `output/quick-demo/index.html`. The command builds only the existing core,
matching demo and teaching comparison. It emits native JSON, matching state,
SHA-256 checksums, measured time and peak child-process RSS. The RSS includes the
compiler for a build; it is not aggregate system memory. A reused build is faster
than a clean build. No dependency installation, network access or ML training runs.

Three existing aggressive baseline schedules share one 100-lot buy order and the
same ask path: immediate, four-slice TWAP and a fixed past-volume profile. The
profile cutoff precedes the order. Actual future asks settle orders but do not
choose their schedule. Two hand-authored paths show a reversal in the lowest-cost
policy. Every fill is valued by the real C++ accounting engine and audited; six
expected costs are also independently transcribed from the hand tape.

This settlement assumes sufficient quantity and immediate fills at the given
ask, no fees, latency or impact. It is deliberately not a queue-aware strategy
replay. The separate matching demo executes real core submissions, replacements,
cancellations and matching and checks its invariants. Neither demonstration
establishes historical profitability. Gate C remains closed.

## Recruiter explanation

“I built a C++/Python execution research system, starting with exact matching and
accounting, then comparing control and ML policies under controlled stress. The
important finding is that improved prediction does not automatically improve
execution cost, and that fallback dependence and compute overhead matter. The
short tour makes those accounting and scope distinctions inspectable.”

## Interview route

1. Explain price-time priority with `cpp/apps/re_matching_demo.cpp` and its state.
2. Reconstruct the first volume-profile cost: 9,980 paid versus 10,000 reference
   quote atoms, or -20 bps. Follow the exact metrics/audit implementation.
3. Explain why a known past-volume profile is allowed, and future-volume leakage
   is not. Then inspect the causal feature contract and time partitions.
4. Compare prediction error with downstream decision value and the ablations.
5. Report all fallback figures together: 69.30% raw OOD agreement, 94.78% combined
   agreement, 82.61% teacher fallback. Discuss teacher cost, not just student speed.
6. Explain the exact workload behind CPU throughput and why T4 loses at batch one.

The report is a personal technical manuscript in IEEE-style layout, not a claimed
peer-reviewed publication. The measured CPU/CUDA evidence and larger controlled
study are separate from the quick tour. Follow `paper/CLAIM_TRACEABILITY.md` for
headline sources.

## A future historical study

Before opening Gate C, admit a licensed dataset that meets the existing minimum
coverage (100 days per instrument), sequence/snapshot integrity, clocks, train/test
separation and reproducibility requirements. Record fees, latency and explicit
queue assumptions; aggregate L2 cannot establish exact L3 queue position. A small
licensed sample can first test ingestion and admission, but cannot waive the
frozen minimum. Budget/licensing approval and a distinct exploratory protocol are
needed before any new data acquisition or scientific claim. No historical gate
or locked protocol is changed by this tour.


## Verification on 1 November 2026

The native original core suite passed 53 tests; the added teaching contract passed
separately (one test). An earlier integrated 54-test build also passed before the
tour was isolated to preserve the research CMake/evidence hashes. Specification,
repository, release and twelve paper-claim validators passed. No model retraining
or CPU/CUDA rebenchmark was performed. Desktop 1280px and mobile 390px reports were
checked for readable rows and absence of horizontal overflow and visually inspected.

A clean dedicated tour build took 12.07 seconds on this Mac with AppleClang 15,
peaking at 175.20 MiB child-process RSS including compilation. A later clean-source,
no-build receipt is published in quick-tour/run.json: these are distinct runs.
No-build timing does not include compilation. Original matching/policy code and
scientific outputs are unchanged; the prior release manifest is archived.

For a concrete fallback cost comparison, the recorded step-26 engineering
manifest reports student NumPy p50 of 12.43 microseconds and C++ teacher p50 of
199.41 microseconds. This is a particular engineering workload, separate from the
later compiled-inference timings and not exchange latency. It explains why an
82.61% teacher-fallback rate must accompany the 94.78% combined agreement claim.
