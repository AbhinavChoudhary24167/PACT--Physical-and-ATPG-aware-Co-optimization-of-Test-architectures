#!/usr/bin/env python3
"""Evaluate conventional scan baselines on one fixed placed ATPG-mapped design."""
from __future__ import annotations

import argparse
import gc
import gzip
import json
from pathlib import Path
import re
import time

from jsonschema import validate

from pact.physical.grid_metrics import placement_grid, spatial_activity
from pact.physical.scan_wirelength import scan_wirelength
from pact.scan.model import ScanArchitecture
from pact.scan.orderings import activity_only, nearest_neighbor, physical_activity, random_order, serpentine
from pact.scan.validate import validate_ff_identity_map, validate_scan
from pact.test.activity_metrics import activity_metrics
from pact.test.pattern_parser import map_ppi_patterns, parse_fan_pat
from pact.test.shift_simulator import ShiftTrace, simulate_shift


def save_trace(trace: ShiftTrace, names: list[str], path: Path) -> None:
    """Archive every before/after/toggle bit with a stable FF column order."""
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=6) as stream:
        stream.write(json.dumps({"cell_order": names, "between_pattern_state": trace.between_pattern_state}, separators=(",", ":")) + "\n")
        for cycle in trace.cycles:
            row = [cycle.pattern_index, cycle.cycle_index,
                   "".join(str(cycle.before[name]) for name in names),
                   "".join(str(cycle.after[name]) for name in names),
                   "".join(str(cycle.toggles[name]) for name in names)]
            stream.write(json.dumps(row, separators=(",", ":")) + "\n")


def physical_metrics(root: Path, design: str, variant: str | None) -> tuple[dict[str, object], list[str]]:
    """Read ORFS JSON only; absent physical reruns remain null."""
    empty = {"wns_ns": None, "tns_ns": None, "congestion_metric": None,
             "drv_count": None, "routed_wirelength_um": None}
    if variant is None:
        return empty, []
    folder = root / f"artifacts/raw/orfs_physical/{design}/{variant}/metrics"
    global_path, detailed_path = folder / "5_1_grt.json", folder / "5_2_route.json"
    grt = json.loads(global_path.read_text(encoding="utf-8"))
    drt = json.loads(detailed_path.read_text(encoding="utf-8"))
    return {
        "wns_ns": grt["globalroute__timing__setup__ws"],
        "tns_ns": grt["globalroute__timing__setup__tns"],
        "congestion_metric": None,
        "drv_count": grt["globalroute__design__violations"],
        "routed_wirelength_um": drt["detailedroute__route__wirelength"],
        "drc_count": drt["detailedroute__route__drc_errors"],
        "timing_stage": "global_route",
        "global_route_wirelength": grt["globalroute__global_route__wirelength"],
    }, [str(global_path.relative_to(root)), str(detailed_path.relative_to(root))]


