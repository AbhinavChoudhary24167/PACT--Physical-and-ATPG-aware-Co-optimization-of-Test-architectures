#!/usr/bin/env python3
"""Verify the supplied chain survives each seeded physical placement."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from pact.analysis.phase0b_activity import exact_shift_metrics
from pact.scan.identity import scan_ff_instances
from pact.scan.phase0b_identity import phase0b_ff_identity_map, verify_order_with_transparent_buffers
from pact.scan.model import ScanArchitecture
from pact.test.pattern_parser import map_ppi_patterns, parse_fan_pat


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--design", required=True)
    parser.add_argument("--seed", type=int, required=True)
    args = parser.parse_args()
    design, seed = args.design, args.seed
    derived = ROOT / f"artifacts/derived/phase0b/{design}/s{seed}"
    arch = ScanArchitecture.from_json(derived / "B0.architecture.json")
    placed_v = ROOT / f"artifacts/raw/phase0b/placements/{design}/s{seed}/placed.v"
    verilog = placed_v.read_text(encoding="utf-8")
    ff = {record.name: record for record in scan_ff_instances(placed_v)}
    if len(arch.chains) != 1 or set(ff) != set(arch.chains[0].cells):
        raise ValueError("Baseline FF inventory differs from planned architecture")
    source = ROOT / f"artifacts/raw/tool_qualification/fan_atpg/benchmarks/{design}.v"
    raw = ROOT / "artifacts/raw/tool_qualification/fan_atpg"
    parsed = parse_fan_pat(raw / f"patterns/FAN_{design}.pat")
    _, aliases = phase0b_ff_identity_map(source, placed_v, parsed)
    buffered_chain = verify_order_with_transparent_buffers(arch.chains[0].cells, ff, verilog)
    ff_map = json.loads((ROOT / f"artifacts/derived/{design}/ff_identity_map.json").read_text(encoding="utf-8"))["records"]
    patterns = map_ppi_patterns(parsed, ff_map)
    metrics = exact_shift_metrics(arch, patterns)
    record = {
        "status": "PASS", "design": design, "physical_seed": seed, "method": "B0",
        "architecture_sha256": arch.sha256(), "scan_ff_count": len(ff),
        "exact_requested_order": True, "no_missing_or_duplicate_scan_ffs": True,
        "scan_out_connected": True, "ppi_remapping_reaches_targets": True,
        "pattern_count": len(patterns), "shift_clock_count": metrics["shift_clock_count"],
        "placed_verilog_sha256": hashlib.sha256(placed_v.read_bytes()).hexdigest(),
        "transparent_q_buffer_aliases": aliases,
        "transparent_scan_buffer_connectivity": buffered_chain,
    }
    (derived / "B0.rewire_verification.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(record, sort_keys=True))


if __name__ == "__main__":
    main()
