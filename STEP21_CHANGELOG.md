# Step 21 Changelog — Causal Targets and Features

## Added

- strict Step 21 prediction-data configuration;
- normalized market-event and decision-point contracts;
- physically separated feature and label tables;
- frozen 20-feature causal dictionary;
- 250 ms, 1 s and 5 s quote-depletion/trade-through labels;
- 250 ms, 1 s and 5 s side-signed adverse-selection labels;
- complete-history and complete-label-coverage gates;
- reconnect-boundary rejection for target windows;
- deterministic synthetic two-instrument validation tape;
- future, post-horizon and past mutation tests;
- immutable input, feature, label, dictionary and manifest hashes;
- two JSON Schema contracts;
- Step 21 generator and independent verifier;
- Python failure-path and tamper tests.

## Not changed

- the central research question;
- candidate target horizons;
- the primary-horizon selection rule;
- chronological split protocol;
- Step 20 non-ML MPC comparator;
- historical queue-position claim boundary;
- Gate C status.

## Research status

Synthetic validation only. No model has been trained and no horizon has been selected.
