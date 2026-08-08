# Step 11 change log — Market-data source selection

**Date:** 2026-08-06  
**Repository version:** 0.8.0  
**Specification change:** None

## Added

- Official-source market-data comparison for Binance Spot, Bybit Spot, and Coinbase Exchange.
- Primary venue decision: Binance Spot.
- Primary instruments: BTCUSDT and ETHUSDT.
- Official Binance snapshot/delta and trade-feed contract for Step 12.
- Conditional Tardis historical-backfill path, explicitly gated on Othmane's approval before purchase.
- Data licensing and publication policy.
- Acquisition alternatives and primary-source audit trail.
- JSON Schema, canonical decision artifact, validator, negative controls, and Python tests.
- Step 11 checks in the Makefile, local validation script, repository contract, and hosted CI.

## Changed

- Repository version advanced from 0.7.0 to 0.8.0.

## Not changed

- Central research question.
- Research scope, hypotheses, protocol, or definition of done.
- Any of the seven frozen specification files.
- The unapproved Step 5 schema amendment.

## Not performed

- No paid data purchase.
- No Tardis subscription or one-off order.
- No raw or normalized market-data redistribution.
- No claim that a 100-day usable dataset exists.
- No claim that the selected live endpoints are reachable from the eventual capture host; Step 12 must verify this.
