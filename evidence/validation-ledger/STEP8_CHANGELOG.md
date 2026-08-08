# Step 8 change log — Execution-policy interfaces

**Date:** 2026-08-06  
**Repository version:** 0.5.0  
**Scope:** Step 8 only

## Added

- `robust_execution/policy` C++ interface layer:
  - parent-order and policy-environment types;
  - exact cash/notional accounting;
  - shared child-order and parent-order state;
  - immutable causal policy observations and lineage hashes;
  - no-op, submit, cancel and replace action contracts;
  - action validation and exchange-command translation;
  - abstract execution-policy interface;
  - terminal-completion planner;
  - validated dispatch integration with the Step 7 kernel.
- Canonical system delivery for explicit terminal-completion events.
- Four Draft 2020-12 policy interchange schemas.
- Four deterministic policy fixtures with a SHA-256 manifest.
- Deterministic Step 8 executable demonstration and cross-compiler hash evidence.
- Nine Step 8 C++ test executables, including negative and end-to-end terminal tests.
- Python policy-schema validation test.
- Step 8 documentation, validation commands and CI checks.

## Corrected during implementation

1. The original bootstrap version assertion still expected `0.4.0`; it now checks `0.5.0`.
2. Rejected crossed-book updates initially mutated `ObservationBuilder` before throwing. Ingestion is now transactional and restores the prior book/trade state on failure.
3. Environment compatibility initially compared only strategy, venue and instrument IDs. It now compares the complete instrument definition and every policy constraint/configuration field, including fee and latency IDs.
4. The repository `clean` target deleted committed deterministic fixtures under `results/sample`; it now preserves source-controlled evidence.
5. Terminal-attempt accounting is recorded only after successful dispatch, not merely when a plan is proposed.
6. Explicit terminal completion is delivered through the scheduler as a canonical system event rather than mutating accounting out of band.

## Deliberately unchanged

- The exact central research question and all seven frozen research-contract files.
- The unapproved Step 5 terminal cancel/replace rejection-schema amendment.
- Venue/feed rules, market generation, impact, fee calculation, queue assumptions and execution strategies.
- Step 9 and later functionality.
