#!/usr/bin/env python3
"""Execute the frozen cheap intervention screen after parent physical routing."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys

from phase0c_run_route import ROOT


STATE = ROOT / "artifacts/manifests/phase0c/intervention_execution.json"
DATASET = ROOT / "artifacts/derived/phase0c/intervention_dataset.jsonl"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def save(record: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def current_count(design: str, seed: int, k: int, parent_sha: str) -> int:
    if not DATASET.exists():
        return 0
    return sum(1 for line in DATASET.read_text(encoding="utf-8").splitlines()
               if (lambda r: r.get("screen_id") == "FROZEN_C7_LOCAL_SWAP"
                   and r["design"] == design and r["physical_seed"] == seed
                   and r["K"] == k and r["parent_architecture_sha256"] == parent_sha)(json.loads(line)))


def main() -> None:
    campaign = json.loads((ROOT / "config/phase0c_campaign.json").read_text())
    if campaign["status"] != "FROZEN_FOR_FINAL_CAMPAIGN":
        raise RuntimeError("Frozen campaign required")
    execution_path = ROOT / "artifacts/manifests/phase0c/campaign_execution.json"
    execution = json.loads(execution_path.read_text())
    if execution["status"] not in ("COMPLETED", "CAP_REACHED"):
        raise RuntimeError("Parent route campaign has not finished")
    freeze_commit = execution["freeze_commit"]
    if STATE.exists():
        state = json.loads(STATE.read_text())
        if state["freeze_commit"] != freeze_commit:
            raise RuntimeError("Intervention screen freeze commit changed")
    else:
        start = utcnow()
        state = {"schema_version": "phase0c-intervention-execution-1",
                 "freeze_commit": freeze_commit, "started_utc": start.isoformat(),
                 "deadline_utc": (start + timedelta(seconds=campaign["intervention_screen_cap_s"])).isoformat(),
                 "runs": {}, "status": "RUNNING"}
        save(state)
    screen = campaign["intervention_screen"]
    k, method, count = screen["K"], screen["parent_method"], screen["local_position_pair_proposals_per_design_seed"]
    deadline = datetime.fromisoformat(state["deadline_utc"])
    for design in campaign["designs"]:
        for seed in campaign["physical_seeds"]:
            key = f"{design}/s{seed}/k{k}/{method}"
            left = int((deadline - utcnow()).total_seconds())
            if left <= 0:
                state["runs"].setdefault(key, {"status": "SCREEN_CAP_REACHED"})
                continue
            parent_path = ROOT / f"artifacts/raw/phase0c/physical/{design}/s{seed}/k{k}/{method}/route_metrics.json"
            parent = json.loads(parent_path.read_text()) if parent_path.exists() else {}
            if (parent.get("status") != "QUALIFIED" or parent.get("DRC_errors") != 0
                    or parent.get("campaign_freeze_commit") != freeze_commit):
                state["runs"][key] = {"status": "PARENT_ROUTE_UNQUALIFIED", "timestamp_utc": utcnow().isoformat()}
                save(state)
                continue
            parent_sha = parent["architecture_sha256"]
            if current_count(design, seed, k, parent_sha) >= count:
                state["runs"][key] = {"status": "PASS", "timestamp_utc": utcnow().isoformat(),
                                      "records": count, "resumed": True}
                save(state)
                continue
            folder = ROOT / f"artifacts/raw/phase0c/interventions/{design}/s{seed}/k{k}/{method}"
            folder.mkdir(parents=True, exist_ok=True)
            attempt = len(list(folder.glob("attempt_*.stdout.log"))) + 1
            stdout_path = folder / f"attempt_{attempt:03d}.stdout.log"
            stderr_path = folder / f"attempt_{attempt:03d}.stderr.log"
            command = [sys.executable, str(ROOT / "scripts/phase0c_interventions.py"),
                       "--design", design, "--seed", str(seed), "--k", str(k),
                       "--methods", method, "--sample-swaps", str(count), "--screen-only"]
            try:
                result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                        timeout=min(left, 300))
                label = "PASS" if result.returncode == 0 and current_count(design, seed, k, parent_sha) >= count else "SCREEN_FAILED"
                stdout_path.write_text(result.stdout, encoding="utf-8")
                stderr_path.write_text(result.stderr, encoding="utf-8")
                code = result.returncode
            except subprocess.TimeoutExpired as exc:
                label, code = "SCREEN_TIMEOUT", None
                stdout_path.write_bytes(exc.stdout.encode() if isinstance(exc.stdout, str) else exc.stdout or b"")
                stderr_path.write_bytes(exc.stderr.encode() if isinstance(exc.stderr, str) else exc.stderr or b"")
            state["runs"][key] = {"status": label, "timestamp_utc": utcnow().isoformat(),
                                  "command": command, "return_code": code,
                                  "stdout_log": str(stdout_path.relative_to(ROOT)),
                                  "stderr_log": str(stderr_path.relative_to(ROOT)),
                                  "records": current_count(design, seed, k, parent_sha)}
            save(state)
            print(json.dumps({"run": key, "status": label, "records": state["runs"][key]["records"]}), flush=True)
    state["status"] = "COMPLETED" if all(r["status"] != "SCREEN_CAP_REACHED" for r in state["runs"].values()) else "CAP_REACHED"
    state["finished_utc"] = utcnow().isoformat()
    save(state)
    print(json.dumps({"status": state["status"], "runs": len(state["runs"])}), flush=True)


if __name__ == "__main__":
    main()
