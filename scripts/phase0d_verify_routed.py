#!/usr/bin/env python3
"""CLI for Phase-0D routed structural verification."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pact.physical.phase0d_routed import verify_routed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--routed", type=Path, required=True)
    parser.add_argument("--architecture", type=Path, required=True)
    parser.add_argument("--frozen-def", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify_routed(args.routed, args.architecture, args.frozen_def)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in (
        "status", "scan_ff_count", "K", "scan_edges", "exclusive_exact_edge_count")}, sort_keys=True))


if __name__ == "__main__":
    main()
