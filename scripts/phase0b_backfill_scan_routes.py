#!/usr/bin/env python3
"""Archive and re-extract completed routes with explicit buffer-edge semantics."""
from __future__ import annotations

import json
from pathlib import Path
import shutil

from phase0b_run_command import run


ROOT = Path(__file__).resolve().parents[1]
VENV = Path("/root/pact-deps/pact-venv/bin/python")


def invoke(label: str, command: list[str], required: Path) -> None:
    result = run(command, ROOT / f"artifacts/raw/phase0b/runs/{label}", ROOT, 120, [required])
    if result["exit_code"] != 0 or result["timed_out"] or not result["required_outputs_present"]:
        raise RuntimeError(f"Backfill failed: {label}")


def main() -> None:
    for design in ("s5378", "s9234"):
        for seed in (11, 13, 17, 19, 23):
            for physical in sorted((ROOT / f"artifacts/raw/phase0b/physical/{design}/s{seed}").glob("*")):
                if not (physical / "5_2_route.odb").is_file():
                    continue
                method = physical.name
                tsv = physical / "scan_edges.tsv"
                metrics = physical / "scan_route_metrics.json"
                if tsv.is_file() and "via_transparent_buffer" not in tsv.open(encoding="utf-8").readline():
                    archive = physical / "scan_edges.pre_buffered.tsv"
                    if not archive.exists():
                        shutil.copy2(tsv, archive)
                    if metrics.is_file():
                        old_metrics = physical / "scan_route_metrics.pre_buffered.json"
                        if not old_metrics.exists():
                            shutil.copy2(metrics, old_metrics)
                    order = ROOT / f"artifacts/derived/phase0b/{design}/s{seed}/{method}.scan_order.json"
                    invoke(f"{design}/s{seed}/{method}_scan_route_extract_buffered",
                           ["env", f"PACT_PHASE0B_ROUTED_ODB={physical / '5_2_route.odb'}",
                            f"PACT_PHASE0B_ORDER_JSON={order}", f"PACT_PHASE0B_SCAN_ROUTE_TSV={tsv}",
                            "openroad", "-python", "-no_init", "-exit",
                            str(ROOT / "scripts/phase0b_scan_route_extract.py")], tsv)
                if tsv.is_file() and (not metrics.is_file() or "buffered_scan_edge_count" not in
                                      json.loads(metrics.read_text(encoding="utf-8"))):
                    invoke(f"{design}/s{seed}/{method}_scan_route_parse_buffered",
                           [str(VENV), str(ROOT / "scripts/phase0b_parse_scan_route.py"),
                            "--design", design, "--seed", str(seed), "--method", method], metrics)
                    print(f"BACKFILLED {design} s{seed} {method}", flush=True)


if __name__ == "__main__":
    main()
