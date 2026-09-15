#!/usr/bin/env python3
"""Recompute a saved proxy row without writing it across Python runtimes."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from pact.analysis.phase0c_activity import direct_sink_weights, parallel_activity_metrics
from pact.scan.identity import scan_ff_instances
from pact.scan.model import ScanArchitecture
from pact.test.pattern_parser import map_ppi_patterns, parse_fan_pat


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--design", default="s5378")
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--k", type=int, default=2)
    parser.add_argument("--method", default="B0")
    args = parser.parse_args()
    folder = ROOT / f"artifacts/derived/phase0c/{args.design}/s{args.seed}/k{args.k}"
    row = json.loads((folder / f"{args.method}.proxy.json").read_text())
    arch = ScanArchitecture.from_json(folder / f"{args.method}.architecture.json")
    placed = ROOT / f"artifacts/raw/phase0b/placements/{args.design}/s{args.seed}/placed.v"
    ff = {item.name: item.q_net for item in scan_ff_instances(placed)}
    weights = direct_sink_weights(placed, ff)
    patterns = map_ppi_patterns(
        parse_fan_pat(ROOT / f"artifacts/raw/tool_qualification/fan_atpg/patterns/FAN_{args.design}.pat"),
        json.loads((ROOT / f"artifacts/derived/{args.design}/ff_identity_map.json").read_text())["records"])
    current = parallel_activity_metrics(arch, patterns, weights)
    saved = row["activity"]
    keys = ("parallel_shift_clock_count", "total_shift_toggles", "peak_simultaneous_toggles",
            "p95_simultaneous_toggles", "p99_simultaneous_toggles", "weighted_total", "weighted_peak")
    for key in keys:
        if not math.isclose(current[key], saved[key], abs_tol=1e-9, rel_tol=1e-12):
            raise AssertionError(f"Runtime disagreement: {key}")
    for grid in ("8", "16", "32"):
        for key in ("H_density", "H_eff", "peak_bin_toggle"):
            if not math.isclose(current["grids"][grid][key], saved["grids"][grid][key], abs_tol=1e-9, rel_tol=1e-12):
                raise AssertionError(f"Runtime disagreement: {grid}/{key}")
    print(json.dumps({"status": "PASS", "design": args.design, "K": args.k,
                      "method": args.method, "total_toggles": current["total_shift_toggles"],
                      "H_eff8": current["grids"]["8"]["H_eff"]}))


if __name__ == "__main__":
    main()
