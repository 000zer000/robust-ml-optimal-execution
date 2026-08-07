# Step 21 — Leakage and Mutation Tests

Step 21 uses mutation tests as executable evidence for the timestamp contract.

## Future-target mutation

A BTCUSDT ask-depth event at 6.05 s occurs strictly after the 6.0 s decision row's 5.9 s source cutoff. Replacing the future quote-depletion event with a non-depleting update must:

- leave the complete 6.0 s ask feature row byte-equivalent;
- change the 250 ms quote-depletion target from positive to negative.

This proves the label future is not read by feature construction for the same decision checkpoint.

## Post-horizon mutation

A trade after every checkpoint's complete 5-second label horizon is mutated by orders of magnitude. No feature or label row may change.

This checks that target construction cannot accidentally use arbitrary data after the declared horizon.

## Causal-past mutation

A trade inside the 250 ms causal feature window is changed. The corresponding side-normalized trade-flow feature must change, while the other instrument remains identical.

This establishes that the future-invariance tests are not passing simply because the builder ignores event data.

## Structural failure tests

The suite also rejects:

- insufficient five-second feature history;
- incomplete future label coverage;
- snapshot/reconnect boundaries inside a label horizon;
- duplicate event sequences;
- per-symbol event-order inversions;
- availability-order inversions;
- crossed or empty books;
- unknown decision symbols;
- missing coverage metadata;
- duplicate decision rows;
- malformed snapshot/depth/trade payloads;
- feature, input, schema or manifest tampering.

## Interpretation

Passing mutation tests proves the implemented fixture obeys the declared information contract. It does not prove that an arbitrary future model is leakage-free. Step 22 and Step 23 must retain chronological splits, training-only preprocessing and final-test isolation.
