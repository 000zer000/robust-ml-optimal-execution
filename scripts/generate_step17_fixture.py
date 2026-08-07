#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--executable", type=Path, required=True)
    arguments = parser.parse_args()
    target = arguments.output_root / "step17-metrics-validation"
    if target.exists():
        raise SystemExit(f"refusing to overwrite immutable metrics fixture: {target}")
    target.mkdir(parents=True)

    completed = subprocess.run(
        [str(arguments.executable)],
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(completed.stdout)
    report_path = target / "report.json"
    report_path.write_text(
        json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    detailed = report["detailed_episode"]
    write_csv(
        target / "episode-metrics.csv",
        [
            "episode_id",
            "side",
            "parent_quantity_lots",
            "filled_quantity_lots",
            "completion_rate",
            "implementation_shortfall_quote_atoms",
            "implementation_shortfall_bps",
            "terminal_quantity_lots",
            "terminal_completion_cost_quote_atoms",
            "passive_fraction",
            "aggressive_fraction",
            "explicit_fees_quote_atoms",
            "net_cash_flow_quote_atoms",
        ],
        [
            {
                "episode_id": detailed["episode_id"],
                "side": detailed["side"],
                "parent_quantity_lots": detailed["parent_quantity_lots"],
                "filled_quantity_lots": detailed["filled_quantity_lots"],
                "completion_rate": format(detailed["completion_rate"], ".17g"),
                "implementation_shortfall_quote_atoms": detailed[
                    "implementation_shortfall_quote_atoms"
                ],
                "implementation_shortfall_bps": format(
                    detailed["implementation_shortfall_bps"], ".17g"
                ),
                "terminal_quantity_lots": detailed["terminal_quantity_lots"],
                "terminal_completion_cost_quote_atoms": detailed[
                    "terminal_completion_cost_quote_atoms"
                ],
                "passive_fraction": format(detailed["passive_fraction"], ".17g"),
                "aggressive_fraction": format(detailed["aggressive_fraction"], ".17g"),
                "explicit_fees_quote_atoms": detailed["explicit_fees_quote_atoms"],
                "net_cash_flow_quote_atoms": detailed["net_cash_flow_quote_atoms"],
            }
        ],
    )
    write_csv(
        target / "inventory-trajectory.csv",
        ["episode_id", "timestamp_ns", "remaining_lots"],
        [
            {
                "episode_id": detailed["episode_id"],
                "timestamp_ns": row["timestamp_ns"],
                "remaining_lots": row["remaining_lots"],
            }
            for row in detailed["inventory_trajectory"]
        ],
    )
    write_csv(
        target / "tail-risk.csv",
        ["episode_id", "implementation_shortfall_bps", "terminal_fraction"],
        [
            {
                "episode_id": row["episode_id"],
                "implementation_shortfall_bps": format(
                    row["implementation_shortfall_bps"], ".17g"
                ),
                "terminal_fraction": format(row["terminal_fraction"], ".17g"),
            }
            for row in report["tail_episodes"]
        ],
    )

    artifact_paths = [
        "report.json",
        "episode-metrics.csv",
        "inventory-trajectory.csv",
        "tail-risk.csv",
    ]
    manifest = {
        "schema_version": "metrics-evidence-manifest-v1",
        "step": 17,
        "report_id": "step17-metrics-validation",
        "software_version": "0.14.0",
        "research_status": "synthetic_validation_only_non_research",
        "report_sha256": sha256(report_path),
        "artifacts": [
            {
                "path": relative,
                "sha256": sha256(target / relative),
                "bytes": (target / relative).stat().st_size,
            }
            for relative in artifact_paths
        ],
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
