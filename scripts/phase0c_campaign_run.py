#!/usr/bin/env python3
"""Execute the frozen Phase-0C matrix with one persistent campaign deadline.

Rerunning this driver resumes valid rows. A restart does not reset the deadline.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from phase0c_prepare import prepare
from phase0c_run_route import ROOT, route_one


MANIFEST = ROOT / "artifacts/manifests/phase0c/campaign_execution.json"
FREEZE_FILES = [
    "config/phase0c_campaign.json",
    "config/phase0c_analysis_contract.json",
    "config/phase0c_seed_method.json",
    "config/phase0c_objectives.json",
    "scripts/phase0c_prepare.py",
    "scripts/phase0c_rewire_odb.py",
    "scripts/phase0c_verify_routed.py",
    "scripts/phase0c_run_route.py",
    "scripts/phase0c_campaign_run.py",
    "scripts/phase0c_interventions.py",
    "scripts/phase0c_run_intervention_screen.py",
    "scripts/phase0c_classify.py",
    "src/pact/scan/phase0c.py",
    "src/pact/scan/phase0c_interventions.py",
    "src/pact/analysis/phase0c_activity.py",
    "src/pact/physical/phase0c_port_policy.py",
    "src/pact/physical/phase0c_scan_geometry.py",
    "src/pact/physical/phase0c_congestion.py",
    "artifacts/manifests/phase0c/tool_qualification.json",
    "artifacts/manifests/phase0c/benchmark_candidate_audit.json",
    "artifacts/manifests/phase0c/prefreeze_audit.json",
    "artifacts/manifests/phase0c/phase0b_pre_edit.sha256",
    "scripts/phase0c_prefreeze_audit.py",
]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def file_hashes() -> dict[str, str]:
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in FREEZE_FILES}


def save(record: dict) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    temporary = MANIFEST.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, MANIFEST)


def matrix(campaign: dict) -> list[tuple[str, int, int, str]]:
    rows = []
    for seed in campaign["physical_seeds"]:
        for k in campaign["K_values"]:
            for design in campaign["designs"]:
                rows.extend((design, seed, k, method)
                            for method in campaign["route_families_each_K"])
                if k == 1:
                    rows.append((design, seed, k, campaign["native_B1_k1_method"]))
    return rows


def main() -> None:
    campaign = json.loads((ROOT / "config/phase0c_campaign.json").read_text(encoding="utf-8"))
    contract = json.loads((ROOT / "config/phase0c_analysis_contract.json").read_text(encoding="utf-8"))
    if campaign["status"] != "FROZEN_FOR_FINAL_CAMPAIGN" or contract["status"] != "FROZEN_FOR_FINAL_CAMPAIGN":
        raise RuntimeError("Phase-0C campaign and analysis contract must be frozen before final execution")
    cases = matrix(campaign)
    if len(cases) != campaign["planned_routes_if_qualified"]:
        raise ValueError("Frozen planned-route count does not match Cartesian matrix")
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--", *FREEZE_FILES],
                                    cwd=ROOT, text=True)
    if dirty.strip():
        raise RuntimeError(f"Frozen campaign inputs are uncommitted:\n{dirty}")
    hashes = file_hashes()
    if MANIFEST.exists():
        record = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if record["frozen_input_sha256"] != hashes or record["planned_routes"] != len(cases):
            raise RuntimeError("Frozen campaign inputs changed after execution began")
    else:
        freeze_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                                 text=True).strip()
        start = utcnow()
        record = {
            "schema_version": "phase0c-campaign-execution-1",
            "status": "RUNNING", "freeze_commit": freeze_commit,
            "frozen_input_sha256": hashes,
            "started_utc": start.isoformat(),
            "deadline_utc": (start + timedelta(seconds=campaign["campaign_cap_s"])).isoformat(),
            "planned_routes": len(cases), "runs": {},
        }
        save(record)
    deadline = datetime.fromisoformat(record["deadline_utc"])
    for design, seed, k, method in cases:
        key = f"{design}/s{seed}/k{k}/{method}"
        left = int((deadline - utcnow()).total_seconds())
        if left <= 0:
            record["runs"].setdefault(key, {"status": "CAMPAIGN_CAP_REACHED"})
            continue
        if shutil.disk_usage(ROOT).free < campaign["minimum_workspace_free_bytes_before_route"]:
            record["runs"].setdefault(key, {"status": "WORKSPACE_DISK_FLOOR_REACHED"})
            continue
        try:
            proxy = prepare(design, seed, k, [method])[0]
            result = route_one(design, seed, k, method, left,
                               campaign_freeze_commit=record["freeze_commit"])
            status = result["status"]
            detail = {"DRC_errors": result.get("DRC_errors"),
                      "physical_primary_um": result.get("physical_primary_um"),
                      "variant": result.get("variant"),
                      "resumed_valid_result": result.get("resumed_valid_result", False)}
        except Exception as exc:
            proxy = None
            status, detail = "DRIVER_EXCEPTION", {"exception": repr(exc)}
        record["runs"][key] = {
            "status": status,
            "run_id": proxy["run_id"] if proxy else None,
            "timestamp_utc": utcnow().isoformat(),
            "detail": detail,
        }
        save(record)
        print(json.dumps({"run": key, "status": status,
                          "remaining_campaign_s": max(0, int((deadline - utcnow()).total_seconds()))}), flush=True)
    counts: dict[str, int] = {}
    for value in record["runs"].values():
        counts[value["status"]] = counts.get(value["status"], 0) + 1
    record["status"] = ("COMPLETED" if len(record["runs"]) == len(cases)
                        and counts.get("CAMPAIGN_CAP_REACHED", 0) == 0
                        and counts.get("WORKSPACE_DISK_FLOOR_REACHED", 0) == 0 else "CAP_REACHED")
    record["finished_utc"] = utcnow().isoformat()
    record["counts"] = counts
    save(record)
    print(json.dumps({"status": record["status"], "counts": counts,
                      "planned_routes": len(cases)}), flush=True)


if __name__ == "__main__":
    main()
