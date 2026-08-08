# Preregistered Research Design

This document summarizes the scientific choices fixed before final evaluation. The detailed
estimands, data boundaries, models, stress conditions, and statistical rules are defined in
[`RESEARCH_PROTOCOL.md`](RESEARCH_PROTOCOL.md), [`RESEARCH_QUESTIONS.md`](RESEARCH_QUESTIONS.md),
[`SCOPE.md`](SCOPE.md), and [`SPECIFICATION.yaml`](SPECIFICATION.yaml).

## Confirmatory design

- The parent order is exogenous; the study evaluates execution, not alpha generation.
- Implementation shortfall in basis points is the primary cost metric.
- ML-assisted MPC is compared with the same MPC controller without ML on paired episodes.
- Completion and CVaR guardrails prevent apparent gains from residual inventory or excess tail risk.
- Training, validation, calibration, controlled holdout, and OOD populations are separated.
- Causal feature cutoffs precede every decision and label horizon.
- Final comparisons use paired seeds and dependence-aware moving-block bootstrap inference.

## Evidence boundary

- Strategy findings are controlled-simulator results under the committed generator, queue,
  latency, impact, and stress assumptions.
- Systems findings are direct measurements on the hardware recorded with each benchmark.
- Historical-feed ingestion and replay contracts are implemented, but no historical strategy
  performance is claimed because no qualifying licensed multi-day feed was admitted.
- No result is presented as live profitability, deployment safety, or a universal execution rule.

## Integrity controls

The specification lock records SHA-256 hashes for the four authoritative design files. CI verifies
the lock, evidence manifests, paper claims, deterministic fixtures, native tests, Python tests,
and sanitizer builds. Any scientific amendment requires an explicit rationale and a refreshed
lock before new confirmatory evaluation.
