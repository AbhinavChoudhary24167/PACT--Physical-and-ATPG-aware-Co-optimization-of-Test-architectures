#!/usr/bin/env python3
"""Seal shared Gate10A controls using preregistered SI tolerances."""
import argparse
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from gate10a_run import ROOT, OUT, binding, verify, frozen


def records(folder, filename, keys, numeric):
    with (folder / filename).open() as stream:
        rows = list(csv.DictReader(stream))
    output = {}
    for row in rows:
        key = tuple(row[k] for k in keys)
        if key in output:
            raise ValueError("Duplicate control key in " + filename)
        output[key] = tuple(float(row[k]) * scale for k, scale in numeric)
    if not output or not all(math.isfinite(v) for values in output.values() for v in values):
        raise ValueError("Empty/nonfinite control records in " + filename)
    return output


def run(args):
    output = OUT / "control/smoke_qualification.json"
    if output.exists():
        raise ValueError("Preserve immutable shared qualification")
    protocol, protocol_binding = frozen("reports/gate10a/protocol.json", args.preregistered_commit)
    result = {"schema": "pact_gate10a_smoke_qualification_v1", "status": "STARTED",
              "started_utc": datetime.now(timezone.utc).isoformat(), "preregistered_commit": args.preregistered_commit,
              "protocol": protocol_binding, "source": binding(Path(__file__)),
              "design": "b14_opt", "architecture": "B3T", "records": [], "checks": {}}
    try:
        labels = [args.nominal, args.repeat, args.zero, args.double]
        expected_scales = [1.0, 1.0, 0.0, 2.0]
        receipts = []
        folders = []
        for label, scale in zip(labels, expected_scales):
            folder = OUT / "runs/b14_opt/B3T" / label
            path = folder / "receipt.json"
            receipt = json.loads(path.read_text())
            if receipt["status"] != "QUALIFIED" or receipt["nonclock_density_scale"] != scale or receipt["preregistered_commit"] != args.preregistered_commit:
                raise ValueError("Unqualified/mismatched shared control " + label)
            if receipt["result"].get("parser_coordinate_connectivity_integrity") != "PASS" or receipt["result"].get("native_power_integrity", {}).get("status") != "PASS":
                raise ValueError("Shared control lacks complete parser/native/coordinate qualification")
            for item in receipt["outputs"]:
                verify(item)
            folders.append(folder)
            receipts.append(receipt)
            result["records"].append(binding(path))
        fingerprints = [{Path(item["path"]).name: item["sha256"] for item in r["execution_source_snapshots"]
                         if Path(item["path"]).name in ("runner_source.py", "measurement_source.tcl")} for r in receipts]
        if len(fingerprints[0]) != 2 or any(f != fingerprints[0] for f in fingerprints[1:]):
            raise ValueError("Shared control source fingerprints differ")
        result["flow_fingerprint"] = fingerprints[0]
        for key in ("sources_sha256", "pdn_geometry_sha256"):
            if len({r["result"][key] for r in receipts}) != 1:
                raise ValueError("Frozen source/PDN geometry differs between controls")
        atol = protocol["reproducibility_absolute_SI_tolerance"]
        rtol = protocol["reproducibility_relative_tolerance"]
        layouts = [
            ("instance_power.csv", ["instance"], [("x_um", 1e-6), ("y_um", 1e-6), ("internal_w", 1), ("switching_w", 1), ("leakage_w", 1), ("total_w", 1)]),
            ("instance_voltage.csv", ["Instance", "Terminal", "Layer", "X location", "Y location"], [("X location", 1e-6), ("Y location", 1e-6), ("Voltage", 1)]),
            ("segment_current.csv", ["Node0 Layer", "Node0 X location", "Node0 Y location", "Node1 Layer", "Node1 X location", "Node1 Y location"], [("Current", 1)])]
        for filename, keys, numeric in layouts:
            first, second = [records(f, filename, keys, numeric) for f in folders[:2]]
            if first.keys() != second.keys():
                raise ValueError("Nominal-repeat population differs: " + filename)
            maximum_absolute = 0.0
            for key in first:
                for a, b in zip(first[key], second[key]):
                    maximum_absolute = max(maximum_absolute, abs(a - b))
                    if not math.isclose(a, b, rel_tol=rtol, abs_tol=atol):
                        raise ValueError("Nominal-repeat numeric mismatch: " + filename)
            result["checks"][filename] = {"status": "PASS", "population": len(first), "maximum_absolute_SI_difference": maximum_absolute}
        s1, sr, s0, s2 = [r["result"]["power"]["switching_w"] for r in receipts]
        delta1, delta2 = s1 - s0, s2 - s0
        if not delta1 > atol:
            raise ValueError("Activity ingestion control has no positive nonclock switching response")
        if not math.isclose(delta2, 2 * delta1, rel_tol=protocol["switching_linearity_relative_tolerance"], abs_tol=atol):
            raise ValueError("Nonclock switching density linearity failed")
        native_reports = [json.loads((f / "power_report.json").read_text()) for f in folders]
        clock = [float(r["Clock"]["switching"]) for r in native_reports]
        if not all(math.isclose(v, clock[0], rel_tol=rtol, abs_tol=atol) for v in clock):
            raise ValueError("Clock switching changed with nonclock control")
        result["checks"]["density_linearity"] = {"status": "PASS", "switching_density0_w": s0,
            "switching_density1_w": s1, "switching_density2_w": s2,
            "nonclock_response1_w": delta1, "nonclock_response2_w": delta2,
            "absolute_residual_w": abs(delta2 - 2 * delta1), "relative_tolerance": protocol["switching_linearity_relative_tolerance"],
            "absolute_tolerance_w": atol, "fixed_clock_switching_w": clock[0]}
        result["invalidated_receipts"] = []
        for folder in sorted((OUT / "runs/b14_opt/B3T").iterdir()):
            path = folder / "receipt.json"
            if path.exists() and folder not in folders:
                prior = json.loads(path.read_text())
                if prior.get("status") == "QUALIFIED":
                    result["invalidated_receipts"].append(binding(path))
        result["invalidation_reason"] = "Earlier locally complete attempts predate shared-qualified ingestion/parser/source implementation; attempt4 masks frozen nonclock activity. Source mismatch excludes all provisional attempts. Original receipts remain preserved."
        result["invalidation_diagnostic"] = binding(OUT / "control/smoke_attempt4_invalidation.json")
        result["nominal_architecture_receipt"] = binding(folders[0] / "receipt.json")
        result["PG_normalization_audit"] = binding(OUT / "control/pg_connectivity_normalization.json")
        result["status"] = "PASS"
    except Exception as exc:
        result["status"] = "FAIL"
        result["error"] = str(exc)
    result["completed_utc"] = datetime.now(timezone.utc).isoformat()
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "receipt": str(output.relative_to(ROOT)), "error": result.get("error")}))
    return result["status"] == "PASS"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("nominal", "repeat", "zero", "double", "preregistered_commit"):
        parser.add_argument("--" + name.replace("_", "-"), required=True)
    raise SystemExit(0 if run(parser.parse_args()) else 2)
