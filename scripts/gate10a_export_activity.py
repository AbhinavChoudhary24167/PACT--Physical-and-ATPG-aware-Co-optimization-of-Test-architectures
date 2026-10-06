#!/usr/bin/env python3
"""Regenerate Gate10A per-net activity inputs from frozen compact counts.

Uses <=512 count rows in memory; no PACT search, ATPG or simulation runs.
Every input is checked against preregistered frozen Gate09 expected hashes.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import platform
import struct
import subprocess
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "src")]
from gate10a_audit import digest, resolve, SELECTION
from pact.analysis.phase2b_reference import parse_spef


def checked(expected):
    path = resolve(expected["path"])
    if path is None or not path.is_file():
        raise ValueError("Required frozen input missing: " + expected["path"])
    observed = digest(path)
    if observed != {key: expected[key] for key in ("sha256", "bytes")}:
        raise ValueError("Frozen input identity mismatch: " + expected["path"])
    return path, {"expected": expected, "observed": observed, "status": "PASS"}


def stream_totals(path, names, cycles, chunk_cycles=512):
    if not 1 <= chunk_cycles <= 512:
        raise ValueError("Count chunks must be between 1 and 512 cycles")
    def exact(stream, size):
        value = stream.read(size)
        if len(value) != size:
            raise ValueError("Incomplete compact activity output")
        return value
    totals = np.zeros(len(names), dtype=np.uint64)
    with gzip.open(path, "rb") as stream:
        if exact(stream, 8) != b"PACTCN01":
            raise ValueError("Unknown count format")
        width, recorded_cycles = struct.unpack("<II", exact(stream, 8))
        if (width, recorded_cycles) != (len(names), cycles):
            raise ValueError("Count dimensions differ from frozen workload/mapping")
        recorded = [exact(stream, struct.unpack("<I", exact(stream, 4))[0]).decode("utf-8")
                    for _ in range(width)]
        if recorded != names:
            raise ValueError("Count net names/order differs from frozen mapping")
        for first in range(0, cycles, chunk_cycles):
            length = min(chunk_cycles, cycles - first)
            values = np.frombuffer(exact(stream, length * width), dtype=np.uint8).reshape(length, width)
            totals += values.sum(axis=0, dtype=np.uint64)
        if exact(stream, 8) != b"PACTDONE" or stream.read(1):
            raise ValueError("Invalid completion footer/trailing output")
    return totals, {"status": "PASS", "format": "PACTCN01", "complete": True,
                    "gzip_crc": "PASS", "cycles": cycles, "mapped_nets": len(names),
                    "payload_bytes": cycles * len(names), "maximum_count_rows_in_memory": chunk_cycles,
                    "logic_high_occupancy_available": False}


def export(row, output_root, prereg_commit, selection_binding):
    folder = output_root / row["design"] / row["architecture"]
    if folder.exists():
        raise ValueError("Preserve existing activity export: " + str(folder))
    started = datetime.now(timezone.utc).isoformat()
    wall_start, cpu_start = time.perf_counter(), time.process_time()
    records = []
    parser_relative = "src/pact/analysis/phase2b_reference.py"
    frozen_parser = subprocess.check_output(["git", "show", row["parent_published_commit"] + ":" + parser_relative], cwd=ROOT)
    parser_binding = {"path": "repo://" + parser_relative, "bytes": len(frozen_parser),
                      "sha256": hashlib.sha256(frozen_parser).hexdigest()}
    _, parser_record = checked(parser_binding)
    records.append(parser_record)
    inputs = row["exact_inputs"]
    for expected in (row["count_trace"], inputs["net_mapping.json"], inputs["extracted.spef"], row["frozen_result"]):
        _, record = checked(expected)
        records.append(record)
    mapping = json.loads(resolve(inputs["net_mapping.json"]["path"]).read_text(encoding="utf-8"))
    names = sorted(mapping["nets"])
    totals, structure = stream_totals(resolve(row["count_trace"]["path"]), names, row["cycles"])
    spef = parse_spef(resolve(inputs["extracted.spef"]["path"]).read_text(encoding="utf-8"))
    caprows = []
    for name, total in zip(names, totals, strict=True):
        info, parasitic = mapping["nets"][name], spef.get(name)
        if parasitic is None and total:
            raise ValueError("Switched net missing SPEF: " + name)
        x, y = info["xy_um"]
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("Nonfinite source coordinate")
        capacitance = None if parasitic is None else parasitic["ground_ff"] + info["pin_cap_ff"]
        caprows.append({"net": name, "source": info["source"], "x_um": x, "y_um": y,
                        "scope_scan_data": info["scan_data"], "transitions": int(total),
                        "ground_ff": None if parasitic is None else parasitic["ground_ff"],
                        "incident_coupling_ff": None if parasitic is None else parasitic["coupling_ff"],
                        "pin_ff": info["pin_cap_ff"], "ground_pin_ff": capacitance,
                        "cap_status": "EXTRACTED" if parasitic else "MISSING_STATIC_NET_EXCLUDED"})
    expected_summary_path = Path(resolve(row["frozen_result"]["path"])).parent / "activity_summary.json"
    relative_summary = expected_summary_path.relative_to(ROOT).as_posix()
    frozen_summary_bytes = subprocess.check_output(["git", "show", row["parent_published_commit"] + ":" + relative_summary], cwd=ROOT)
    expected_summary = {"path": "repo://" + relative_summary, "bytes": len(frozen_summary_bytes),
                        "sha256": hashlib.sha256(frozen_summary_bytes).hexdigest()}
    _, record = checked(expected_summary)
    records.append(record)
    summary = json.loads(frozen_summary_bytes)
    integrity = {}
    for scope in ("all_data", "scan_data"):
        included = caprows if scope == "all_data" else [item for item in caprows if item["scope_scan_data"]]
        transitions = sum(item["transitions"] for item in included)
        weighted = math.fsum((item["ground_pin_ff"] or 0.0) * item["transitions"] for item in included)
        frozen_scope = summary["scopes"][scope]
        frozen_weighted = frozen_scope["cap_weighted_ff_transitions"]["total"]
        if transitions != frozen_scope["transitions"]["total"] or not math.isclose(weighted, frozen_weighted, rel_tol=1e-12, abs_tol=1e-7):
            raise ValueError("Frozen aggregate activity integrity mismatch: " + scope)
        integrity[scope] = {"status": "PASS", "transition_sum": transitions,
                            "cap_weighted_sum": weighted, "frozen_cap_weighted_sum": frozen_weighted,
                            "cap_weighted_relative_tolerance": 1e-12, "cap_weighted_absolute_tolerance": 1e-7}
    q_population = len({item["source"][:-2] for item in mapping["nets"].values() if item["source"].endswith("/Q")})
    if q_population != row["ff_count"]:
        raise ValueError("Expected FF Q population mismatch")
    folder.mkdir(parents=True)
    csv_path = folder / "net_activity_capacitance.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(caprows[0]))
        writer.writeheader()
        writer.writerows(caprows)
    receipt = {"schema": "pact_gate10a_frozen_activity_export_v1", "status": "PASS",
               "started_utc": started, "completed_utc": datetime.now(timezone.utc).isoformat(),
               "preregistered_commit": prereg_commit, "parent_published_commit": row["parent_published_commit"],
               "selection_binding": selection_binding, "design": row["design"], "architecture": row["architecture"],
               "architecture_sha256": row["architecture_sha256"], "FF_Q_population": q_population,
               "input_verifications": records, "complete_count_validation": structure,
               "aggregate_integrity": integrity, "bounds_um": mapping["bounds_um"],
               "source_attribution": mapping["attribution"], "scan_cycles": row["cycles"],
               "capacitance": "OpenRCX ground + Liberty sink pin fF; coupling excluded from frozen primary proxy",
               "output": {"path": str(csv_path), **digest(csv_path)},
               "runtime": {"wall_seconds": time.perf_counter() - wall_start, "CPU_seconds": time.process_time() - cpu_start,
                           "peak_RSS_bytes": None, "peak_RSS_reason": "Exporter uses bounded count chunks; native process RSS recorded by campaign runner where available"},
               "tools": {"python": platform.python_version(), "numpy": np.__version__},
               "exporter_source": {"path": str(Path(__file__).resolve()), **digest(Path(__file__).resolve())},
               "command": sys.argv, "scientific_stages_reexecuted": 0,
               "activity_values": "Existing frozen settled transition counts; no new replay or logic-duty inference"}
    receipt_path = folder / "activity_export_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("EXPORTED", row["design"], row["architecture"], flush=True)
    return {"path": str(receipt_path), **digest(receipt_path)}


def run(selection_path, output_root, prereg_commit, only):
    # Require an actual committed preregistration before deriving analysis inputs.
    subprocess.check_output(["git", "show", prereg_commit + ":reports/gate10a/preregistration.md"], cwd=ROOT)
    relative = selection_path.resolve().relative_to(ROOT).as_posix()
    frozen = subprocess.check_output(["git", "show", prereg_commit + ":" + relative], cwd=ROOT)
    selection_binding = {"path": "repo://" + relative, "bytes": len(frozen), "sha256": hashlib.sha256(frozen).hexdigest()}
    checked(selection_binding)
    selection = json.loads(frozen)
    if selection["selection"] != SELECTION:
        raise ValueError("Preregistered selection differs from required frozen set")
    receipts = []
    for row in selection["architectures"]:
        if only and row["design"] + "/" + row["architecture"] not in only:
            continue
        row["parent_published_commit"] = selection["parent_published_commit"]
        receipts.append(export(row, output_root, prereg_commit, selection_binding))
    return receipts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, default=ROOT / "reports/gate10a/selected_architectures.json")
    parser.add_argument("--output-root", type=Path, default=ROOT / "reports/gate10a/inputs")
    parser.add_argument("--preregistered-commit", required=True)
    parser.add_argument("--only", action="append", help="Restrict to design/architecture (repeatable)")
    args = parser.parse_args()
    print(json.dumps(run(args.selection, args.output_root, args.preregistered_commit, args.only), indent=2))
