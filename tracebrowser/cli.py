from __future__ import annotations

import argparse
import json
from pathlib import Path

from .benchmark import run_benchmark


def main() -> None:
    parser = argparse.ArgumentParser(prog="tracebrowser")
    sub = parser.add_subparsers(dest="command", required=True)
    benchmark = sub.add_parser("benchmark", help="run the deterministic 50-task benchmark")
    benchmark.add_argument("--output", default="reports/tracebrowser-benchmark.json")
    args = parser.parse_args()
    if args.command == "benchmark":
        result = run_benchmark()
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
