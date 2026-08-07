# Step 26 — Covariate shift, DAgger and fallback contract

1. Fit the initial behavior clone on teacher-labelled training states only.
2. Choose architecture/regularisation on validation only.
3. Roll the learner through validation episodes and query the exact teacher on learner-visited states.
4. Trigger correction if raw agreement is below 98%, completion fails, or standardized mean-state shift exceeds 0.35.
5. If triggered, collect teacher labels only from the dedicated correction pool and perform one DAgger-style retraining round with frozen hyperparameters.
6. Refit normalization only on train plus correction rows; validation remains excluded from fitting.
7. Choose the confidence fallback threshold on validation only, with a 99% accepted-action agreement target where feasible.
8. Compute the feature-distance threshold from the fitted training distribution only.
9. Evaluate raw student and fallback student once on engineering-holdout and OOD episodes.
10. Preserve OOD failure modes. Do not tune the detector, student or teacher against OOD results.

The committed engineering fixture triggers one correction round. DAgger improves validation rollout agreement, but the OOD student remains materially weaker than the teacher. The fallback mitigates the OOD disagreement while retaining a non-zero residual error. That negative result is intentionally preserved and becomes an input to later robustness work rather than a reason to tune on OOD data.
