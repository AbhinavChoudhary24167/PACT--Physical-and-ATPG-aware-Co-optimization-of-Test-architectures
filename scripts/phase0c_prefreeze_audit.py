#!/usr/bin/env python3
"""Audit Phase-0B preservation and the Phase-0C physical qualification evidence."""
from __future__ import annotations

from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

from pact.scan.model import ScanArchitecture


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def uncompressed_gzip_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with gzip.open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_phase0b() -> dict:
    manifest = ROOT / "artifacts/manifests/phase0c/phase0b_pre_edit.sha256"
    missing, mismatched = [], []
    rows = [line.split("  ", 1) for line in manifest.read_text(encoding="utf-8").splitlines() if line]
    for expected, relative in rows:
        path = ROOT / relative
        if not path.is_file():
            missing.append(relative)
        elif sha256(path) != expected:
            mismatched.append(relative)
    return {"hashed_files": len(rows), "missing": missing, "mismatched": mismatched,
            "status": "PASS" if not missing and not mismatched else "FAIL"}


def audit_route(path: Path) -> tuple[dict, list[str]]:
    errors: list[str] = []
    record = json.loads(path.read_text(encoding="utf-8"))
    prefix = path.relative_to(ROOT).as_posix()
    design, seed, k, method = (record.get(name) for name in ("design", "physical_seed", "K", "method"))
    if record.get("status") != "QUALIFIED" or record.get("DRC_errors") != 0:
        errors.append(f"{prefix}: route is not zero-DRC QUALIFIED")
    architecture_path = ROOT / f"artifacts/derived/phase0c/{design}/s{seed}/k{k}/{method}.architecture.json"
    proxy_path = ROOT / f"artifacts/derived/phase0c/{design}/s{seed}/k{k}/{method}.proxy.json"
    if not architecture_path.is_file() or not proxy_path.is_file():
        errors.append(f"{prefix}: architecture or proxy is missing")
        return record, errors
    architecture = ScanArchitecture.from_json(architecture_path)
    proxy = json.loads(proxy_path.read_text(encoding="utf-8"))
    if record.get("architecture_sha256") != architecture.sha256():
        errors.append(f"{prefix}: architecture hash mismatch")
    if record.get("scan_hpwl_proxy_um") != proxy["scan_geometry"]["total_scan_hpwl_um"]:
        errors.append(f"{prefix}: route/proxy physical metric mismatch")
    proof_relative = record.get("postroute_verification")
    proof_path = ROOT / proof_relative if proof_relative else None
    if not proof_path or not proof_path.is_file():
        errors.append(f"{prefix}: routed verification is missing")
    else:
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
        expected_links = len(architecture.cells) + len(architecture.chains)
        if not (proof.get("status") == "PASS"
                and proof.get("all_chain_inputs_outputs_verified") is True
                and proof.get("fixed_port_positions_verified") is True
                and proof.get("bounded_scan_path_link_count") == expected_links
                and proof.get("routed_full_scan_path_net_length_upper_bound_um")
                == record.get("routed_full_scan_path_net_length_upper_bound_um")):
            errors.append(f"{prefix}: routed structural/port/path proof is incomplete")
    archive = ROOT / str(record.get("routed_odb_archive", ""))
    if not archive.is_file():
        errors.append(f"{prefix}: routed ODB archive is missing")
    elif (sha256(archive) != record.get("routed_odb_gzip_sha256")
          or uncompressed_gzip_sha256(archive) != record.get("routed_odb_sha256")):
        errors.append(f"{prefix}: routed ODB archive hash mismatch")
    metrics = record.get("structured_metrics", {})
    congestion = metrics.get("congestion")
    if (metrics.get("detailed_route_drc_errors") != 0 or not congestion
            or congestion.get("total", {}).get("total_overflow") is None
            or metrics.get("setup_wns_ns") is None or metrics.get("hold_wns_ns") is None):
        errors.append(f"{prefix}: physical/timing/congestion metrics are incomplete")
    return record, errors


def audit_qualification() -> dict:
    paths = sorted((ROOT / "artifacts/raw/phase0c/physical").glob("*/s*/k*/*/route_metrics.json"))
    records, errors = [], []
    for path in paths:
        record, route_errors = audit_route(path)
        records.append(record)
        errors.extend(route_errors)
    batch_path = ROOT / "artifacts/derived/phase0c/s5378/s11/qualification_batch.json"
    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    batch_pass = (batch.get("planned") == 25 and len(batch.get("runs", {})) == 25
                  and all(row.get("status") == "QUALIFIED" for row in batch["runs"].values()))
    if not batch_pass:
        errors.append("s5378/s11 qualification matrix is not 25/25 QUALIFIED")
    cross_design = {(row.get("design"), row.get("physical_seed"), row.get("K"), row.get("method"))
                    for row in records}
    for expected in (("s9234", 11, 8, "B0"), ("s15850", 11, 8, "B0")):
        if expected not in cross_design:
            errors.append(f"missing cross-design qualification {expected}")
    return {
        "route_records": len(records),
        "status_counts": dict(sorted(Counter(row.get("status") for row in records).items())),
        "zero_drc_records": sum(row.get("DRC_errors") == 0 for row in records),
        "s5378_s11_matrix": "PASS" if batch_pass else "FAIL",
        "cross_design_k8_B0": "PASS" if all(item in cross_design for item in
                                                 (("s9234", 11, 8, "B0"),
                                                  ("s15850", 11, 8, "B0"))) else "FAIL",
        "errors": errors,
        "status": "PASS" if not errors else "FAIL",
    }


def main() -> None:
    result = {
        "schema_version": "phase0c-prefreeze-audit-1",
        "phase0b_preservation": audit_phase0b(),
        "phase0c_physical_qualification": audit_qualification(),
    }
    result["status"] = ("PASS" if all(section["status"] == "PASS" for section in
                                      (result["phase0b_preservation"],
                                       result["phase0c_physical_qualification"])) else "FAIL")
    output = ROOT / "artifacts/manifests/phase0c/prefreeze_audit.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
