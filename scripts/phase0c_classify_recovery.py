#!/usr/bin/env python3
"""Apply the frozen C1-C9 gates to the exact original-plus-recovery execution union."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from phase0c_campaign_recover import (LIVE_ORIGINAL, MANIFEST, ORIGINAL, RECOVERY_CONFIG,
                                      eligible_cases, recovery_hashes)
from phase0c_campaign_run import ROOT, matrix
from phase0c_classify import classify as classify_original


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def key_for(case: tuple[str, int, int, str]) -> str:
    design, seed, k, method = case
    return f"{design}/s{seed}/k{k}/{method}"


def recovery_integrity() -> tuple[bool, dict]:
    campaign = read(ROOT / "config/phase0c_campaign.json")
    recovery = read(RECOVERY_CONFIG)
    original = read(ORIGINAL)
    details = {"recovery_manifest_present": MANIFEST.is_file(), "errors": []}
    if sha256(ORIGINAL) != recovery["original_campaign_manifest_sha256"]:
        details["errors"].append("interrupted manifest hash mismatch")
    if not LIVE_ORIGINAL.is_file() or LIVE_ORIGINAL.read_bytes() != ORIGINAL.read_bytes():
        details["errors"].append("live original manifest differs from preserved interrupted copy")
    if original.get("freeze_commit") != recovery["original_freeze_commit"]:
        details["errors"].append("interrupted manifest freeze commit mismatch")
    if original.get("status") != recovery["original_status"]:
        details["errors"].append("interrupted manifest status mismatch")
    eligible = eligible_cases(campaign, original, recovery["eligible_original_status"])
    expected_all = {key_for(case) for case in matrix(campaign)}
    original_qualified = {key for key, value in original["runs"].items()
                          if value["status"] == "QUALIFIED"}
    expected_recovery = {key_for(case) for case in eligible}
    details.update({"original_qualified_rows": len(original_qualified),
                    "expected_recovery_rows": len(expected_recovery),
                    "planned_union_rows": len(expected_all)})
    if len(eligible) != recovery["eligible_routes"]:
        details["errors"].append("eligible recovery count mismatch")
    if original_qualified & expected_recovery or original_qualified | expected_recovery != expected_all:
        details["errors"].append("original and recovery populations are not an exact disjoint union")
    if not MANIFEST.is_file():
        return False, details
    manifest = read(MANIFEST)
    details.update({"recovery_status": manifest.get("status"),
                    "recorded_recovery_rows": len(manifest.get("runs", {})),
                    "recovery_counts": manifest.get("counts", {})})
    if manifest.get("original_freeze_commit") != recovery["original_freeze_commit"]:
        details["errors"].append("recovery references wrong original freeze")
    if manifest.get("original_campaign_manifest_sha256") != sha256(ORIGINAL):
        details["errors"].append("recovery references changed interrupted manifest")
    if manifest.get("eligible_routes") != recovery["eligible_routes"]:
        details["errors"].append("recovery manifest eligible count mismatch")
    if manifest.get("frozen_input_sha256") != recovery_hashes():
        details["errors"].append("recovery frozen inputs changed")
    if set(manifest.get("runs", {})) != expected_recovery:
        details["errors"].append("recovery ledger differs from eligible population")
    allowed_statuses = {"QUALIFIED", "REWIRE_FAILED", "CAMPAIGN_TIMEOUT_BEFORE_REWIRE",
                        "CAMPAIGN_TIMEOUT_BEFORE_ROUTE", "ROUTE_TIMEOUT", "ROUTE_FAILED",
                        "ROUTED_DRC_FAIL", "POSTROUTE_VERIFICATION_FAILED",
                        "RECOVERY_DRIVER_EXCEPTION", "RECOVERY_CAP_REACHED",
                        "RECOVERY_DISK_FLOOR_REACHED"}
    unknown = sorted({run.get("status") for run in manifest.get("runs", {}).values()}
                     - allowed_statuses)
    if unknown:
        details["errors"].append(f"unknown recovery statuses: {unknown}")
    try:
        start = datetime.fromisoformat(manifest["started_utc"])
        deadline = datetime.fromisoformat(manifest["deadline_utc"])
        if (deadline - start).total_seconds() != recovery["recovery_cap_s"]:
            details["errors"].append("recovery deadline differs from frozen cap")
    except (KeyError, TypeError, ValueError):
        details["errors"].append("recovery timing fields are invalid")
    for key, run in manifest.get("runs", {}).items():
        if run["status"] != "QUALIFIED":
            continue
        design, seed, k, method = key.split("/")
        path = ROOT / f"artifacts/raw/phase0c/physical/{design}/{seed}/{k}/{method}/route_metrics.json"
        route = read(path) if path.is_file() else {}
        if (route.get("status") != "QUALIFIED" or route.get("DRC_errors") != 0
                or route.get("campaign_freeze_commit") != recovery["original_freeze_commit"]
                or route.get("variant") != run.get("detail", {}).get("variant")):
            details["errors"].append(f"qualified recovery row lacks matching physical evidence: {key}")
    return not details["errors"], details


def detailed_classification(gates: dict) -> str:
    if gates["C9"]["status"] == "PASS":
        return "MULTICHAIN_CONFLICT_REPLICATED_HEURISTICS_INSUFFICIENT_PHASE1_GO"
    if gates["C2"]["status"] != "PASS":
        return "MULTICHAIN_CAMPAIGN_INCOMPLETE_PHASE1_NO_GO"
    if gates["C3"]["status"] != "PASS":
        return "MULTICHAIN_CONFLICT_NOT_ESTABLISHED_PHASE1_NO_GO"
    if gates["C5"]["status"] != "PASS":
        return "MULTICHAIN_CONFLICT_PRESENT_NOT_REPLICATED_PHASE1_NO_GO"
    if gates["C6"]["status"] != "PASS":
        return "MULTICHAIN_CONFLICT_REPLICATED_HEURISTICS_SUFFICIENT_PHASE1_NO_GO"
    return "MULTICHAIN_LEARNING_PREREQUISITES_INCOMPLETE_PHASE1_NO_GO"


def classify() -> dict:
    result = classify_original()
    intact, recovery = recovery_integrity()
    c1 = result["gates"]["C1"]
    c1["original_campaign_and_recovery_union_intact"] = intact
    c1["recovery_ledger"] = recovery
    if not intact:
        c1["status"] = "NOT QUALIFIED"
        c1["reason"] = "original frozen inputs plus the precommitted disk-floor recovery must form an exact, hash-intact execution union"
        result["gates"]["C2"]["status"] = "NOT QUALIFIED"
        result["gates"]["C2"]["reason"] = "physical evidence is not admissible until the recovery execution union passes integrity"
    go = all(result["gates"][f"C{i}"]["status"] == "PASS" for i in range(1, 9))
    result["gates"]["C9"] = {"status": "PASS" if go else "FAIL",
                              "reason": "all C1-C8 must pass on the original-plus-recovery execution union"}
    result["schema_version"] = "phase0c-analysis-recovery-1"
    result["recovery"] = recovery
    result["classification"] = ("PACT_PHASE0C_LEARNING_GATE_PASS" if go
                                else "PACT_PHASE0C_LEARNING_GATE_FAIL")
    result["detailed_classification"] = detailed_classification(result["gates"])
    return result


def main() -> None:
    result = classify()
    target = ROOT / "artifacts/derived/phase0c/gate_analysis.json"
    target.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode())
    print(result["classification"])
    print(result["detailed_classification"])


if __name__ == "__main__":
    main()
