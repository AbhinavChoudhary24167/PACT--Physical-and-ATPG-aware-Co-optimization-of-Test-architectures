#!/usr/bin/env python3
"""First bounded experiment: one mapped design, two orders, one seed."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import time

from jsonschema import validate

from pact.physical.grid_metrics import placement_grid, spatial_activity
from pact.physical.scan_wirelength import scan_wirelength
from pact.scan.model import ScanArchitecture
from pact.scan.orderings import nearest_neighbor
from pact.scan.validate import validate_ff_identity_map, validate_scan
from pact.test.activity_metrics import activity_metrics
from pact.test.pattern_parser import map_ppi_patterns, parse_fan_pat
from pact.test.shift_simulator import simulate_shift


def main() -> None:
    """Evaluate supplied and nearest orders for a placed FAN design."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--design", choices=("s5378", "s9234"), default="s5378")
    design = parser.parse_args().design
    root = Path(__file__).resolve().parents[1]
    inputs = root / f"artifacts/derived/{design}"
    raw = root / "artifacts/raw/tool_qualification/fan_atpg"
    ff_map_path = inputs / "ff_identity_map.json"
    ff_map = json.loads(ff_map_path.read_text(encoding="utf-8"))["records"]
    base = ScanArchitecture.from_json(inputs / "supplied_architecture.json")
    validate_ff_identity_map(ff_map, (c.name for c in base.cells))
    validate_scan(base)
    parsed = parse_fan_pat(raw / f"patterns/FAN_{design}.pat")
    patterns = map_ppi_patterns(parsed, ff_map)
    report = (raw / f"reports/FAN_{design}.rpt").read_text(encoding="utf-8")
    coverage_match = re.search(r"#\s+fault coverage\s+([\d.]+)%", report)
    if not coverage_match:
        raise ValueError("Fault coverage absent from FAN report")
    coverage = float(coverage_match.group(1))
    schema = json.loads((root / "config/schemas/result.schema.json").read_text(encoding="utf-8"))
    out = root / f"artifacts/derived/phase0/smoke_{design}"
    out.mkdir(parents=True, exist_ok=True)
    versions = {"openroad": (root / "artifacts/raw/tool_qualification/openroad/version.log").read_text(encoding="utf-8").strip(),
                "yosys": "Ubuntu 0.33-5build2", "fan_atpg": (raw / "commit").read_text(encoding="utf-8").strip()}
    records = []
    for method, architecture in (("supplied_fan", base), ("nearest_neighbor", nearest_neighbor(base))):
        started = time.perf_counter()
        validate_scan(architecture)
        architecture_path = out / f"{method}.architecture.json"
        architecture.to_json(architecture_path)
        geometry = scan_wirelength(architecture)
        trace = simulate_shift(architecture, patterns, between_pattern_state="carry_loaded")
        test = activity_metrics(trace)
        spatial = spatial_activity(trace, architecture.cells, placement_grid(architecture.cells, 8))
        record = {
            "schema_version": "0.1", "analysis_level": "FIXED_PLACEMENT_PROXY",
            "design": design, "platform": "nangate45", "seed": 11, "method": method,
            "architecture_sha256": architecture.sha256(), "tool_versions": versions,
            "scan": {"num_cells": len(architecture.cells), "num_chains": len(architecture.chains),
                     "total_hpwl_um": geometry["total_scan_hpwl_um"], "mean_edge_um": geometry["mean_scan_edge_um"],
                     "max_edge_um": geometry["max_scan_edge_um"],
                     "p95_edge_um": geometry["p95_scan_edge_um"], "p99_edge_um": geometry["p99_scan_edge_um"],
                     "chain_length_balance": geometry["chain_length_balance"]},
            "test": {"fault_model": "stuck_at", "fault_coverage_pct": coverage,
                     "pattern_count": len(patterns), "total_shift_toggles": test["total_shift_toggles"],
                     "peak_simultaneous_toggles": test["peak_simultaneous_toggles"],
                     "p99_simultaneous_toggles": test["p99_simultaneous_toggles"],
                     "peak_local_activity": spatial["peak_bin_toggle"],
                     "p99_local_activity": spatial["p99_bin_toggle"],
                     "spatial_activity_gini": spatial["spatial_activity_gini"],
                     "between_pattern_state": "carry_loaded", "grid_size": 8},
            "physical": {"wns_ns": None, "tns_ns": None, "congestion_metric": None,
                         "drv_count": None, "routed_wirelength_um": None},
            "pdn": {"classification": "NOT_RUN", "worst_drop_v": None},
            "runtime_s": time.perf_counter() - started,
            "status": "PASS",
            "evidence": [str(path.relative_to(root)) for path in (
                ff_map_path, raw / f"patterns/FAN_{design}.pat", raw / f"reports/FAN_{design}.rpt",
                root / f"artifacts/raw/orfs_smoke/{design}/placed.def", architecture_path,
            )],
        }
        validate(record, schema)
        records.append(record)
        (out / f"{method}.grid8.json").write_text(json.dumps(spatial, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "results.jsonl").write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in records), encoding="utf-8")


if __name__ == "__main__":
    main()
