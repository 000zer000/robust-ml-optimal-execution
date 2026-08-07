# Step 11 source-comparison matrix

Scores are decision aids, not empirical measurements. Five is strongest for this project's needs.
All time-sensitive claims were checked against provider or venue documentation on 2026-08-06.

| Criterion | Binance Spot | Bybit Spot | Coinbase Exchange |
|---|---:|---:|---:|
| Public live L2 access | 5 | 5 | 5 |
| Explicit snapshot/delta reconstruction | 5 | 5 | 4 |
| Gap/sequence semantics | 5 (`U`,`u`) | 5 (`u`,`seq`) | 3 for L2; stronger on full/L3 |
| Event timestamps | 5; microsecond option | 4; ms system and engine clocks | 4; engine timestamp |
| Same-feed trade stream | 5 | 5 | 5 |
| Historical L2 availability through Tardis | 5; high caps since 2019-03-30 | 4; since 2021-12-04 | 5; since 2019-03-30 |
| Scientific simplicity for this project | 5 | 4 | 4 |
| Visibility caveat | 3; aggregate L2 and 5000-level snapshot cap | 2; RPI orders excluded | 3; aggregate L2 |
| Licensing/public-release simplicity | 3 | 3 | 2; explicit Coinbase restrictions |
| Overall fit | **Selected** | Fallback | Fallback |

## Binance Spot

Strengths:

- public market-data-only REST and WebSocket endpoints;
- documented 100 ms diff-depth feed;
- explicit update ranges and restart rule;
- raw trade events;
- microsecond timestamp request option;
- long third-party historical coverage for both selected instruments;
- spot instrument semantics avoid derivative-specific confounders.

Weaknesses:

- aggregate data cannot reveal individual orders or queue position;
- the REST snapshot is capped at 5000 levels per side;
- connections expire after 24 hours;
- complete historical L2 requires self-capture or a vendor;
- redistribution rights are not inferred from public accessibility.

## Bybit Spot

Strengths:

- snapshot/delta feed;
- depths up to 1000;
- update ID, cross sequence, system timestamp, and matching-engine timestamp;
- detailed documented push frequencies.

Reason not selected:

The standard order-book feed explicitly excludes Retail Price Improvement orders. That does not make
the feed unusable, but it adds a venue-specific visibility caveat. Its Tardis history also starts
later than the selected Binance high-cap history.

## Coinbase Exchange

Strengths:

- Level-2 delivery guarantee;
- full snapshot followed by replacement-size updates;
- matching-engine timestamps;
- full/L3 channels expose sequences and order IDs when required.

Reason not selected:

The straightforward L2 channel has less explicit reconstruction/gap procedure than Binance's
`U`/`u` contract. Coinbase market data also carries explicit additional licensing restrictions in
the reviewed vendor terms. L3 would create a different research-data mode and is unnecessary for
the frozen aggregate historical design.

## Fallback order

1. Bybit Spot BTCUSDT/ETHUSDT, after documenting RPI exclusion.
2. Coinbase Exchange BTC-USD/ETH-USD, after licence approval.
3. Reopen venue selection only if Binance access, terms, or data quality fail the 72-hour pilot.
