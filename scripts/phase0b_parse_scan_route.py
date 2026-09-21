#!/usr/bin/env python3
"""Parse machine-readable OpenDB scan-edge extraction into qualified metrics."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from pact.physical.phase0b_routed_scan import summarize_routed_scan_edges
from pact.scan.model import ScanArchitecture


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--design", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--method", required=True)
    args = parser.parse_args()
    arch = ScanArchitecture.from_json(ROOT / f"artifacts/derived/phase0b/{args.design}/s{args.seed}/{args.method}.architecture.json")
    cells = {cell.name: cell for cell in arch.cells}
    ordered = arch.chains[0].cells
    geometry = [abs(cells[a].x_um - cells[b].x_um) + abs(cells[a].y_um - cells[b].y_um)
                for a, b in zip(ordered, ordered[1:])]
    raw = ROOT / f"artifacts/raw/phase0b/physical/{args.design}/s{args.seed}/{args.method}/scan_edges.tsv"
    with raw.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    if [(r["source_ff"], r["dest_ff"]) for r in rows] != list(zip(ordered, ordered[1:])):
        raise ValueError("OpenDB routed edge list differs from requested architecture")
    edges = [{**row, "connected": row["connected"] == "1",
              "via_transparent_buffer": row.get("via_transparent_buffer", "0") == "1",
              "buffered_full_net_upper_dbu": int(row.get("buffered_full_net_upper_dbu", "-1")),
              "routed_nonvia_dbu": int(row["routed_nonvia_dbu"]),
              "iterm_count": int(row["iterm_count"]),
              "bterm_count": int(row["bterm_count"]),
              "dbu_per_um": int(row["dbu_per_um"])} for row in rows]
    result = summarize_routed_scan_edges(edges, geometry)
    result.update({"design": args.design, "physical_seed": args.seed, "method": args.method,
                   "architecture_sha256": arch.sha256(),
                   "source": str(raw.relative_to(ROOT)).replace("\\", "/"),
                   "length_definition": "OpenDB dbWire.getLength non-via routed geometry; exact only on two-ITerm Q/SI nets without BTerms"})
    out = raw.with_name("scan_route_metrics.json")
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"classification": result["classification"],
                      "exclusive_edges": result["exclusive_scan_edge_count"],
                      "mixed_edges": result["mixed_functional_scan_edge_count"]}))


if __name__ == "__main__":
    main()
