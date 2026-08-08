# Step 5 event-model schemas

These files are JSON Schema Draft 2020-12 interchange contracts. They are
venue-neutral and versioned independently from any raw feed schema.

- `event-envelope-v1.schema.json`: normalized market, policy, order, fill, fee, and
  timer events.
- `audit-record-v1.schema.json`: append-indexed SHA-256 chain around one event.
- `instrument-definition-v1.schema.json`: exact rational unit metadata.
- `episode-metadata-v1.schema.json`: research-protocol metadata for one execution
  episode.

Cross-field invariants are enforced in C++ and Python, because JSON Schema alone does
not express all ordering, conservation, lifecycle, and hash-chain rules.
