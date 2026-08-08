# Step 11 validation — Market-data source selection

**Date:** 2026-08-06  
**Repository version:** 0.8.0  
**Decision:** PASS — Step 12 may begin with a live-capture pilot  
**Research specification changed:** No

## 1. Governance

The central research question, hypotheses, final scope, data requirement, and research protocol were
not changed. `scripts/verify_specification_lock.py` reports seven matching files. The lock was not
regenerated.

The unapproved Step 5 terminal-rejection amendment remains unapplied. No paid data purchase was
made.

## 2. Source decision

| Field | Selected value |
|---|---|
| Primary venue | Binance Spot |
| Instruments | BTCUSDT, ETHUSDT |
| Live semantic authority | Official Binance Spot API documentation and live feed |
| Canonical raw corpus | Self-capture from Binance market-data-only endpoints |
| Historical acceleration | Tardis Binance L2/trades, conditional on explicit purchase approval |
| Official Binance archive | Independent trade cross-check, not full L2 history |
| Historical replay type | Aggregate L2; no exact historical FIFO claim |

The decision is encoded identically in configuration, sample, and validation-result locations and
validates against `market-data-source-decision-v1.schema.json`.

## 3. Feed contract verified from documentation

The binding Step 12 contract records:

- `BTCUSDT` and `ETHUSDT`;
- diff-depth streams at 100 ms and raw trade streams;
- `U`/`u` update-range continuity;
- REST snapshots capped at 5000 levels per side;
- microsecond timestamp request;
- collector UTC and monotonic arrival clocks;
- controlled rotation before the documented 24-hour connection limit;
- immediate invalidation and resynchronisation on a sequence gap;
- capture-time `exchangeInfo` persistence rather than hard-coded symbol filters.

## 4. Acquisition and licence boundary

No subscription or one-off vendor order was placed. Tardis remains a conditional backfill route,
not an approved expenditure. Its free first-day-of-month files may be used for parser development
once network access is available, but they do not satisfy the 100-valid-day requirement.

The public repository must not contain credentials, raw exchange messages, vendor-normalized rows,
or a reconstructive high-frequency derived dataset. Written licence clearance is required before
publishing any market-data sample.

## 5. Test matrix

| Validation | Result |
|---|---|
| Frozen specification | 7/7 PASS |
| Step 11 schema and semantic validator | PASS |
| Negative decision controls | 4/4 rejected as intended |
| Repository contract | 127 required files PASS |
| Python tests | 55/55 PASS |
| Python branch-aware coverage | 93.69% |
| GCC 14 Debug | 36/36 C++ tests PASS |
| Clang 17 Debug | 36/36 PASS |
| GCC 14 Release + IPO | 36/36 PASS |
| GCC ASan + UBSan | 36/36 PASS, no findings |
| GCC/Clang/Release Gate B output | Byte-identical |
| Clean Release installation | PASS |
| External `find_package(robust_execution 0.8)` consumer | PASS |
| JSON, TOML, and Python syntax | PASS |

The canonical Step 11 source-decision file SHA-256 is:

```text
8583582d2b7f6909180c29221c81a0a89cf365db7ad0321aa1075d80c21451a1
```

## 6. Network-execution limitation

The working container could not resolve either `data-api.binance.vision` or
`datasets.tardis.dev`. Consequently, Step 11 did not claim:

- a successful live endpoint connection;
- a downloaded Tardis sample;
- current symbol filters obtained from `exchangeInfo`;
- measured message rates or storage volume.

The exact curl failure evidence is retained in
`results/validation/step11/local_network_access.txt`. These checks are mandatory in Step 12's
72-hour pilot and cannot be replaced by documentation review.

## 7. Tools not executed locally

- Ruff and mypy were not installed and package-registry access was unavailable; hosted CI remains
  configured but is not claimed green.
- Docker and isolated wheel construction were not rerun locally.
- Local TSan retains the previously documented Swift-Clang linker incompatibility and was not
  claimed as passing.

## 8. Scientific boundary

Step 11 selects a defensible source and acquisition design. It does not establish data quality,
historical realism, exact queue position, hidden liquidity, market impact, strategy performance,
or profitability. Those claims remain blocked by Steps 12–16 and subsequent research gates.

## 9. Final decision

**Step 11 passes.** Step 12 may implement the raw Binance collector and run the 72-hour pilot for
both instruments. A Tardis purchase remains blocked until Othmane explicitly approves a current
written quote.
