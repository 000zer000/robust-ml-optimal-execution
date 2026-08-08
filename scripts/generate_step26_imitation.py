from __future__ import annotations

import argparse
from pathlib import Path

from native_executable import native_executable
from robust_execution.imitation.learning import generate_step26_artifacts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--oracle",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/imitation/step26_imitation_engineering.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/sample/imitation/step26-imitation-validation"),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    oracle = args.oracle or native_executable(root, "robust_execution_imitation_oracle")
    report = generate_step26_artifacts(root, oracle, args.config, args.output)
    print(report["payload_sha256"])


if __name__ == "__main__":
    main()
