from __future__ import annotations

import argparse
from pathlib import Path

from robust_execution.imitation.learning import generate_step26_artifacts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--oracle",
        type=Path,
        default=Path("build/gcc-debug/robust_execution_imitation_oracle"),
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
    report = generate_step26_artifacts(args.root, args.oracle, args.config, args.output)
    print(report["payload_sha256"])


if __name__ == "__main__":
    main()
