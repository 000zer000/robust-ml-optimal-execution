# Step 30 Changelog — Performance engineering and CUDA decision

**Step:** 30 of 32  
**Research specification changed:** No

## Added

- reproducible C++ matching-engine microbenchmark with raw repetition timings;
- `gprof` baseline profile evidence;
- fixed-affinity baseline/optimised 1/2/4-thread measurements;
- process-level memory measurements;
- optional matching-engine expected-order-count capacity hint;
- semantic regression proving capacity reservation does not alter matching results;
- repeated model batch-one and batched CPU inference benchmark;
- TorchScript compatibility timing and current `torch.compile`/`torch.export` experiments;
- compute-latency decision-grid occupancy analysis;
- CUDA hardware availability decision;
- Step 30 config, schemas, tests, validator and performance documentation.

## Explicit negative/no-go findings

- no CUDA/NVIDIA device is visible on the validation machine, so no CPU/GPU speed claim is made;
- the pybind11 build dependency is unavailable locally, so no Python/pybind boundary timing is
  fabricated;
- temporal Inductor graph-break compilation is slower at batch one in the measured run;
- full-graph compilation is unsupported for the current temporal LSTM path;
- TorchScript is faster here but deprecated in the installed PyTorch release and is not promoted
  as the future deployment interface.

## Not changed

- frozen research specification;
- simulator/event semantics;
- matching priority or accounting;
- model weights or research selections;
- Gate C or Gate I status.
