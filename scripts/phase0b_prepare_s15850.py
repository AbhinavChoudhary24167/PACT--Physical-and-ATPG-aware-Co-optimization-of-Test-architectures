#!/usr/bin/env python3
"""Qualify and explicitly translate the predeclared FAN s15850 source."""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from pact.physical.netlist_compat import audit_masters
from pact.physical.translate_netlist import translate_buf_x3_to_x4
from pact.scan.identity import scan_ff_instances
from pact.test.pattern_parser import parse_fan_pat


ROOT = Path(__file__).resolve().parents[1]
ORFS = Path("/root/pact-deps/OpenROAD-flow-scripts/flow/platforms/nangate45")


def main() -> None:
    source = ROOT / "artifacts/raw/tool_qualification/fan_atpg/benchmarks/s15850.v"
    pattern = ROOT / "artifacts/raw/tool_qualification/fan_atpg/patterns/FAN_s15850.pat"
    output = ROOT / "artifacts/derived/phase0b/s15850/s15850_nangate45_compatible.v"
    audit = audit_masters(source, ORFS / "lib/NangateOpenCellLibrary_typical.lib",
                          ORFS / "lef/NangateOpenCellLibrary.macro.mod.lef")
    if audit["missing_liberty"] != {"BUF_X3": 172} or audit["missing_lef"] != {"BUF_X3": 172}:
        raise ValueError("Unexpected s15850 technology incompatibility")
    translation = translate_buf_x3_to_x4(source, output, expected_count=172)
    report = (ROOT / "artifacts/raw/tool_qualification/fan_atpg/reports/FAN_s15850.rpt").read_text(encoding="utf-8")
    if "fault coverage                           94.62%" not in report:
        raise ValueError("Saved s15850 fault coverage changed")
    record = {
        "design": "s15850", "source_url": "https://github.com/NTU-LaDS-II/FAN_ATPG/blob/26b2b36c0e9db11a4b6d9e759df6e44357121f39/mod_netlist/s15850.v",
        "source_rights": "FAN_ATPG repository MIT; original ISCAS89 benchmark rights not independently verified",
        "source_scan_ff_count": len(scan_ff_instances(source)),
        "pattern_count": len(parse_fan_pat(pattern).patterns),
        "fault_model": "stuck_at", "fault_coverage_pct": 94.62,
        "technology": "ORFS Nangate45/FreePDK45",
        "compatibility_audit": audit,
        "translation": asdict(translation),
        "translation_note": "172 BUF_X3 masters replaced by Boolean-equivalent BUF_X4; physical drive strength differs and is held fixed across all Phase-0B orders",
    }
    target = ROOT / "artifacts/manifests/phase0b/s15850_benchmark.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"scan_ff_count": record["source_scan_ff_count"],
                      "pattern_count": record["pattern_count"], "translated": 172}))


if __name__ == "__main__":
    main()
