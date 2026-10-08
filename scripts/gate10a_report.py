#!/usr/bin/env python3
"""Build Gate 10A evidence from explicitly selected, hash-bound qualified runs.

Run selection is earliest completed qualified density-one attempt per frozen
architecture, after shared smoke qualification. Controls never enter results.
No architecture or statistic is chosen from its observed numerical outcome.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pact import gate10a_decision as decision
from pact import gate10a_spatial as spatial

OUT = ROOT / "reports/gate10a"


def resolve(path):
    text = str(path).replace("\\", "/")
    if text.startswith("repo://"):
        return ROOT / text[7:]
    if "/PACT/PACT/" in text:
        return ROOT / text.split("/PACT/PACT/", 1)[1]
    if os.name == "nt" and re.match(r"^/mnt/[a-z]/", text):
        return Path(text[5].upper() + ":/" + text[7:])
    if os.name != "nt" and re.match(r"^[A-Za-z]:/", text):
        return Path("/mnt/" + text[0].lower() + "/" + text[3:])
    path = Path(text)
    return path if path.is_absolute() else ROOT / path


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def binding(path):
    path = Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return dict(path="repo://" + path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path),
                bytes=path.stat().st_size, sha256=digest.hexdigest())


def verify(expected):
    path = resolve(expected["path"])
    actual = binding(path)
    if actual["sha256"] != expected["sha256"] or actual["bytes"] != expected["bytes"]:
        raise ValueError("Bound evidence changed: " + str(path))
    return path


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def number(value, label, *, signed=False):
    if isinstance(value, bool):
        raise ValueError("Invalid " + label)
    value = float(value)
    if not math.isfinite(value) or (not signed and value < 0):
        raise ValueError("Invalid " + label)
    return value


def percentile(values, p):
    if not values:
        raise ValueError("Empty registered percentile population")
    ordered = sorted(values)
    index = (len(ordered) - 1) * p / 100
    lo, hi = math.floor(index), math.ceil(index)
    return ordered[lo] + (index - lo) * (ordered[hi] - ordered[lo])


def write_json(path, data, *, immutable=False):
    path = Path(path)
    text = json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if immutable and path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise ValueError("Preserve immutable derived evidence: " + str(path))
        return
    path.write_text(text, encoding="utf-8")


def write_csv(path, rows, fields):
    with Path(path).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows({key: json.dumps(value, sort_keys=True, allow_nan=False) if isinstance(value, (list, dict)) else value
                         for key, value in row.items()} for row in rows)


def _close(actual, expected, label):
    if not math.isclose(actual, number(expected, label), rel_tol=1e-10, abs_tol=1e-12):
        raise ValueError("Independent raw-CSV aggregate differs: " + label)


def supported_power_partitions(native, totals, population_n):
    """Keep the supported native OpenSTA Clock category in SI watts.

    Category semantics are those of report_power; this is not a new instance
    classifier and is distinct from clock/nonclock *activity* annotation.
    """
    if type(population_n) is not int or not 0 < population_n < 2**24:
        raise ValueError("Valid native float32 reduction population required")
    u = 2**-24
    gamma = population_n * u / (1 - population_n * u)
    result = dict(native_float32_population_n=population_n, native_float32_gamma_n=gamma)
    for component in ("internal", "switching", "leakage", "total"):
        field = component + "_w"
        native_total = number(native["Total"][component], "native total " + component)
        difference = native_total - totals[field]
        bound = gamma * abs(totals[field])
        if abs(difference) > bound + 1e-15:
            raise ValueError("Native design/instance float32 reduction bound exceeded: " + field)
        result["native_" + field] = native_total
        result["native_vs_instance_" + component + "_difference_w"] = difference
        result["native_" + component + "_float32_reduction_bound_w"] = bound
        clock = number(native["Clock"][component], "native clock " + component)
        nonclock = totals[field] - clock
        if nonclock < 0:
            raise ValueError("Native clock component exceeds qualified design total")
        result["clock_" + field] = clock
        result["nonclock_" + field] = nonclock
    result["clock_dynamic_w"] = result["clock_internal_w"] + result["clock_switching_w"]
    result["nonclock_dynamic_w"] = result["nonclock_internal_w"] + result["nonclock_switching_w"]
    return result


def normalized_inventory(power_rows):
    result = []
    names = set()
    for row in power_rows:
        name = row["instance"]
        if name in names:
            raise ValueError("Duplicate power instance")
        names.add(name)
        if any(row[field] not in ("0", "1") for field in ("physical_only", "powered", "liberty_modelled")):
            raise ValueError("Invalid explicit instance role flag")
        physical = row["physical_only"] == "1"
        powered = row["powered"] == "1"
        modelled = row["liberty_modelled"] == "1"
        if not physical and (not powered or not modelled):
            raise ValueError("Nonphysical instance lacks qualified power model or VDD")
        result.append(dict(id=name, x_um=number(row["x_um"], "x_um", signed=True),
                           y_um=number(row["y_um"], "y_um", signed=True), powered=powered and modelled,
                           physical_only=physical))
    return result


def frozen_peak_maps(count_path, activity_rows, bounds, cycles, resolutions):
    """Read retained counts once; reconstruct maximum C×N in each fixed bin.

    These are secondary temporal-mismatch maps, not primary mean activity.
    A different cycle can supply each regional maximum. No simulation runs.
    """
    rows = sorted(activity_rows, key=lambda row: row["net"])
    names = [row["net"] for row in rows]
    if names != sorted(set(names)) or not names:
        raise ValueError("Complete unique peak-map net inventory required")
    if type(cycles) is not int or cycles <= 0:
        raise ValueError("Positive integer peak-map cycle population required")
    weights, memberships, supports = {}, {}, {}
    for resolution in resolutions:
        weights[resolution] = np.zeros(len(rows))
        memberships[resolution] = [[] for _ in range(resolution**2)]
        supports[resolution] = [0] * resolution**2
        for index, row in enumerate(rows):
            bid = spatial.spatial_bin((number(row["x_um"], "x_um", signed=True),
                                       number(row["y_um"], "y_um", signed=True)), bounds, resolution)
            supports[resolution][bid] += 1
            memberships[resolution][bid].append(index)
            cap = row["ground_pin_ff"]
            if cap in (None, ""):
                if number(row["transitions"], "transitions"):
                    raise ValueError("Switched net missing peak-map capacitance")
            else:
                weights[resolution][index] = number(cap, "peak-map capacitance")
    peaks = {resolution: np.zeros(resolution**2) for resolution in resolutions}
    peak_cycles = {resolution: np.zeros(resolution**2, dtype=np.int64) for resolution in resolutions}
    totals = np.zeros(len(rows), dtype=np.uint64)
    with gzip.open(count_path, "rb") as stream:
        def exact(size):
            value = stream.read(size)
            if len(value) != size:
                raise ValueError("Incomplete peak-map compact activity output")
            return value
        if exact(8) != b"PACTCN01" or struct.unpack("<II", exact(8)) != (len(names), cycles):
            raise ValueError("Peak-map compact dimensions/format differ from frozen workload")
        for name in names:
            length = struct.unpack("<I", exact(4))[0]
            if length != len(name.encode()) or exact(length).decode() != name:
                raise ValueError("Peak-map compact net mapping differs")
        for first in range(0, cycles, 512):
            count = min(512, cycles - first)
            block = np.frombuffer(exact(count * len(rows)), np.uint8).reshape(count, len(rows))
            totals += block.sum(axis=0, dtype=np.uint64)
            for resolution in resolutions:
                regional = np.zeros((count, resolution**2))
                for bid, indices in enumerate(memberships[resolution]):
                    if indices:
                        regional[:, bid] = (block[:, indices] * weights[resolution][indices]).sum(axis=1)
                local_cycles = np.argmax(regional, axis=0)
                local_peaks = regional[local_cycles, np.arange(resolution**2)]
                changed = local_peaks > peaks[resolution]
                peaks[resolution][changed] = local_peaks[changed]
                peak_cycles[resolution][changed] = first + local_cycles[changed]
        if exact(8) != b"PACTDONE" or stream.read(1):
            raise ValueError("Peak-map compact completion footer/trailing output failed")
    if [int(value) for value in totals] != [int(row["transitions"]) for row in rows]:
        raise ValueError("Peak-map counts differ from qualified activity totals")
    return {str(resolution): dict(values=peaks[resolution].tolist(),
                                  peak_cycle_index_zero_based=peak_cycles[resolution].tolist(),
                                  support_counts=supports[resolution], grid=spatial.grid_metadata(bounds, resolution),
                                  unit="fF transitions",
                                  reduction="maximum regional C×N over all qualified shift cycles",
                                  temporal_limit="regional maxima can occur on different cycles; comparison to average/static maps is secondary")
            for resolution in resolutions}


def summarize_raw(power_rows, voltage_rows, segment_rows, activity_rows, export, protocol, result):
    """Independently verify primitives and retain complete spatial vectors."""
    inventory = normalized_inventory(power_rows)
    bounds, cycles = export["bounds_um"], export["scan_cycles"]
    origin_check = spatial.crosscheck_source_origins(activity_rows, inventory)
    components = spatial.power_points(power_rows)
    if any(point["value"] is None for points in components.values() for point in points):
        raise ValueError("Missing raw instance power component")
    for row in power_rows:
        _close(number(row["total_w"], "total_w"),
               math.fsum(number(row[field], field) for field in ("internal_w", "switching_w", "leakage_w")),
               "per-instance power closure: " + row["instance"])
    totals = {field: math.fsum(point["value"] for point in points) for field, points in components.items()}
    for field, total in totals.items():
        _close(total, result["power"][field], field)
    _close(totals["total_w"], totals["internal_w"] + totals["switching_w"] + totals["leakage_w"], "power component closure")
    terminals = spatial.ir_terminal_points(voltage_rows, inventory, supply_voltage_v=protocol["voltage_v"])
    for point in terminals:
        spatial.spatial_bin((point["terminal_x_um"], point["terminal_y_um"]), bounds, 4)
        if point["value"] is None:
            raise ValueError("Missing raw supply-terminal voltage")
    powered_names = {row["id"] for row in inventory if row["powered"] and not row["physical_only"]}
    powered_terminals = [row for row in terminals if row["instance"] in powered_names]
    drops = {}
    for point in powered_terminals:
        if point["value"] is None:
            raise ValueError("Missing powered-instance supply voltage")
        drops[point["instance"]] = max(drops.get(point["instance"], 0.0), point["value"])
    if set(drops) != powered_names or not drops:
        raise ValueError("Incomplete powered-instance voltage population")
    drop_values = [drops[name] for name in sorted(drops)]
    ir = dict(worst_drop_v=max(drop_values), mean_drop_v=math.fsum(drop_values) / len(drop_values),
              **{f"p{p}_drop_v": percentile(drop_values, p) for p in protocol["percentiles"]},
              powered_instances=len(drop_values), voltage_rows=len(terminals),
              primary_population="one worst VDD terminal per nonphysical Liberty-powered instance")
    ir["worst_drop_instances"] = [dict(instance=row["id"], x_um=row["x_um"], y_um=row["y_um"])
                                 for row in inventory if drops.get(row["id"]) == ir["worst_drop_v"]]
    for field in ("worst_drop_v", "mean_drop_v", "p50_drop_v", "p95_drop_v", "p99_drop_v"):
        _close(ir[field], result["ir"][field], field)
    if ir["powered_instances"] != result["ir"]["powered_instances"] or ir["voltage_rows"] != result["ir"]["voltage_rows"]:
        raise ValueError("Raw voltage population differs from receipt")
    currents, current_points = [], []
    segment_ids = set()
    for row in segment_rows:
        coordinates = [number(row[field], field, signed=True) for field in
                       ("Node0 X location", "Node0 Y location", "Node1 X location", "Node1 Y location")]
        current = abs(number(row["Current"], "segment current A", signed=True))
        sid = json.dumps([row["Node0 Layer"], *coordinates[:2], row["Node1 Layer"], *coordinates[2:]])
        if sid in segment_ids:
            raise ValueError("Duplicate raw PDN segment observation")
        segment_ids.add(sid)
        # Keep both endpoints; only separately labeled diagnostic maps use midpoint.
        for point in (coordinates[:2], coordinates[2:]):
            spatial.spatial_bin(point, bounds, 4)
        current_points.append(dict(id=sid, x_um=(coordinates[0] + coordinates[2]) / 2,
                                   y_um=(coordinates[1] + coordinates[3]) / 2, current_a=current))
        currents.append(current)
    if not currents:
        raise ValueError("Missing raw PDN segment currents")
    current_stats = dict(peak_segment_current_a=max(currents), segments=len(currents),
                         **{f"p{p}_segment_current_a": percentile(currents, p) for p in protocol["percentiles"]},
                         current_density_status="NOT_EVALUATED_NO_QUALIFIED_METAL_CROSS_SECTION")
    _close(current_stats["peak_segment_current_a"], result["current"]["peak_segment_current_a"], "peak current A")
    for p in protocol["percentiles"]:
        _close(current_stats[f"p{p}_segment_current_a"], result["current"][f"p{p}_segment_current_a"], "current percentile")
    if current_stats["segments"] != result["current"]["segments"]:
        raise ValueError("Raw segment population differs from receipt")
    current_stats["peak_segments"] = [point for point in current_points if point["current_a"] == current_stats["peak_segment_current_a"]]
    grids, correlations = {}, []
    for resolution in protocol["spatial_resolutions"]:
        domain = spatial.powered_domain(inventory, bounds, resolution)
        activity = spatial.regional_activity(activity_rows, bounds, cycles, resolution)
        power = spatial.aggregate_points(components["dynamic_w"], bounds, resolution, reduction="sum", unit="W")
        voltage = spatial.aggregate_points(powered_terminals, bounds, resolution, reduction="maximum", unit="V")
        power_compare = spatial.compare_regions(activity["values"], power["values"], domain["bin_ids"])
        ir_compare = spatial.compare_regions(activity["values"], voltage["values"], domain["bin_ids"])
        current_bins = [[] for _ in range(resolution**2)]
        for point in current_points:
            bid = spatial.spatial_bin((point["x_um"], point["y_um"]), bounds, resolution)
            current_bins[bid].append(point["current_a"])
        current_values = [max(values) if values else None for values in current_bins]
        current_compare = spatial.compare_regions(activity["values"], current_values, domain["bin_ids"])
        grids[str(resolution)] = dict(domain=domain, activity=activity, dynamic_power=power, static_vdd_drop=voltage,
                                      activity_vs_dynamic_power=power_compare, activity_vs_static_ir=ir_compare,
                                      diagnostic_peak_segment_current_a=current_values,
                                      diagnostic_mean_activity_vs_peak_segment_current=current_compare,
                                      diagnostic_segment_support=[len(values) for values in current_bins])
        for comparison_name, comparison in (("mean_activity_vs_dynamic_power", power_compare), ("mean_activity_vs_static_ir", ir_compare)):
            correlations.append(dict(resolution=resolution, comparison=comparison_name, **comparison["primary"],
                                     domain_bin_ids=json.dumps(domain["bin_ids"]),
                                     diagnostic_pairwise_finite=json.dumps(comparison["diagnostic_pairwise_finite"], sort_keys=True)))
        correlations.append(dict(resolution=resolution, comparison="diagnostic_mean_activity_vs_peak_segment_current",
                                 **current_compare["primary"], domain_bin_ids=json.dumps(domain["bin_ids"]),
                                 diagnostic_pairwise_finite=json.dumps(current_compare["diagnostic_pairwise_finite"], sort_keys=True),
                                 spatial_limit="segment midpoints versus cell-origin activity; branch current A, not current density"))
    for fraction in protocol["drop_threshold_fraction"]:
        label = f"{round(fraction * 100)}pct"
        threshold = fraction * protocol["voltage_v"]
        ir[f"count_over_{label}_supply"] = sum(value > threshold for value in drop_values)
        ir[f"fraction_over_{label}_supply"] = ir[f"count_over_{label}_supply"] / len(drop_values)
        for resolution in protocol["spatial_resolutions"]:
            grid = grids[str(resolution)]
            count = sum(grid["static_vdd_drop"]["values"][bid] > threshold for bid in grid["domain"]["bin_ids"])
            area = ((bounds[2] - bounds[0]) * (bounds[3] - bounds[1])) / resolution**2
            ir[f"grid{resolution}_regions_over_{label}_supply"] = count
            ir[f"grid{resolution}_coarse_area_um2_over_{label}_supply"] = count * area
    return dict(power=totals, ir=ir, current=current_stats, grids=grids, correlations=correlations,
                source_origin_check=origin_check, terminal_sample_count=len(terminals))


def flow_fingerprint(receipt):
    snapshots = {Path(item["path"].replace("\\", "/")).name: item for item in receipt.get("execution_source_snapshots", [])}
    return {name: snapshots[name]["sha256"] for name in ("runner_source.py", "measurement_source.tcl") if name in snapshots}


def selected_runs(manifest_path):
    manifest = read_json(manifest_path)
    smoke_path = verify(manifest["smoke_qualification"])
    smoke = read_json(smoke_path)
    if smoke.get("status") not in ("PASS", "QUALIFIED"):
        raise ValueError("Shared smoke did not qualify; final scientific comparisons are unavailable")
    fingerprint = smoke.get("flow_fingerprint")
    if not isinstance(fingerprint, dict) or set(fingerprint) != {"runner_source.py", "measurement_source.tcl"}:
        raise ValueError("Shared smoke lacks qualified execution-source fingerprint")
    invalidated = set()
    for expected in smoke.get("invalidated_receipts", []):
        invalidated.add(verify(expected).resolve())
    for expected in smoke.get("invalidation_records", []):
        invalidation = read_json(verify(expected))
        for item in invalidation.get("invalidated_receipts", []):
            invalidated.add(verify(item).resolve())
    smoke_records = []
    for expected in smoke.get("records", []):
        path = verify(expected)
        receipt = read_json(path)
        if (receipt.get("status") != "QUALIFIED" or (receipt.get("design"), receipt.get("architecture")) != ("b14_opt", "B3T")
                or path.resolve() in invalidated or flow_fingerprint(receipt) != fingerprint):
            raise ValueError("Shared smoke control record lacks qualified common method")
        for output in receipt["outputs"]:
            verify(output)
        smoke_records.append((path.resolve(), receipt))
    if len({path for path, _ in smoke_records}) != 4 or sorted(row["nonclock_density_scale"] for _, row in smoke_records) != [0, 1, 1, 2]:
        raise ValueError("Shared smoke requires two nominal and zero/two density controls")
    smoke_nominal = verify(smoke["nominal_architecture_receipt"]).resolve()
    if smoke_nominal not in {path for path, row in smoke_records if row["nonclock_density_scale"] == 1}:
        raise ValueError("Shared smoke nominal reuse record differs")
    records = {}
    for item in manifest["runs"]:
        key = (item["design"], item["architecture"])
        if key in records:
            raise ValueError("Duplicate selected architecture run")
        receipt_path = verify(item["receipt"])
        receipt = read_json(receipt_path)
        if (receipt.get("design"), receipt.get("architecture")) != key:
            raise ValueError("Run selection identity mismatch")
        if receipt.get("status") != "QUALIFIED" or receipt.get("nonclock_density_scale") != 1:
            raise ValueError("Controls or incomplete runs cannot be scientific architecture evidence")
        if receipt_path.resolve() in invalidated or flow_fingerprint(receipt) != fingerprint:
            raise ValueError("Selected run is invalidated or differs from shared qualified flow")
        for snapshot in receipt.get("execution_source_snapshots", []):
            verify(snapshot)
        # Metadata-only selection audit; no numerical outcomes influence selection.
        eligible = []
        for candidate_path in receipt_path.parent.parent.glob("*/receipt.json"):
            candidate = read_json(candidate_path)
            if (candidate.get("status") == "QUALIFIED" and candidate.get("nonclock_density_scale") == 1
                    and candidate_path.resolve() not in invalidated and flow_fingerprint(candidate) == fingerprint):
                eligible.append((candidate["completed_utc"], candidate_path.as_posix(), candidate_path))
        if eligible and min(eligible)[2].resolve() != receipt_path.resolve():
            raise ValueError("Run selection did not use earliest completed qualified nominal attempt")
        records[key] = (receipt_path, receipt)
    return records, manifest, smoke


def qualified_record(selected, receipt_path, receipt, protocol, prereg):
    if (receipt.get("design"), receipt.get("architecture")) != (selected["design"], selected["architecture"]):
        raise ValueError("Selected run design/architecture mismatch")
    if receipt.get("status") != "QUALIFIED" or receipt.get("nonclock_density_scale") != 1:
        raise ValueError("Scientific record requires qualified nominal density")
    if receipt["architecture_sha256"] != selected["architecture_sha256"]:
        raise ValueError("Selected architecture SHA mismatch")
    if receipt.get("preregistered_commit") != prereg["commit"]:
        raise ValueError("Run preregistration commit differs")
    for field in ("protocol", "selection", "tool_provenance"):
        verify(receipt[field])
    if any(receipt.get("scientific_stages_reexecuted", {}).values()):
        raise ValueError("Disallowed scientific stage rerun")
    for item in receipt["outputs"]:
        verify(item)
    outputs = {Path(item["path"].replace("\\", "/")).name: item for item in receipt["outputs"]}
    if len(outputs) != len(receipt["outputs"]):
        raise ValueError("Duplicate run output basename")
    paths = {name: verify(outputs[name]) for name in
             ("instance_power.csv", "instance_voltage.csv", "segment_current.csv", "sources.csv", "pdn_geometry_canonical.tsv")}
    export_path = verify(receipt["activity_export"])
    export = read_json(export_path)
    if (export["status"] != "PASS" or export["architecture_sha256"] != selected["architecture_sha256"]
            or (export.get("design"), export.get("architecture")) != (selected["design"], selected["architecture"])
            or export.get("preregistered_commit") != prereg["commit"]
            or export.get("scan_cycles") != selected["cycles"]
            or export.get("FF_Q_population") != selected["ff_count"]
            or export.get("bounds_um") != selected["bounds_um"]):
        raise ValueError("Activity export lacks matching frozen architecture")
    csv_path = verify(export["output"])
    verify(receipt["derived_activity_csv"])
    if any(receipt["derived_activity_csv"][field] != export["output"][field] for field in ("sha256", "bytes")):
        raise ValueError("Run activity CSV differs from qualified export")
    activity_rows = read_csv(csv_path)
    power_rows = read_csv(paths["instance_power.csv"])
    summary = summarize_raw(power_rows, read_csv(paths["instance_voltage.csv"]),
                            read_csv(paths["segment_current.csv"]), activity_rows, export, protocol, receipt["result"])
    native_path = verify(outputs["power_report.json"])
    summary["power"].update(supported_power_partitions(read_json(native_path), summary["power"], len(power_rows)))
    summary["power_partition_definition"] = "native OpenSTA report_power Clock category; nonclock is design total minus Clock; SI W"
    if binding(paths["sources.csv"])["sha256"] != receipt["result"]["sources_sha256"]:
        raise ValueError("Source geometry hash differs from run result")
    if binding(paths["pdn_geometry_canonical.tsv"])["sha256"] != receipt["result"]["pdn_geometry_sha256"]:
        raise ValueError("PDN geometry hash differs from run result")
    count_path = verify(selected["count_trace"])
    peaks = frozen_peak_maps(count_path, activity_rows, export["bounds_um"], export["scan_cycles"], protocol["spatial_resolutions"])
    for resolution in protocol["spatial_resolutions"]:
        grid = summary["grids"][str(resolution)]
        peak = peaks[str(resolution)]
        _close(max(peak["values"]), selected["frozen_metrics"][f"H{resolution}"], f"frozen H{resolution} peak-map closure")
        grid["secondary_peak_cycle_activity"] = peak
        for suffix, physical in (("dynamic_power", "dynamic_power"), ("static_ir", "static_vdd_drop")):
            comparison = spatial.compare_regions(peak["values"], grid[physical]["values"], grid["domain"]["bin_ids"])
            grid["secondary_peak_activity_vs_" + suffix] = comparison
            summary["correlations"].append(dict(resolution=resolution, comparison="secondary_peak_cycle_activity_vs_" + suffix,
                **comparison["primary"], domain_bin_ids=json.dumps(grid["domain"]["bin_ids"]),
                diagnostic_pairwise_finite=json.dumps(comparison["diagnostic_pairwise_finite"], sort_keys=True),
                temporal_limit="regional peak-cycle activity versus activity-averaged power/static IR; no transient validation"))
        comparison = spatial.compare_regions(peak["values"], grid["diagnostic_peak_segment_current_a"], grid["domain"]["bin_ids"])
        grid["diagnostic_peak_activity_vs_peak_segment_current"] = comparison
        summary["correlations"].append(dict(resolution=resolution, comparison="diagnostic_peak_cycle_activity_vs_peak_segment_current",
            **comparison["primary"], domain_bin_ids=json.dumps(grid["domain"]["bin_ids"]),
            diagnostic_pairwise_finite=json.dumps(comparison["diagnostic_pairwise_finite"], sort_keys=True),
            spatial_limit="segment midpoints versus cell-origin peak activity; branch current A, not current density",
            temporal_limit="regional peak-cycle activity versus static averaged-load segment current; no transient validation"))
    summary.update(design=selected["design"], architecture=selected["architecture"],
                   architecture_sha256=selected["architecture_sha256"], status="QUALIFIED", reason=None,
                   frozen_metrics=selected["frozen_metrics"], run_receipt=binding(receipt_path),
                   pdn_geometry_sha256=receipt["result"]["pdn_geometry_sha256"], sources_sha256=receipt["result"]["sources_sha256"])
    derived = OUT / "derived" / selected["design"] / selected["architecture"] / receipt["label"]
    vector_path = derived / "spatial_vectors.json"
    write_json(vector_path, {key: summary[key] for key in ("design", "architecture", "architecture_sha256", "grids", "source_origin_check", "run_receipt")}, immutable=True)
    derivation = dict(schema="pact_gate10a_spatial_derivation_v1", status="PASS",
               run_receipt=binding(receipt_path), source_outputs=[outputs[name] for name in paths],
               native_power_report=outputs["power_report.json"],
               activity_export=binding(export_path), derived_activity_csv=binding(csv_path),
               retained_count_trace=selected["count_trace"], reporter=binding(Path(__file__)),
               spatial_module=binding(ROOT / "src/pact/gate10a_spatial.py"), vector_output=binding(vector_path))
    derivation_path = derived / "derivation_receipt.json"
    if derivation_path.exists() and read_json(derivation_path) != derivation:
        # Preserve the original derivation; source/reporting repairs append a
        # new receipt rather than invalidating unchanged bound raw/vector data.
        derivation_path = derived / ("derivation_receipt_" + derivation["reporter"]["sha256"][:16] + ".json")
    write_json(derivation_path, derivation, immutable=True)
    summary["derivation_receipt"] = binding(derivation_path)
    summary["spatial_vectors"] = binding(vector_path)
    return summary


def relative_delta(candidate, reference):
    if candidate is None or reference is None or reference == 0:
        return None
    return (candidate - reference) / reference


def comparison_records(records, protocol):
    lookup = {(row["design"], row["architecture"]): row for row in records}
    comparisons = []
    for design, roles in protocol["architecture_set"].items():
        reference_role = protocol["references"][design]
        reference = lookup[(design, reference_role)]
        for role in roles:
            if role == reference_role:
                continue
            candidate = lookup[(design, role)]
            qualified = candidate["status"] == reference["status"] == "QUALIFIED"
            row = dict(design=design, candidate=role, reference=reference_role,
                       comparison_role="primary" if role == "CS_C1" else "secondary" if role.startswith("CS_") else "control",
                       status="QUALIFIED" if qualified else "UNAVAILABLE", reason=None if qualified else "candidate_or_reference_incomplete")
            for metric in ("E", "H4", "H8", "routed_scan_wirelength_um"):
                row["delta_" + metric + "_fraction"] = relative_delta(candidate["frozen_metrics"][metric], reference["frozen_metrics"][metric])
            row["delta_routed_scan_wire_fraction"] = row["delta_routed_scan_wirelength_um_fraction"]
            row.update({field: None for field in decision.DELTA_FIELDS if field not in row})
            if qualified:
                for name, source in (("worst", "worst_drop_v"), ("p99", "p99_drop_v"), ("p95", "p95_drop_v"), ("mean", "mean_drop_v"), ("median", "p50_drop_v")):
                    value, base = candidate["ir"][source], reference["ir"][source]
                    row[f"delta_{name}_ir_v"] = value - base
                    row[f"delta_{name}_ir_fraction"] = relative_delta(value, base)
                for field in ("dynamic_w", "switching_w", "internal_w", "leakage_w", "total_w"):
                    row[f"delta_{field}"] = candidate["power"][field] - reference["power"][field]
                    row[f"delta_{field}_fraction"] = relative_delta(candidate["power"][field], reference["power"][field])
                row["delta_dynamic_power_fraction"] = row["delta_dynamic_w_fraction"]
                row["delta_peak_segment_current_a"] = candidate["current"]["peak_segment_current_a"] - reference["current"]["peak_segment_current_a"]
                row["delta_peak_segment_current_fraction"] = relative_delta(candidate["current"]["peak_segment_current_a"], reference["current"]["peak_segment_current_a"])
                for field in candidate["ir"]:
                    if "_over_" in field:
                        row["delta_" + field] = candidate["ir"][field] - reference["ir"][field]
            row["materiality"] = decision.assess_comparison(row)
            for field in ("material_pi_benefit", "material_adverse_drop", "modest_scan_wire_cost", "dynamic_guardrail_pass", "current_guardrail_pass"):
                row[field] = row["materiality"][field]
            comparisons.append(row)
    return comparisons


def runtime_rows(selected_receipts=()):
    selected_paths = {Path(path).resolve() for path in selected_receipts}
    rows = []
    for path in sorted((OUT / "runs").glob("*/*/*/receipt.json")):
        receipt = read_json(path)
        runtime = receipt.get("runtime", {})
        rows.append(dict(design=receipt.get("design"), architecture=receipt.get("architecture"), attempt=receipt.get("label"),
                         status=receipt.get("status"), density_scale=receipt.get("nonclock_density_scale"),
                         started_utc=receipt.get("started_utc"), completed_utc=receipt.get("completed_utc"),
                         wall_seconds=receipt.get("wall_seconds"), CPU_user_seconds=runtime.get("CPU_user_seconds"),
                         CPU_system_seconds=runtime.get("CPU_system_seconds"), peak_RSS_bytes=runtime.get("peak_RSS_bytes"),
                         disk_bytes=receipt.get("disk_bytes"), receipt_path=str(path.relative_to(ROOT)),
                         selected_scientific_record=path.resolve() in selected_paths,
                         receipt_sha256=binding(path)["sha256"], command=json.dumps(receipt.get("command")),
                         environment_overrides=json.dumps(receipt.get("environment_overrides"), sort_keys=True), error=receipt.get("error")))
    return rows


def fmt(value, scale=1, suffix=""):
    return "—" if value is None else f"{value * scale:.6g}{suffix}"


def report_text(summary, comparisons, provenance, diagnostic):
    verdict = summary["decision"]
    lines = ["# Gate 10A practical-impact validation", "", "## A. Executive classification", "",
             f"**{verdict['classification']}**. Development recommendation: **{verdict['recommendation']}**.", "", verdict["rationale"], "",
             "## B. External research question", "", '“What is the practical impact of the 2.4% reduction? Does this translate in IR-drop or thermal hotspot improvement?”', "",
             "The quoted 2.4% is the maintainer's historical question, separate from the full-precision Gate 09 values tested here. The [original comment](https://github.com/The-OpenROAD-Project/OpenROAD/discussions/11478#discussioncomment-18767526) was independently verified; the read-only verification is retained in `control/external_question_verification.json`.", "",
             "## C. Frozen Gate 09 inputs", "", f"Published Gate 09 parent: `{summary['published_parent']}`. Preregistration: `{summary['preregistration_commit']}`.",
             "Frozen routed ODBs, original SPEF, exact load/unload counts and qualified FAN patterns were reused. No PACT search, ATPG, placement, routing, extraction or replay was rerun.", "",
             "## D. Architecture selection", "", "b14: B3T, CS_C1, CS_C3, B5. b15: B2, CS_C1, CS_C2, CS_C3, B5. Co-primary comparisons are CS_C1 versus the respective B3T/B2 reference.",
             "The earliest completed admissible qualified nominal density-one run matching the shared qualified execution-source fingerprint is selected; zero/two-density controls and explicitly invalidated implementation attempts are excluded. Selection never uses architecture comparison values.", "",
             "## E. Power/PI methodology", "", "Nangate45 typical Liberty, 1.1 V, 10 ns scan period. Non-clock measured transition density is annotated with fixed duty 0.5; scan enable is asserted and clock activity remains fixed.",
             "Dynamic power is OpenSTA internal plus switching power. PDNSim solves static VDD drop on the original PDN with ideal sources at both ends of each original top VDD stripe; no package resistance is included.", "",
             "A common measurement-import repair assigns previously unassigned late-added buffer PG ITerms to the existing VDD/VSS nets in memory using exact ^VDD$/^VSS$ pin rules. Original routed ODB hashes are retained; COMPONENTS/NETS/PINS/VIAS and original PG shapes are checked unchanged. The PDN geometry is frozen while PG connectivity metadata is normalized identically across all nine architectures.", "",
             "## F. Approximations and limitations", "", "Cycle-resolved source-localized C×N activity, averaged activity-derived Liberty power and static VDD voltage drop are distinct quantities. The method does not establish transient scan droop, physical glitches, signoff PI, ground bounce, package effects or thermal behavior.",
             "Fixed duty lacks measured logic-high occupancy; Liberty state/slew dependence is approximate. Activity-to-power correspondence is partly model-coupled. These two related benchmark families do not establish broad generalization.", "",
             "## G. Artifact reuse", "", "All nine derived activity CSVs are bound to full validated compact count traces, original mappings and SPEF. Every scientific run retains immutable input/output bindings and execution-source snapshots. Full spatial vectors are retained beneath `reports/gate10a/derived/`.", "",
             "## H. FAN_ATPG status / repair status", "", "Qualified Gate 09 patterns were reused; FAN_ATPG was not executed. The qualified existing repair identity is `4c253bfa613e5827f17c42a5fce8be7bea779e1e`.", "",
             "## I. Power results", "", "Power values are estimates under the fixed-duty model, in watts. Blank entries are unavailable evidence.", "",
             "The CSV also retains the supported native OpenSTA Clock-category internal/switching/leakage/total watts and nonclock complements (design total minus Clock). These native library/timing categories are separate from clock versus nonclock activity annotations; the entire design power remains the PDNSim load.", "",
             "Primary design power uses a high-accuracy sum of exported per-instance components. Native JSON aggregate differences are retained and checked against the population-derived binary32 gamma_n reduction bound already qualified by the runner; this parser bound is separate from scientific materiality and reproducibility thresholds.", "",
             "| Design | Architecture | Status | Dynamic mW | Switching mW | Internal mW | Leakage mW |", "|---|---|---|---:|---:|---:|---:|"]
    for row in summary["architectures"]:
        power = row.get("power", {}) if row["status"] == "QUALIFIED" else {}
        lines.append(f"| {row['design']} | {row['architecture']} | {row['status']} | {fmt(power.get('dynamic_w'), 1000)} | {fmt(power.get('switching_w'), 1000)} | {fmt(power.get('internal_w'), 1000)} | {fmt(power.get('leakage_w'), 1000)} |")
    lines += ["", "## J. IR-drop results", "", "Primary statistics use one worst VDD terminal per powered nonphysical Liberty-modelled instance; percentiles use linear interpolation. Absolute supply thresholds are strict >11, >33 and >55 mV.",
              "Native PDNSim terminal voltage CSVs have six decimals in volts (about 1 µV resolution); segment currents have roughly four significant digits. Derived arithmetic retains the available source precision. Equal exported voltages do not establish exact equality inside the solver. The registered 0.1 mV materiality threshold is much larger than this voltage export resolution.", "",
              "| Design | Architecture | Worst mV | p99 mV | p95 mV | Mean mV | Powered instances |", "|---|---|---:|---:|---:|---:|---:|"]
    for row in summary["architectures"]:
        ir = row.get("ir", {}) if row["status"] == "QUALIFIED" else {}
        lines.append(f"| {row['design']} | {row['architecture']} | {fmt(ir.get('worst_drop_v'), 1000)} | {fmt(ir.get('p99_drop_v'), 1000)} | {fmt(ir.get('p95_drop_v'), 1000)} | {fmt(ir.get('mean_drop_v'), 1000)} | {ir.get('powered_instances', '—')} |")
    lines += ["", "## K. Current-density results", "", "Peak/p95/p99 absolute PDN segment current is reported in amperes. Current density was **NOT EVALUATED** because no qualified metal cross-section (width and thickness) was supplied. Segment current is not current density; no EM limit is applied.",
              "Full raw segment endpoints and currents are retained. Regional maximum segment-current maps use segment midpoints and are diagnostic. Mean/peak activity correspondence and fixed top-quartile hotspot IoU against those maps use the same occupied-domain and missing-value rules; these current proxies do not enter the classifier. Worst-drop instance origins and peak-current segment locations are retained in the machine summary and IR CSV.", "",
              "## L. Spatial correlations", "", "Both Pearson and average-tie-rank Spearman are reported at 4×4 and 8×8. The primary domain is occupied nonphysical Liberty-powered instance-origin bins; empty die regions are excluded. Mean regional C×N per shift cycle is compared with regional dynamic-power sum and static-IR maximum.",
              "Top-quartile IoU uses ceil(occupied bins/4), with ascending bin ID breaking value ties. Missing occupied values invalidate primary statistics; finite-subset calculations are diagnostic. Constant vectors have undefined agreement.",
              f"The preregistered proxy criterion uses all eight reference/CS_C1 architecture-grid Spearman values ≥0.5: **{'PASS' if verdict['spatial_correspondence']['passes'] else 'NOT MET' if verdict['spatial_correspondence']['complete'] else 'UNAVAILABLE'}**.",
              "Complete vectors/supports and all correlations are in `spatial_correlations.csv` and per-architecture `spatial_vectors.json`. Secondary per-bin maximum C×N maps are reconstructed from the bound retained cycle counts and crosschecked against frozen H4/H8. Different bins can peak on different cycles; correlations against averaged power and static IR do not validate transient peak prediction.", "",
              "| Design | Architecture | Grid | Mean-activity comparison | n | Pearson r | Spearman ρ | Top-quartile IoU | Status |", "|---|---|---|---|---:|---:|---:|---:|---|"]
    for row in summary["spatial_correlations"]:
        if not row["comparison"].startswith("mean_activity_"):
            continue
        lines.append(f"| {row['design']} | {row['method']} | {row['resolution']}×{row['resolution']} | {row['comparison'].removeprefix('mean_activity_vs_')} | {row['n_bins']} | {fmt(row['pearson_r'])} | {fmt(row['spearman_rho'])} | {fmt(row['hotspot_iou'])} | {row['status']} |")
    lines += ["", "All secondary peak-map statistics, hotspot bin IDs, finite-subset diagnostics and unavailable reasons are retained alongside the primary table in the CSV/JSON evidence. They do not enter the campaign classifier.", "",
              "## M. Thermal results", "", "**THERMAL_IMPACT_NOT_EVALUATED**. No thermal hotspot improvement is established.", "",
              "## N. Practical interpretation", "", "Material PI benefit requires ≥1% relative and ≥0.1 mV absolute reductions in BOTH worst and p99 drop, with ≤1% dynamic-power and peak-current regression. Modest scan-wire cost is ≤2%.", "",
              "| Design | Candidate vs reference | Δ scan WL % | Δ E % | Δ H4 % | Δ H8 % | Δ dynamic % | Δ worst IR % | Δ p99 IR % | Δ peak current % | Material PI benefit |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for row in comparisons:
        values = [fmt(row.get(field), 100) for field in ("delta_routed_scan_wire_fraction", "delta_E_fraction", "delta_H4_fraction", "delta_H8_fraction", "delta_dynamic_power_fraction", "delta_worst_ir_fraction", "delta_p99_ir_fraction", "delta_peak_segment_current_fraction")]
        flag = row["materiality"]["material_pi_benefit"]
        lines.append(f"| {row['design']} | {row['candidate']} vs {row['reference']} | " + " | ".join(values) + f" | {'—' if flag is None else 'YES' if flag else 'NO'} |")
    lines += ["", "## O. OpenROAD maintainer question — direct answer", "", direct_answer(verdict, comparisons), "",
              "## P. Go/no-go recommendation", "", f"**SHOULD PACT DEVELOPMENT CONTINUE? {verdict['recommendation']}.**", "",
              "Evidence: the tables above and bound raw records. Interpretation: the fixed materiality and correspondence rules determine the classification; smaller effects remain reported. Recommendation: " + verdict["rationale"], "",
              "## Q. Upstream issues/PRs", "", "No new upstream contribution is asserted by this report. Failed implementation attempts are retained separately from scientific architecture results; any separately qualified repair/PR is listed by the publication receipt.", "",
              "## R. Complete provenance", "", f"Scientific power runs use OpenSTA embedded in OpenROAD `{provenance['tools']['openroad']['version']}`, binary SHA-256 `{provenance['tools']['openroad']['sha256']}`, declared embedded OpenSTA revision `{provenance['installed_declared_opensta_revision']}`. Separately inventoried `/usr/bin/sta` reports `{provenance['tools']['sta']['version']}` and is not the scientific power engine.",
              provenance["source_limitation"],
              "Protocol, selected inputs, tool/Liberty hashes, smoke controls, per-attempt commands/environment/resources, raw output bindings and derived vector receipts are retained in the Gate 10A evidence tree. `runtime_resources.csv` includes failed/held/control attempts as well as scientific runs.", "",
              "## S. Next action", "", next_action(verdict["recommendation"])]
    if diagnostic:
        lines += ["", "Shared-flow diagnostic: " + diagnostic]
    if summary["qualification_errors"]:
        lines += ["", "Unresolved qualification records:", ""] + ["- " + error for error in summary["qualification_errors"]]
    return "\n".join(lines) + "\n"


def direct_answer(verdict, comparisons):
    primary = [row for row in comparisons if row["comparison_role"] == "primary"]
    if verdict["classification"].endswith("INCONCLUSIVE"):
        return "The quoted 2.4% reduction does not yet establish an IR-drop or thermal benefit. Required power/static-VDD evidence is incomplete or unqualified, so its practical impact remains unresolved. The historical question is separate from the frozen Gate 09 H4/H8 comparisons tested here. Thermal was not evaluated; no transient IR claim is supported."
    effects = []
    for row in primary:
        effects.append(f"{row['design']} CS_C1 versus {row['reference']}: H8 {fmt(row['delta_H8_fraction'], 100, '%')}, dynamic power {fmt(row.get('delta_dynamic_power_fraction'), 100, '%')}, worst static VDD drop {fmt(row.get('delta_worst_ir_fraction'), 100, '%')} ({fmt(row.get('delta_worst_ir_v'), 1000, ' mV')}), p99 drop {fmt(row.get('delta_p99_ir_fraction'), 100, '%')}")
    return "; ".join(effects) + ". " + verdict["rationale"] + " These are observed responses of an activity-derived static model; transient droop and thermal hotspot improvement were not evaluated."


def next_action(recommendation):
    return {"CONTINUE": "Consider a separately preregistered next gate only after reviewing these qualified static results; do not implement it in Gate 10A.",
            "PIVOT": "Define future PDN/power-aware objective research separately; no replacement objective or new optimization was implemented in this gate.",
            "FREEZE": "Freeze PACT algorithm development; retain the evidence and document the lack of registered material physical benefit.",
            "HOLD": "Hold algorithm development and qualify the missing or invalid measurement basis before drawing a scientific continuation, pivot or stop conclusion."}[recommendation]


def generate(manifest_path=None, diagnostic_receipt=None):
    protocol = read_json(OUT / "protocol.json")
    selection = read_json(OUT / "selected_architectures.json")
    provenance = read_json(OUT / "tool_provenance.json")
    prereg = read_json(OUT / "control/preregistration_commit.json")
    for item in prereg["files"]:
        verify(item)
    errors, records, correlations = [], [], []
    manifest, smoke, chosen = None, None, {}
    diagnostic = None
    if diagnostic_receipt is not None:
        failure = read_json(diagnostic_receipt)
        diagnostic = failure.get("error") or failure.get("reason") or failure.get("status") or "Shared flow not qualified"
        errors.append(diagnostic)
    else:
        chosen, manifest, smoke = selected_runs(manifest_path)
        registered = {(row["design"], row["architecture"]) for row in selection["architectures"]}
        if set(chosen) - registered:
            raise ValueError("Selection manifest includes unregistered architecture")
    for selected in selection["architectures"]:
        key = (selected["design"], selected["architecture"])
        if key not in chosen:
            record = dict(design=key[0], architecture=key[1], architecture_sha256=selected["architecture_sha256"],
                          frozen_metrics=selected["frozen_metrics"], status="UNAVAILABLE", reason="shared_method_unqualified" if diagnostic else "no_qualified_selected_run")
        else:
            try:
                record = qualified_record(selected, *chosen[key], protocol, prereg)
                for row in record["correlations"]:
                    row.update(design=key[0], method=key[1], architecture_sha256=selected["architecture_sha256"])
                    correlations.append(row)
            except Exception as exc:
                errors.append(f"{key[0]}/{key[1]}: {exc}")
                record = dict(design=key[0], architecture=key[1], architecture_sha256=selected["architecture_sha256"],
                              frozen_metrics=selected["frozen_metrics"], status="UNAVAILABLE", reason=str(exc))
        records.append(record)
    for design in protocol["architecture_set"]:
        group = [row for row in records if row["design"] == design and row["status"] == "QUALIFIED"]
        if len({row["pdn_geometry_sha256"] for row in group}) > 1 or len({row["sources_sha256"] for row in group}) > 1:
            errors.append(design + ": incomparable original PDN/source geometry")
            for row in group:
                row["status"] = "UNAVAILABLE"
                row["reason"] = "incomparable_common_physical_backend"
    qualified_keys = {(row["design"], row["architecture"]) for row in records if row["status"] == "QUALIFIED"}
    correlations = [row for row in correlations if (row["design"], row["method"]) in qualified_keys]
    comparisons = comparison_records(records, protocol)
    spatial_rows = [row for row in correlations if row["comparison"] == "mean_activity_vs_static_ir"]
    complete = not errors and all(row["status"] == "QUALIFIED" for row in records)
    verdict = decision.classify_campaign(comparisons, spatial_rows, evidence_complete=complete)
    summary = dict(schema="pact_gate10a_machine_summary_v1", campaign=protocol["campaign"], external_question=protocol["external_question"],
                   published_parent=protocol["published_parent"], preregistration_commit=prereg["commit"],
                   selection_manifest=None if manifest_path is None else binding(manifest_path),
                   smoke_qualification=smoke, diagnostic_receipt=None if diagnostic_receipt is None else binding(diagnostic_receipt),
                   independent_numeric_support=(binding(OUT / "control/independent_numeric_support.json")
                                                if (OUT / "control/independent_numeric_support.json").exists() else None),
                   architectures=[{key: value for key, value in row.items() if key not in ("grids", "correlations")} for row in records],
                   comparisons=comparisons, spatial_correlations=correlations, decision=verdict, qualification_errors=errors,
                   thermal_status="THERMAL_IMPACT_NOT_EVALUATED", power_model=protocol["power_model"], ir_model=protocol["ir_model"],
                   new_scientific_stages=dict(ATPG=0, PACT_search=0, placement=0, routing=0, extraction=0, replay=0))
    power_rows = [dict(design=row["design"], architecture=row["architecture"], status=row["status"], reason=row.get("reason"), **(row.get("power", {}) if row["status"] == "QUALIFIED" else {})) for row in records]
    ir_rows = [dict(design=row["design"], architecture=row["architecture"], status=row["status"], reason=row.get("reason"), **(dict(row["ir"], **row["current"]) if row["status"] == "QUALIFIED" else {})) for row in records]
    for path, rows, initial in (("power_results.csv", power_rows, ["design", "architecture", "status", "reason", "dynamic_w", "switching_w", "internal_w", "leakage_w", "total_w"]),
                                ("ir_results.csv", ir_rows, ["design", "architecture", "status", "reason", "worst_drop_v", "p99_drop_v", "p95_drop_v", "p50_drop_v", "mean_drop_v", "peak_segment_current_a"]),
                                ("spatial_correlations.csv", correlations, ["design", "method", "resolution", "comparison", "status", "reason", "n_bins", "pearson_r", "spearman_rho", "hotspot_iou", "hotspot_k"]),
                                ("runtime_resources.csv", runtime_rows(path for path, _ in chosen.values()), ["design", "architecture", "attempt", "status", "density_scale", "selected_scientific_record", "wall_seconds", "CPU_user_seconds", "CPU_system_seconds", "peak_RSS_bytes", "disk_bytes"]),
                                ("final_comparison.csv", comparisons, ["design", "candidate", "reference", "comparison_role", "status", "reason", *decision.DELTA_FIELDS])):
        fields = initial + sorted({key for row in rows for key in row if key not in initial and key != "materiality"})
        write_csv(OUT / path, rows, fields)
    write_json(OUT / "machine_summary.json", summary)
    write_json(OUT / "decision.json", verdict)
    (OUT / "report.md").write_text(report_text(summary, comparisons, provenance, diagnostic), encoding="utf-8")
    publication = ROOT / "publication/openroad_discussion_gate10a_reply.md"
    publication.parent.mkdir(parents=True, exist_ok=True)
    publication.write_text("# Draft OpenROAD discussion response — not posted\n\n" + direct_answer(verdict, comparisons)
        + "\n\nEstablished: frozen Gate 09 activity and routed-wire differences. Observed: qualified Gate 10A architecture responses in the supplied tables, when available. Approximate: fixed-duty activity-derived OpenSTA power and static VDD PDNSim under ideal stripe-end supplies. Not evaluated: transient scan droop, thermal hotspots, ground bounce, package effects and signoff reliability.\n\n"
        + f"Classification: `{verdict['classification']}`. Development recommendation: **{verdict['recommendation']}**. The full data and provenance are in `reports/gate10a/report.md` and its linked CSV/JSON records.\n", encoding="utf-8")
    outputs = [binding(OUT / name) for name in ("power_results.csv", "ir_results.csv", "spatial_correlations.csv", "runtime_resources.csv", "final_comparison.csv", "machine_summary.json", "decision.json", "report.md")]
    outputs.append(binding(publication))
    content_id = hashlib.sha256(json.dumps(outputs, sort_keys=True).encode()).hexdigest()
    write_json(OUT / "control" / ("report_generation_" + content_id[:16] + ".json"),
               dict(schema="pact_gate10a_report_derivation_v1", inputs=[binding(OUT / name) for name in ("protocol.json", "selected_architectures.json", "tool_provenance.json")],
                    selection_manifest=summary["selection_manifest"], diagnostic_receipt=summary["diagnostic_receipt"],
                    reporter=binding(Path(__file__)), decision_module=binding(ROOT / "src/pact/gate10a_decision.py"),
                    spatial_module=binding(ROOT / "src/pact/gate10a_spatial.py"), outputs=outputs), immutable=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--run-manifest", type=Path, default=OUT / "control/scientific_run_selection.json")
    group.add_argument("--diagnostic-receipt", type=Path)
    args = parser.parse_args()
    summary = generate(None if args.diagnostic_receipt else args.run_manifest, args.diagnostic_receipt)
    print(json.dumps(dict(classification=summary["decision"]["classification"], recommendation=summary["decision"]["recommendation"],
                         qualified_architectures=sum(row["status"] == "QUALIFIED" for row in summary["architectures"]))))
