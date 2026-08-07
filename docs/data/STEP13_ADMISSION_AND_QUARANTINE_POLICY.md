# Step 13 admission and quarantine policy

## Binding primary-study rules

A UTC day is admitted only when all of the following are true:

- the source Step 12 manifest and all referenced artifacts verify;
- `data_origin` is `live_binance`;
- the capture status is `complete`;
- the live 72-hour pilot is marked complete with supporting duration;
- both BTCUSDT and ETHUSDT are present;
- both depth and trade streams are represented for each symbol;
- receive timestamps cover the complete UTC day within the configured boundary tolerance;
- each connection has contiguous zero-based message indices;
- receive UTC and monotonic timestamps do not reverse within a connection;
- every stored payload hash and wrapper field matches;
- trade values are finite and strictly positive;
- every connection/symbol has exactly one unambiguous depth snapshot;
- snapshot and buffered deltas overlap correctly;
- depth update IDs remain continuous after synchronization;
- reconstructed books never become crossed or locked;
- no critical issue affects the day.

## Quarantine scope

Step 13 currently makes conservative day-level decisions. A critical issue causes the affected UTC day to be quarantined. Issue records retain the narrowest available pointers: artifact, connection, symbol, message index, receive timestamp, and day.

Later work may define safe episode-level exclusion inside an otherwise valid day, but it may not retroactively weaken the day-level raw admission gate without an explicit protocol amendment.

## Prohibited actions

- changing raw files in place;
- replacing a missing update with a synthetic event;
- interpolating prices or quantities;
- treating a reconnect as continuous without a new snapshot;
- admitting a synthetic fixture;
- admitting data before the live pilot completes;
- deleting evidence of failed validation;
- changing the frozen research question or scope through data-validation code.
