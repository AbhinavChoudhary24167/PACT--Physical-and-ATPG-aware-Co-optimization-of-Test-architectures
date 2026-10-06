#!/usr/bin/env python3
"""Execute all remaining preregistered architectures serially after smoke PASS."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
from gate10a_run import ROOT, OUT, binding, verify, sha


def run():
    path = OUT / "control/selected_architecture_execution.json"
    if path.exists():
        raise ValueError("Preserve immutable architecture execution receipt")
    smoke_path = OUT / "control/smoke_qualification.json"
    smoke = json.loads(smoke_path.read_text())
    if smoke["status"] != "PASS":
        raise ValueError("Shared smoke is not qualified")
    for field, source in (("runner_source.py", ROOT / "scripts/gate10a_run.py"),
                          ("measurement_source.tcl", ROOT / "scripts/tcl/gate10a_measure.tcl")):
        if sha(source) != smoke["flow_fingerprint"][field]:
            raise ValueError("Qualified flow source changed")
    for item in smoke["records"]:
        verify(item)
    selection = json.loads((OUT / "selected_architectures.json").read_text())
    result = {"schema": "pact_gate10a_selected_execution_v1", "status": "STARTED",
              "started_utc": datetime.now(timezone.utc).isoformat(), "smoke": binding(smoke_path),
              "source": binding(Path(__file__)), "threads_per_job": 1, "maximum_concurrent_EDA_jobs": 1,
              "reference_b14_B3T_reused": smoke["nominal_architecture_receipt"], "records": []}
    for row in selection["architectures"]:
        if row["design"] == "b14_opt" and row["architecture"] == "B3T":
            continue
        argv = [sys.executable, "scripts/gate10a_run.py", "--design", row["design"],
                "--architecture", row["architecture"], "--label", "science_nominal",
                "--preregistered-commit", smoke["preregistered_commit"]]
        before = time.monotonic()
        proc = subprocess.run(argv, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        receipt_path = OUT / "runs" / row["design"] / row["architecture"] / "science_nominal/receipt.json"
        record = {"design": row["design"], "architecture": row["architecture"], "command": argv,
                  "returncode": proc.returncode, "wall_seconds": time.monotonic() - before, "stdout": proc.stdout}
        if receipt_path.exists():
            record["receipt"] = binding(receipt_path)
            record["status"] = json.loads(receipt_path.read_text())["status"]
        else:
            record["status"] = "MISSING_RUN_RECEIPT"
        result["records"].append(record)
        # Continuous driver checkpoint supplements each immutable run receipt.
        checkpoint = OUT / "control" / ("selected_execution_checkpoint_" + str(len(result["records"])) + ".json")
        if checkpoint.exists():
            raise ValueError("Preserve existing execution checkpoint")
        checkpoint.write_text(json.dumps(result, indent=2) + "\n")
        print(row["design"], row["architecture"], record["status"], flush=True)
    result["status"] = "PASS" if all(r["status"] == "QUALIFIED" for r in result["records"]) else "COMPLETE_WITH_ADMISSION_FAILURES"
    result["completed_utc"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "receipt": str(path.relative_to(ROOT))}), flush=True)
    return result["status"] == "PASS"


if __name__ == "__main__":
    raise SystemExit(0 if run() else 2)
