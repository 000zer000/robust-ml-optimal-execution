# Step 12 — Raw Binance Spot capture

**Implementation status:** complete and locally validated  
**Live 72-hour pilot:** pending because the current execution container cannot resolve the selected
Binance market-data hosts  
**Research specification changed:** no

## 1. Purpose

Step 12 preserves the official Binance Spot public feed before any normalization, feature
construction, replay, or repair. It captures BTCUSDT and ETHUSDT diff-depth updates at 100 ms and
raw trades, together with the exact `exchangeInfo` response and depth snapshots used to establish
local-book continuity.

This stage does not create research episodes and does not admit a day as valid. Step 13 performs
formal data-quality validation and quarantine.

## 2. Production endpoints

- REST: `https://data-api.binance.vision`
- WebSocket: `wss://data-stream.binance.vision`
- streams: `<symbol>@depth@100ms` and `<symbol>@trade`
- requested timestamp unit: `MICROSECOND`
- snapshot: `/api/v3/depth`, limit 5000
- metadata: `/api/v3/exchangeInfo`

No API key, account credential, or trading endpoint is used.

## 3. Raw record contract

Every WebSocket message is stored before semantic processing in a gzip JSONL segment. Each record
contains:

- run and connection identifiers;
- zero-based connection message index;
- collector UTC receive time in nanoseconds;
- collector monotonic receive time in nanoseconds;
- combined-stream name;
- parsed symbol and event type when available;
- the exact UTF-8 payload string returned by the WebSocket library;
- SHA-256 of those UTF-8 bytes.

Verification re-encodes `raw_payload_utf8` and checks the embedded digest. Parser failures therefore
do not erase or rewrite the source message.

## 4. Immutable storage

```text
<output-root>/<run-id>/
├── manifest.json
├── manifest.sha256.json
├── metadata/
│   ├── exchange-info.json.gz
│   └── symbol-contract.json.gz
├── snapshots/
│   ├── BTCUSDT/<connection>-<lastUpdateId>.json.gz
│   └── ETHUSDT/<connection>-<lastUpdateId>.json.gz
└── raw/
    └── YYYY-MM-DD/
        ├── segment-000000.jsonl.gz
        └── ...
```

Files are created through `.partial` paths, flushed, `fsync`ed, and atomically renamed. Existing
final or partial paths cause failure rather than overwrite. The manifest is written last and is also
create-only.

Gzip is the executable Step 12 format because it is available in the Python standard library. The
format decision is not a market-model or research-scope change. Segment sizes, message limits, and periodic `fsync` intervals are configuration fields. Segments also rotate at UTC-day boundaries.

## 5. Snapshot and sequence diagnostics

For each symbol, the collector:

1. connects and starts buffering diff-depth messages;
2. requests a 5000-level snapshot;
3. discards buffered events whose final ID is not newer than the snapshot;
4. requires the first retained event to overlap the snapshot update ID;
5. applies replacement quantities and removes zero-quantity levels;
6. ignores old events and counts exact duplicates separately;
7. invalidates the local book if `U > local_update_id + 1`;
8. requests a new snapshot after a detected gap;
9. rejects crossed or locked reconstructed books;
10. records synchronized update-ID intervals in the final manifest.

The local aggregate book is only a capture diagnostic. It is not an exact FIFO reconstruction and
is not yet a historical replay engine.

## 6. Connections and rotation

The production config rotates at 82,800 seconds, before the documented 24-hour lifetime. Each
connection records start/end times, endpoint, selected remote address when available, outcome,
message count, close code, and close reason. A transport failure causes a bounded retry and a fresh
snapshot cycle. Ping/pong-related close text is classified separately in the error log.

The connection timestamps expose the handoff interval. The collector never labels that interval as
valid market data merely because reconnection succeeded.

## 7. Metadata extraction

The complete `exchangeInfo` response is preserved. A separate derived symbol contract extracts
selected fields only from that response, including status, assets, precision, order types,
self-trade-prevention modes, and all active filters. Nothing is hard-coded into the raw artifacts.
A selected symbol that is absent, non-`TRADING`, or missing filters aborts the run.

## 8. Manifest claim controls

The manifest distinguishes:

- `live_binance`;
- `synthetic_transport_fixture`.

A synthetic fixture is forbidden from satisfying the 72-hour pilot. A live manifest can set
`pilot_72h_complete=true` only when its status is `complete` and its measured runtime is at least
259,200 seconds. Independent verification checks this rule, all artifact hashes, segment counts,
and embedded raw-payload hashes.

Raw market data is marked non-public, credentials are marked absent, and redistribution is marked
uncleared.

## 9. Current evidence

The deterministic fixture covers two connections, a forced reconnect, both selected instruments,
snapshot installation, sequence application, two segment rotations, six exact payload records, and
immutable manifest verification. It is synthetic test data and contains no real Binance observations.

A real live smoke attempt was made on 2026-08-06. Both selected hosts failed DNS resolution in the
execution container. The resulting live manifest is correctly marked `aborted`, contains zero
messages, and does not claim pilot completion.
