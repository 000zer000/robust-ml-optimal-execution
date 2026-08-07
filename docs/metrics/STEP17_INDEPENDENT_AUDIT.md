# Step 17 — Independent metric audit

## Purpose

A strategy result is not accepted merely because the primary calculator produced a number. Each episode must pass an independent reconstruction audit before it can enter an aggregate result.

## C++ audit

The C++ audit is implemented in a separate translation unit and reconstructs from the raw ledger:

- unique execution identifiers;
- cumulative and residual quantity;
- exact notional;
- signed gross cash;
- fees and rebates;
- net cash;
- arrival-price implementation shortfall;
- terminal quantity and terminal cost;
- maker, taker, and unknown quantities;
- inventory state bounds;
- throughput and action ratios.

The audit uses a separate notional-reconstruction path and compares exact integer outputs. Floating-point ratios use a scale-aware tolerance only after the exact numerators and denominators agree.

## Python audit

The committed fixture is independently reconstructed again in Python from the embedded ledger. The Python verifier recalculates:

- all exact accounting values;
- implementation shortfall and basis points;
- inventory path;
- adverse-selection costs and coverage;
- activity ratios;
- throughput;
- aggregate mean, sample variance, median, VaR, and CVaR.

It also verifies artifact hashes, CSV/JSON agreement, schema identity, research-status boundaries, and deterministic regeneration.

## Aggregate admission

`TailRiskSummary` requires one passing audit for every episode. It throws if:

- the audit count differs from the episode count;
- any audit failed;
- an episode is incomplete;
- implementation shortfall is undefined.

This is a structural control against omitting residual inventory, selecting only successful episodes, or aggregating corrupted accounting.

## Tamper campaign

The Python tests deliberately modify:

- manifest identity and hashes;
- research-status claims;
- gate flags;
- fills, prices, quantities, times, fees and roles;
- inventory and markouts;
- exact accounting totals;
- tail rows and aggregate statistics;
- CSV content and row counts.

Every modified artifact must be rejected, including correctly rehashed but semantically inconsistent evidence.

## Boundary

The independent audits validate calculation consistency. They do not establish that a historical queue assumption, market-impact model, benchmark choice, or strategy is economically correct. Those are separate modelling and experimental questions.
