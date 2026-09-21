#!/usr/bin/env python3
"""Prepare one exact SI-only OpenDB edit from a frozen placed seed."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from pact.scan.identity import scan_ff_instances
from pact.scan.model import ScanArchitecture
from pact.scan.validate import validate_scan


ROOT = Path(__file__).resolve().parents[1]


def prepare(design: str, seed: int, method: str) -> Path:
    derived = ROOT / f"artifacts/derived/phase0b/{design}/s{seed}"
    plan = json.loads((derived / "plan.json").read_text(encoding="utf-8"))
    row = next((row for row in plan["rows"] if row["method"] == method), None)
    if row is None or row["canonical_method"] != method:
        raise ValueError("Method is missing or deduplicated; route its canonical method")
    arch = ScanArchitecture.from_json(ROOT / row["architecture_path"])
    validate_scan(arch)
    if len(arch.chains) != 1:
        raise ValueError("Rewire supports exactly one scan chain")
    placed_v = ROOT / f"artifacts/raw/phase0b/placements/{design}/s{seed}/placed.v"
    source = placed_v.read_text(encoding="utf-8")
    ff = {record.name: record for record in scan_ff_instances(placed_v)}
    if set(ff) != {cell.name for cell in arch.cells}:
        raise ValueError("Placed FF inventory differs from architecture")
    baseline = ScanArchitecture.from_json(derived / "B0.architecture.json")
    root_net = ff[baseline.chains[0].cells[0]].si_net
    terminal_q = ff[baseline.chains[0].cells[-1]].q_net
    matches = []
    for match in re.finditer(r"\bBUF_X1\s+([A-Za-z_][\w$]*)\s*\((.*?)\)\s*;", source, re.DOTALL):
        pins = dict(re.findall(r"\.([A-Za-z_][\w$]*)\s*\(\s*([^()\s]+)\s*\)", match.group(2)))
        if pins.get("Z") == "test_so" and pins.get("A") == terminal_q:
            matches.append(match.group(1))
    if len(matches) != 1:
        raise ValueError("Unique baseline scan-out buffer not found")
    lines = [f"set scan_root_net {{{root_net}}}", f"set scan_out_buffer {{{matches[0]}}}",
             "set scan_out_buffer_pin {A}",
             "set scan_order {" + " ".join(arch.chains[0].cells) + "}",
             "set q_by_ff {" + " ".join(f"{name} {ff[name].q_net}" for name in arch.chains[0].cells) + "}"]
    path = derived / f"{method}.rewire.tcl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (derived / f"{method}.rewire_endpoints.json").write_text(json.dumps({
        "scan_root_net": root_net, "scan_out_buffer": matches[0],
        "scan_out_buffer_pin": "A", "baseline_terminal_q": terminal_q,
        "new_terminal_q": ff[arch.chains[0].cells[-1]].q_net,
        "ff_count": len(ff), "architecture_sha256": arch.sha256(),
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--design", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--method", required=True)
    args = parser.parse_args()
    print(prepare(args.design, args.seed, args.method))


if __name__ == "__main__":
    main()
