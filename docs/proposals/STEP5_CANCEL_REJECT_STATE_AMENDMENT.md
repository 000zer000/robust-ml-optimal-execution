# Proposed Step 5 Amendment — Terminal State in Cancel/Replace Rejections

**Status:** Proposed only — not applied  
**Discovered:** Step 6 matching-engine integration  
**Requires:** Othmane's explicit approval before modifying the Step 5 event schema or validation

## Problem

The Step 5 model defines `RejectReason::AlreadyTerminal`, but validation currently rejects any terminal value in:

- `CancelRejected.resulting_state`;
- `ReplaceRejected.resulting_state`.

A truthful synthetic exchange response to a cancel-after-fill or replace-after-cancel request should be able to report that the referenced order is already `Filled`, `Cancelled`, `Expired`, or `Replaced`. Forcing a non-terminal state would create false audit data.

## Proposed correction

Allow a terminal `resulting_state` **only** when the rejection reason is `AlreadyTerminal`. Keep the existing prohibition for other reasons unless a future venue contract proves another case.

The conditional validation would be conceptually:

```text
if reason == AlreadyTerminal:
    resulting_state must be terminal
else:
    resulting_state must be non-terminal unless a documented venue rule says otherwise
```

The JSON schema, C++ validator, Python validator, fixtures, tests, and schema-evolution record would be updated together under one approved amendment.

## Current Step 6 handling

No prior schema was changed. `MatchingEngine` returns an engine-local `EngineFailure` with `current_state`, allowing cancellations and replacements to report the truth internally. Step 7 must not publish an invalid `CancelRejected` or `ReplaceRejected` event from that result unless this amendment is approved or another explicitly approved event representation is chosen.
