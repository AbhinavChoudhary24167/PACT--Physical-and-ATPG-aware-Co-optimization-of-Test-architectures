#!/usr/bin/env python3
"""Audit the completed frozen Phase-0C campaign and its archived physical evidence."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from phase0c_campaign_run import FREEZE_FILES, ROOT, file_hashes, matrix
from phase0c_classify import proxy_integrity
from phase0c_classify_recovery import recovery_integrity
from phase0c_prefreeze_audit import audit_phase0b, audit_route


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    campaign = read(ROOT / "config/phase0c_campaign.json")
    contract_path = ROOT / "config/phase0c_analysis_contract.json"
    execution_path = ROOT / "artifacts/manifests/phase0c/campaign_execution.json"
    execution = read(execution_path)
    recovery_execution = read(ROOT / "artifacts/manifests/phase0c/campaign_recovery.json")
    expected = {(design, seed, k, method) for design, seed, k, method in matrix(campaign)}
    errors = []
    if execution.get("frozen_input_sha256") != file_hashes():
        errors.append("frozen campaign input hashes changed")
    if execution.get("planned_routes") != len(expected):
        errors.append("campaign planned count differs from frozen matrix")
    run_keys = {tuple(part for part in key.replace("/s", "/").replace("/k", "/").split("/"))
                for key in execution.get("runs", {})}
    parsed_run_keys = {(design, int(seed), int(k), method) for design, seed, k, method in run_keys}
    if parsed_run_keys != expected:
        errors.append("execution-manifest keys differ from frozen matrix")
    recovery_ok, recovery_details = recovery_integrity()
    if not recovery_ok:
        errors.append(f"recovery execution union failed: {recovery_details['errors']}")

    proxies = [read(path) for path in sorted((ROOT / "artifacts/derived/phase0c").glob(
        "*/s*/k*/*.proxy.json"))]
    proxy_ok, proxy_counts = proxy_integrity(
        proxies, campaign, hashlib.sha256(contract_path.read_bytes()).hexdigest())
    if not proxy_ok:
        errors.append(f"proxy integrity failed: {proxy_counts}")

    route_paths = sorted((ROOT / "artifacts/raw/phase0c/physical").glob(
        "*/s*/k*/*/route_metrics.json"))
    final_records, qualified_records, route_errors = [], [], []
    for path in route_paths:
        record = read(path)
        if record.get("campaign_freeze_commit") != execution.get("freeze_commit"):
            continue
        final_records.append(record)
        if record.get("status") == "QUALIFIED" and record.get("DRC_errors") == 0:
            qualified_records.append(record)
            _, problems = audit_route(path)
            route_errors.extend(problems)
    errors.extend(route_errors)
    actual = {(row["design"], row["physical_seed"], row["K"], row["method"])
              for row in qualified_records}
    original_qualified = {key: run for key, run in execution.get("runs", {}).items()
                          if run["status"] == "QUALIFIED"}
    combined_runs = {**original_qualified, **recovery_execution.get("runs", {})}
    qualified_expected = set()
    for key, run in combined_runs.items():
        design, seed, k, method = key.split("/")
        identity = (design, int(seed[1:]), int(k[1:]), method)
        if run["status"] == "QUALIFIED":
            qualified_expected.add(identity)
        else:
            evidence = ROOT / f"artifacts/raw/phase0c/physical/{design}/{seed}/{k}/{method}"
            manifest_only = {"RECOVERY_CAP_REACHED", "RECOVERY_DISK_FLOOR_REACHED",
                             "RECOVERY_DRIVER_EXCEPTION"}
            if run["status"] not in manifest_only and not (evidence / "status.json").is_file():
                errors.append(f"unqualified run lacks status evidence: {key}")
    if actual != qualified_expected:
        errors.append(f"qualified final route identity mismatch: missing={len(qualified_expected - actual)}, extra={len(actual - qualified_expected)}")
    execution_counts = Counter(row["status"] for row in combined_runs.values())
    record_counts = Counter(row["status"] for row in qualified_records)
    if execution_counts.get("QUALIFIED", 0) != record_counts.get("QUALIFIED", 0):
        errors.append(f"execution/route qualified counts differ: {execution_counts} versus {record_counts}")

    phase0b = audit_phase0b()
    if phase0b["status"] != "PASS":
        errors.append("Phase-0B preservation audit failed")
    result = {
        "schema_version": "phase0c-postcampaign-audit-1",
        "status": "PASS" if not errors else "FAIL",
        "freeze_commit": execution.get("freeze_commit"),
        "original_execution_status": execution.get("status"),
        "recovery_execution_status": recovery_execution.get("status"),
        "recovery_integrity": recovery_details,
        "planned_routes": len(expected), "final_route_records": len(final_records),
        "qualified_route_records": len(qualified_records),
        "combined_execution_status_counts": dict(sorted(execution_counts.items())),
        "proxy_rows": len(proxies), "proxy_integrity": proxy_counts,
        "phase0b_preservation": phase0b,
        "frozen_files_checked": len(FREEZE_FILES),
        "route_evidence_errors": len(route_errors), "errors": errors,
    }
    output = ROOT / "artifacts/manifests/phase0c/postcampaign_audit.json"
    output.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode())
    print(json.dumps(result, indent=2, sort_keys=True))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
