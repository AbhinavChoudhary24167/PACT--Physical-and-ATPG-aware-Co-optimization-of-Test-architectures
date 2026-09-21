#!/usr/bin/env python3
"""Record any physical scan-edge aliases that prevent direct B0 verification."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from pact.scan.identity import scan_ff_instances
from pact.scan.model import ScanArchitecture


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--design", required=True)
    parser.add_argument("--seed", type=int, required=True)
    args = parser.parse_args()
    folder = ROOT / f"artifacts/derived/phase0b/{args.design}/s{args.seed}"
    arch = ScanArchitecture.from_json(folder / "B0.architecture.json")
    path = ROOT / f"artifacts/raw/phase0b/placements/{args.design}/s{args.seed}/placed.v"
    text = path.read_text(encoding="utf-8")
    ff = {rec.name: rec for rec in scan_ff_instances(path)}
    order = arch.chains[0].cells
    buffers = []
    for match in re.finditer(r"\bBUF_X1\s+([A-Za-z_][\w$]*)\s*\((.*?)\)\s*;", text, re.DOTALL):
        pins = dict(re.findall(r"\.([A-Za-z_][\w$]*)\s*\(\s*([^()\s]+)\s*\)", match.group(2)))
        buffers.append({"instance": match.group(1), "A": pins.get("A"), "Z": pins.get("Z")})
    mismatches = []
    for i in range(len(order) - 1):
        left, right = ff[order[i]], ff[order[i + 1]]
        if left.q_net != right.si_net:
            mismatches.append({"edge_index": i, "from": left.name, "to": right.name,
                               "q_net": left.q_net, "si_net": right.si_net,
                               "matching_buffer": [b for b in buffers if b["A"] == left.q_net and b["Z"] == right.si_net]})
    result = {"design": args.design, "seed": args.seed, "first_ff_si": ff[order[0]].si_net,
              "last_ff_q": ff[order[-1]].q_net, "direct_edge_mismatch_count": len(mismatches),
              "first_mismatches": mismatches[:20]}
    target = folder / "B0.scan_edge_diagnosis.json"
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
