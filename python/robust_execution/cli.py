"""Command-line entry point for repository bootstrap and validation tasks."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from robust_execution import __version__
from robust_execution.canonical_data.builder import CanonicalDataError, build_canonical_dataset
from robust_execution.canonical_data.config import (
    CanonicalDataConfigurationError,
    load_canonical_data_config,
)
from robust_execution.canonical_data.verify import (
    CanonicalDataVerificationError,
    verify_canonical_dataset,
)
from robust_execution.config import ConfigurationError, load_config
from robust_execution.data_capture.collector import (
    BinanceRawCollector,
    CaptureError,
    resolve_hostnames,
)
from robust_execution.data_capture.config import CaptureConfigurationError, load_capture_config
from robust_execution.data_capture.verify import CaptureVerificationError, verify_capture_manifest
from robust_execution.data_validation.config import (
    DataValidationConfigurationError,
    load_data_validation_config,
)
from robust_execution.data_validation.validator import DataValidationError, validate_capture_data
from robust_execution.data_validation.verify import (
    DataValidationVerificationError,
    verify_data_validation_report,
)
from robust_execution.event_model import EventModelError, verify_audit_log
from robust_execution.event_sample import write_event_model_sample
from robust_execution.historical_replay import (
    HistoricalReplayConfigurationError,
    HistoricalReplayError,
    HistoricalReplayVerificationError,
    build_historical_replay,
    load_historical_replay_config,
    verify_historical_replay,
)
from robust_execution.logging import configure_logging
from robust_execution.sample import write_bootstrap_artifact
from robust_execution.specification import verify_specification_lock


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="robust-execution")
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate-config", help="Validate a TOML config")
    validate.add_argument("config", type=Path)

    sample = subparsers.add_parser("bootstrap-sample", help="Write deterministic sample artifact")
    sample.add_argument("config", type=Path)
    sample.add_argument("--output", type=Path)

    verify = subparsers.add_parser("verify-spec", help="Verify frozen specification hashes")
    verify.add_argument("--root", type=Path, default=_repository_root())

    audit = subparsers.add_parser("verify-audit", help="Verify a Step 5 hash-chained audit log")
    audit.add_argument("path", type=Path)

    event_sample = subparsers.add_parser(
        "event-model-sample", help="Generate deterministic Step 5 event-model fixtures"
    )
    event_sample.add_argument("--output-dir", type=Path, default=Path("data/sample/event_model"))

    capture = subparsers.add_parser("capture-binance", help="Run Binance Spot raw capture")
    capture.add_argument("config", type=Path)
    capture.add_argument("--duration-seconds", type=float)
    capture.add_argument("--max-messages", type=int)
    capture.add_argument("--run-id")

    network = subparsers.add_parser(
        "capture-network-check", help="Resolve configured Binance market-data hosts"
    )
    network.add_argument("config", type=Path)

    verify_capture = subparsers.add_parser(
        "verify-capture", help="Verify a Step 12 capture manifest and artifacts"
    )
    verify_capture.add_argument("manifest", type=Path)

    validate_data = subparsers.add_parser(
        "validate-raw-data", help="Validate and quarantine a Step 12 capture"
    )
    validate_data.add_argument("manifest", type=Path)
    validate_data.add_argument("config", type=Path)
    validate_data.add_argument("--output-root", type=Path, default=Path("results/data_validation"))
    validate_data.add_argument("--validation-id")

    verify_data = subparsers.add_parser(
        "verify-data-validation", help="Verify Step 13 report and quarantine hashes"
    )
    verify_data.add_argument("report", type=Path)

    canonical = subparsers.add_parser(
        "build-canonical-data", help="Build a Step 14 canonical dataset"
    )
    canonical.add_argument("capture_manifest", type=Path)
    canonical.add_argument("validation_report", type=Path)
    canonical.add_argument("config", type=Path)
    canonical.add_argument("--output-root", type=Path, default=Path("data/sample/canonical"))
    canonical.add_argument("--dataset-id")

    verify_canonical = subparsers.add_parser(
        "verify-canonical-data", help="Verify a Step 14 canonical dataset"
    )
    verify_canonical.add_argument("manifest", type=Path)

    replay = subparsers.add_parser(
        "build-historical-replay", help="Build a Step 15 aggregate-L2 replay"
    )
    replay.add_argument("canonical_manifest", type=Path)
    replay.add_argument("config", type=Path)
    replay.add_argument("--output-root", type=Path, default=Path("data/sample/historical_replay"))
    replay.add_argument("--replay-id")

    verify_replay = subparsers.add_parser(
        "verify-historical-replay", help="Verify a Step 15 replay manifest"
    )
    verify_replay.add_argument("manifest", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "verify-spec":
            failures = verify_specification_lock(args.root)
            if failures:
                print(json.dumps({"status": "failed", "failures": failures}, indent=2))
                return 1
            print(json.dumps({"status": "ok", "checked": "frozen specification"}))
            return 0

        if args.command == "verify-audit":
            verification = verify_audit_log(args.path)
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "records": verification.records,
                        "run_id": verification.run_id,
                        "final_sha256": verification.final_sha256,
                    },
                    sort_keys=True,
                )
            )
            return 0

        if args.command == "event-model-sample":
            manifest = write_event_model_sample(args.output_dir)
            print(json.dumps({"status": "ok", "manifest": str(manifest)}, sort_keys=True))
            return 0

        if args.command == "verify-capture":
            result = verify_capture_manifest(args.manifest)
            print(json.dumps(result, sort_keys=True))
            return 0

        if args.command == "validate-raw-data":
            validation_config = load_data_validation_config(args.config)
            report = validate_capture_data(
                args.manifest,
                validation_config,
                args.output_root,
                validation_id=args.validation_id,
            )
            print(json.dumps({"status": "ok", "report": str(report)}, sort_keys=True))
            return 0

        if args.command == "verify-data-validation":
            result = verify_data_validation_report(args.report)
            print(json.dumps(result, sort_keys=True))
            return 0

        if args.command == "build-canonical-data":
            canonical_config = load_canonical_data_config(args.config)
            manifest = build_canonical_dataset(
                args.capture_manifest,
                args.validation_report,
                canonical_config,
                args.output_root,
                dataset_id=args.dataset_id,
            )
            print(json.dumps({"status": "ok", "manifest": str(manifest)}, sort_keys=True))
            return 0

        if args.command == "verify-canonical-data":
            result = verify_canonical_dataset(args.manifest)
            print(json.dumps(result, sort_keys=True))
            return 0

        if args.command == "build-historical-replay":
            replay_config = load_historical_replay_config(args.config)
            replay_manifest = build_historical_replay(
                args.canonical_manifest,
                replay_config,
                args.output_root,
                replay_id=args.replay_id,
            )
            print(json.dumps({"status": "ok", "manifest": str(replay_manifest)}, sort_keys=True))
            return 0

        if args.command == "verify-historical-replay":
            result = verify_historical_replay(args.manifest)
            print(json.dumps(result, sort_keys=True))
            return 0

        if args.command == "capture-network-check":
            capture_config = load_capture_config(args.config)
            result = resolve_hostnames(capture_config)
            print(json.dumps(result, sort_keys=True))
            return 0 if all(item["status"] == "resolved" for item in result.values()) else 4

        if args.command == "capture-binance":
            capture_config = load_capture_config(args.config)
            collector = BinanceRawCollector(capture_config)
            manifest = asyncio.run(
                collector.run(
                    duration_seconds=args.duration_seconds,
                    max_messages=args.max_messages,
                    run_id=args.run_id,
                )
            )
            print(json.dumps({"status": "ok", "manifest": str(manifest)}, sort_keys=True))
            return 0

        config = load_config(args.config)
        configure_logging(config.logging.level, json_output=config.logging.json)
        logger = logging.getLogger("robust_execution.cli")

        if args.command == "validate-config":
            logger.info(
                "configuration valid",
                extra={"event": "config_validated", "fields": {"path": str(args.config)}},
            )
            print(json.dumps({"status": "ok", "config": str(args.config)}))
            return 0

        if args.command == "bootstrap-sample":
            target = write_bootstrap_artifact(config, args.config, args.output)
            logger.info(
                "bootstrap artifact written",
                extra={"event": "artifact_written", "fields": {"path": str(target)}},
            )
            print(json.dumps({"status": "ok", "artifact": str(target)}))
            return 0
    except (CaptureError, CaptureConfigurationError, CaptureVerificationError) as exc:
        print(f"capture error: {exc}", file=sys.stderr)
        return 4
    except (
        DataValidationError,
        DataValidationConfigurationError,
        DataValidationVerificationError,
    ) as exc:
        print(f"data-validation error: {exc}", file=sys.stderr)
        return 5
    except (
        CanonicalDataError,
        CanonicalDataConfigurationError,
        CanonicalDataVerificationError,
    ) as exc:
        print(f"canonical-data error: {exc}", file=sys.stderr)
        return 6
    except (
        HistoricalReplayError,
        HistoricalReplayConfigurationError,
        HistoricalReplayVerificationError,
    ) as exc:
        print(f"historical-replay error: {exc}", file=sys.stderr)
        return 7
    except EventModelError as exc:
        print(f"event-model error: {exc}", file=sys.stderr)
        return 3
    except ConfigurationError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
