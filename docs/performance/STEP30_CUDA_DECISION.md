# Step 30 — CUDA decision

**Gate J CUDA measurement:** PASS.

The registered inference workloads were benchmarked on an NVIDIA Tesla T4 using PyTorch 2.11.0+cu128. Every CUDA result was compared against its CPU output before timing was accepted.

## Decision

For the latency-sensitive **batch-one execution path, use CPU inference**. Transfer-inclusive CUDA latency (host-to-device transfer, inference, device-to-host transfer) is slower for the imitation, PPO and temporal workloads.

The temporal model becomes GPU-favorable at batch 256, where the measured transfer-inclusive speedup is approximately **1.704x** versus CPU. GPU execution is therefore appropriate for sufficiently large batched temporal scoring, not as the default real-time decision path.

No custom CUDA kernel is justified by the current measured bottleneck profile.

Canonical evidence: `evidence/performance/STEP30_CUDA_GATE.json`.
