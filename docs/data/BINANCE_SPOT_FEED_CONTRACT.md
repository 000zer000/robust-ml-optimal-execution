# Binance Spot feed contract for Step 12

This document converts current official semantics into implementation requirements. It is not a
substitute for rechecking the live documentation at deployment time.

## Endpoints

- WebSocket: `wss://data-stream.binance.vision`
- REST: `https://data-api.binance.vision`
- Metadata: `GET /api/v3/exchangeInfo`
- Snapshot: `GET /api/v3/depth?symbol=<SYMBOL>&limit=5000`

No private account or trading credentials are required or permitted for market-data capture.

## Streams

For `BTCUSDT` and `ETHUSDT`:

- `<symbol_lower>@depth@100ms`;
- `<symbol_lower>@trade`;
- combined or separate connections are allowed, but connection identity must be preserved.

Add `timeUnit=MICROSECOND` to the WebSocket URL. Store the payload exactly as received and record a
collector UTC receive timestamp and monotonic receive timestamp outside the payload.

## Snapshot/delta algorithm

1. Connect and buffer diff-depth events.
2. Fetch a 5000-level snapshot.
3. If snapshot `lastUpdateId` is below the first buffered `U`, refetch.
4. Discard buffered events with `u <= lastUpdateId`.
5. Require the first retained event to overlap `lastUpdateId` within `[U,u]`.
6. Apply replacement quantities; zero removes a level.
7. Require each subsequent update range to continue the book.
8. If `U > local_update_id + 1`, invalidate the book and rebuild.

Do not patch gaps using the last known value. Do not mark an episode valid while the book is
unsynchronised.

## Connection lifecycle

A connection is valid for only 24 hours. Step 12 must rotate before the deadline with either an
overlap-and-handoff procedure or a controlled reconnect whose gap is explicitly measured. The
manifest records:

- connection start/end;
- close code and reason;
- server-shutdown event if received;
- ping/pong failures;
- DNS and selected endpoint;
- first/last exchange update IDs per symbol;
- snapshot ID and checksum;
- all detected sequence anomalies.

## Metadata snapshot

At every capture start, persist the full `exchangeInfo` response and extract, without hard-coding:

- symbol status;
- base and quote assets;
- price tick;
- quantity step and min/max;
- minimum notional;
- permitted order types;
- self-trade-prevention modes;
- any other active filters.

If either selected symbol is not `TRADING`, the capture may continue for diagnostics but cannot be
admitted as a valid research day without an explicit decision.

## Timestamp model

- `E`: exchange event time;
- `T`: trade time for trade messages;
- collector UTC arrival time: our wall-clock observation;
- collector monotonic arrival time: within-process ordering/latency diagnostics;
- canonical ordering: raw-file byte order, then per-connection message index.

Exchange timestamps are not assumed perfectly monotone or synchronised with the collector. Clock
offset is measured, not silently corrected.

## Data-admission boundary

The historical replay consumes only periods with a synchronised book. Any pre-snapshot buffered
updates, gap interval, malformed payload, checksum failure, or unknown schema transition is
quarantined and visible in the day-quality report.
