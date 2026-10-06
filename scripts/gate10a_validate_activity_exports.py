#!/usr/bin/env python3
"""Seal the nine verified activity exports without rereading count payloads."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

from gate10a_audit import ROOT, SELECTION, digest, resolve


def validate(preregistered_commit, output):
    if output.exists():
        raise ValueError("Preserve existing full-count validation receipt")
    selection_relative = "reports/gate10a/selected_architectures.json"
    frozen = subprocess.check_output(["git", "show", preregistered_commit + ":" + selection_relative], cwd=ROOT)
    expected_selection = {"path": "repo://" + selection_relative, "sha256": hashlib.sha256(frozen).hexdigest(), "bytes": len(frozen)}
    if digest(ROOT / selection_relative) != {key: expected_selection[key] for key in ("sha256", "bytes")}:
        raise ValueError("Preregistered selection bytes changed")
    selected = json.loads(frozen)
    if selected["selection"] != SELECTION:
        raise ValueError("Architecture set changed")
    records = []
    for row in selected["architectures"]:
        receipt_path = ROOT / "reports/gate10a/inputs" / row["design"] / row["architecture"] / "activity_export_receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        count = receipt["complete_count_validation"]
        count_input = next(record for record in receipt["input_verifications"] if record["expected"]["path"] == row["count_trace"]["path"])
        assert receipt["status"] == "PASS" and receipt["preregistered_commit"] == preregistered_commit
        assert receipt["architecture_sha256"] == row["architecture_sha256"]
        assert count["status"] == "PASS" and count["complete"] and count["gzip_crc"] == "PASS"
        assert (count["cycles"], count["mapped_nets"]) == (row["cycles"], row["mapped_nets"])
        assert receipt["FF_Q_population"] == row["ff_count"]
        assert count_input["expected"] == row["count_trace"] and count_input["status"] == "PASS"
        assert all(item["status"] == "PASS" for item in receipt["input_verifications"])
        assert all(item["status"] == "PASS" for item in receipt["aggregate_integrity"].values())
        output_csv = receipt["output"]
        if digest(resolve(output_csv["path"])) != {key: output_csv[key] for key in ("sha256", "bytes")}:
            raise ValueError("Derived activity CSV bytes changed")
        records.append({"design": row["design"], "architecture": row["architecture"], "status": "PASS",
                        "receipt": {"path": str(receipt_path), **digest(receipt_path)},
                        "frozen_count_trace": row["count_trace"], "complete_count_validation": count,
                        "expected_FF_population": row["ff_count"], "observed_FF_Q_population": receipt["FF_Q_population"],
                        "aggregate_integrity": receipt["aggregate_integrity"], "regenerated_CSV": output_csv})
    result = {"schema": "pact_gate10a_complete_count_validation_v1", "status": "PASS",
              "created_utc": datetime.now(timezone.utc).isoformat(), "preregistered_commit": preregistered_commit,
              "parent_published_commit": selected["parent_published_commit"], "frozen_selection": expected_selection,
              "architectures_validated": len(records), "counts_payloads_read_again": 0,
              "method": "Bind completed bounded-stream exporter receipts and rehash derived CSVs; each exporter checked frozen raw hash before its sole complete payload read",
              "scientific_stages_reexecuted": 0, "records": records}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": result["status"], "architectures_validated": len(records), "receipt": {"path": str(output), **digest(output)}}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preregistered-commit", required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "reports/gate10a/control/full_count_validation.json")
    args = parser.parse_args()
    validate(args.preregistered_commit, args.output)
