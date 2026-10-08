#!/usr/bin/env python3
"""Read-only Gate09 reuse audit anchored to the published Git parent.

This verifies frozen input identities and count-file structure. It never runs
ATPG, PACT, placement, routing, extraction, simulation or physical analysis.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
GATE09 = "results/pact_gate09_open_source_20261005"
PUBLISHED_PARENT = "53ebab37fd76970d7c5e676b0caec13c7c16296e"
SELECTION = {"b14_opt": ["B3T", "CS_C1", "CS_C3", "B5"],
             "b15_opt": ["B2", "CS_C1", "CS_C2", "CS_C3", "B5"]}


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return {"sha256": h.hexdigest(), "bytes": path.stat().st_size}


def resolve(path):
    if path.startswith("repo://"):
        return ROOT / path[7:]
    if path.startswith("/mnt/"):
        match = re.match(r"/mnt/([a-z])/(.*)", path)
        if match and os.name == "nt":
            return Path(match[1].upper() + ":/" + match[2])
    if path.startswith("/") and os.name == "nt":
        return None  # Linux-resident tools qualified by the flow lane.
    return Path(path) if Path(path).is_absolute() else ROOT / path


def bindings(value, pointer=""):
    if isinstance(value, dict):
        if isinstance(value.get("path"), str) and isinstance(value.get("sha256"), str):
            yield value, pointer
        else:
            for key, child in value.items():
                yield from bindings(child, pointer + "/" + key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from bindings(child, pointer + "/" + str(index))


def git_bytes(parent, relative):
    return subprocess.check_output(["git", "show", parent + ":" + relative], cwd=ROOT)


def count_structure(path, names, cycles):
    """Check exact names, complete payload, footer and gzip CRC without analytics."""
    def exact(stream, size):
        data = stream.read(size)
        if len(data) != size:
            raise ValueError("Incomplete compact activity file")
        return data
    with gzip.open(path, "rb") as stream:
        if exact(stream, 8) != b"PACTCN01":
            raise ValueError("Unknown compact activity format")
        width, recorded_cycles = struct.unpack("<II", exact(stream, 8))
        if (width, recorded_cycles) != (len(names), cycles):
            raise ValueError("Count dimensions differ from frozen mapping/workload")
        recorded_names = [exact(stream, struct.unpack("<I", exact(stream, 4))[0]).decode("utf-8")
                          for _ in range(width)]
        if recorded_names != names:
            raise ValueError("Count net names differ from frozen mapping")
        remaining = width * recorded_cycles
        while remaining:
            block = exact(stream, min(1024 * 1024, remaining))
            remaining -= len(block)
        if exact(stream, 8) != b"PACTDONE" or stream.read(1):
            raise ValueError("Invalid completion footer or trailing bytes")
    return {"status": "PASS", "format": "PACTCN01", "cycles": cycles,
            "mapped_nets": width, "payload_bytes": width * cycles,
            "gzip_crc": "PASS", "logic_high_occupancy_recorded": False}


class Audit:
    def __init__(self, parent):
        self.parent = parent
        self.records = {}
        self.jsons = {}

    def frozen(self, relative):
        expected = git_bytes(self.parent, relative)
        binding = {"path": "repo://" + relative, "bytes": len(expected),
                   "sha256": hashlib.sha256(expected).hexdigest()}
        record = self.verify(binding, {"kind": "published_git_blob",
                                      "commit": self.parent, "path": relative})
        if record["status"] != "PASS":
            raise ValueError("Frozen parent file changed: " + relative)
        value = json.loads(expected)
        self.jsons[binding["path"]] = value
        return value, binding

    def verify(self, expected, source):
        key = (expected["path"], expected["sha256"])
        if key in self.records:
            result = self.records[key]
            if source not in result["expected_from"]:
                result["expected_from"].append(source)
            return result
        path = resolve(expected["path"])
        result = {"expected": expected, "expected_from": [source],
                  "resolved_path": str(path) if path else None}
        if path is None:
            result["status"] = "LINUX_TOOL_CHECK_DELEGATED_TO_FLOW_LANE"
        elif not path.is_file():
            result["status"] = "MISSING"
        else:
            observed = digest(path)
            result["observed"] = observed
            result["status"] = "PASS" if observed["sha256"] == expected["sha256"] and (
                "bytes" not in expected or observed["bytes"] == expected["bytes"]) else "FAIL"
        if result["status"] in ("FAIL", "MISSING"):
            snapshot = ROOT / GATE09 / "publication/execution_sources" / (expected["sha256"] + ".py")
            if snapshot.is_file() and digest(snapshot)["sha256"] == expected["sha256"]:
                result.update(status="PASS", resolved_path=str(snapshot),
                              observed=digest(snapshot), preserved_execution_source=True)
        self.records[key] = result
        return result

    def descend(self, value, source_path, *, depth=0):
        if depth > 20:
            raise ValueError("Receipt provenance recursion exceeded")
        for expected, pointer in bindings(value):
            record = self.verify(expected, {"kind": "frozen_receipt_binding",
                                          "receipt": source_path, "json_pointer": pointer})
            key = expected["path"]
            dataset = Path(key).name in ("cycles.json", "workload.json", "ff_identity_map.json")
            # Verify original preparation receipts by their frozen hash, but do
            # not expand their historical/cohort graph: those stages are not
            # Gate10A inputs. Exact inputs and final qualification are expanded.
            historical_graph = pointer.split("/")[1] in (
                "Gate09_preparation", "source_manifest", "source_preparation",
                "frozen_simulation_manifest", "preselection", "frozen_method")
            if record["status"] == "PASS" and key not in self.jsons and key.endswith(".json") and not dataset and not historical_graph:
                path = Path(record["resolved_path"])
                self.jsons[key] = json.loads(path.read_text(encoding="utf-8"))
                self.descend(self.jsons[key], key, depth=depth + 1)


def run(parent, output_dir, check_payload):
    for name in ("selected_architectures.json", "artifact_reuse_manifest.json"):
        if (output_dir / name).exists():
            raise ValueError("Preserve existing audit/selection; use a new --output-dir: " + str(output_dir / name))
    audit = Audit(parent)
    publication = []
    pubfiles = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", parent,
                                       GATE09 + "/publication", GATE09 + "/final"], cwd=ROOT).decode().splitlines()
    for relative in pubfiles:
        if relative.endswith(".json"):
            value, binding = audit.frozen(relative)
            publication.append(binding)
    resolution = audit.jsons["repo://" + GATE09 + "/publication/integration_qualification/resolution.json"]
    for key in ("previous_qualification",):
        audit.verify(resolution[key], {"kind": "frozen_receipt_binding", "receipt": resolution["schema"], "json_pointer": "/" + key})
    integrity = audit.jsons["repo://" + GATE09 + "/publication/integration_qualification/qualification.json"]
    audit.verify(integrity["preintegration_audit"], {"kind": "frozen_receipt_binding", "receipt": integrity["schema"], "json_pointer": "/preintegration_audit"})
    selections = []
    for design, roles in SELECTION.items():
        comparison_path = "repo://" + GATE09 + "/final/" + design + "/comparison.json"
        comparison = audit.jsons[comparison_path]
        attempt = "python_transport" if design == "b14_opt" else "metadata_registration_b15_opt"
        for role in roles:
            row = next(item for item in comparison["rows"] if item["role"] == role)
            audit.descend(row, comparison_path)
            normal = GATE09 + "/repair_attempts/" + attempt + "/activity/GATE09_PRIMARY/" + design + "/" + role + "/normal/"
            result, result_binding = audit.frozen(normal + "result.json")
            summary, summary_binding = audit.frozen(normal + "activity_summary.json")
            crosscheck, crosscheck_binding = audit.frozen(normal + "FF_transition_crosscheck.json")
            audit.descend(result, result_binding["path"])
            manifest = audit.jsons[row["exact_manifest"]["path"]]
            folder = result["output_folder"]
            trace = summary["activity_trace"]
            count_binding = {"path": folder + "/activity.counts.gz", "bytes": trace["bytes"], "sha256": trace["sha256"]}
            audit.verify(count_binding, {"kind": "frozen_git_summary_binding", "receipt": summary_binding["path"], "json_pointer": "/activity_trace"})
            if trace != row["exact_trace"]:
                raise ValueError("Comparison and frozen activity summary trace disagree")
            mapping_path = manifest["inputs"]["net_mapping.json"]["path"]
            mapping = audit.jsons[mapping_path]
            ff_names = [item["source"][:-2] for item in mapping["nets"].values() if item["source"].endswith("/Q")]
            if len(set(ff_names)) != row["ff_count"]:
                raise ValueError("Expected FF Q population mismatch")
            structural = count_structure(resolve(count_binding["path"]), sorted(mapping["nets"]), row["cycles"]) if check_payload else {"status": "NOT_CHECKED"}
            for name, binding in (("activity_summary.json", summary_binding), ("result.json", result_binding), ("FF_transition_crosscheck.json", crosscheck_binding)):
                external = {"path": folder + "/" + name, "bytes": binding["bytes"], "sha256": binding["sha256"]}
                audit.verify(external, {"kind": "identical_copy_of_frozen_git_receipt", "receipt": binding["path"]})
            route = manifest["rows"][0]["qualification"]
            route_receipt = audit.jsons[route["path"]]
            if route_receipt["architecture_sha256"] != row["architecture_hash"] or route_receipt["status"] != "QUALIFIED":
                raise ValueError("Route identity/qualification mismatch")
            selections.append({"design": design, "architecture": role, "architecture_sha256": row["architecture_hash"],
                               "frozen_comparison": comparison_path, "frozen_result": result_binding,
                               "source_reference": comparison["reference_method"], "primary_candidate": comparison["primary_candidate"],
                               "ff_count": row["ff_count"], "patterns": row["patterns"], "cycles": row["cycles"],
                               "mapped_nets": row["mapped_nets"], "qualification_status": row["qualification_status"],
                               "frozen_metrics": {key: row[key] for key in ("E", "H4", "H8", "routed_scan_wirelength_um", "WNS", "hold_WNS", "DRC")},
                               "common_inputs": row["common_inputs"], "SDC": row["SDC"],
                               "source_netlist": row["source_netlist"], "source_placed_database": row["source_placed_database"],
                               "exact_manifest": row["exact_manifest"], "exact_folder": folder,
                               "routed_archive": manifest["rows"][0]["routed_archive"],
                               "exact_inputs": manifest["inputs"], "count_trace": count_binding,
                               "count_structure": structural, "FF_crosscheck": crosscheck,
                               "FF_Q_population": len(set(ff_names)), "bounds_um": mapping["bounds_um"],
                               "attribution": mapping["attribution"], "VCD_available": False,
                               "VCD_reason": manifest["stimulus_change"], "logic_high_occupancy_available": False,
                               "unsealed_derived_files": ["net_activity_capacitance.csv", "spatial_bins.json", "per_cycle.csv"],
                               "derived_file_policy": "Regenerate deterministically from frozen hash-verified counts/mapping/SPEF; current bytes alone are not frozen provenance"})
            print("verified", design, role, flush=True)
    statuses = Counter(record["status"] for record in audit.records.values())
    failures = [record for record in audit.records.values() if record["status"] in ("FAIL", "MISSING")]
    selected = {"schema": "pact_gate10a_selected_architectures_v1", "campaign": "PACT_GATE10A_PRACTICAL_IMPACT_VALIDATION",
                "parent_published_commit": parent, "selection_basis": "User required frozen Gate09 set; no Gate10A outcomes considered",
                "selection": SELECTION, "architectures": selections}
    manifest = {"schema": "pact_gate10a_artifact_reuse_manifest_v1", "created_utc": datetime.now(timezone.utc).isoformat(),
                "parent_published_commit": parent, "sealed_scientific_commit": resolution["sealed_scientific_commit"],
                "status": "PASS" if not failures else "FAIL", "scientific_stages_executed": 0,
                "method": "Current bytes compared to expected SHA256 in frozen published Git blobs, then verified receipt bindings followed transitively",
                "publication_receipts": publication, "status_counts": dict(statuses), "failures": failures,
                "records": list(audit.records.values()), "architectures_verified": len(selections),
                "payload_validation": check_payload, "ATPG_required": False,
                "FAN_repair_sha": "4c253bfa613e5827f17c42a5fce8be7bea779e1e",
                "limitations": ["No Gate09 VCD was emitted for exact compact-count primary packages",
                                "Settled count traces contain no logic-high occupancy or subcycle waveforms",
                                "Linux-resident tool/source hashes are assigned to the power/IR flow qualification lane",
                                "Unbound raw derived CSV/spatial maps require deterministic regeneration before analysis"]}
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in (("selected_architectures.json", selected), ("artifact_reuse_manifest.json", manifest)):
        (output_dir / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": manifest["status"], "counts": dict(statuses), "architectures": len(selections)}, indent=2))
    return not failures


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", default=PUBLISHED_PARENT)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports/gate10a")
    parser.add_argument("--skip-payload-check", action="store_true")
    args = parser.parse_args()
    raise SystemExit(0 if run(args.parent, args.output_dir, not args.skip_payload_check) else 2)
