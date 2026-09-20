#!/usr/bin/env python3
"""Recover only predeclared Phase-0C rows skipped by the workspace disk floor."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from phase0c_campaign_run import FREEZE_FILES, ROOT, file_hashes, matrix
from phase0c_prepare import prepare
from phase0c_run_route import route_one


RECOVERY_CONFIG = ROOT / "config/phase0c_recovery_contract.json"
ORIGINAL = ROOT / "artifacts/manifests/phase0c/campaign_execution_interrupted.json"
LIVE_ORIGINAL = ROOT / "artifacts/manifests/phase0c/campaign_execution.json"
MANIFEST = ROOT / "artifacts/manifests/phase0c/campaign_recovery.json"
RECOVERY_FILES = [
    "config/phase0c_recovery_contract.json",
    "docs/PACT_PHASE0C_RECOVERY.md",
    "scripts/phase0c_campaign_recover.py",
    "scripts/phase0c_classify_recovery.py",
    "scripts/phase0c_postcampaign_audit.py",
    "artifacts/manifests/phase0c/campaign_execution_interrupted.json",
]


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def save(record: dict) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    temporary = MANIFEST.with_suffix(".json.tmp")
    temporary.write_bytes((json.dumps(record, indent=2, sort_keys=True) + "\n").encode())
    os.replace(temporary, MANIFEST)


def recovery_hashes() -> dict[str, str]:
    return {name: sha256(ROOT / name) for name in RECOVERY_FILES}


def eligible_cases(campaign: dict, original: dict, eligible_status: str) -> list[tuple[str, int, int, str]]:
    result = []
    for case in matrix(campaign):
        design, seed, k, method = case
        key = f"{design}/s{seed}/k{k}/{method}"
        if original["runs"].get(key, {}).get("status") == eligible_status:
            result.append(case)
    return result


def main() -> None:
    campaign = read(ROOT / "config/phase0c_campaign.json")
    recovery = read(RECOVERY_CONFIG)
    original = read(ORIGINAL)
    if recovery["status"] != "FROZEN_FOR_DISK_FLOOR_RECOVERY":
        raise RuntimeError("Recovery contract is not frozen")
    if sha256(ORIGINAL) != recovery["original_campaign_manifest_sha256"]:
        raise RuntimeError("Interrupted campaign manifest changed")
    if LIVE_ORIGINAL.read_bytes() != ORIGINAL.read_bytes():
        raise RuntimeError("Live original campaign manifest differs from preserved interrupted copy")
    if original["freeze_commit"] != recovery["original_freeze_commit"]:
        raise RuntimeError("Original freeze commit mismatch")
    if original["frozen_input_sha256"] != file_hashes():
        raise RuntimeError("Original frozen campaign inputs changed")
    cases = eligible_cases(campaign, original, recovery["eligible_original_status"])
    if len(cases) != recovery["eligible_routes"]:
        raise RuntimeError("Recovery population differs from frozen disk-floor population")
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--", *RECOVERY_FILES],
                                     cwd=ROOT, text=True)
    if dirty.strip():
        raise RuntimeError(f"Recovery inputs are uncommitted:\n{dirty}")
    hashes = recovery_hashes()
    if MANIFEST.exists():
        record = read(MANIFEST)
        if record["frozen_input_sha256"] != hashes or record["eligible_routes"] != len(cases):
            raise RuntimeError("Frozen recovery inputs changed after execution began")
    else:
        recovery_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                                   text=True).strip()
        start = utcnow()
        record = {
            "schema_version": "phase0c-campaign-recovery-execution-1",
            "status": "RUNNING", "original_freeze_commit": original["freeze_commit"],
            "recovery_freeze_commit": recovery_commit,
            "original_campaign_manifest_sha256": sha256(ORIGINAL),
            "frozen_input_sha256": hashes,
            "started_utc": start.isoformat(),
            "deadline_utc": (start + timedelta(seconds=recovery["recovery_cap_s"])).isoformat(),
            "eligible_routes": len(cases), "runs": {},
        }
        save(record)
    deadline = datetime.fromisoformat(record["deadline_utc"])
    for design, seed, k, method in cases:
        key = f"{design}/s{seed}/k{k}/{method}"
        if key in record["runs"]:
            continue
        left = int((deadline - utcnow()).total_seconds())
        if left <= 0:
            record["runs"][key] = {
                "status": "RECOVERY_CAP_REACHED", "run_id": None,
                "timestamp_utc": utcnow().isoformat(), "detail": {},
            }
            save(record)
            continue
        if shutil.disk_usage(ROOT).free < recovery["minimum_workspace_free_bytes_before_route"]:
            record["runs"][key] = {
                "status": "RECOVERY_DISK_FLOOR_REACHED", "run_id": None,
                "timestamp_utc": utcnow().isoformat(), "detail": {},
            }
            save(record)
            continue
        try:
            proxy = prepare(design, seed, k, [method])[0]
            result = route_one(design, seed, k, method, left,
                               campaign_freeze_commit=original["freeze_commit"])
            status = result["status"]
            detail = {"DRC_errors": result.get("DRC_errors"),
                      "physical_primary_um": result.get("physical_primary_um"),
                      "variant": result.get("variant"),
                      "resumed_valid_result": result.get("resumed_valid_result", False)}
        except Exception as exc:
            proxy = None
            status, detail = "RECOVERY_DRIVER_EXCEPTION", {"exception": repr(exc)}
        record["runs"][key] = {
            "status": status,
            "run_id": proxy["run_id"] if proxy else None,
            "timestamp_utc": utcnow().isoformat(),
            "detail": detail,
        }
        save(record)
        print(json.dumps({"run": key, "status": status,
                          "remaining_recovery_s": max(0, int((deadline - utcnow()).total_seconds()))}),
              flush=True)
    counts = Counter(value["status"] for value in record["runs"].values())
    limiting = counts["RECOVERY_CAP_REACHED"] + counts["RECOVERY_DISK_FLOOR_REACHED"]
    record["status"] = ("COMPLETED" if len(record["runs"]) == len(cases) and limiting == 0
                        else "CAP_REACHED")
    record["finished_utc"] = utcnow().isoformat()
    record["counts"] = dict(sorted(counts.items()))
    save(record)
    print(json.dumps({"status": record["status"], "counts": record["counts"],
                      "eligible_routes": len(cases)}), flush=True)


if __name__ == "__main__":
    main()
