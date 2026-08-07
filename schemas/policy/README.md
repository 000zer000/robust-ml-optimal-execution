# Policy-contract schemas

These JSON Schema Draft 2020-12 files are the versioned interchange contract for Step 8. The C++ types in `robust_execution/policy` remain the executable source of truth; the schemas define how parent orders, policy environments, raw policy actions and causal observations cross process or language boundaries.

The schemas intentionally do not encode venue-specific queue, fee or feed semantics. Those remain referenced by immutable configuration identifiers and are resolved in later steps.

Schema version `1.0` is additive only within the major version. A breaking field or semantic change requires a new major schema and migration notes.
