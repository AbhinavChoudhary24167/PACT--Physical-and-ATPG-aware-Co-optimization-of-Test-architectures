#!/usr/bin/env python3
"""Finalize Optimizer-v1 reports without changing the frozen search state."""
from __future__ import annotations

import json
from pathlib import Path
import runpy
import time


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts/phase0d_optimizer_v1.py"
ARTIFACT_ROOT = ROOT / "artifacts/derived/phase0d/optimizer_v1/s5378/s11/k2"
REPORT_ROOT = ROOT / "reports/phase0d/optimizer_v1"


def main() -> None:
    started = time.monotonic()
    runner = runpy.run_path(str(RUNNER_PATH))
    state = runner["read_json"](ARTIFACT_ROOT / "optimizer_state.json")
    optimizer_invocation = sum(
        float(row["invocation_search_wall_seconds"])
        for row in state.get("process_invocations", [])
    )
    runner["finalize"](state, ARTIFACT_ROOT, optimizer_invocation)
    status_path = REPORT_ROOT / "optimizer_v1_status.json"
    status = runner["read_json"](status_path)

    rewire_seconds = sum(float(row.get("rewire_wall_seconds") or 0.0) for row in status["route_results"])
    route_seconds = sum(float(row.get("route_wall_seconds") or 0.0) for row in status["route_results"])
    successful_verify_seconds = sum(
        float(row.get("postroute_verify_wall_seconds") or 0.0) for row in status["route_results"]
    )
    superseded_verify_seconds = 0.0
    for route in status["route_results"]:
        route_path = ROOT / route["path"]
        verify_dir = route_path.parent / "postroute_verify"
        for attempt in verify_dir.glob("attempt_*/execution.json"):
            superseded_verify_seconds += float(runner["read_json"](attempt).get("elapsed_s") or 0.0)
    reporting_seconds = time.monotonic() - started
    runtime = status["runtime"]
    runtime.update({
        "process_invocation_wall_seconds": optimizer_invocation,
        "process_invocation_definition": (
            "cumulative optimizer process interval from search entry through search completion; "
            "report finalization is recorded separately"
        ),
        "route_wall_seconds": route_seconds,
        "rewire_wall_seconds": rewire_seconds,
        "successful_postroute_verification_wall_seconds": successful_verify_seconds,
        "superseded_postroute_verification_wall_seconds": superseded_verify_seconds,
        "report_finalization_wall_seconds_to_status_write": reporting_seconds,
        "total_campaign_elapsed_seconds": (
            optimizer_invocation + rewire_seconds + route_seconds + successful_verify_seconds
            + superseded_verify_seconds + reporting_seconds
        ),
        "total_campaign_elapsed_definition": (
            "sum of recorded active optimizer, rewire, route, all verification attempts, and finalization intervals; "
            "excludes idle time between invocations"
        ),
    })
    runner["atomic_write_json"](status_path, status)

    routed_lines = []
    for row in status["route_results"]:
        metrics = row["structured_metrics"]
        congestion = metrics["initial_global_route_congestion"]["total"]
        proof = row["postroute_verification"]
        routed_lines.extend([
            f"- architecture: `{row['architecture_sha256']}`",
            f"- status: `{row['status']}`; detailed-route DRC errors: {row['DRC_errors']}",
            f"- full-netlist detailed-route wirelength: {metrics['total_detailed_route_wirelength_um']} µm",
            f"- detailed-route vias: {metrics['detailed_route_vias']}",
            f"- global-route setup/hold WNS: {metrics['setup_wns_ns']} / {metrics['hold_wns_ns']} ns",
            f"- initial global-route utilization/overflow: {congestion['usage_percent']}% / {congestion['total_overflow']}",
            f"- route wall time: {row['route_wall_seconds']:.6f} s",
            f"- compressed routed ODB: {row['routed_odb_archive_bytes']} bytes",
            f"- structural reconstruction: `{proof['status']}`; {proof['scan_edges']} scan edges verified",
            f"- routed full scan-path upper bound: {proof['routed_full_scan_path_net_length_upper_bound_um']} µm",
        ])
    report_path = REPORT_ROOT / "OPTIMIZER_V1_REPORT.md"
    report = report_path.read_text(encoding="utf-8").split("\n## Routed qualification evidence\n")[0].rstrip()
    report += "\n\n## Routed qualification evidence\n\n"
    report += ("\n".join(routed_lines) if routed_lines else "No routing was performed.") + "\n"
    report_path.write_text(report, encoding="utf-8", newline="\n")

    status_md_path = REPORT_ROOT / "OPTIMIZER_V1_STATUS.md"
    status_md = status_md_path.read_text(encoding="utf-8").split("\n## Routed evidence\n")[0].rstrip()
    status_md += "\n\n## Routed evidence\n\n"
    status_md += ("\n".join(routed_lines) if routed_lines else "No routing was performed.") + "\n"
    status_md_path.write_text(status_md, encoding="utf-8", newline="\n")

    manifest_path = REPORT_ROOT / "optimizer_v1_manifest.json"
    manifest = runner["read_json"](manifest_path)
    manifest["reporting_generator"] = {
        "path": runner["relative"](Path(__file__).resolve()),
        "sha256": runner["file_sha256"](Path(__file__).resolve()),
    }
    for artifact in manifest["artifacts"]:
        path = ROOT / artifact["path"]
        artifact["sha256"] = runner["file_sha256"](path)
        artifact["bytes"] = path.stat().st_size
    runner["atomic_write_json"](manifest_path, manifest)
    print(json.dumps({
        "status": status["status"], "route_status": status["route_status"],
        "process_invocation_wall_seconds": optimizer_invocation,
        "search_wall_clock_seconds": runtime["search_wall_clock_seconds"],
        "route_wall_seconds": route_seconds,
        "total_campaign_elapsed_seconds": runtime["total_campaign_elapsed_seconds"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
