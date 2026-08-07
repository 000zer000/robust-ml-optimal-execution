# Step 14 — Canonical datasets

## Status

Step 14 implements the immutable conversion layer between independently validated raw capture and later historical replay. It does not admit any real market day because the live 72-hour pilot remains incomplete.

The committed dataset is a deterministic synthetic fixture and is permanently labelled `sample_only_non_research`.

## Input gate

Canonicalisation accepts a day only when the Step 13 report can be independently verified and the day is structurally valid.

Two output tiers exist:

- `sample`: accepts only the deterministic synthetic fixture, provided it is structurally valid; it can never be research admissible;
- `processed`: accepts only a live day whose Step 13 decision is `admitted`.

The converter rejects quarantined days, mismatched capture and validation manifests, missing provenance, unsupported event types, inexact decimal conversion, conflicting duplicate keys, and any attempt to repair or interpolate missing events.

## Canonical tables

The dataset contains six tables.

### `instrument_definitions`

One row per instrument, recording the exact price and quantity increments and their source.

For the committed fixture, increments come from the explicit fixture contract. A real dataset must obtain and retain them from captured Binance `exchangeInfo` filters. Placeholder values are not accepted.

### `source_records`

One row per unique raw WebSocket message. It preserves:

- capture run and artifact path;
- source line and global source-record index;
- connection and connection-local message index;
- stream and event type;
- exchange event timestamp;
- UTC and monotonic collector timestamps;
- raw-payload SHA-256;
- adapter-assigned canonical message sequence.

The raw payload itself is not copied into the canonical dataset.

### `book_snapshots`

One row per snapshot price level, with side, exact fixed-point price and quantity, snapshot update ID, connection, and connection-start timestamp.

Snapshots are included only for connections whose start day is selected for the dataset.

### `book_deltas`

One row per bid or ask level update. A Binance depth message containing several levels becomes several rows, while all rows retain the source message sequence and update-ID range.

### `trades`

One row per raw trade with exchange event time, trade time, trade ID, exact fixed-point price and quantity, maker-side flag, and best-price-match flag.

### `duplicate_records`

An audit table for exact duplicates dropped during canonicalisation. The policy is:

- same natural key and same raw-payload hash: retain the first occurrence and record the later one as `exact_duplicate_dropped`;
- same natural key and different raw-payload hash: stop with an error.

Natural keys are `(symbol, trade_id)` for trades and `(symbol, first_update_id, final_update_id)` for depth updates.

## Exact fixed-point conversion

Prices and quantities remain decimal strings until conversion. A value is accepted only when it is an exact integer multiple of the declared increment. No binary floating-point rounding, truncation, or tolerance is used.

The stored integers are signed 64-bit values:

- `price_ticks = price / price_increment`;
- `quantity_lots = quantity / quantity_increment`.

A zero depth quantity is retained and marked as a deletion. Negative, non-finite, inexact, or overflowing values are rejected.

## Deterministic order

The canonical order is:

1. capture-manifest artifact order;
2. record order inside each immutable raw segment;
3. payload level order, bids before asks, for multi-level depth updates.

Exchange timestamps are data fields and are not used to silently reorder messages. This preserves the observed capture order while retaining exchange event time for later analysis.

## Physical formats

### Auditable base layer

Every table is written in `re_columnar_v1`:

- one versioned schema JSON;
- one deterministic gzip-compressed JSON object containing one array per column;
- equal-length columns and an explicit column order;
- SHA-256 hashes in the dataset manifest.

This format has no external runtime dependency and is used for deterministic tests, source review, and small reproducibility examples.

### Research Parquet layer

Any `processed` research dataset must also write all six tables as Parquet using the repository-pinned `pyarrow==25.0.0`. The build fails if that exact engine is unavailable. A custom base-layer file, CSV, pandas pickle, or untested claimed Parquet file cannot satisfy the processed-data gate.

The sample fixture does not require Parquet and remains non-research regardless of whether PyArrow is installed.

## Output layout

```text
dataset-id/
├── canonical-config.json
├── dataset-manifest.json
├── dataset-manifest.sha256.json
└── tables/
    ├── instrument_definitions/
    ├── source_records/
    ├── book_snapshots/
    ├── book_deltas/
    ├── trades/
    └── duplicate_records/
        ├── schema.json
        ├── columns.json.gz
        └── table.parquet       # mandatory only for processed research data
```

## Research boundary

Step 14 creates representation and provenance. It does not claim:

- a completed live capture;
- a research-admissible day;
- historical queue position;
- reconstructed individual orders;
- hidden liquidity;
- empirical impact;
- replay validity;
- strategy performance.
