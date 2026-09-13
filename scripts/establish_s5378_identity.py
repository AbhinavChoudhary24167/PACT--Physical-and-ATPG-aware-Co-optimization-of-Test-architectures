#!/usr/bin/env python3
"""Verify a one-to-one FAN PPI to ORFS placed scan FF map."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from pact.physical.extract_placement import extract_def_scan_cells
from pact.scan.identity import ff_identity_map, scan_ff_instances, supplied_scan_order
from pact.scan.model import ScanArchitecture, ScanChain
from pact.scan.validate import validate_scan
from pact.test.pattern_parser import parse_fan_pat


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    raw = root / "artifacts/raw/tool_qualification/fan_atpg"
    source = raw / "benchmarks/s5378.v"
    patterns_path = raw / "patterns/FAN_s5378.pat"
    placed = root / "artifacts/raw/orfs_smoke/s5378/placed.v"
    placed_def = root / "artifacts/raw/orfs_smoke/s5378/placed.def"
    patterns = parse_fan_pat(patterns_path)
    records = ff_identity_map(source, placed, patterns)
    source_ff = {r.name: r for r in scan_ff_instances(source)}
    placed_ff = {r.name: r for r in scan_ff_instances(placed)}
    si_mismatches = sorted(name for name in source_ff if source_ff[name].si_net != placed_ff[name].si_net)
    names = {record["physical_instance"] for record in records}
    cells = extract_def_scan_cells(placed_def, names, "CK")
    # DEF instance master must match the exact qualified SDFF type.
    def_text = placed_def.read_text(encoding="utf-8")
    def_scan_names = set(re.findall(r"(?m)^\s*-\s+(\S+)\s+SDFF_X1\s+\+", def_text))
    if def_scan_names != names:
        raise ValueError("DEF SDFF_X1 master or FF set mismatch")
    order = supplied_scan_order(source)
    architecture = ScanArchitecture(cells, (ScanChain("chain0", order, "test_si", "test_so"),))
    validate_scan(architecture)
    out = root / "artifacts/derived/s5378"
    out.mkdir(parents=True, exist_ok=True)
    (out / "ff_identity_map.json").write_text(json.dumps({
        "schema_version": "0.1",
        "status": "PASS",
        "design": "s5378",
        "records": records,
        "inputs": {
            "source_netlist": str(source.relative_to(root)),
            "patterns": str(patterns_path.relative_to(root)),
            "placed_netlist": str(placed.relative_to(root)),
            "placed_def": str(placed_def.relative_to(root)),
        },
        "evidence": {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in (source, patterns_path, placed, placed_def)},
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    architecture.to_json(out / "supplied_architecture.json")
    (out / "identity_check.json").write_text(json.dumps({
        "status": "PASS", "ff_count": len(records), "chain_count": 1,
        "ppi_order_matches_ff_set": True, "placed_q_nets_match_source": True,
        "def_ff_master": "SDFF_X1", "supplied_order_reconstructed": True,
        "placed_si_mismatch_count": len(si_mismatches),
        "placed_si_mismatches": si_mismatches,
        "architecture_sha256": architecture.sha256(),
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
