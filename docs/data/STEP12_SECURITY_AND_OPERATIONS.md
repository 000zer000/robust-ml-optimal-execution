# Step 12 security and operational boundary

- Only public market-data endpoints are permitted.
- No Binance account, API key, secret, cookie, or trading permission is required.
- Raw capture directories must not be committed or published.
- The repository sample is generated through a synthetic transport and is safe to commit.
- Capture hosts and paths come from validated configuration, not arbitrary user input.
- Existing run IDs and artifacts are never overwritten.
- Rate-limit responses, DNS failures, close reasons, and reconnects are evidence, not events to hide.
- The collector does not submit orders or call private APIs.
- Tardis remains unpurchased and is not used by Step 12.
