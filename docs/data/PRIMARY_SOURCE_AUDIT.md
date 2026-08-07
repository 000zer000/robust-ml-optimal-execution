# Step 11 primary-source audit

**Access date:** 2026-08-06

| Claim | Primary source evidence | Decision consequence |
|---|---|---|
| Binance diff depth publishes `U` and `u` and documents restart on gaps | Binance WebSocket Streams | Supports explicit continuity validation |
| Binance supports 100 ms depth and real-time raw trades | Binance WebSocket Streams | Required capture streams |
| Market-data-only REST/WS requires no API key | Binance Market Data Only URLs | No trading credential needed |
| WebSocket lifetime is 24 hours and timestamps can be microseconds | Binance WebSocket Streams | Controlled rotation and microsecond request |
| REST snapshot supports up to 5000 levels per side | Binance REST API | Snapshot depth cap documented |
| Binance official archive documents trades/aggTrades/klines, not full Spot L2 | Binance Public Data README | Archive is cross-check, not primary L2 history |
| Tardis Binance high-cap history begins 2019-03-30 | Tardis Binance Spot details | Long backfill available |
| Tardis L2 CSV has exchange/local timestamps, snapshot flag, replacement amount, capture order | Tardis downloadable CSV files | Useful normalized replay and latency proxy |
| Free Tardis access covers first day of each month | Tardis downloadable CSV files | Parser-only sample path |
| Academic/Solo provide CSV only; quarterly gives 12 months | Tardis billing FAQ | Raw replay and cost require plan check |
| Tardis terms restrict redistribution | Tardis Terms of Service | No raw/vendor rows in public repository |
| Bybit standard book excludes RPI orders | Bybit order-book docs | Visibility caveat lowers rank |
| Coinbase L2 guarantees delivery; full/L3 carries sequences/order IDs | Coinbase WebSocket channels | Viable fallback but different semantics/licensing |

## Source URLs

- https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md
- https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md
- https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md
- https://github.com/binance/binance-public-data/blob/master/README.md
- https://docs.tardis.dev/historical-data-details/binance
- https://docs.tardis.dev/downloadable-csv-files
- https://docs.tardis.dev/faq/billing-and-subscriptions
- https://docs.tardis.dev/legal/terms-of-service
- https://bybit-exchange.github.io/docs/v5/websocket/public/orderbook
- https://docs.cdp.coinbase.com/exchange/websocket-feed/channels
