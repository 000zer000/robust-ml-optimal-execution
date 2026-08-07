# Step 13 change log — Raw-data validation and quarantine

**Repository version:** 0.10.0  
**Date:** 2026-08-06  
**Scope:** Step 13 only; no Step 14 canonical-dataset implementation

## Added

- strict Step 13 validation configuration and loader;
- independent source-capture verification before semantic validation;
- raw record, payload-hash, wrapper, stream, symbol, and event-type checks;
- trade price, quantity, ID, flag, and timestamp validation;
- connection-local index and timestamp continuity checks;
- snapshot-to-delta overlap and aggregate-L2 reconstruction checks;
- crossed/locked-book, sequence-gap, and missing/ambiguous-snapshot quarantine;
- UTC-day coverage and per-symbol stream-presence decisions;
- separate structural-validity and research-admission statuses;
- immutable validation reports and quarantine manifests with SHA-256 sidecars;
- deterministic full-day fixture that is structurally valid but intentionally non-admissible;
- corruption tests for gaps, crossed books, invalid quantities, metadata mismatches, index gaps, timestamp reversal, source tampering, and output tampering;
- four Step 13 JSON schemas;
- two new CLI commands: `validate-raw-data` and `verify-data-validation`;
- Step 13 Makefile and repository-contract gates;
- documentation of admission, quarantine, and no-repair rules.

## Correctness boundaries

- No missing market event is repaired or interpolated.
- No synthetic fixture is admitted to the historical study.
- No live day is admitted before the required 72-hour pilot completes.
- No canonical dataset, historical replay, queue model, or strategy result was created.
- The seven frozen research-specification files were not modified.

## Version changes

- Repository version advanced from 0.9.0 to 0.10.0.
- CMake package, Python package, lock metadata, and build-info tests were updated consistently.

## Compatibility refresh

Advancing the repository version to 0.10.0 changed the software-version field in the deterministic Step 12 offline fixture. The fixture was regenerated with identical six raw messages and unchanged feed semantics, and `STEP12_MANIFEST.json` was updated to preserve its reproducibility check. No live capture evidence or historical result was altered.
