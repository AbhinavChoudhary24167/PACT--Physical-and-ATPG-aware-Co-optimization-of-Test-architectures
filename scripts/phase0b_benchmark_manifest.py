#!/usr/bin/env python3
"""Derive benchmark provenance and ATPG quality from frozen FAN evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from pact.scan.identity import scan_ff_instances
from pact.test.pattern_parser import parse_fan_pat


ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = "https://github.com/NTU-LaDS-II/FAN_ATPG"
COMMIT = (ROOT / "artifacts/raw/tool_qualification/fan_atpg/commit").read_text(encoding="utf-8").strip()


def evidence(path: Path) -> dict:
    return {"path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def capture(pattern: str, text: str, label: str) -> str:
    match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
    if not match:
        raise ValueError(f"Missing {label} in FAN report")
    return match.group(1)


def main() -> None:
    designs = []
    substitutions = {"s5378": 34, "s9234": 96, "s15850": 172}
    for design in ("s5378", "s9234", "s15850"):
        source = ROOT / f"artifacts/raw/tool_qualification/fan_atpg/benchmarks/{design}.v"
        pat = ROOT / f"artifacts/raw/tool_qualification/fan_atpg/patterns/FAN_{design}.pat"
        report = ROOT / f"artifacts/raw/tool_qualification/fan_atpg/reports/FAN_{design}.rpt"
        atpg_log = ROOT / f"artifacts/raw/tool_qualification/fan_atpg/{design}.atpg.log"
        text = report.read_text(encoding="utf-8")
        atpg_text = atpg_log.read_text(encoding="utf-8")
        required_options = ("set_fault_type saf", "set_static_compression on",
                            "set_dynamic_compression on", "set_X-Fill on")
        if any(option not in atpg_text for option in required_options):
            raise ValueError(f"ATPG configuration changed: {design}")
        patterns = parse_fan_pat(pat)
        reported_patterns = int(capture(r"^#\s*#Patterns\s+(\d+)\s*$", text, "pattern count"))
        if len(patterns.patterns) != reported_patterns:
            raise ValueError(f"Pattern count mismatch: {design}")
        source_text = source.read_text(encoding="utf-8")
        observed_buf_x3 = len(re.findall(r"\bBUF_X3\s+\w+\s*\(", source_text))
        if observed_buf_x3 != substitutions[design]:
            raise ValueError(f"Translation count mismatch: {design}: {observed_buf_x3}")
        designs.append({
            "design": design,
            "source_url": f"{UPSTREAM}/blob/{COMMIT}/mod_netlist/{design}.v",
            "upstream_repository": UPSTREAM, "upstream_commit": COMMIT,
            "license_provenance": "FAN_ATPG repository MIT; original ISCAS89 netlist redistribution rights not independently established",
            "scan_ff_count": len(scan_ff_instances(source)),
            "pattern_count": len(patterns.patterns),
            "stuck_at_coverage_percent": float(capture(r"^#\s*fault coverage\s+([\d.]+)%", text, "coverage")),
            "fault_model": capture(r"^#\s*Fault model\s+(\w+)\s*$", text, "fault model"),
            "pattern_type": capture(r"^#\s*Pattern type\s+(\w+)\s*$", text, "pattern type"),
            "atpg_configuration": {"static_compression": "on", "dynamic_compression": "on",
                                   "x_fill": "on", "frame_count": 1},
            "technology": "Nangate45 / FreePDK45 ORFS flow",
            "compatibility_translations": [{"from_cell": "BUF_X3", "to_cell": "BUF_X4",
                                            "instance_count": observed_buf_x3,
                                            "reason": "BUF_X3 absent from ORFS Nangate45 Liberty"}],
            "evidence": [evidence(path) for path in (source, pat, report, atpg_log)],
        })
    record = {
        "schema_version": "phase0b-benchmarks-1", "designs": designs,
        "additional_benchmark_audit": {
            "pact_sanity": {"source": "benchmarks/pact_sanity/pact_sanity.v",
                            "status": "NOT_COMPATIBLE", "reason": "No verified FAN full-scan abstraction or PPI patterns"},
            "additional_FAN_ISCAS89": {"source": f"{UPSTREAM}/tree/{COMMIT}/mod_netlist",
                                        "status": "NOT_ADMITTED",
                                        "reason": "Original ISCAS89 netlist redistribution rights not independently established; no additional source has completed the ATPG-to-placed-FF identity qualification"},
        },
    }
    target = ROOT / "artifacts/manifests/phase0b/benchmark_manifest.json"
    target.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
