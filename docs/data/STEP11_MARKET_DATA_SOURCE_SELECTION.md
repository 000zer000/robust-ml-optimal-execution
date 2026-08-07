# Step 11 — Market-data source selection

**Decision date:** 2026-08-06  
**Decision:** Binance Spot, `BTCUSDT` and `ETHUSDT`  
**Historical acquisition:** official self-capture is canonical; Tardis.dev is a conditional acceleration path  
**Research specification changed:** No

## 1. Decision

The project selects **Binance Spot** as the primary historical-replay venue and freezes the two
required instruments as **BTCUSDT** and **ETHUSDT**. The official Binance Spot API documentation is
the semantic authority. The primary live source is Binance's unauthenticated market-data-only
WebSocket and REST infrastructure.

This is an aggregate Level-2 selection. It does not change the frozen separation between exact
synthetic FIFO matching and approximate historical queue modelling. No claim of exact historical
order identity, hidden liquidity, or queue position is introduced.

## 2. Why Binance Spot was selected

Binance documents a snapshot-plus-delta reconstruction procedure with explicit first and final
update IDs (`U`, `u`). A consumer can detect a missing interval, invalidate its local book, and
restart from a fresh REST snapshot. The diff-depth stream is available at 100 ms, raw trades are
real-time, public market-data-only endpoints require no API key, and timestamps may be requested in
microseconds. A connection has a documented 24-hour lifetime, which makes reconnect testing a
first-class requirement rather than an accidental operational detail.

Spot was preferred over perpetual futures because it avoids funding, mark-price, leverage,
liquidation, and contract-roll semantics that are not needed to answer the execution question. This
does not imply that spot findings generalise to futures, equities, or other venues.

BTCUSDT and ETHUSDT were selected because the vendor history explicitly covers both high-cap pairs
and the same venue/feed contract can be applied to both. Their current `TRADING` status, tick size,
lot size, minimum notional, and other filters must still be queried and persisted from
`exchangeInfo` at the beginning of every capture or purchased-data ingestion. Static values are not
hard-coded in Step 11.

## 3. Binding feed contract for Step 12

For each symbol, capture:

- `<symbol>@depth@100ms`;
- `<symbol>@trade`;
- a REST `/api/v3/depth` snapshot with `limit=5000`;
- `/api/v3/exchangeInfo` metadata;
- collector receive time from a monotonic and UTC clock;
- raw bytes before parsing;
- connection, DNS/endpoint, host, software, and clock metadata.

Use the market-data-only endpoints. Request `timeUnit=MICROSECOND`. Buffer deltas before taking the
snapshot and apply Binance's documented `[U,u]` overlap rule. If `U > local_update_id + 1`, discard
the local book and resynchronise. Do not interpolate or silently bridge a gap.

Because each connection expires after 24 hours, Step 12 must implement controlled rotation. A
rotation is not considered continuous unless a fresh snapshot and the buffered updates produce a
valid sequence after the handoff.

## 4. Historical acquisition roles

### 4.1 Canonical raw corpus

The scientifically strongest no-cost path is self-capture from the official Binance endpoints. It
preserves raw messages, sequence IDs, local arrival time, reconnect evidence, and collector
metadata under our own provenance controls. The target remains at least 100 validated whole days per
instrument. The operational plan starts with 120 calendar days, giving a 20-day buffer for rejected
days; only validated days count.

### 4.2 Tardis.dev acceleration path

Tardis has Binance Spot high-cap history from 2019-03-30 and provides daily `incremental_book_L2`
and `trades` files. Its CSV rows contain exchange timestamp, local arrival timestamp, snapshot flag,
side, price, and replacement amount, and preserve capture order. Free access covers only the first
day of each month, which is useful for parser development but insufficient for the 100-day study.

Tardis is conditionally selected as a historical backfill source, not silently purchased. A paid
order requires Othmane's explicit approval. Normalized CSV is acceptable for historical aggregate
replay and cross-checks, but it does not replace our raw-message capture or justify claims about
sequence fields that are absent from the normalized schema. Exchange-native raw replay is eligible
only under an access plan that actually includes it.

### 4.3 Binance public archive

The official Binance public archive is useful for independent trade cross-checks and checksums. Its
current documented Spot products are trades, aggregate trades, and klines; it is therefore not the
selected source for full historical Level-2 reconstruction.

## 5. Acquisition gate

No paid purchase was made. Before buying data, obtain a current quote for exactly:

- venue: Binance Spot;
- instruments: BTCUSDT, ETHUSDT;
- types: incremental L2 and raw trades;
- period: enough calendar days to yield at least 100 validated whole days;
- desired representation: exchange-native raw messages when affordable, otherwise normalized CSV.

The current public pricing snapshot lists the Academic Spot plan at USD 450 per month with quarterly
or yearly billing, and the billing FAQ says quarterly access includes 12 months of history. This
implies USD 1,350 before tax for a quarterly academic subscription, but checkout or a one-off quote
is authoritative. The site also advertises one-off purchases and a USD 300 minimum order. No cost is
committed in this decision.

## 6. Storage decision

Step 11 does not invent a bytes-per-day estimate. Exact storage must be measured during a 72-hour
pilot because message rates, compression ratios, reconnects, and raw-envelope overhead materially
affect the result. The capacity formula is:

```text
required_capacity =
    measured_p95_compressed_bytes_per_complete_day
    × acquisition_calendar_days
    × 1.25 safety factor
```

Raw and normalized data must remain separate. At least one checksum-verified backup is required.
Procurement is forbidden until the pilot report records actual bytes per day for both instruments.

## 7. Publication and licensing boundary

The public repository will not contain raw Binance messages, Tardis rows, API keys, or a
high-frequency derived dataset. Tardis's published terms grant analysis rights but restrict
redistribution and define a narrow exception for aggregated/calculated data at no finer than
10-minute resolution. Until written clearance is obtained, only code, synthetic fixtures,
configuration, provenance manifests, and non-reconstructive paper figures/tables may be public.

Public API access does not by itself establish redistribution rights. A licence review is required
before any market-data sample or high-frequency derived artifact is released.

## 8. Step 12 entry criteria

Step 12 may start because the venue, instruments, streams, snapshot procedure, and provenance
requirements are now selected. It must not claim a usable dataset until all of the following pass:

1. `exchangeInfo` is captured for both symbols;
2. a 72-hour pilot completes;
3. snapshot/delta reconstruction survives forced reconnects;
4. gaps, duplicates, out-of-order arrivals, and clock fields are measured;
5. raw-file checksums and immutable manifests are generated;
6. storage consumption is measured;
7. no paid vendor access is used without explicit approval.

## 9. Sources reviewed

All sources were accessed on 2026-08-06.

1. Binance Spot WebSocket Streams: https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md
2. Binance Spot REST API: https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md
3. Binance Market Data Only URLs: https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md
4. Binance Public Data archive: https://github.com/binance/binance-public-data/blob/master/README.md
5. Tardis Binance Spot details: https://docs.tardis.dev/historical-data-details/binance
6. Tardis downloadable CSV files: https://docs.tardis.dev/downloadable-csv-files
7. Tardis billing and subscriptions: https://docs.tardis.dev/faq/billing-and-subscriptions
8. Tardis Terms of Service: https://docs.tardis.dev/legal/terms-of-service
9. Bybit public order book: https://bybit-exchange.github.io/docs/v5/websocket/public/orderbook
10. Coinbase Exchange WebSocket channels: https://docs.cdp.coinbase.com/exchange/websocket-feed/channels
