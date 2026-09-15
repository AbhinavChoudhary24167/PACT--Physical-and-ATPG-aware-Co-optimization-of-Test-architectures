#!/usr/bin/env python3
"""Resumable bounded Phase-0C route attempt from a frozen physical seed."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import time

from pact.physical.phase0b_structured_metrics import extract_structured_metrics
from pact.physical.phase0c_congestion import parse_grt_congestion
from pact.scan.model import ScanArchitecture
from phase0b_run_command import run


ROOT = Path(__file__).resolve().parents[1]
FLOW = Path("/root/pact-deps/OpenROAD-flow-scripts/flow")
BLOCK = {"s5378": "s5378", "s9234": "s9234f", "s15850": "s15850"}


def remaining(deadline: float, stage_cap: int) -> int:
    return max(0, min(stage_cap, int(deadline - time.monotonic())))


def status(path: Path, value: str, **extra) -> None:
    path.write_text(json.dumps({"status": value, **extra}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def archived_odb_matches(path: Path, expected_sha256: str) -> bool:
    if not path.is_file():
        return False
    digest = hashlib.sha256()
    with gzip.open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest() == expected_sha256


def archive_superseded_evidence(evidence: Path, previous: dict) -> None:
    """Copy a completed pilot aside before the frozen campaign reuses its path."""
    old_variant = str(previous.get("variant", "unknown"))
    archive_dir = evidence / "variants" / old_variant
    archive_dir.mkdir(parents=True, exist_ok=True)
    for source in evidence.iterdir():
        if source.is_file():
            destination = archive_dir / source.name
        else:
            continue
        if not destination.exists():
            shutil.copy2(source, destination)


def route_one(design: str, seed: int, k: int, method: str, cap_s: int,
              campaign_freeze_commit: str | None = None) -> dict:
    campaign = json.loads((ROOT / "config/phase0c_campaign.json").read_text())
    if design not in campaign["designs"] or seed not in campaign["physical_seeds"] or k not in campaign["K_values"] or (method not in campaign["route_families_each_K"] and not (method == "B1" and k == 1)):
        raise ValueError("Run not in candidate campaign")
    architecture = ROOT / f"artifacts/derived/phase0c/{design}/s{seed}/k{k}/{method}.architecture.json"
    arch = ScanArchitecture.from_json(architecture)
    rewire_sha256 = hashlib.sha256((ROOT / "scripts/phase0c_rewire_odb.py").read_bytes()).hexdigest()
    prefix = f"phase0c_f{campaign_freeze_commit[:8]}" if campaign_freeze_commit else "phase0c"
    variant_name = f"{prefix}_s{seed}_k{k}_{method}_{arch.sha256()[:8]}_{rewire_sha256[:8]}"
    block = BLOCK[design]
    base = FLOW / f"results/nangate45/{block}/phase0b_s{seed}_B0"
    variant = FLOW / f"results/nangate45/{block}/{variant_name}"
    logs = FLOW / f"logs/nangate45/{block}/{variant_name}"
    evidence = ROOT / f"artifacts/raw/phase0c/physical/{design}/s{seed}/k{k}/{method}"
    evidence.mkdir(parents=True, exist_ok=True)
    state_path = evidence / "status.json"
    metrics_path = evidence / "route_metrics.json"
    if metrics_path.exists():
        previous = json.loads(metrics_path.read_text(encoding="utf-8"))
        raw_odb = evidence / "5_2_route.odb"
        compressed_odb = evidence / "5_2_route.odb.gz"
        odb_valid = (archived_odb_matches(compressed_odb, previous.get("routed_odb_sha256", ""))
                     if compressed_odb.exists() else
                     raw_odb.is_file() and hashlib.sha256(raw_odb.read_bytes()).hexdigest()
                     == previous.get("routed_odb_sha256"))
        if (previous.get("status") == "QUALIFIED" and previous.get("DRC_errors") == 0
                and previous.get("architecture_sha256") == arch.sha256()
                and previous.get("variant") == variant_name
                and odb_valid):
            return {**previous, "resumed_valid_result": True}
        archive_superseded_evidence(evidence, previous)
    deadline = time.monotonic() + cap_s
    variant.mkdir(parents=True, exist_ok=True)
    command = ["openroad", "-python", "-no_init", "-exit", str(ROOT / "scripts/phase0c_rewire_odb.py"),
               "--source", str(base / "3_place.odb"), "--architecture", str(architecture),
               "--output", str(variant / "3_place.odb")]
    status(state_path, "REWIRE_RUNNING", variant=variant_name)
    budget = remaining(deadline, 120)
    if budget == 0:
        status(state_path, "CAMPAIGN_TIMEOUT_BEFORE_REWIRE", variant=variant_name)
        return {"status": "CAMPAIGN_TIMEOUT_BEFORE_REWIRE"}
    rewired = run(command, evidence / "rewire", ROOT, budget, [variant / "3_place.odb"])
    if rewired["exit_code"] != 0 or rewired["timed_out"] or not rewired["required_outputs_present"]:
        status(state_path, "REWIRE_FAILED", variant=variant_name, execution=str(evidence / "rewire/execution.json"))
        return {"status": "REWIRE_FAILED"}
    shutil.copy2(base / "3_place.sdc", variant / "3_place.sdc")
    config = (ROOT / f"experiments/phase0b/s15850_orfs/config.mk" if design == "s15850" else
              ROOT / f"experiments/phase0/{design}_orfs/config.mk")
    make_command = ["make", "-o", f"./results/nangate45/{block}/{variant_name}/3_place.odb",
                    "-o", f"./results/nangate45/{block}/{variant_name}/3_place.sdc",
                    f"DESIGN_CONFIG={config}", f"FLOW_VARIANT={variant_name}", f"GRT_SEED={seed}",
                    "OPENROAD_EXE=/usr/bin/openroad", "YOSYS_EXE=/usr/bin/yosys", "route"]
    required = [logs / "5_1_grt.json", logs / "5_2_route.json", variant / "5_2_route.odb"]
    budget = remaining(deadline, campaign["per_run_timeout_s"])
    if budget == 0:
        status(state_path, "CAMPAIGN_TIMEOUT_BEFORE_ROUTE", variant=variant_name)
        return {"status": "CAMPAIGN_TIMEOUT_BEFORE_ROUTE"}
    status(state_path, "ROUTE_RUNNING", variant=variant_name, route_timeout_s=budget)
    routed = run(make_command, evidence / "route", FLOW, budget, required)
    if routed["exit_code"] != 0 or routed["timed_out"] or not routed["required_outputs_present"]:
        label = "ROUTE_TIMEOUT" if routed["timed_out"] else "ROUTE_FAILED"
        status(state_path, label, variant=variant_name, execution=str(evidence / "route/execution.json"))
        return {"status": label}
    for source in required:
        if source.suffix == ".odb":
            with source.open("rb") as incoming, (evidence / "5_2_route.odb.gz").open("wb") as outgoing:
                with gzip.GzipFile(filename="", mode="wb", fileobj=outgoing, mtime=0) as compressed:
                    shutil.copyfileobj(incoming, compressed)
        else:
            shutil.copy2(source, evidence / source.name)
    metrics = extract_structured_metrics(json.loads((evidence / "5_1_grt.json").read_text()),
                                         json.loads((evidence / "5_2_route.json").read_text()))
    congestion = parse_grt_congestion((evidence / "route/stdout.log").read_text(encoding="utf-8", errors="replace"))
    if congestion:
        congestion["source_stdout_sha256"] = routed["stdout_sha256"]
    metrics["congestion"] = congestion
    metrics["global_route_overflow"] = congestion["total"]["total_overflow"] if congestion else None
    metrics["layer_utilization"] = ({name: row["usage_percent"] for name, row in congestion["layers"].items()}
                                    if congestion else {})
    metrics["congestion_classification"] = ("QUALIFIED_INITIAL_GLOBAL_ROUTE_REPORT" if congestion else
                                            "UNAVAILABLE_IN_SAVED_ROUTE_STDOUT")
    verification_path = evidence / "routed_verification.json"
    verification_command = ["openroad", "-python", "-no_init", "-exit",
                            str(ROOT / "scripts/phase0c_verify_routed.py"),
                            "--routed", str(variant / "5_2_route.odb"),
                            "--architecture", str(architecture), "--output", str(verification_path)]
    verify_budget = remaining(deadline, 90)
    verified = (run(verification_command, evidence / "postroute_verify", ROOT, verify_budget,
                    [verification_path]) if verify_budget else None)
    proof = json.loads(verification_path.read_text()) if verification_path.exists() else None
    proof_ok = bool(verified and verified["exit_code"] == 0 and not verified["timed_out"]
                    and verified["required_outputs_present"] and proof and proof.get("status") == "PASS")
    label = ("ROUTED_DRC_FAIL" if metrics["detailed_route_drc_errors"] != 0 else
             "POSTROUTE_VERIFICATION_FAILED" if not proof_ok else "QUALIFIED")
    record = {"status": label, "design": design, "physical_seed": seed, "K": k, "method": method,
              "architecture_sha256": arch.sha256(), "DRC_errors": metrics["detailed_route_drc_errors"],
              "rewire_script_sha256": rewire_sha256,
              "campaign_freeze_commit": campaign_freeze_commit,
              "physical_primary_um": None, "scan_hpwl_proxy_um": json.loads((ROOT / f"artifacts/derived/phase0c/{design}/s{seed}/k{k}/{method}.proxy.json").read_text())["scan_geometry"]["total_scan_hpwl_um"],
              "structured_metrics": metrics, "source_placement_odb": str(base / "3_place.odb"),
              "variant": variant_name,
              "routed_odb_sha256": hashlib.sha256((variant / "5_2_route.odb").read_bytes()).hexdigest(),
              "routed_odb_archive": str((evidence / "5_2_route.odb.gz").relative_to(ROOT)),
              "routed_odb_gzip_sha256": hashlib.sha256((evidence / "5_2_route.odb.gz").read_bytes()).hexdigest()}
    record["postroute_verification"] = str(verification_path.relative_to(ROOT)) if proof_ok else None
    record["exact_scan_only_routed_length_um"] = proof["exact_scan_only_total_um"] if proof_ok else None
    record["routed_full_scan_path_net_length_upper_bound_um"] = (
        proof["routed_full_scan_path_net_length_upper_bound_um"] if proof_ok else None)
    record["physical_primary_um"] = record["scan_hpwl_proxy_um"] if label == "QUALIFIED" else None
    metrics_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    status(state_path, label, variant=variant_name, DRC_errors=record["DRC_errors"])
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--design", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--k", type=int, required=True)
    parser.add_argument("--method", required=True)
    parser.add_argument("--cap-s", type=int, default=1020)
    args = parser.parse_args()
    print(json.dumps(route_one(args.design, args.seed, args.k, args.method, args.cap_s), sort_keys=True))


if __name__ == "__main__":
    main()
