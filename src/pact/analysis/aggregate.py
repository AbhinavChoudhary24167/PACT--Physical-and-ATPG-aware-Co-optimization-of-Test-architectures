"""Load and compare validated architecture evaluations."""
from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
from typing import Any

from jsonschema import validate

from .statistics import describe


def load_results(path: Path, schema_path: Path) -> list[dict[str, Any]]:
    """Load JSONL, validate each record, and reject missing evidence links."""
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    root = schema_path.parents[2]
    records = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        record = json.loads(line)
        validate(instance=record, schema=schema)
        missing = [ref for ref in record["evidence"] if not (root / ref).is_file()]
        if missing:
            raise ValueError(f"Result line {index} references missing evidence: {missing}")
        records.append(record)
    if not records:
        raise ValueError("No result records")
    return records


def hotspot(record: dict[str, Any], grid: str = "8") -> float:
    """Use the preregistered distance-weighted hotspot proxy."""
    return float(record["test"]["spatial_by_grid"][grid]["distance_weighted_hotspot"])


def compare_results(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute descriptive method summaries and an exact observed conflict test."""
    by_design: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_design[record["design"]].append(record)
    if len(by_design) > 1:
        designs = {name: compare_results(rows) for name, rows in sorted(by_design.items())}
        conflict_count = sum(bool(summary["observed_wirelength_activity_conflict"]) for summary in designs.values())
        return {
            "record_count": len(records), "design_count": len(designs),
            "design_summaries": designs,
            "proxy_conflict_design_count": conflict_count,
            "proxy_conflict_replicated": conflict_count >= 2,
        }
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[record["method"]].append(record)
    summaries = {}
    for method, rows in sorted(grouped.items()):
        summaries[method] = {
            "scan_hpwl_um": describe([float(row["scan"]["total_hpwl_um"]) for row in rows]),
            "hotspot_grid8": describe([hotspot(row) for row in rows]),
            "peak_bin_grid8": describe([float(row["test"]["peak_local_activity"]) for row in rows]),
        }
    unique = {record["architecture_sha256"]: record for record in records}
    candidates = list(unique.values())
    best_wire = min(candidates, key=lambda row: (row["scan"]["total_hpwl_um"], row["architecture_sha256"]))
    best_activity = min(candidates, key=lambda row: (hotspot(row), row["architecture_sha256"]))
    wire_min = float(best_wire["scan"]["total_hpwl_um"])
    activity_min = hotspot(best_activity)
    wire_optima = {row["architecture_sha256"] for row in candidates if abs(float(row["scan"]["total_hpwl_um"]) - wire_min) < 1e-9}
    activity_optima = {row["architecture_sha256"] for row in candidates if abs(hotspot(row) - activity_min) < 1e-9}
    frontier = []
    for row in candidates:
        wl, hot = float(row["scan"]["total_hpwl_um"]), hotspot(row)
        if not any((float(other["scan"]["total_hpwl_um"]) <= wl and hotspot(other) <= hot and
                    (float(other["scan"]["total_hpwl_um"]) < wl or hotspot(other) < hot))
                   for other in candidates):
            frontier.append({"method": row["method"], "seed": row["seed"],
                             "architecture_sha256": row["architecture_sha256"],
                             "scan_hpwl_um": wl, "hotspot_grid8": hot})
    return {
        "record_count": len(records), "distinct_architectures": len(unique),
        "primary_hotspot_metric": "distance_weighted_hotspot", "primary_grid_size": 8,
        "method_statistics": summaries,
        "minimum_wirelength": {"method": best_wire["method"], "seed": best_wire["seed"],
                               "architecture_sha256": best_wire["architecture_sha256"],
                               "scan_hpwl_um": wire_min, "hotspot_grid8": hotspot(best_wire)},
        "minimum_hotspot": {"method": best_activity["method"], "seed": best_activity["seed"],
                            "architecture_sha256": best_activity["architecture_sha256"],
                            "scan_hpwl_um": best_activity["scan"]["total_hpwl_um"],
                            "hotspot_grid8": activity_min},
        "observed_wirelength_activity_conflict": not bool(wire_optima & activity_optima),
        "pareto_frontier": sorted(frontier, key=lambda row: row["scan_hpwl_um"]),
    }
