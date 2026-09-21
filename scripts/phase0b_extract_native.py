#!/usr/bin/env python3
"""Qualify the actual OpenROAD DFT chain on an explicitly pre-scanned design."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from pact.scan.identity import scan_ff_instances
from pact.scan.model import ScanArchitecture, ScanChain
from pact.scan.validate import validate_scan


ROOT = Path(__file__).resolve().parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract(design: str, seed: int) -> dict[str, object]:
    raw = ROOT / f"artifacts/raw/phase0b/dft_annotated/{design}/s{seed}"
    report_path = raw / "stdout.log"
    execution_path = raw / "execution.json"
    if not report_path.is_file():
        run_dir = ROOT / f"artifacts/raw/phase0b/runs/{design}/s{seed}/native_dft"
        report_path = run_dir / "stdout.log"
        execution_path = run_dir / "execution.json"
    report = report_path.read_text(encoding="utf-8")
    count = re.search(r"Number of chains:\s*(\d+)", report)
    chain = re.search(r"Scan chain 'chain_0' has (\d+) cells \(\d+ bits\)\s*\n(.*?)(?:\n\s*\n|\Z)",
                      report, re.DOTALL)
    if not count or int(count.group(1)) != 1 or not chain:
        raise ValueError("OpenROAD did not report exactly one scan chain")
    report_order = tuple(re.findall(r"(?m)^\s{2}(\S+)(?: \([^\n]*\))?\s*$", chain.group(2)))
    if len(report_order) != int(chain.group(1)):
        raise ValueError("Verbose DFT report count disagrees with order")
    native_v = raw / "native.v"
    ff = {record.name: record for record in scan_ff_instances(native_v)}
    net = "scan_in_0"
    observed = []
    while True:
        matches = [record for record in ff.values() if record.si_net == net]
        if not matches:
            break
        if len(matches) != 1 or matches[0].name in observed:
            raise ValueError("OpenROAD native chain branches or loops")
        observed.append(matches[0].name)
        net = matches[0].q_net
    if tuple(observed) != report_order or set(observed) != set(ff):
        raise ValueError("execute_dft_plan netlist disagrees with report_dft_plan")
    if not re.search(rf"\bassign\s+scan_out_0\s*=\s*{re.escape(net)}\s*;", native_v.read_text(encoding="utf-8")):
        raise ValueError("OpenROAD native scan-out disconnected")
    base = ScanArchitecture.from_json(ROOT / f"artifacts/derived/phase0b/{design}/s{seed}/B0.architecture.json")
    if set(observed) != {cell.name for cell in base.cells}:
        raise ValueError("Native DFT changed scan FF inventory")
    native = ScanArchitecture(base.cells, (ScanChain("chain0", report_order, "scan_in_0", "scan_out_0"),))
    validate_scan(native)
    # For paired route comparisons we use the observed native *order* with the
    # common FAN scan ports and scan-enable network. This port normalization is
    # recorded explicitly; the original native netlist remains archived.
    paired = ScanArchitecture(base.cells, (ScanChain("chain0", report_order, "test_si", "test_so"),))
    validate_scan(paired)
    derived = ROOT / f"artifacts/derived/phase0b/{design}/s{seed}"
    native.to_json(derived / "B1.openroad_native.architecture.json")
    paired.to_json(derived / "B1.architecture.json")
    record = {
        "status": "PASS", "design": design, "physical_seed": seed,
        "openroad_report_cell_count": len(report_order), "netlist_scan_ff_count": len(ff),
        "report_matches_stitched_netlist": True,
        "original_native_architecture_sha256": native.sha256(),
        "paired_port_normalized_architecture_sha256": paired.sha256(),
        "paired_implementation": "Exact execute_dft_plan FF order rewired onto unchanged FAN test_si/test_so port infrastructure",
        "prescan_verilog_sha256": sha(raw / "prescan.v"),
        "native_verilog_sha256": sha(native_v),
        "dft_annotated_liberty_sha256": sha(ROOT / "artifacts/derived/phase0b/lib/NangateOpenCellLibrary_typical_dft.lib"),
        "evidence": [str(path.relative_to(ROOT)).replace("\\", "/")
                     for path in (execution_path, report_path, raw / "prescan.v", raw / "native.v", raw / "native.def")],
    }
    (derived / "B1.native_qualification.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--design", required=True)
    parser.add_argument("--seed", type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(extract(args.design, args.seed), sort_keys=True))


if __name__ == "__main__":
    main()
