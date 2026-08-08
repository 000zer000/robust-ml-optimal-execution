# v0.14.0 research release

This release packages the complete C++/Python optimal-execution research system together with the accompanying IEEE-style manuscript, reproducibility instructions, deterministic experiment artifacts, and measured CPU/CUDA evidence.

## Research components

- exact integer-arithmetic C++20 limit-order-book matching and event simulation;
- historical replay and aggregate-L2 queue models;
- classical execution baselines and finite-horizon receding MPC;
- causal microstructure targets/features, calibrated supervised models, and a Conv1D-LSTM temporal model;
- matched ML-assisted MPC with prediction-value ablations;
- behavior cloning with DAgger correction and OOD fallback diagnostics;
- categorical PPO with multi-seed evaluation and independently reconstructed reward accounting;
- 43-condition robustness matrix and dependence-aware paired block-bootstrap analysis;
- profile-guided C++ optimization, Python/C++ boundary measurement, compiled inference, and transfer-inclusive Tesla T4 benchmarking.

## Canonical manuscript

The canonical technical description of the project is:

`paper/Robust_ML_Optimal_Execution_Research_Paper.pdf`

Its LaTeX source, BibTeX bibliography, and reproducible figure-generation script are stored in the same `paper/` directory.

## Evaluation scope

Strategy comparisons reported in the manuscript use the registered controlled execution environment and paired synthetic stress experiments. Systems results are direct measurements on the documented CPU and Tesla T4 environments. Historical-feed capture, reconstruction, admission, and replay infrastructure is included as a separate research component.
