# Step 30 Validation — Performance engineering and CUDA decision

**Engineering implementation decision:** PASS on the available CPU validation machine.  
**Gate J:** PASS — the local pybind boundary measurement and an external Tesla T4 transfer-inclusive CUDA comparison are both complete.  
**Gate I:** remains pending historical activation from Step 29.  
**Research specification changed:** No; the frozen specification lock remains unchanged.

## 1. Validation machine

- CPU: AMD EPYC 9V74 80-Core Processor
- visible logical/physical CPUs: 5 / 5
- memory: 6368813056 bytes
- compiler: c++ (Debian 14.2.0-19) 14.2.0
- Python: 3.13.5
- PyTorch: 2.10.0+cpu
- CUDA available: False
- NVIDIA device utility visible: False

All performance numbers below are fixed-machine engineering evidence, not portable performance or
historical execution claims.

## 2. Matching-engine profile and optimisation

The exact Step 29 baseline was rebuilt beside the Step 30 tree. `gprof` identified unordered-map
insertion/bucket work and rehash allocation among the measurable hot paths. Step 30 therefore adds
an optional expected-order-count capacity hint that reserves matching-engine identifier/history
containers while preserving the zero-hint default.

The dedicated semantic regression proves zero-hint and reserved configurations produce the same
canonical matching state.

Fixed-affinity 60,000-submit medians:

| Threads | Baseline median | Reserved median | Speedup | Reserved throughput |
|---:|---:|---:|---:|---:|
| 1 | 13.527 ms | 13.286 ms | 1.018x | 4.516 Mops/s |
| 2 | 6.895 ms | 6.591 ms | 1.046x | 9.103 Mops/s |
| 4 | 4.932 ms | 3.465 ms | 1.423x | 17.316 Mops/s |

The 4-thread result is retained with raw samples and is not promoted as a portable scaling claim on
a noisy five-vCPU virtual machine.

A 100,000-pair process-level memory check measured 49,544 KiB baseline versus 49,128 KiB reserved
maximum RSS.

## 3. Model inference

One-thread batch-one medians/p95:

| Path | p50 | p95 |
|---|---:|---:|
| Temporal eager | 178.4 us | 180.9 us |
| Temporal TorchScript trace | 134.0 us | 144.2 us |
| PPO eager | 31.1 us | 32.1 us |
| PPO TorchScript trace | 15.8 us | 17.5 us |
| Imitation NumPy | 11.9 us | 14.0 us |
| Imitation TorchScript trace | 9.8 us | 10.4 us |

TorchScript is a measured compatibility datapoint only because the installed PyTorch version emits
a deprecation warning for tracing.

Current compiler-path experiment:

- temporal `torch.compile` with graph breaks: 216.4 us median versus 188.6 us eager; first
  compile/run 10.70 s;
- temporal full graph: `unsupported:Unsupported`;
- temporal `torch.export`: `captured`;
- PPO full-graph Inductor: 28.5 us versus 30.0 us eager; first compile/run 1.41 s.

## 4. Compute-latency injection

The formal p95 values used for timing-budget occupancy are:

- temporal traced: 144.16 us;
- PPO traced: 17.53 us;
- imitation NumPy: 14.01 us.

They are injected into 25/50/100/250/500 us decision-grid budgets. True historical price-path impact
remains blocked by Gate C.

## 5. CUDA and Python/C++ boundary decision

The missing measurements were subsequently completed without changing the frozen workload definitions.

- Python/C++ boundary: the existing binding was built against PyTorch-vendored pybind11 3.0.1 headers. Exact `diagnostic_sequence` semantics were verified before timing. Median boundary cost was 304.05 ns versus 1,748.6 ns for the pure-Python reference; this is explicitly a small-call boundary measurement, not a whole-simulator speedup claim.
- CUDA: the registered temporal, PPO and imitation workloads were run on a Google Colab Tesla T4 with PyTorch 2.11.0+cu128. CPU and CUDA outputs were checked for numerical equivalence before timing. Transfer-inclusive GPU latency was slower at batch one for all three workloads. The temporal model became GPU-favorable only at batch 256, with a measured 1.704x transfer-inclusive speedup versus CPU.

Therefore **Gate J passes**. The deployment recommendation is CPU for latency-sensitive batch-one decisions, with GPU reserved for sufficiently large batched temporal inference.

## 6. Correctness and quality matrix

- Python tests in the final audited tree: **478/478 passed**;
- branch-aware repository coverage: **91%** (required >=90%);
- dedicated Step 30 Python tests: **7/7 passed**;
- GCC Debug C++: **53/53 passed**;
- Clang Debug C++: **53/53 passed**;
- GCC Release C++: **53/53 passed**;
- ASan + UBSan: **53/53 passed**, no findings;
- frozen specification: **7/7 hashes matched**;
- Python compileall and Step 30 JSON/schema parsing: passed;
- clean Release installation and external CMake consumer: passed;
- new/touched Step 30 source lines over 100 characters: **0**.

The full one-shot Python suite passed at 90.75% branch coverage. No coverage threshold was lowered
and no Step 30 module was excluded. Ruff 0.15.22 formatting/lint and mypy 2.3.0 also pass on the
final audited tree.

## 7. Gate decision

**Step 30 available-hardware engineering implementation: PASS.**

**Gate J: PASS.** Numeric CPU/GPU and Python/C++ boundary comparisons are now documented. **Gate I remains pending** because the historical locked test remains blocked by Gate C.

## 8. Integrated repository command

The final audit ran every semantic validator through Step 30, all 478 Python tests with branch
coverage, all 53 native tests under Clang Debug, ASan+UBSan and ThreadSanitizer, and the static
quality checks. The GitHub Actions workflows independently exercise GCC, Clang, AppleClang,
Python 3.11/3.13, wheel installation, Docker smoke testing, reproducibility and sanitizers.
