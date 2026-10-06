#!/usr/bin/env python3
"""Select earliest admissible nominal receipts using metadata only; audit hashes."""
from datetime import datetime, timezone
import json
from pathlib import Path
from gate10a_run import ROOT, OUT, binding, verify, frozen, sha


def fingerprint(receipt):
    return {Path(item["path"].replace("\\", "/")).name: item["sha256"]
        for item in receipt.get("execution_source_snapshots", [])
        if Path(item["path"].replace("\\", "/")).name in ("runner_source.py", "measurement_source.tcl")}


def run():
    path = OUT / "control/scientific_run_selection.json"
    audit_path = OUT / "control/architecture_receipt_hash_audit.json"
    if path.exists() or audit_path.exists():
        raise ValueError("Preserve original selection and hash audit")
    smoke_path = OUT / "control/smoke_qualification.json"
    smoke = json.loads(smoke_path.read_text())
    if smoke["status"] != "PASS":
        raise ValueError("Shared smoke did not qualify")
    selection, selected_binding = frozen("reports/gate10a/selected_architectures.json", smoke["preregistered_commit"])
    invalidated = {verify(item).resolve() for item in smoke["invalidated_receipts"]}
    for field, source in (("runner_source.py", ROOT / "scripts/gate10a_run.py"),
                          ("measurement_source.tcl", ROOT / "scripts/tcl/gate10a_measure.tcl")):
        if sha(source) != smoke["flow_fingerprint"][field]:
            raise ValueError("Current implementation differs from shared qualified flow")
    manifest = {"schema": "pact_gate10a_scientific_run_selection_v1", "status": "PASS",
        "created_utc": datetime.now(timezone.utc).isoformat(), "preregistered_commit": smoke["preregistered_commit"],
        "selection_rule": "Earliest completed QUALIFIED nominal density-one record matching shared-qualified source fingerprint and not explicitly invalidated. Numerical outcomes never determine selection.",
        "smoke_qualification": binding(smoke_path), "selected_architectures": selected_binding,
        "selector_source": binding(Path(__file__)), "runs": [], "attempt_admission_audit": []}
    audit = {"schema": "pact_gate10a_receipt_output_hash_audit_v1", "status": "PASS",
             "created_utc": datetime.now(timezone.utc).isoformat(), "records": [],
             "scientific_processes_rerun": 0, "total_output_files_verified": 0, "total_output_bytes_verified": 0}
    for row in selection["architectures"]:
        eligible = []
        for candidate_path in sorted((OUT / "runs" / row["design"] / row["architecture"]).glob("*/receipt.json")):
            receipt = json.loads(candidate_path.read_text())
            reason = None
            if receipt.get("status") != "QUALIFIED":
                reason = "local_qualification_failed"
            elif candidate_path.resolve() in invalidated:
                reason = "explicit_invalidation"
            elif receipt.get("nonclock_density_scale") != 1:
                reason = "density_control"
            elif fingerprint(receipt) != smoke["flow_fingerprint"]:
                reason = "qualified_flow_fingerprint_mismatch"
            elif (receipt.get("design"), receipt.get("architecture"), receipt.get("architecture_sha256")) != (row["design"], row["architecture"], row["architecture_sha256"]):
                reason = "architecture_identity_mismatch"
            manifest["attempt_admission_audit"].append({"receipt": binding(candidate_path), "eligible": reason is None,
                "exclusion_reason": reason, "numerical_outcomes_inspected": False})
            if reason is None:
                eligible.append((receipt["completed_utc"], candidate_path.as_posix(), candidate_path, receipt))
        if not eligible:
            raise ValueError("No admissible nominal record for " + row["design"] + "/" + row["architecture"])
        _, _, receipt_path, receipt = min(eligible)
        if receipt["preregistered_commit"] != smoke["preregistered_commit"] or any(receipt["scientific_stages_reexecuted"].values()):
            raise ValueError("Preregistration or forbidden stage execution mismatch")
        for expected in receipt["outputs"]:
            verify(expected)
            audit["total_output_files_verified"] += 1
            audit["total_output_bytes_verified"] += expected["bytes"]
        for expected in receipt["execution_source_snapshots"]:
            verify(expected)
        record = {"design": row["design"], "architecture": row["architecture"],
                  "architecture_sha256": row["architecture_sha256"], "receipt": binding(receipt_path)}
        manifest["runs"].append(record)
        audit["records"].append({**record, "status": "PASS", "output_count": len(receipt["outputs"])})
    if len(manifest["runs"]) != 9:
        raise ValueError("Selected preregistered population is not nine")
    for expected in smoke["records"]:
        verify(expected)
        receipt = json.loads(verify(expected).read_text())
        for output in receipt["outputs"]:
            verify(output)
    pg = json.loads(verify(smoke["PG_normalization_audit"]).read_text())
    if pg["status"] != "PASS" or len(pg["records"]) != 9:
        raise ValueError("Shared nine-input PG audit differs")
    for row in pg["records"]:
        for expected in row["outputs"]:
            verify(expected)
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    audit["scientific_run_selection"] = binding(path)
    audit["smoke_qualification"] = binding(smoke_path)
    audit["PG_normalization_audit"] = smoke["PG_normalization_audit"]
    audit["completed_utc"] = datetime.now(timezone.utc).isoformat()
    audit_path.write_text(json.dumps(audit, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "selected_nominal_runs": len(manifest["runs"]),
        "selection": str(path.relative_to(ROOT)), "hash_audit": str(audit_path.relative_to(ROOT))}))


if __name__ == "__main__":
    run()
