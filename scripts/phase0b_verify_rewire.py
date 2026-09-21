#!/usr/bin/env python3
"""Verify one Phase-0B scan-only edit and exact ATPG target reconstruction."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from pact.analysis.phase0b_activity import exact_shift_metrics
from pact.scan.identity import scan_ff_instances
from pact.scan.phase0b_identity import phase0b_ff_identity_map
from pact.scan.model import ScanArchitecture
from pact.test.pattern_parser import map_ppi_patterns, parse_fan_pat
from verify_rewire_s5378 import def_placements, normalize_scan_connectivity


ROOT = Path(__file__).resolve().parents[1]


def verify(design: str, seed: int, method: str) -> dict[str, object]:
    derived = ROOT / f"artifacts/derived/phase0b/{design}/s{seed}"
    endpoints = json.loads((derived / f"{method}.rewire_endpoints.json").read_text(encoding="utf-8"))
    arch = ScanArchitecture.from_json(derived / f"{method}.architecture.json")
    before_dir = ROOT / f"artifacts/raw/phase0b/placements/{design}/s{seed}"
    after_dir = ROOT / f"artifacts/raw/phase0b/rewire/{design}/s{seed}/{method}"
    before = (before_dir / "placed.v").read_text(encoding="utf-8")
    after = (after_dir / "rewired.v").read_text(encoding="utf-8")
    normalized_before = normalize_scan_connectivity(before, endpoints["scan_out_buffer"])
    normalized_after = normalize_scan_connectivity(after, endpoints["scan_out_buffer"])
    if normalized_before != normalized_after:
        raise ValueError("Functional netlist changed outside SI and scan-out")
    before_placement = def_placements(before_dir / "placed.def")
    after_placement = def_placements(after_dir / "rewired.def")
    if before_placement != after_placement:
        raise ValueError("Paired component inventory or placement changed")
    ff = {record.name: record for record in scan_ff_instances(after_dir / "rewired.v")}
    net = endpoints["scan_root_net"]
    observed = []
    while True:
        matches = [record for record in ff.values() if record.si_net == net]
        if not matches:
            break
        if len(matches) != 1 or matches[0].name in observed:
            raise ValueError("Scan chain branches, duplicates, or loops")
        observed.append(matches[0].name)
        net = matches[0].q_net
    if set(observed) != set(ff) or tuple(observed) != arch.chains[0].cells or net != endpoints["new_terminal_q"]:
        raise ValueError("Requested scan order is not realized")
    buffer_pattern = rf"\bBUF_X1\s+{re.escape(endpoints['scan_out_buffer'])}\s*\((.*?)\)\s*;"
    buffer = re.search(buffer_pattern, after, re.DOTALL)
    if not buffer:
        raise ValueError("Scan-out buffer missing")
    input_net = re.search(r"\.A\s*\(\s*([^()\s]+)\s*\)", buffer.group(1))
    if not input_net or input_net.group(1) != net:
        raise ValueError("Scan-out buffer not driven by final Q")
    source = ROOT / f"artifacts/raw/tool_qualification/fan_atpg/benchmarks/{design}.v"
    parsed = parse_fan_pat(ROOT / f"artifacts/raw/tool_qualification/fan_atpg/patterns/FAN_{design}.pat")
    _, aliases = phase0b_ff_identity_map(source, after_dir / "rewired.v", parsed)
    ff_map = json.loads((ROOT / f"artifacts/derived/{design}/ff_identity_map.json").read_text(encoding="utf-8"))["records"]
    patterns = map_ppi_patterns(parsed, ff_map)
    activity = exact_shift_metrics(arch, patterns)
    record = {
        "status": "PASS", "design": design, "physical_seed": seed, "method": method,
        "architecture_sha256": arch.sha256(),
        "placed_component_count": len(before_placement), "scan_ff_count": len(ff),
        "pattern_count": len(patterns), "shift_clock_count": activity["shift_clock_count"],
        "functional_structure_excluding_scan_sha256": hashlib.sha256(normalized_before.encode()).hexdigest(),
        "placement_unchanged": True, "exact_requested_order": True,
        "scan_out_connected": True, "ppi_remapping_reaches_targets": True,
        "no_missing_or_duplicate_scan_ffs": True,
        "transparent_q_buffer_aliases": aliases,
    }
    (derived / f"{method}.rewire_verification.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--design", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--method", required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.design, args.seed, args.method), sort_keys=True))


if __name__ == "__main__":
    main()
