#!/usr/bin/env python3
"""Gate scan-only OpenDB edits on exact structural and placement invariants."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from pact.scan.identity import ff_identity_map, scan_ff_instances
from pact.scan.model import ScanArchitecture
from pact.test.pattern_parser import map_ppi_patterns, parse_fan_pat
from pact.test.shift_simulator import simulate_shift


def normalize_scan_connectivity(verilog: str, out_buffer: str) -> str:
    """Hide only FF SI and the verified scan-out buffer input net."""
    def ff_replace(match: re.Match[str]) -> str:
        body, count = re.subn(r"(\.SI\s*\()\s*[^()\s]+\s*(\))", r"\g<1>SCAN_NET\g<2>", match.group(0))
        if count != 1:
            raise ValueError("An SDFF instance lacks one SI pin")
        return body
    normalized = re.sub(r"\bSDFF_X1\s+[A-Za-z_][\w$]*\s*\(.*?\)\s*;", ff_replace, verilog, flags=re.DOTALL)
    pattern = rf"\bBUF_X1\s+{re.escape(out_buffer)}\s*\(.*?\)\s*;"
    def output_replace(match: re.Match[str]) -> str:
        body, count = re.subn(r"(\.A\s*\()\s*[^()\s]+\s*(\))", r"\g<1>SCAN_OUT_NET\g<2>", match.group(0))
        if count != 1:
            raise ValueError("Scan-out buffer input absent")
        return body
    normalized, count = re.subn(pattern, output_replace, normalized, flags=re.DOTALL)
    if count != 1:
        raise ValueError("Unique scan-out buffer absent")
    return normalized


def def_placements(path: Path) -> dict[str, tuple[str, str, str, str]]:
    """Read all placed/fixed instance masters, coordinates, and orientation."""
    text = path.read_text(encoding="utf-8")
    section = re.search(r"\bCOMPONENTS\s+\d+\s*;(.*?)\bEND\s+COMPONENTS", text, re.DOTALL)
    if not section:
        raise ValueError("DEF components missing")
    placements = {}
    for match in re.finditer(r"(?m)^\s*-\s+(\S+)\s+(\S+)(.*?)\s*;", section.group(1), re.DOTALL):
        placement = re.search(r"\+\s+(?:PLACED|FIXED)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+(\S+)", match.group(3))
        if not placement:
            raise ValueError(f"Unplaced component {match.group(1)}")
        placements[match.group(1)] = (match.group(2), *placement.groups())
    return placements


def main() -> None:
    """Verify scan-only edits, fixed placement, and target remapping."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--design", choices=("s5378", "s9234"), default="s5378")
    design = parser.parse_args().design
    root = Path(__file__).resolve().parents[1]
    base_dir = root / f"artifacts/raw/orfs_smoke/{design}"
    rewire_dir = root / f"artifacts/raw/orfs_rewire/{design}/nearest_neighbor"
    derived = root / f"artifacts/derived/phase0/smoke_{design}"
    endpoints = json.loads((derived / "nearest_neighbor.rewire_endpoints.json").read_text(encoding="utf-8"))
    arch = ScanArchitecture.from_json(derived / "nearest_neighbor.architecture.json")
    before = (base_dir / "placed.v").read_text(encoding="utf-8")
    after = (rewire_dir / "rewired.v").read_text(encoding="utf-8")
    normalized_before = normalize_scan_connectivity(before, endpoints["scan_out_buffer"])
    normalized_after = normalize_scan_connectivity(after, endpoints["scan_out_buffer"])
    if normalized_before != normalized_after:
        raise ValueError("Functional netlist changed outside legal scan connectivity")
    before_placement = def_placements(base_dir / "placed.def")
    after_placement = def_placements(rewire_dir / "rewired.def")
    if before_placement != after_placement:
        raise ValueError("Component identities or placement changed")
    ff = {record.name: record for record in scan_ff_instances(rewire_dir / "rewired.v")}
    net = endpoints["scan_root_net"]
    observed = []
    while True:
        matches = [record for record in ff.values() if record.si_net == net]
        if not matches:
            break
        if len(matches) != 1 or matches[0].name in observed:
            raise ValueError("Rewired scan chain branches or loops")
        observed.append(matches[0].name)
        net = matches[0].q_net
    if tuple(observed) != arch.chains[0].cells or net != endpoints["new_terminal_q"]:
        raise ValueError("Physical scan chain does not match requested architecture")
    ff_map = json.loads((root / f"artifacts/derived/{design}/ff_identity_map.json").read_text(encoding="utf-8"))["records"]
    parsed = parse_fan_pat(root / f"artifacts/raw/tool_qualification/fan_atpg/patterns/FAN_{design}.pat")
    patterns = map_ppi_patterns(parsed, ff_map)
    ff_identity_map(root / f"artifacts/raw/tool_qualification/fan_atpg/benchmarks/{design}.v", rewire_dir / "rewired.v", parsed)
    trace = simulate_shift(arch, patterns)
    record = {
        "status": "PASS", "architecture_sha256": arch.sha256(),
        "placed_component_count": len(before_placement), "scan_ff_count": len(ff),
        "pattern_count": len(patterns), "shift_clock_count": len(trace.cycles),
        "functional_structure_excluding_scan_sha256": hashlib.sha256(normalized_before.encode()).hexdigest(),
        "placement_unchanged": True, "scan_order_verified_from_rewired_netlist": True,
        "pattern_remapping_reaches_targets": True,
    }
    (derived / "nearest_neighbor.rewire_verification.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
