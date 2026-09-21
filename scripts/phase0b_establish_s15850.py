#!/usr/bin/env python3
"""Establish s15850 FAN PPI to placed SDFF identity without touching Phase 0."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from pact.physical.extract_placement import extract_def_scan_cells
from pact.scan.identity import scan_ff_instances, supplied_scan_order
from pact.scan.phase0b_identity import phase0b_ff_identity_map
from pact.scan.model import ScanArchitecture, ScanChain
from pact.scan.validate import validate_scan
from pact.test.pattern_parser import parse_fan_pat


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    design = "s15850"
    source = ROOT / f"artifacts/raw/tool_qualification/fan_atpg/benchmarks/{design}.v"
    pattern_path = ROOT / f"artifacts/raw/tool_qualification/fan_atpg/patterns/FAN_{design}.pat"
    placed_v = ROOT / f"artifacts/raw/phase0b/source_place/{design}/placed.v"
    placed_def = ROOT / f"artifacts/raw/phase0b/source_place/{design}/placed.def"
    patterns = parse_fan_pat(pattern_path)
    records, q_aliases = phase0b_ff_identity_map(source, placed_v, patterns)
    names = {record["physical_instance"] for record in records}
    if names != {ff.name for ff in scan_ff_instances(placed_v)}:
        raise ValueError("Placed FF set differs from FAN PPI identity")
    cells = extract_def_scan_cells(placed_def, names, "CK")
    def_names = set(re.findall(r"(?m)^\s*-\s+(\S+)\s+SDFF_X1\s+\+", placed_def.read_text(encoding="utf-8")))
    if def_names != names:
        raise ValueError("DEF scan-cell master/inventory mismatch")
    architecture = ScanArchitecture(cells, (ScanChain("chain0", supplied_scan_order(source), "test_si", "test_so"),))
    validate_scan(architecture)
    out = ROOT / "artifacts/derived/s15850"
    out.mkdir(parents=True, exist_ok=True)
    architecture.to_json(out / "supplied_architecture.json")
    (out / "ff_identity_map.json").write_text(json.dumps({
        "schema_version": "0.1", "status": "PASS", "design": design,
        "records": records,
        "transparent_q_buffer_aliases": q_aliases,
        "evidence": {str(path.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in (source, pattern_path, placed_v, placed_def)},
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"design": design, "scan_ff_count": len(records),
                      "architecture_sha256": architecture.sha256()}))


if __name__ == "__main__":
    main()
