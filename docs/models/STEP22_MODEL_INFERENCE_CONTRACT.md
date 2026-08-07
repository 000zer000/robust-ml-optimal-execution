# Step 22 — Model inference contract

A Step 22 probability model accepts exactly the ordered 20-feature vector frozen in Step 21 and returns one finite probability in `[0,1]` for the model card's quote-depletion horizon.

Requirements:

- input feature order must equal the Step 21 feature dictionary exactly;
- raw integer/fixed-point features are converted to `float64` only at the model boundary;
- logistic and MLP scaling uses training-only scaler statistics stored inside the trusted model artifact;
- the base-rate and tree models do not use a learned scaler;
- calibration is a post-model transform fitted only on the calibration segment;
- prediction artifacts retain both uncalibrated and calibrated probabilities;
- any missing, non-finite, reordered or additional feature must be rejected by the caller before inference;
- batch-one inference is the execution-controller interface; batched throughput is a separate later performance question;
- model loading is version-sensitive and limited to trusted locally generated pickle artifacts with pinned NumPy/scikit-learn versions.

Step 24 must inject measured inference latency into the same event-time path used by the non-ML MPC rather than treating prediction as instantaneous.
