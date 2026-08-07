# Step 12 live-pilot runbook

The 72-hour pilot must run in a networked environment that can maintain a process continuously and
has sufficient local storage. Do not run it in a notebook session that may suspend.

## 1. Install

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements/capture.lock
python -m pip install -e .
```

`requirements/capture.lock` pins `websockets==16.0`. REST requests use the Python standard library.

## 2. Preflight

```bash
robust-execution verify-spec
robust-execution capture-network-check configs/data/binance_capture_pilot.json
python scripts/validate_step12_capture.py
```

Check that the output filesystem has ample free space. Do not guess the 100-day storage need before
measuring pilot bytes per complete day.

## 3. Launch the mandatory pilot

The default configuration already requires 259,200 seconds:

```bash
robust-execution capture-binance \
  configs/data/binance_capture_pilot.json \
  --run-id "pilot-$(date -u +%Y%m%dT%H%M%SZ)"
```

Do not pass `--max-messages` for the real pilot. That option exists for smoke and deterministic tests.
Use an operating-system service manager or another persistent foreground-process supervisor. Keep
stdout/stderr outside the raw-data directory.

## 4. Verify after completion

```bash
robust-execution verify-capture \
  data/raw/binance_spot/<run-id>/manifest.json
```

Then inspect:

- `pilot_72h_complete` is true;
- actual duration is at least 259,200 seconds;
- both symbols have synchronized intervals;
- no unreviewed gaps or crossed-book diagnostics;
- all reconnects and rotations are visible;
- every segment and snapshot checksum verifies;
- no `.partial` files remain.

## 5. Storage measurement

For each UTC day and instrument, Step 13 will calculate:

- raw payload bytes;
- envelope JSONL bytes;
- compressed bytes;
- message count;
- depth/trade split;
- snapshot and metadata overhead;
- compression ratio;
- peak hourly rate.

The 100-valid-day acquisition budget must use measured upper quantiles plus safety margin, not the
small synthetic fixture.

## 6. Failure handling

- DNS or initial REST failure: run is `aborted`; fix connectivity and start a new run ID.
- WebSocket disconnect: collector reconnects within the configured bound and resnapshots.
- update-ID gap: local book is invalidated and resynchronized; the affected interval remains visible.
- stale snapshot: connection cycle is restarted and snapshot is fetched again.
- disk or immutable-write failure: stop; do not edit or append manually.
- process termination: retain partial evidence for diagnosis, but do not admit the run as complete.

Never modify a completed run in place. Corrections produce a new derived artifact or a new capture
run, preserving the original bytes.
