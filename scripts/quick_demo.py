#!/usr/bin/env python3
"""Build the existing C++ core and produce an offline, explicitly synthetic demo."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import platform
import resource
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=ROOT / "build/quick-tour")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output/quick-demo")
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args()
    build, output = args.build_dir.resolve(), args.output_dir.resolve()
    started = time.monotonic()
    if not args.no_build:
        subprocess.run(
            [
                "cmake",
                "-S",
                str(ROOT / "demos/quick"),
                "-B",
                str(build),
                "-DCMAKE_BUILD_TYPE=Release",
                "-DRE_BUILD_TESTING=ON",
                "-DRE_BUILD_PYTHON_BINDINGS=OFF",
                "-DRE_WARNINGS_AS_ERRORS=ON",
            ],
            check=True,
        )
        subprocess.run(
            [
                "cmake",
                "--build",
                str(build),
                "--parallel",
                "4",
                "--target",
                "robust_execution_quick_demo",
                "robust_execution_matching_demo",
            ],
            check=True,
        )
    run_started = time.monotonic()
    matching = subprocess.check_output([str(build / "core/robust_execution_matching_demo")])
    raw = subprocess.check_output([str(build / "robust_execution_quick_demo")])
    data = json.loads(raw)
    assert data["kind"] == "hand_authored_synthetic_teaching_example"
    assert data["historical_gate_c_open"] is False
    assert data["profile_cutoff_ns"] < data["episode_start_ns"]
    for scenario in data["scenarios"]:
        assert len(scenario["policies"]) == 3
        for policy in scenario["policies"]:
            assert policy["complete"] and sum(policy["slice_lots"]) == 100
    demo_seconds = time.monotonic() - run_started
    output.mkdir(parents=True, exist_ok=True)
    (output / "results.json").write_bytes(raw)
    (output / "matching-engine.txt").write_bytes(matching)
    metadata = {
        "scope": "Build and two native demonstration processes, no training or market data",
        "platform": platform.platform(),
        "python": platform.python_version(),
        "wall_seconds": round(time.monotonic() - started, 4),
        "native_demo_seconds": round(demo_seconds, 4),
        "peak_child_rss_mib": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        / (1024**2 if sys.platform == "darwin" else 1024),
        "memory_scope": "Peak child RSS; includes compiler when built, not aggregate RAM",
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)),
        "results_sha256": hashlib.sha256(raw).hexdigest(),
        "matching_state_sha256": hashlib.sha256(matching).hexdigest(),
    }
    (output / "run.json").write_text(json.dumps(metadata, indent=2) + "\n")
    cards = []
    for scenario in data["scenarios"]:
        low, high = min(scenario["ask_ticks"]), max(scenario["ask_ticks"])
        points = " ".join(
            f"{20 + 85 * i},{55 - 40 * (price - low) / max(1, high - low):.2f}"
            for i, price in enumerate(scenario["ask_ticks"])
        )
        labels = "".join(
            f'<text x="{20 + 85 * i}" y="78" text-anchor="middle">{price}</text>'
            for i, price in enumerate(scenario["ask_ticks"])
        )
        plot = (
            '<svg viewBox="0 0 300 85" role="img" aria-label="Hand-authored ask path in ticks" '
            'style="max-width:420px;width:100%;font-size:12px">'
            f'<polyline points="{points}" fill="none" stroke="#237d71" stroke-width="3"/>'
            + labels
            + "</svg>"
        )
        rows = "".join(
            f"<tr><th>{html.escape(p['name'])}</th><td>{p['shortfall_bps']:g}</td>"
            f"<td>{' / '.join(str(q) for q in p['slice_lots'])}</td><td>100 / 100</td></tr>"
            for p in scenario["policies"]
        )
        cards.append(
            f"<section><h2>{html.escape(scenario['scenario'])}</h2>"
            + plot
            + f"<p>Available ask path: {' → '.join(str(x) for x in scenario['ask_ticks'])} ticks.</p>"
            "<table><thead><tr><th>Policy</th><th>Cost (bps)</th>"
            "<th>Slice lots</th><th>Filled lots</th></tr></thead>"
            f"<tbody>{rows}</tbody></table></section>"
        )
    page = (
        """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Execution lab — five-minute tour</title>
<style>body{font:16px system-ui;color:#172f3b;background:#f1f5f7;margin:0}
main{max-width:980px;margin:auto;padding:32px 18px}h1{font-size:clamp(30px,6vw,48px)}
section{background:white;border:1px solid #ccd8df;border-radius:12px;padding:22px;margin:18px 0}
.badge{background:#ddece8;padding:8px 12px;border-radius:6px;display:inline-block}
table{width:100%;border-collapse:collapse;font-size:clamp(12px,2vw,16px)}
td,th{padding:12px 4px;text-align:left;border-bottom:1px solid #dce3e8}p{line-height:1.6}
a{color:#175a75}small{color:#415d6b}pre{overflow:auto;font-size:12px}</style>
<main><span class="badge">Controlled synthetic teaching example</span>
<h1>The best execution schedule depends on the path.</h1>
<p>One 100-lot buy order, three existing C++ scheduling policies, two hand-authored ask paths.
The past-volume profile is fixed before the episode. Future asks are used only to settle fills.
The native accounting engine independently audits every result.</p>
"""
        + "".join(cards)
        + """
<section><h2>Read the result correctly</h2><p>Lower cost is better; zero is the 100-tick
arrival reference. Cost = (paid quote atoms - 100 * 100) / (100 * 100) * 10,000.
For the first past-volume path, 10*101 + 20*100 + 30*99 + 40*100 = 9,980, hence -20 bps.</p>
<p>This teaching settlement assumes sufficient available quantity and immediate fills at
each specified ask, zero fees and zero latency. It omits queue uncertainty and impact.
It is not a full matching-engine strategy replay. The matching-engine demonstration runs
separately and checks price-time priority, replacements, cancellation and invariants.</p>
<p>Historical Gate C remains closed. No historical profitability, learned strategy advantage,
live execution or GPU performance is established by these examples.</p></section>
<section><h2>Inspect the evidence</h2><p><a href="results.json">Native results</a> ·
<a href="matching-engine.txt">Matching-engine state</a> · <a href="run.json">Measured run</a></p>
<p>The larger controlled study, fallback dependence and workload-specific CPU/GPU measurements
remain separate from this short demonstration.</p></section>
<small>No server, model download, payment or network call is required.</small>
</main></html>
"""
    )
    (output / "index.html").write_text(page)
    print(json.dumps(metadata, indent=2))
    print(f"Open {output / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
