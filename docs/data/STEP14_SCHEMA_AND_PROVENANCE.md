# Step 14 schema and provenance contract

## Lineage chain

Every canonical message or event row can be traced through:

```text
canonical dataset manifest
  -> Step 13 validation report hash
  -> Step 12 capture manifest hash
  -> immutable raw segment path and line
  -> raw-payload SHA-256
```

The canonical tables do not embed raw payload text. They retain sufficient identifiers and hashes to recover and independently verify the exact source message from the private raw store.

## Schema evolution

The current schemas are version 1. A change requires a new schema version when it alters:

- a column name, type, nullability, or semantic meaning;
- the canonical order;
- fixed-point units;
- natural duplicate keys;
- table partitioning or row granularity;
- the interpretation of timestamps or source identifiers.

Adding an optional physical encoding without changing logical rows does not by itself change the logical schema, but its engine and version must be recorded.

Existing immutable datasets are never rewritten in place. A migration creates a new dataset ID and records the prior manifest hash.

## Timestamp semantics

All stored exchange and collector timestamps use integer nanoseconds.

- Binance microsecond timestamps are multiplied exactly by 1,000.
- `received_utc_ns` is the collector wall-clock observation time.
- `received_monotonic_ns` is the collector monotonic timestamp and is not interpreted as UTC.
- snapshots have no invented exchange event timestamp; they retain connection start and source update ID.

## Ordering and causality

`canonical_message_sequence` is assigned from preserved capture order. It is not inferred from event timestamps. `canonical_row_sequence` is table-specific and deterministic.

Later historical replay must use the source contract defined in Step 15. Step 14 does not decide how simultaneous exchange events, snapshots, trades, and policy events interact in the simulator.

## Duplicate semantics

Exact duplicates are observable data-quality events, not silently erased. The first record remains canonical and every removed occurrence is listed in `duplicate_records`.

Conflicting records with the same natural key are not resolved by choosing one, averaging, or using the later arrival. The entire conversion fails for investigation.

## Publication boundary

Canonical book deltas and snapshots can reconstruct detailed market states. They are therefore treated as reconstructive market data even though raw payload text is absent.

The committed public repository may contain only the tiny synthetic fixture. Real or vendor-derived canonical tables require a separate licensing and redistribution review. Dataset manifests always record that public redistribution is not cleared by default.

## Validation responsibilities

The independent verifier checks:

- dataset-manifest hash;
- every table schema and data hash;
- equal column lengths;
- schema and physical column agreement;
- row-count consistency;
- instrument coverage;
- source-message and duplicate counts;
- sample versus processed admission boundary;
- mandatory Parquet policy for processed data;
- unchanged research specification and zero repaired events.
