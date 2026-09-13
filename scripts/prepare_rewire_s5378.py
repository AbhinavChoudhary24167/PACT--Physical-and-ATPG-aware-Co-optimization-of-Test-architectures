#!/usr/bin/env python3
"""Derive OpenDB rewire inputs from verified architecture and placed netlist."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from pact.scan.identity import scan_ff_instances
from pact.scan.model import ScanArchitecture
from pact.scan.validate import validate_scan


def main() -> None:
    """Create a deterministic OpenDB SI-rewire plan for one verified design."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--design", choices=("s5378", "s9234"), default="s5378")
    design = parser.parse_args().design
    root = Path(__file__).resolve().parents[1]
    base_v = root / f"artifacts/raw/orfs_smoke/{design}/placed.v"
    base_arch = ScanArchitecture.from_json(root / f"artifacts/derived/{design}/supplied_architecture.json")
    next_arch = ScanArchitecture.from_json(root / f"artifacts/derived/phase0/smoke_{design}/nearest_neighbor.architecture.json")
    validate_scan(next_arch)
    if {c.name for c in base_arch.cells} != {c.name for c in next_arch.cells}:
        raise ValueError("Scan cell inventory changed")
    if tuple(len(c.cells) for c in base_arch.chains) != tuple(len(c.cells) for c in next_arch.chains):
        raise ValueError("Scan chain lengths changed")
    if len(next_arch.chains) != 1:
        raise ValueError("This bounded rewire supports exactly one chain")
    source = base_v.read_text(encoding="utf-8")
    ff = {record.name: record for record in scan_ff_instances(base_v)}
    if set(ff) != {c.name for c in next_arch.cells}:
        raise ValueError("Placed FFs and architecture differ")
    root_net = ff[base_arch.chains[0].cells[0]].si_net
    terminal_q = ff[base_arch.chains[0].cells[-1]].q_net
    buffer_matches = []
    for match in re.finditer(r"\bBUF_X1\s+([A-Za-z_][\w$]*)\s*\((.*?)\)\s*;", source, re.DOTALL):
        pins = dict(re.findall(r"\.([A-Za-z_][\w$]*)\s*\(\s*([^()\s]+)\s*\)", match.group(2)))
        if pins.get("Z") == "test_so" and pins.get("A") == terminal_q:
            buffer_matches.append(match.group(1))
    if len(buffer_matches) != 1:
        raise ValueError("Cannot identify unique placed scan-out buffer")
    out = root / f"artifacts/derived/phase0/smoke_{design}"
    lines = [f"set scan_root_net {{{root_net}}}", f"set scan_out_buffer {{{buffer_matches[0]}}}", "set scan_out_buffer_pin {A}"]
    lines.append("set scan_order {" + " ".join(next_arch.chains[0].cells) + "}")
    lines.append("set q_by_ff {" + " ".join(f"{name} {ff[name].q_net}" for name in next_arch.chains[0].cells) + "}")
    (out / "nearest_neighbor.rewire.tcl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "nearest_neighbor.rewire_endpoints.json").write_text(json.dumps({
        "scan_root_net": root_net, "scan_out_buffer": buffer_matches[0],
        "scan_out_buffer_pin": "A", "baseline_terminal_q": terminal_q,
        "new_terminal_q": ff[next_arch.chains[0].cells[-1]].q_net,
        "ff_count": len(ff), "architecture_sha256": next_arch.sha256(),
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
