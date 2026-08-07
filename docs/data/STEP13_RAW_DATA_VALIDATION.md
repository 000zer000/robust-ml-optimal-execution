# Step 13 — Raw-data validation and quarantine

## Status

The Step 13 validation engine is implemented and validated against deterministic full-day and corrupted fixtures. No real Binance day is admitted because the required live 72-hour Step 12 pilot has not completed.

## Purpose

Step 13 decides whether an immutable Step 12 capture is structurally trustworthy and whether each UTC day may enter the primary historical study. It does not repair missing events, fabricate continuity, interpolate book states, or transform the raw feed into the Step 14 canonical dataset.

The engine distinguishes:

1. **Source integrity** — the Step 12 manifest, artifact checksums, embedded raw-payload hashes, record counts, and provenance must verify.
2. **Structural validity** — record schemas, timestamps, stream metadata, trade fields, snapshots, depth sequences, reconstructed books, connection counts, and UTC-day coverage must pass.
3. **Research admissibility** — a structurally valid day must also originate from the live Binance feed, belong to a complete capture, and follow a completed 72-hour pilot.

Synthetic fixtures can prove that the validator works, but they can never satisfy the live-data admission gate.

## Validation order

The implementation validates in this order:

1. verify the immutable Step 12 capture manifest;
2. read every gzip JSONL segment without modifying it;
3. validate the stored record envelope and embedded payload hash;
4. parse the exact Binance combined-stream payload;
5. cross-check stored stream, symbol, and event type against the raw payload;
6. validate receive timestamps and contiguous connection-local message indices;
7. validate trade IDs, prices, quantities, flags, and exchange timestamps;
8. validate depth-update fields and decimal levels;
9. locate exactly one snapshot for each connection and symbol;
10. reconstruct each connection/symbol book through the Step 12 synchronizer;
11. reject gaps, non-overlapping snapshots, malformed levels, and crossed or locked books;
12. group records by receive-date UTC day;
13. evaluate full-day boundaries and required stream counts;
14. write an immutable validation report and quarantine manifest.

## Day statuses

- `admitted` — structurally valid and all live-data admission gates pass.
- `quarantined` — one or more critical structural or provenance failures exist.
- `fixture_valid_not_admissible` — structurally valid synthetic fixture, intentionally barred from the research dataset.
- `not_admissible` — structurally valid non-fixture input that does not yet meet operational admission gates.

## No-repair policy

The primary historical study never fills a sequence gap, synthesizes a missing update, interpolates depth, or silently drops an invalid span. The raw capture is preserved. Problems are represented by explicit issue records and day-level decisions in `quarantine-manifest.json`.

Exact duplicate trades are detected and recorded as warnings because reconnect boundaries can repeat already observed public messages. Canonical deduplication rules belong to Step 14 and must preserve provenance. Sequence gaps, malformed values, crossed books, timestamp reversals, and ambiguous snapshots are critical.

## Provisional operational thresholds

The checked-in configuration requires, per symbol and UTC day, at least two depth messages and two trade messages. These low values exist solely so deterministic fixtures can exercise all code paths. They are **not a claim that such a sparse day is suitable for research**.

A real day cannot be admitted until the live 72-hour pilot is complete. After the pilot, observed message-rate distributions may justify a separate, explicitly approved operational threshold amendment. Until then, the full-day coverage, live-origin, complete-capture, and pilot gates prevent sparse fixture thresholds from admitting real research data.

## Outputs

Each validation run creates a new immutable directory containing:

- `validation-config.json`;
- `validation-report.json`;
- `validation-report.sha256.json`;
- `quarantine-manifest.json`;
- `quarantine-manifest.sha256.json`.

The output directory is create-only. Reusing a validation ID fails.

## Scientific boundary

A Step 13 pass means the observed raw feed is internally consistent under the documented aggregate-L2 reconstruction rules. It does not establish exact individual-order FIFO position, hidden liquidity, endogenous market impact, or strategy performance.
