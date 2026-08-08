# Step 14 change log

**Repository version:** 0.11.0  
**Step:** 14 — Canonical datasets  
**Research specification changed:** No

## Added

- `robust_execution.canonical_data` configuration, builder, columnar writer, Parquet exporter, and independent verifier.
- Six versioned canonical tables: instruments, source records, snapshots, deltas, trades, and duplicate audit.
- Exact decimal-to-fixed-point conversion with no rounding tolerance.
- Deterministic ordering and full source-lineage columns.
- Exact-duplicate removal and conflicting-duplicate rejection.
- Immutable dataset manifests, table schemas, hashes, and create-only output.
- Strict sample/processed admission boundary.
- Pinned `pyarrow==25.0.0` research-output dependency.
- Three JSON schemas, two configurations, CLI commands, deterministic fixture, validation scripts, and tests.
- Step 14 documentation and CI/reproducibility integration.

## Compatibility updates

The repository version advanced from 0.10.0 to 0.11.0. Deterministic Step 12 and Step 13 fixtures were regenerated because their manifests record the software version. Their raw messages, validation decisions, admission boundary, and research meaning did not change.

## Not changed

- central or secondary research questions;
- hypotheses;
- final project scope;
- Step 13 admission rules;
- venue or instruments;
- raw-data repair prohibition;
- historical queue or impact claims.

## Pending external evidence

No live day is research-admitted. The 72-hour capture pilot remains incomplete, so the committed Step 14 dataset is synthetic, sample-only, and non-research. The exact PyArrow Parquet path is implemented and unit-tested with a controlled interface substitute, but a real local PyArrow binary was unavailable in this execution environment.
