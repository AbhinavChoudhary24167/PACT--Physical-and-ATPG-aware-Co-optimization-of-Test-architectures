#!/usr/bin/env python3
"""Route one shortlisted Phase-0D architecture under a hard, resumable budget."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pact.phase0d.campaign import atomic_write_json, check_disk_floor, file_sha256  # noqa: E402
from pact.phase0d.external import extract_structured_metrics, run_bounded  # noqa: E402
from pact.physical.phase0c_congestion import parse_grt_congestion  # noqa: E402
from pact.scan.model import ScanArchitecture  # noqa: E402


BLOCK = {"s5378": "s5378", "s9234": "s9234f", "s15850": "s15850"}


def _remaining(deadline: float, cap: int) -> int:
    return max(0, min(cap, int(deadline - time.monotonic())))


def _archived_odb_matches(path: Path, expected_sha256: str) -> bool:
    if not path.is_file():
        return False
    digest = hashlib.sha256()
    with gzip.open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest() == expected_sha256


def route_one(design: str, seed: int, K: int, candidate_dir: Path, cap_seconds: int,
              evidence_namespace: str = "pilot") -> dict:
    if evidence_namespace not in {"pilot", "optimizer_v1"}:
        raise ValueError("Unsupported Phase-0D evidence namespace")
    pilot_contract_path = ROOT / "config/phase0d_pilot_contract.json"
    pilot_contract = json.loads(pilot_contract_path.read_text(encoding="utf-8"))
    if evidence_namespace == "pilot":
        contract_path = pilot_contract_path
        campaign = pilot_contract["benchmark_population"]
    else:
        contract_path = ROOT / "config/phase0d_optimizer_v1_contract.json"
        campaign = json.loads((ROOT / "config/phase0c_campaign.json").read_text(encoding="utf-8"))
    if design not in campaign["designs"] or seed not in campaign["physical_seeds"] or K not in campaign["K_values"]:
        raise ValueError("Route context is outside the frozen population")
    candidate_dir = candidate_dir.resolve()
    architecture_path = candidate_dir / "architecture.json"
    proxy_path = candidate_dir / "proxy.json"
    architecture = ScanArchitecture.from_json(architecture_path)
    proxy = json.loads(proxy_path.read_text(encoding="utf-8"))
    if proxy.get("architecture_sha256") != architecture.sha256() or len(architecture.chains) != K:
        raise ValueError("Candidate architecture/proxy/K mismatch")

    flow = Path(os.environ.get("PACT_ORFS_FLOW", "/root/pact-deps/OpenROAD-flow-scripts/flow"))
    block = BLOCK[design]
    base = flow / f"results/nangate45/{block}/phase0b_s{seed}_B0"
    variant_name = f"phase0d_{evidence_namespace}_s{seed}_k{K}_{architecture.sha256()[:12]}"
    variant = flow / f"results/nangate45/{block}/{variant_name}"
    logs = flow / f"logs/nangate45/{block}/{variant_name}"
    frozen_def = ROOT / f"artifacts/raw/phase0b/placements/{design}/s{seed}/placed.def"
    evidence = ROOT / f"artifacts/raw/phase0d/{evidence_namespace}/{design}/s{seed}/k{K}/{architecture.sha256()}"
    evidence.mkdir(parents=True, exist_ok=True)
    result_path = evidence / "route_result.json"
    archive_path = evidence / "5_2_route.odb.gz"
    route_inputs = [
        architecture_path, proxy_path, frozen_def, base / "3_place.odb", base / "3_place.sdc",
        contract_path, pilot_contract_path, ROOT / "scripts/phase0c_rewire_odb.py",
        ROOT / "scripts/phase0d_verify_routed.py", ROOT / "scripts/phase0d_run_route.py",
    ]
    route_input_sha256 = {
        (str(path.relative_to(ROOT)).replace("\\", "/") if path.is_relative_to(ROOT)
         else f"external/{path.name}"): file_sha256(path)
        for path in route_inputs
    }
    if result_path.is_file():
        prior = json.loads(result_path.read_text(encoding="utf-8"))
        if (prior.get("status") == "QUALIFIED" and prior.get("architecture_sha256") == architecture.sha256()
                and prior.get("input_sha256") == route_input_sha256
                and _archived_odb_matches(archive_path, prior.get("routed_odb_sha256", ""))):
            return {**prior, "reuse_status": "REUSED_VERIFIED"}

    disk_floor = int(pilot_contract["routing"]["minimum_free_disk_bytes"])
    check_disk_floor(ROOT, disk_floor)
    check_disk_floor(flow, disk_floor)
    deadline = time.monotonic() + cap_seconds
    variant.mkdir(parents=True, exist_ok=True)
    rewire_command = [
        "openroad", "-python", "-no_init", "-exit", str(ROOT / "scripts/phase0c_rewire_odb.py"),
        "--source", str(base / "3_place.odb"), "--architecture", str(architecture_path),
        "--output", str(variant / "3_place.odb"),
    ]
    rewire_budget = _remaining(deadline, 120)
    if rewire_budget == 0:
        return {"status": "TIMEOUT", "stage": "BEFORE_REWIRE"}
    rewired = run_bounded(rewire_command, evidence / "rewire", ROOT, rewire_budget,
                          [variant / "3_place.odb"])
    if rewired["exit_code"] != 0 or rewired["timed_out"] or not rewired["required_outputs_present"]:
        result = {"status": "TIMEOUT" if rewired["timed_out"] else "FAILED", "stage": "REWIRE"}
        atomic_write_json(result_path, result)
        return result
    shutil.copy2(base / "3_place.sdc", variant / "3_place.sdc")
    design_config = (ROOT / "experiments/phase0b/s15850_orfs/config.mk" if design == "s15850"
                     else ROOT / f"experiments/phase0/{design}_orfs/config.mk")
    make_command = [
        "make", "-o", f"./results/nangate45/{block}/{variant_name}/3_place.odb",
        "-o", f"./results/nangate45/{block}/{variant_name}/3_place.sdc",
        f"DESIGN_CONFIG={design_config}", f"FLOW_VARIANT={variant_name}", f"GRT_SEED={seed}",
        "OPENROAD_EXE=/usr/bin/openroad", "YOSYS_EXE=/usr/bin/yosys", "route",
    ]
    required = [logs / "5_1_grt.json", logs / "5_2_route.json", variant / "5_2_route.odb"]
    route_budget = _remaining(deadline, int(pilot_contract["routing"]["route_timeout_seconds"]))
    if route_budget == 0:
        result = {"status": "TIMEOUT", "stage": "BEFORE_ROUTE"}
        atomic_write_json(result_path, result)
        return result
    routed = run_bounded(make_command, evidence / "route", flow, route_budget, required)
    if routed["exit_code"] != 0 or routed["timed_out"] or not routed["required_outputs_present"]:
        result = {"status": "TIMEOUT" if routed["timed_out"] else "FAILED", "stage": "ROUTE",
                  "route_execution": "route/execution.json"}
        atomic_write_json(result_path, result)
        return result
    for source in required[:2]:
        shutil.copy2(source, evidence / source.name)
    with (variant / "5_2_route.odb").open("rb") as incoming, archive_path.open("wb") as outgoing:
        with gzip.GzipFile(filename="", mode="wb", fileobj=outgoing, mtime=0) as compressed:
            shutil.copyfileobj(incoming, compressed)
    grt = json.loads((evidence / "5_1_grt.json").read_text(encoding="utf-8"))
    drt = json.loads((evidence / "5_2_route.json").read_text(encoding="utf-8"))
    metrics = extract_structured_metrics(grt, drt)
    congestion = parse_grt_congestion((evidence / "route/stdout.log").read_text(encoding="utf-8", errors="replace"))
    metrics["initial_global_route_congestion"] = congestion
    if congestion:
        metrics["global_route_overflow"] = congestion["total"]["total_overflow"]
        metrics["layer_utilization"] = {name: row["usage_percent"] for name, row in congestion["layers"].items()}

    verification_path = evidence / "routed_verification.json"
    verify_command = [
        "openroad", "-python", "-no_init", "-exit", str(ROOT / "scripts/phase0d_verify_routed.py"),
        "--routed", str(variant / "5_2_route.odb"), "--architecture", str(architecture_path),
        "--frozen-def", str(frozen_def), "--output", str(verification_path),
    ]
    verify_budget = _remaining(deadline, 90)
    verified = (run_bounded(verify_command, evidence / "postroute_verify", ROOT, verify_budget,
                            [verification_path]) if verify_budget else None)
    proof = json.loads(verification_path.read_text(encoding="utf-8")) if verification_path.is_file() else None
    proof_ok = bool(verified and verified["exit_code"] == 0 and not verified["timed_out"]
                    and verified["required_outputs_present"] and proof and proof.get("status") == "PASS")
    status = ("ROUTED_DRC_FAIL" if metrics["detailed_route_drc_errors"] != 0 else
              "POSTROUTE_VERIFICATION_FAILED" if not proof_ok else "QUALIFIED")
    result = {
        "schema_version": "phase0d-route-result-1",
        "status": status,
        "reuse_status": "EXECUTED_NEW",
        "design": design,
        "physical_seed": seed,
        "K": K,
        "evidence_namespace": evidence_namespace,
        "architecture_sha256": architecture.sha256(),
        "proxy_sha256": file_sha256(proxy_path),
        "scan_hpwl_proxy_um": proxy["scan_geometry"]["total_scan_hpwl_um"],
        "DRC_errors": metrics["detailed_route_drc_errors"],
        "structured_metrics": metrics,
        "postroute_verification": proof,
        "exact_scan_only_routed_length_um": proof.get("exact_scan_only_total_um") if proof_ok else None,
        "routed_full_scan_path_net_length_upper_bound_um": (
            proof.get("routed_full_scan_path_net_length_upper_bound_um") if proof_ok else None),
        "route_wall_seconds": routed["elapsed_s"],
        "rewire_wall_seconds": rewired["elapsed_s"],
        "postroute_verify_wall_seconds": verified["elapsed_s"] if verified else None,
        "routed_odb_sha256": file_sha256(variant / "5_2_route.odb"),
        "routed_odb_gzip_sha256": file_sha256(archive_path),
        "routed_odb_archive_bytes": archive_path.stat().st_size,
        "routed_odb_archive": str(archive_path.relative_to(ROOT)).replace("\\", "/"),
        "source_placement": f"${{PACT_ORFS_FLOW}}/results/nangate45/{block}/phase0b_s{seed}_B0/3_place.odb",
        "input_sha256": route_input_sha256,
    }
    atomic_write_json(result_path, result)
    if status == "QUALIFIED":
        shutil.rmtree(variant)
        if logs.is_dir():
            shutil.rmtree(logs)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--design", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--k", type=int, required=True)
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument("--cap-seconds", type=int, default=750)
    parser.add_argument("--evidence-namespace", choices=("pilot", "optimizer_v1"), default="pilot")
    args = parser.parse_args()
    result = route_one(args.design, args.seed, args.k, args.candidate_dir, args.cap_seconds,
                       args.evidence_namespace)
    print(json.dumps({key: result.get(key) for key in (
        "status", "reuse_status", "architecture_sha256", "DRC_errors", "route_wall_seconds")}, sort_keys=True))
    if result.get("status") not in {"QUALIFIED", "TIMEOUT"}:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
