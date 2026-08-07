# Market-data licensing and release policy

## Default rule

Market-data access and market-data redistribution are different rights. Public endpoints do not
automatically make captured records redistributable. Until a written licence review says otherwise,
the repository must not contain raw or normalized third-party market data.

## Never commit

- raw Binance WebSocket or REST payload archives;
- Tardis CSV rows or raw replay messages;
- API keys, invoices, customer identifiers, or signed URLs;
- reconstructed tick-level books;
- timestamp-aligned high-frequency derived datasets that substitute for the source data.

## Publicly releasable by default

- source code;
- schemas and validators;
- synthetic fixtures;
- empty/sample manifests containing no market observations;
- configuration templates;
- aggregate research tables and figures that cannot reconstruct source records, subject to the
  applicable provider terms;
- documentation of data acquisition and quality controls.

## Tardis-specific boundary

The reviewed Terms of Service grant a non-transferable licence for permitted use and allow creation
of Derived Data, but prohibit redistribution/resale of the source data and state an exception for
aggregated/calculated data whose lowest resolution is 10 minutes. Therefore:

- no Tardis row-level data enters Git;
- no public high-frequency feature dataset is released;
- paper figures/tables are reviewed for non-reconstructability;
- written confirmation is obtained before releasing any market-derived sample finer than 10 minutes.

Coinbase data has additional explicit restrictions in the same terms, which is one reason Coinbase
was not selected.

## Reproducibility without redistribution

The public release will provide:

1. capture and ingestion code;
2. exact source identifiers and date-range manifest hashes;
3. acquisition instructions;
4. synthetic and licence-cleared small tests;
5. deterministic transforms;
6. generated table/figure code;
7. a verifier that users can run after obtaining data lawfully.

The reproducibility claim is “reproducible by an authorised data holder,” not “all raw data is
redistributed with the repository.”