def main() -> None:
    """Evaluate all registered conventional orderings on one fixed placement."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--design", choices=("s5378", "s9234"), default="s5378")
    design = parser.parse_args().design
    root = Path(__file__).resolve().parents[1]
    source = root / f"artifacts/derived/{design}"
    raw = root / "artifacts/raw/tool_qualification/fan_atpg"
    base = ScanArchitecture.from_json(source / "supplied_architecture.json")
    validate_scan(base)
    ff_map = json.loads((source / "ff_identity_map.json").read_text(encoding="utf-8"))["records"]
    validate_ff_identity_map(ff_map, (cell.name for cell in base.cells))
    parsed = parse_fan_pat(raw / f"patterns/FAN_{design}.pat")
    patterns = map_ppi_patterns(parsed, ff_map)
    fan_report = (raw / f"reports/FAN_{design}.rpt").read_text(encoding="utf-8")
    coverage_match = re.search(r"#\s+fault coverage\s+([\d.]+)%", fan_report)
    if not coverage_match:
        raise ValueError("FAN coverage absent")
    schema = json.loads((root / "config/schemas/result.schema.json").read_text(encoding="utf-8"))
    version_text = (root / "artifacts/raw/tool_qualification/environment/post_install.txt").read_text(encoding="utf-8")
    yosys_match = re.search(r"Yosys[^\n]+", version_text)
    if not yosys_match:
        raise ValueError("Recorded Yosys version missing")
    versions = {
        "openroad": (root / "artifacts/raw/tool_qualification/openroad/version.log").read_text(encoding="utf-8").strip(),
        "yosys": yosys_match.group(0),
        "fan_atpg": (raw / "commit").read_text(encoding="utf-8").strip(),
    }
    out = root / f"artifacts/derived/phase0/{design}"
    trace_out = root / f"artifacts/raw/metric_campaign/{design}"
    out.mkdir(parents=True, exist_ok=True)
    trace_out.mkdir(parents=True, exist_ok=True)
    variants: list[tuple[str, int, ScanArchitecture, str | None]] = [
        ("supplied_fan", 11, base, "base"),
        ("nearest_neighbor", 11, nearest_neighbor(base), "nearest_neighbor"),
        ("serpentine", 11, serpentine(base), None),
        ("activity_only", 11, activity_only(base, patterns), None),
    ]
    variants += [("random", seed, random_order(base, seed), None) for seed in (11, 13, 17, 19, 23)]
    variants += [(f"physical_activity_alpha_{alpha:.2f}", 11, physical_activity(base, patterns, alpha), None)
                 for alpha in (0.0, 0.25, 0.5, 0.75, 1.0)]
    result_path = out / "results.jsonl"
    with result_path.open("w", encoding="utf-8") as result_stream:
        for method, seed, architecture, physical_variant in variants:
            started = time.perf_counter()
            validate_scan(architecture)
            label = f"{method}_seed{seed}"
            arch_path = out / f"{label}.architecture.json"
            architecture.to_json(arch_path)
            trace = simulate_shift(architecture, patterns)
            names = sorted(c.name for c in architecture.cells)
            trace_path = trace_out / f"{label}.trace.jsonl.gz"
            save_trace(trace, names, trace_path)
            aggregate = activity_metrics(trace)
            spatial = {str(size): spatial_activity(trace, architecture.cells, placement_grid(architecture.cells, size))
                       for size in (8, 16, 32)}
            (out / f"{label}.spatial.json").write_text(json.dumps(spatial, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            geometry = scan_wirelength(architecture)
            physical, physical_evidence = physical_metrics(root, design, physical_variant)
            record = {
                "schema_version": "0.1",
                "analysis_level": "PHYSICAL_RERUN" if physical_variant is not None else "FIXED_PLACEMENT_PROXY",
                "design": design, "platform": "nangate45", "seed": seed, "method": method,
                "architecture_sha256": architecture.sha256(), "tool_versions": versions,
                "scan": {
                    "num_cells": len(architecture.cells), "num_chains": len(architecture.chains),
                    "total_hpwl_um": geometry["total_scan_hpwl_um"],
                    "mean_edge_um": geometry["mean_scan_edge_um"],
                    "max_edge_um": geometry["max_scan_edge_um"],
                    "p95_edge_um": geometry["p95_scan_edge_um"],
                    "p99_edge_um": geometry["p99_scan_edge_um"],
                    "chain_length_balance": geometry["chain_length_balance"],
                },
                "test": {
                    "fault_model": "stuck_at", "fault_coverage_pct": float(coverage_match.group(1)),
                    "pattern_count": len(patterns),
                    "total_shift_toggles": aggregate["total_shift_toggles"],
                    "peak_simultaneous_toggles": aggregate["peak_simultaneous_toggles"],
                    "p99_simultaneous_toggles": aggregate["p99_simultaneous_toggles"],
                    "peak_local_activity": spatial["8"]["peak_bin_toggle"],
                    "p99_local_activity": spatial["8"]["p99_bin_toggle"],
                    "spatial_activity_gini": spatial["8"]["spatial_activity_gini"],
                    "spatial_by_grid": {size: {
                        "peak_bin_toggle": metrics["peak_bin_toggle"],
                        "p99_bin_toggle": metrics["p99_bin_toggle"],
                        "distance_weighted_hotspot": metrics["distance_weighted_hotspot"],
                        "spatial_activity_gini": metrics["spatial_activity_gini"],
                    } for size, metrics in spatial.items()},
                    "between_pattern_state": "carry_loaded",
                },
                "physical": physical,
                "pdn": {"classification": "NOT_RUN", "worst_drop_v": None},
                "runtime_s": time.perf_counter() - started, "status": "PASS",
                "evidence": [str(path.relative_to(root)) for path in (
                    source / "ff_identity_map.json", raw / f"patterns/FAN_{design}.pat",
                    raw / f"reports/FAN_{design}.rpt", root / f"artifacts/raw/orfs_smoke/{design}/placed.def",
                    arch_path, trace_path, out / f"{label}.spatial.json",
                )] + physical_evidence,
            }
            validate(instance=record, schema=schema)
            result_stream.write(json.dumps(record, sort_keys=True) + "\n")
            result_stream.flush()
            del trace
            gc.collect()


if __name__ == "__main__":
    main()
