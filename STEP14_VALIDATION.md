# Step 14 validation report

**Repository version:** 0.11.0  
**Step:** 14 — Canonical datasets  
**Status:** Engineering pass; real processed dataset blocked pending live admission and local PyArrow installation  
**Research specification changed:** No  
**Specification lock regenerated:** No

## Acceptance decision

The Step 14 conversion, provenance, schema, duplicate, fixed-point, immutability, and verification layers pass their engineering gate.

The committed canonical dataset is not a research dataset. It is a deterministic synthetic fixture whose manifest states:

- `dataset_classification = sample_only_non_research`;
- `research_admissible = false`;
- `data_origin = synthetic_transport_fixture`;
- `missing_events_repaired = false`;
- `public_redistribution_cleared = false`.

No real day can be processed until Step 13 admits it. A processed dataset additionally requires all six Parquet tables written with the pinned `pyarrow==25.0.0` implementation.

## Canonical fixture evidence

- selected days: 1 synthetic UTC day;
- input raw records: 8;
- unique canonical messages: 8;
- exact duplicates dropped: 0;
- conflicting duplicates: 0;
- tables: 6;
- total rows across tables: 24;
- source records: 8;
- snapshot levels: 4;
- book-delta rows: 6;
- trade rows: 4;
- instrument definitions: 2;
- repaired or interpolated events: 0.

The fixture regenerates byte-for-byte from the immutable Step 12 capture fixture and Step 13 validation report.

## Python validation

- tests: 162/162 passed;
- branch-aware coverage: 90.11%;
- exact conversion, duplicate, provenance, immutability, tamper, malformed input, sample/processed boundary, and controlled Parquet interface tests passed;
- three Step 14 JSON schemas validated;
- Python compilation passed.

## Native regression validation

Step 14 does not alter C++ exchange or simulator behavior. The complete existing native matrix was rerun after the version change:

- GCC Debug: 36/36 tests passed;
- Clang Debug: 36/36 tests passed;
- GCC Release with IPO: 36/36 tests passed;
- GCC ASan + UBSan: 36/36 tests passed, no findings;
- clean Release installation: passed;
- external `find_package(robust_execution 0.11)` consumer: passed.

## Governance and repository checks

- frozen specification hashes: 7/7 passed;
- specification lock unchanged;
- Step 12 fixture deterministic after version-compatible regeneration;
- Step 13 fixture and validation output deterministic after version-compatible regeneration;
- Step 14 fixture deterministic;
- no raw payload text copied into canonical tables;
- no research-admissible days claimed.

## Tool limitations

A local PyArrow binary was unavailable. The processed-data code path is implemented and tested using a controlled interface substitute, but no claim is made that a real Parquet file was produced in this environment. The repository pins `pyarrow==25.0.0`; a real processed build fails if that exact dependency is absent.

Ruff and mypy could not be executed because their pinned packages were unavailable from the local package registry. Python compilation and the executable test suite passed; hosted CI remains configured for the pinned quality tools.

## Decision

**Step 14 engineering gate: PASS.**  
**Research canonical dataset: PENDING.**

Step 15 historical replay may be implemented and tested against the synthetic canonical fixture. No historical result may be reported until live days pass Step 13 and processed Parquet output passes Step 14 verification.
