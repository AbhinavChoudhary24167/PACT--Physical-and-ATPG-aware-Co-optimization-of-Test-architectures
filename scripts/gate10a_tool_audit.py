#!/usr/bin/env python3
"""Read-only Gate 10A tool and frozen-PDN inventory, without scientific solves."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/gate10a"
PLATFORM = Path("/root/pact-deps/OpenROAD-flow-scripts/flow/platforms/nangate45")
FROZEN = Path("/mnt/d/PACT_EXPERIMENTS/results/pact_gate09_open_source_20261005/repair_attempts")
ODBS = {
    "b14_opt": FROZEN / "python_transport/baselines/b14_opt/B3T/physical/5_2_route.odb.gz",
    "b15_opt": FROZEN / "metadata_registration_b15_opt/baselines/b15_opt/B2/physical/5_2_route.odb.gz",
}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    logs = []

    def run(name, argv, extra_env=None):
        env = dict(os.environ)
        env.update(extra_env or {})
        started = datetime.now(timezone.utc).isoformat()
        before = time.monotonic()
        proc = subprocess.run(argv, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        path = OUT / (name + ".log")
        path.write_bytes(proc.stdout)
        logs.append({"name": name, "argv": argv, "environment_overrides": extra_env or {},
                     "started_utc": started, "wall_seconds": time.monotonic() - before,
                     "returncode": proc.returncode, "log": str(path.relative_to(ROOT)),
                     "log_sha256": sha(path)})
        if proc.returncode or b"Error:" in proc.stdout or b"[ERROR" in proc.stdout:
            raise RuntimeError(f"Read-only probe failed: {name}; inspect {path}")
        return proc.stdout.decode("utf-8", errors="replace")

    capability = run("capability_probe", ["/usr/bin/openroad", "-no_init", "-exit", "scripts/tcl/gate10a_capability_probe.tcl"])
    inventories = {}
    for design, odb in ODBS.items():
        text = run("pdn_inventory_" + design, ["/usr/bin/openroad", "-no_init", "-exit", "scripts/tcl/gate10a_pdn_inventory.tcl"], {"GATE10A_ODB": str(odb)})
        inventories[design] = {"input_path": str(odb), "input_sha256": sha(odb),
                               "structural_inventory": text, "scientific_analysis": False}
    versions = {}
    for tool in ("openroad", "sta"):
        versions[tool] = {"path": "/usr/bin/" + tool, "sha256": sha("/usr/bin/" + tool),
                          "version": run("version_" + tool, ["/usr/bin/" + tool, "-version"]).strip()}
    for name in ("OpenROAD", "OpenROAD-flow-scripts"):
        versions[name + "_source"] = {"path": "/root/pact-deps/" + name,
            "commit": run("source_" + name, ["git", "-C", "/root/pact-deps/" + name, "rev-parse", "HEAD"]).strip()}
    libs = {}
    for name in ("lib/NangateOpenCellLibrary_typical.lib", "setRC.tcl", "grid_strategy-M1-M4-M7.tcl"):
        path = PLATFORM / name
        libs[name] = {"path": str(path), "sha256": sha(path)}
    expected_binary = "fcd7dcfc37d329bd43a7ede75805319a2e70e6879da11d42b4fd1c2e50e645c3"
    record = {
        "schema": "pact_gate10a_tool_provenance_v1", "created_utc": datetime.now(timezone.utc).isoformat(),
        "audit_kind": "READ_ONLY_NO_SCIENTIFIC_EXECUTION", "tools": versions, "platform_inputs": libs,
        "gate09_expected_openroad_binary_sha256": expected_binary,
        "gate09_openroad_binary_identity_matches": versions["openroad"]["sha256"] == expected_binary,
        "installed_openroad_revision": "08f67ee5ecd14db5a42be8c610bbfd1ccf079299",
        "installed_declared_opensta_revision": "76c4d6df3537ccce331b5caa812196c3330ba7c4",
        "source_limitation": "Local OpenROAD checkout is a different revision; OpenSTA submodule is not populated. Runtime embedded Tcl procedure/help is authoritative; local C++ sources are supporting inspection only. Binary linkage has not been rebuilt independently.",
        "capability_probe_complete": "GATE10A_API_COMPLETE" in capability,
        "frozen_pdn_inventories": inventories,
        "method_defaults": {
            "liberty": "NangateOpenCellLibrary_typical.lib", "voltage_v": 1.1, "scan_period_ns": 10,
            "measured_density_per_ns": "sum(uint8_settled_transitions)/(shift_cycles*10)",
            "set_power_activity_semantics": "-density is transitions per library UI time unit; runtime divides by time_ui_sta(1). Library unit=1ns.",
            "activity_syntax": "set_power_activity -pins <instance/pin_collection> -density <transitions/ns> -duty 0.5",
            "clock": "create_clock -name gate10a_scan -period 10 -waveform {0 5} <frozen_clock_port>; propagated clock activity 2 transitions per cycle",
            "nonclock_duty": 0.5, "scan_enable_duty": 1.0,
            "pdn": "REUSE_FROZEN_M1_M4_M7_SPECIAL_WIRES; no synthesis or route changes",
            "source_model": "Explicit ideal VDD sources two per top-layer VDD stripe, endpoint centers inset half stripe width, square size=stripe width, voltage=1.1V; same per-design source and PDN geometry hashes across architectures",
            "source_file_columns": ["x_um", "y_um", "square_size_um", "voltage_v"],
            "pdnsim_external_resistance_ohm": 0.0, "primary_net": "VDD",
            "ir_syntax": "analyze_power_grid -net VDD -vsrc <sources.csv> -voltage_file <instance_voltage.csv> -enable_em -em_outfile <segment_current.csv> -error_file <errors.txt>",
            "voltage_output": "Instance,Terminal,Layer,X location,Y location,Voltage (um,V); instance-terminal samples",
            "current_output": "Node0 Layer,Node0 X location,Node0 Y location,Node1 Layer,Node1 X location,Node1 Y location,Current (um,A); segment current, not physical current density",
            "interpretation": "Liberty-characterized activity-derived mean cell power and static VDD resistive solve, not transient droop or thermal evaluation",
        }, "logs": logs,
    }
    (OUT / "tool_provenance.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"audit": "complete", "tool_provenance": "reports/gate10a/tool_provenance.json", "sha256": sha(OUT / "tool_provenance.json")}))


if __name__ == "__main__":
    main()
