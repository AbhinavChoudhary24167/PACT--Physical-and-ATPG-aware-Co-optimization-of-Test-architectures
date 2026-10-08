#!/usr/bin/env python3
"""Read-only completion of the frozen Gate09 Linux tool identity audit."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def binding(path):
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return {"path": str(path), "sha256": hasher.hexdigest(), "bytes": path.stat().st_size}


def verify(commit, output):
    if output.exists():
        raise ValueError("Preserve existing delegated-tool receipt")
    relative = "reports/gate10a/artifact_reuse_manifest.json"
    frozen = subprocess.check_output(["git", "show", commit + ":" + relative], cwd=ROOT)
    expected_sha = hashlib.sha256(frozen).hexdigest()
    observed_manifest = binding(ROOT / relative)
    if observed_manifest["sha256"] != expected_sha or observed_manifest["bytes"] != len(frozen):
        raise ValueError("Frozen audit manifest bytes changed")
    manifest = json.loads(frozen)
    records = []
    for row in manifest["records"]:
        if row["status"] != "LINUX_TOOL_CHECK_DELEGATED_TO_FLOW_LANE":
            continue
        expected = row["expected"]
        path = Path(expected["path"])
        observed = binding(path) if path.is_file() else None
        status = "PASS" if observed and all(observed[key] == expected[key] for key in ("bytes", "sha256")) else "FAIL"
        records.append({"expected": expected, "expected_from": row["expected_from"], "observed": observed, "status": status})
    receipt = {"schema": "pact_gate10a_delegated_frozen_tool_verification_v1", "created_utc": datetime.now(timezone.utc).isoformat(),
               "status": "PASS" if len(records) == 4 and all(row["status"] == "PASS" for row in records) else "FAIL",
               "preregistered_commit": commit, "parent_published_commit": manifest["parent_published_commit"],
               "frozen_audit_manifest": {"path": "repo://" + relative, "sha256": expected_sha, "bytes": len(frozen)},
               "scientific_stages_executed": 0, "tool_execution": "None; hashes and file sizes only",
               "command": sys.argv, "verification_script": binding(Path(__file__).resolve()), "records": records}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "tools_verified": len(records), "output": binding(output)}, indent=2))
    return receipt["status"] == "PASS"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preregistered-commit", required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "reports/gate10a/control/delegated_tool_hashes.json")
    args = parser.parse_args()
    raise SystemExit(0 if verify(args.preregistered_commit, args.output) else 2)
