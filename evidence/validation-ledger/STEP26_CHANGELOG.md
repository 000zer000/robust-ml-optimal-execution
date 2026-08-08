# Step 26 Changelog — Imitation Learning

**Step:** 26 of 32  
**Status:** Engineering implementation complete; historical research activation blocked by Gate C  
**Research specification changed:** No

## Added

- C++ batch teacher oracle using the exact shared MPC solver.
- Deterministic synthetic train/validation/correction/engineering-holdout/OOD episode fixture.
- Compact behavior-cloning MLP with training-only normalization and validation-only hyperparameter selection.
- Sequential learner rollout with exact teacher queries on learner-induced states.
- Validation-triggered one-round DAgger correction path.
- Confidence plus feature-distance abstention and exact-teacher fallback study.
- Teacher-relative mean/tail implementation-shortfall analysis.
- Persisted deterministic teacher-labelled split tables with provenance and SHA-256 manifest.
- Canonical JSON policy artifact with exact NumPy reconstruction.
- Separate machine-specific teacher/student latency benchmark.
- Step 26 config, schemas, generator, validator, documentation and tests.
- Cross-compiler scientific-artifact checksum record.

## Corrections made during Step 26

1. Rejected the initial non-ML teacher fixture after a broad state sweep proved its first MPC action degenerate (`passive_50` everywhere).
2. Replaced that shallow fixture with the already-validated shared ML-MPC path plus a causal synthetic engineering risk input, explicitly without selecting a research horizon/model/weight.
3. Added controlled teacher-labelled states so the behavior clone sees a meaningful action surface rather than reporting trivial one-class accuracy.
4. Moved latency measurements out of the deterministic report into a machine-specific benchmark artifact.
5. Preserved the OOD negative result: DAgger improves validation and holdout behavior, but the raw OOD student degrades materially and fallback does not restore perfect agreement.

## Explicitly not changed

- frozen research question, hypotheses or protocol;
- final prediction horizon/model family;
- final ML-MPC research weight;
- historical test lock;
- Gate C status;
- reinforcement-learning start gate.
