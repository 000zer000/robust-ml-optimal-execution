# Step 30 — Performance engineering

## Scope and claim boundary

Step 30 profiles and optimises measured bottlenecks without changing the frozen research
specification. All timings are machine-specific engineering evidence. They are not historical
execution results or general hardware claims.

The validation machine exposes five AMD EPYC 9V74 logical CPUs, about 5.9 GiB RAM, GCC 14.2,
Python 3.13.5 and CPU-only PyTorch 2.10.0. No NVIDIA device is visible.

## C++ matching-engine profile and optimisation

A real matching workload repeatedly rests one-lot asks and removes them with IOC buys. Timing
excludes engine construction/destruction and thread creation. Raw timing rows and deterministic
checksums are retained for every repetition.

`gprof` on the exact Step 29 baseline identified unordered-map insertion/bucket work and rehash
allocation among the measurable hot paths. Step 30 therefore adds one narrow optional capacity
hint (`expected_order_count`) that reserves the matching engine's identifier/history containers.
The default is zero, preserving prior behaviour.

The final fixed-affinity medians for 60,000 submit operations per repetition were:

| Threads | Baseline | Reserved | Median speedup | Reserved throughput |
|---:|---:|---:|---:|---:|
| 1 | 13.527 ms | 13.286 ms | 1.018x | 4.516 Mops/s |
| 2 | 6.895 ms | 6.591 ms | 1.046x | 9.103 Mops/s |
| 4 | 4.932 ms | 3.465 ms | 1.423x | 17.316 Mops/s |

The 4-thread improvement is not promoted as a portable scaling claim because the virtual machine
is noisy and exposes only five logical CPUs. Raw samples must be consulted.

A 100,000-pair process-level `/usr/bin/time -v` check observed 49,544 KiB maximum RSS for the
baseline and 49,128 KiB with the capacity hint. The optimisation therefore did not create a
measured memory expansion on this workload.

`re_test_matching_capacity_hint` proves that hinted and default configurations produce the same
canonical matching state.

## Inference engineering

The formal benchmark measures full preprocessing/model/postprocessing wrappers where applicable,
with repeated batch-one and batched CPU runs.

At one CPU thread and batch one:

| Path | Eager/NumPy p50 | TorchScript p50 | TorchScript p95 |
|---|---:|---:|---:|
| 5 s temporal model | 178.4 us | 134.0 us | 144.2 us |
| PPO seed 27 | 31.1 us | 15.8 us | 17.5 us |
| Imitation policy | 11.9 us NumPy | 9.8 us | 10.4 us |

TorchScript is retained only as a measured compatibility datapoint. The installed PyTorch 2.10
build emits deprecation warnings for tracing, so it is not presented as the future deployment
recommendation.

Current compiler-path experiments show:

- temporal LSTM `torch.compile(..., fullgraph=True)` is unsupported in this runtime;
- graph-break Inductor compilation works but is slower at batch one (about 216 us median versus
  189 us eager in the dedicated compile experiment) and incurs about 10.7 s first compile/run;
- `torch.export` successfully captures the temporal wrapper, but export alone is not a runtime
  speedup;
- PPO full-graph Inductor compiles successfully and is only modestly faster in the dedicated run
  (about 28.5 us versus 30.0 us eager), with about 1.4 s first compile/run.

Batching is a throughput question rather than a batch-one latency question. For example, the
traced temporal path reaches hundreds of thousands of rows per second at batch 256, while the
small imitation policy reaches millions of rows per second.

## Compute-latency injection

Measured p95 batch-one compute latency is converted into occupancy of 25/50/100/250/500 us
decision intervals. This identifies when a model would consume or miss complete decision grids.
It is not presented as historical price-path impact because Gate C remains closed.

## Initial validation-machine limitations and supplemental closure

Two required measurements could not be completed on the original validation machine:

1. **CPU/GPU numeric comparison.** PyTorch is a CPU-only build, CUDA availability is false, and no
   NVIDIA device or `nvidia-smi` is visible.
2. **Python/pybind11 boundary microbenchmark.** The pybind11 development package is absent and the
   local package registry cannot supply it. A subprocess benchmark is deliberately not substituted
   because process-launch overhead would answer a different question.

Both measurements were subsequently completed without altering the registered workloads. The
Tesla T4 comparison in `evidence/performance/STEP30_CUDA_GATE.json` verifies CPU/GPU numeric
equivalence and shows transfer-inclusive GPU latency is worse at batch one. The existing binding
measurement in `evidence/performance/STEP30_PYBIND_BOUNDARY_SUPPLEMENT.json` verifies exact
`diagnostic_sequence` semantics and records the Python/C++ call boundary. These supplements close
Gate J; the original CPU-only report remains an immutable record of its machine's limitations.
