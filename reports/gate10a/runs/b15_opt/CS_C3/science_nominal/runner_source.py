#!/usr/bin/env python3
"""Run a preregistered frozen Gate10A architecture; preserve every attempt."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/gate10a"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def binding(path):
    path = Path(path)
    return {"path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def resolve(path):
    if path.startswith("repo://"):
        return ROOT / path[7:]
    # Accept cross-platform receipts, always resolving the current repo explicitly.
    if re.match(r"^[A-Za-z]:[/\\]", path):
        normalized = path.replace("\\", "/")
        marker = "/PACT/PACT/"
        if marker in normalized:
            return ROOT / normalized.split(marker, 1)[1]
        return Path("/mnt/" + normalized[0].lower() + "/" + normalized[3:])
    return Path(path) if Path(path).is_absolute() else ROOT / path


def verify(expected):
    path = resolve(expected["path"])
    observed = binding(path)
    if observed["sha256"] != expected["sha256"] or ("bytes" in expected and observed["bytes"] != expected["bytes"]):
        raise ValueError("Frozen input identity mismatch: " + str(path))
    return path


def frozen(relative, commit):
    data = subprocess.check_output(["git", "show", commit + ":" + relative], cwd=ROOT)
    path = ROOT / relative
    if path.read_bytes() != data:
        raise ValueError("Committed preregistration input changed: " + relative)
    return json.loads(data), binding(path)


def tclword(value):
    value = str(value)
    if any(c in value for c in ("{", "}", "\\", "\n", "\r")):
        raise ValueError("Unsupported Tcl token requires explicit escaping: " + repr(value))
    return "{" + value + "}"


def percentile(values, p):
    ordered = sorted(values)
    x = (len(ordered) - 1) * p / 100
    low, high = math.floor(x), math.ceil(x)
    return ordered[low] + (ordered[high] - ordered[low]) * (x - low)


def resources():
    memory = {line.split(":")[0]: int(line.split()[1]) * 1024
              for line in Path("/proc/meminfo").read_text().splitlines() if len(line.split()) >= 2}
    host = subprocess.check_output(["/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
        "-NoProfile", "-NonInteractive", "-Command", "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory"],
        text=True, stderr=subprocess.PIPE)
    return {"host_available_memory_bytes": int(host.strip()) * 1024,
            "wsl_available_memory_bytes": memory["MemAvailable"],
            "output_disk_free_bytes": shutil.disk_usage(ROOT).free,
            "linux_disk_free_bytes": shutil.disk_usage("/").free}


def parse_outputs(folder, row, protocol):
    log = (folder / "openroad.log").read_text()
    if "GATE10A_MEASURE_COMPLETE" not in log or "[ERROR" in log or re.search(r"(^|\n)Error:", log):
        raise ValueError("OpenROAD completion/error gate failed")
    with (folder / "instance_power.csv").open() as stream:
        powers = list(csv.DictReader(stream))
    if not powers or len({r["instance"] for r in powers}) != len(powers):
        raise ValueError("Empty/duplicate instance power population")
    bounds = row["bounds_um"]
    def coordinate(x, y, description):
        x, y = float(x), float(y)
        if not all(math.isfinite(v) for v in (x, y)) or not (bounds[0] <= x <= bounds[2] and bounds[1] <= y <= bounds[3]):
            raise ValueError("Invalid/out-of-die coordinate: " + description)
        return x, y
    for r in powers:
        coordinate(r["x_um"], r["y_um"], "instance " + r["instance"])
    totals = {key: math.fsum(float(r[key]) for r in powers)
              for key in ("internal_w", "switching_w", "leakage_w", "total_w")}
    for r in powers:
        for key in totals:
            if not math.isfinite(float(r[key])) or float(r[key]) < 0:
                raise ValueError("Nonfinite/negative instance power")
    if not math.isclose(totals["total_w"], sum(totals[k] for k in ("internal_w", "switching_w", "leakage_w")), rel_tol=1e-12, abs_tol=1e-15):
        raise ValueError("Instance power component closure failed")
    inventory = {r["instance"]: r for r in powers}
    domain = {r["instance"] for r in powers if r["physical_only"] == "0" and r["powered"] == "1" and r["liberty_modelled"] == "1"}
    if not domain:
        raise ValueError("Empty powered-instance domain")
    for error_file in ("connectivity_errors.txt", "solve_errors.txt"):
        path = folder / error_file
        if path.exists() and path.read_text().strip():
            raise ValueError("PDNSim connectivity/solve error file is nonempty: " + error_file)
    if log.count("All shapes on net VDD are connected.") != 2 or "IR report" not in log or "EM analysis" not in log:
        raise ValueError("Incomplete PDN connectivity/IR/EM success reports")
    with (folder / "instance_voltage.csv").open() as stream:
        raw = list(csv.DictReader(stream))
    by_instance = {}
    terminal_keys = set()
    for r in raw:
        name = r["Instance"]
        if name not in inventory:
            raise ValueError("Voltage instance lacks exported geometry")
        voltage = float(r["Voltage"])
        drop = protocol["voltage_v"] - voltage
        if not math.isfinite(voltage) or voltage < 0 or drop < -1e-9:
            raise ValueError("Invalid static supply voltage/drop")
        coordinate(r["X location"], r["Y location"], "supply terminal " + name)
        if r["Terminal"] != "VDD":
            raise ValueError("Unexpected primary supply terminal")
        key = (name, r["Terminal"], r["Layer"], r["X location"], r["Y location"])
        if key in terminal_keys:
            raise ValueError("Duplicate voltage terminal sample")
        terminal_keys.add(key)
        if name in domain:
            by_instance.setdefault(name, []).append(max(0.0, drop))
    if set(by_instance) != domain:
        raise ValueError("Incomplete powered-instance voltage coverage: " + repr(sorted(domain - set(by_instance))))
    # One worst terminal drop per powered instance; physical-only cells excluded.
    drops = [max(by_instance[name]) for name in sorted(domain)]
    normalized = folder / "instance_drop.csv"
    with normalized.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["instance", "x_um", "y_um", "drop_v", "powered", "physical_only"])
        writer.writeheader()
        for name in sorted(domain):
            writer.writerow({"instance": name, "x_um": inventory[name]["x_um"], "y_um": inventory[name]["y_um"],
                             "drop_v": repr(max(by_instance[name])), "powered": True, "physical_only": False})
    with (folder / "segment_current.csv").open() as stream:
        segments = list(csv.DictReader(stream))
    currents = [abs(float(r["Current"])) for r in segments]
    if not currents or not all(math.isfinite(v) and v >= 0 for v in currents):
        raise ValueError("Invalid/empty PDN segment-current output")
    for r in segments:
        for node in ("Node0", "Node1"):
            coordinate(r[node + " X location"], r[node + " Y location"], "PDN " + node)
    with (folder / "sources.csv").open() as stream:
        sources = list(csv.reader(stream))
    if not sources:
        raise ValueError("Empty source population")
    for r in sources:
        if len(r) != 4 or not all(math.isfinite(float(v)) for v in r):
            raise ValueError("Invalid PDN supply source row")
        coordinate(r[0], r[1], "PDN supply source")
        if float(r[2]) <= 0 or float(r[3]) != protocol["voltage_v"]:
            raise ValueError("Invalid PDN supply source size/voltage")
    with (folder / "segment_current_normalized.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["x_um", "y_um", "current_a", "layer0", "layer1"])
        writer.writeheader()
        for r, current in zip(segments, currents):
            writer.writerow({"x_um": (float(r["Node0 X location"]) + float(r["Node1 X location"])) / 2,
                             "y_um": (float(r["Node0 Y location"]) + float(r["Node1 Y location"])) / 2,
                             "current_a": current, "layer0": r["Node0 Layer"], "layer1": r["Node1 Layer"]})
    geo_lines = (folder / "pdn_geometry.tsv").read_text().splitlines()
    canonical = "\n".join([geo_lines[0]] + sorted(geo_lines[1:])) + "\n"
    (folder / "pdn_geometry_canonical.tsv").write_text(canonical)
    raw_sample_drop = max(protocol["voltage_v"] - float(r["Voltage"]) for r in raw)
    with (folder / "unannotated_nets.tsv").open() as stream:
        unannotated = list(csv.DictReader(stream, delimiter="\t"))
    if unannotated:
        raise ValueError("Unmeasured nonclock data nets require qualification: " + repr(unannotated[:5]))
    ff = re.search(r"GATE10A_FF_POPULATION (\d+)", log)
    if not ff or int(ff[1]) != row["ff_count"]:
        raise ValueError("Expected FF population mismatch")
    # The native JSON formatter emits SI watts; UI power units are independently
    # retained (Nangate is nW). A native float32 sequential reduction may differ
    # from math.fsum of exported instance float32 values. The standard gamma_n
    # bound follows only population size and IEEE float32 unit roundoff, never
    # observed scientific outcomes. JSON's 12 printed digits fit inside it.
    report = json.loads((folder / "power_report.json").read_text())
    units = json.loads((folder / "native_power_units.json").read_text())
    if not math.isclose(units["watts_per_UI_unit"] * units["UI_units_per_watt"], 1.0, rel_tol=1e-12):
        raise ValueError("Runtime power UI unit round-trip failed")
    categories = {"Sequential", "Combinational", "Clock", "Macro", "Pad", "Total"}
    if set(report) != categories:
        raise ValueError("Incomplete/unexpected native JSON power structure")
    component_names = {"internal_w": "internal", "switching_w": "switching", "leakage_w": "leakage", "total_w": "total"}
    n = len(powers)
    u = 2.0 ** -24
    gamma = n * u / (1.0 - n * u)
    native_checks = {}
    for field, native_name in component_names.items():
        native = float(report["Total"][native_name])
        values = [float(report[k][native_name]) for k in sorted(categories - {"Total"})]
        if not all(math.isfinite(v) and v >= 0 for v in [native, *values]):
            raise ValueError("Invalid native JSON power component")
        error_bound = gamma * abs(totals[field])
        difference = abs(native - totals[field])
        if difference > error_bound + 1e-15 or abs(native - math.fsum(values)) > gamma * native + 1e-15:
            raise ValueError("Native SI design/instance/group power closure failed: " + field)
        native_checks[field] = {"native_si_w": native, "instance_fsum_w": totals[field],
                                "absolute_difference_w": difference, "float32_reduction_bound_w": error_bound}
    log_match = re.search(r"GATE10A_POWER_SI ([\d.eE+-]+) ([\d.eE+-]+) ([\d.eE+-]+)", log)
    if not log_match or any(not math.isclose(float(v), totals[k], rel_tol=1e-12, abs_tol=1e-15)
                            for v, k in zip(log_match.groups(), ("internal_w", "switching_w", "leakage_w"))):
        raise ValueError("Independent log SI component closure failed")
    for group in report.values():
        if not math.isclose(float(group["total"]), math.fsum(float(group[k]) for k in ("internal", "switching", "leakage")), rel_tol=gamma, abs_tol=1e-15):
            raise ValueError("Native JSON component closure failed")
    return {"power": {**totals, "dynamic_w": totals["internal_w"] + totals["switching_w"]},
            "ir": {"worst_drop_v": max(drops), "mean_drop_v": math.fsum(drops) / len(drops),
                   **{f"p{p}_drop_v": percentile(drops, p) for p in protocol["percentiles"]},
                   "raw_terminal_worst_drop_v": raw_sample_drop, "powered_instances": len(domain),
                   "voltage_rows": len(raw), "primary_population": "one worst terminal per nonphysical Liberty-powered instance",
                   **{f"fraction_over_{fraction:g}_supply": sum(v > fraction * protocol["voltage_v"] for v in drops) / len(drops)
                      for fraction in protocol["drop_threshold_fraction"]}},
            "current": {"peak_segment_current_a": max(currents),
                        **{f"p{p}_segment_current_a": percentile(currents, p) for p in protocol["percentiles"]},
                        "segments": len(currents), "current_density_status": "NOT_AVAILABLE_NO_QUALIFIED_CROSS_SECTION"},
            "pdn_geometry_sha256": sha(folder / "pdn_geometry_canonical.tsv"),
            "sources_sha256": sha(folder / "sources.csv"), "bounds_um": row["bounds_um"],
            "annotation": {"unmeasured_nonclock_nets": len(unannotated)},
            "native_power_report_json_structure": type(report).__name__,
            "native_power_integrity": {"status": "PASS", "json_unit": "W", "runtime_UI_units": units,
                "float32_unit_roundoff": u, "population_n": n, "gamma_n": gamma, "checks": native_checks},
            "parser_coordinate_connectivity_integrity": "PASS"}


def run(args):
    protocol, protocol_binding = frozen("reports/gate10a/protocol.json", args.preregistered_commit)
    selection, selection_binding = frozen("reports/gate10a/selected_architectures.json", args.preregistered_commit)
    provenance, provenance_binding = frozen("reports/gate10a/tool_provenance.json", args.preregistered_commit)
    prereg = subprocess.check_output(["git", "show", args.preregistered_commit + ":reports/gate10a/preregistration.md"], cwd=ROOT)
    if (OUT / "preregistration.md").read_bytes() != prereg:
        raise ValueError("Preregistration changed")
    row = next(r for r in selection["architectures"] if r["design"] == args.design and r["architecture"] == args.architecture)
    label = args.label
    if not re.fullmatch(r"[a-z0-9_]+", label):
        raise ValueError("Unsafe run label")
    folder = OUT / "runs" / args.design / args.architecture / label
    if folder.exists():
        raise ValueError("Preserve immutable prior attempt: " + str(folder))
    folder.mkdir(parents=True)
    receipt = {"schema": "pact_gate10a_architecture_run_v1", "status": "STARTED", "started_utc": datetime.now(timezone.utc).isoformat(),
               "design": args.design, "architecture": args.architecture, "architecture_sha256": row["architecture_sha256"],
               "label": label, "nonclock_density_scale": args.density_scale,
               "preregistered_commit": args.preregistered_commit, "protocol": protocol_binding,
               "selection": selection_binding, "tool_provenance": provenance_binding,
               "scientific_stages_reexecuted": {"ATPG": 0, "PACT_search": 0, "placement": 0, "routing": 0, "extraction": 0, "replay": 0}}
    (folder / "started.json").write_text(json.dumps(receipt, indent=2) + "\n")
    lock = OUT / "control/eda.lock"
    locked = False
    try:
        observed = resources()
        receipt["resource_admission"] = observed
        if observed["host_available_memory_bytes"] < protocol["host_available_memory_floor_bytes"] or observed["wsl_available_memory_bytes"] < protocol["wsl_available_memory_floor_bytes"] or observed["output_disk_free_bytes"] < protocol["scratch_floor_bytes"] + protocol["estimated_output_per_architecture_bytes"]:
            receipt["status"] = "RESOURCE_ADMISSION_HOLD"
            raise RuntimeError("Fixed Gate10A resource admission floor not met")
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(descriptor, str(os.getpid()).encode())
        os.close(descriptor)
        locked = True
        verified = []
        for expected in [row["routed_archive"], row["SDC"], row["source_placed_database"], row["count_trace"], *row["exact_inputs"].values()]:
            path = verify(expected)
            verified.append({"expected": expected, "observed": binding(path), "status": "PASS"})
        for item in provenance["tools"].values():
            if "sha256" in item:
                verify(item)
        for item in provenance["platform_inputs"].values():
            verify(item)
        pg_path = OUT / "control/pg_connectivity_normalization.json"
        pg = json.loads(pg_path.read_text())
        pg_row = next(r for r in pg["records"] if r["design"] == args.design and r["architecture"] == args.architecture)
        if pg["status"] != "PASS" or pg_row["status"] != "PASS" or pg_row["original_ODB"] != row["routed_archive"] or pg_row["missing_after"]:
            raise ValueError("Common PG-only normalization audit lacks qualification")
        for expected in pg_row["outputs"]:
            verify(expected)
        receipt["PG_normalization_audit"] = binding(pg_path)
        inputs = OUT / "inputs" / args.design / args.architecture
        export_path = inputs / "activity_export_receipt.json"
        export = json.loads(export_path.read_text())
        if export["status"] != "PASS" or export["architecture_sha256"] != row["architecture_sha256"] or export["preregistered_commit"] != args.preregistered_commit or export["scan_cycles"] != row["cycles"]:
            raise ValueError("Derived activity export lacks qualification/identity")
        activity_csv = verify(export["output"])
        receipt["input_verifications"] = verified
        receipt["activity_export"] = binding(export_path)
        receipt["derived_activity_csv"] = binding(activity_csv)
        mapping = json.loads(verify(row["exact_inputs"]["net_mapping.json"]).read_text())
        with activity_csv.open() as stream:
            rows = list(csv.DictReader(stream))
        if [r["net"] for r in rows] != sorted(mapping["nets"]):
            raise ValueError("Derived CSV net order differs")
        activity = []
        for r in rows:
            name = r["net"]
            if r["source"] != mapping["nets"][name]["source"]:
                raise ValueError("Derived CSV driver mismatch")
            transitions = int(r["transitions"])
            if transitions < 0:
                raise ValueError("Negative transition total")
            is_enable = mapping["nets"][name]["source"] == "PORT/test_se" or name == "test_se"
            density = 0.0 if is_enable else transitions / (row["cycles"] * protocol["scan_period_ns"]) * args.density_scale
            activity.append("gate10a_annotate " + tclword(name) + f" {density:.17g} {1 if is_enable else protocol['nonclock_duty']:.17g} " + tclword("scan_enable" if is_enable else "frozen_count"))
        for name, reason in sorted(mapping["excluded"].items()):
            if reason == "clock":
                activity.append("gate10a_annotate " + tclword(name) + f" {2 / protocol['scan_period_ns']:.17g} {protocol['clock_duty']:.17g} " + tclword("fixed_scan_clock"))
        expected_ffs = sorted({r["source"][:-2] for r in mapping["nets"].values() if r["source"].endswith("/Q")})
        activity.append("set gate10a_expected_ffs {" + " ".join(tclword(name) for name in expected_ffs) + "}")
        activity_path = folder / "activity.tcl"
        activity_path.write_text("\n".join(activity) + "\n")
        source_snapshot = folder / "runner_source.py"
        shutil.copyfile(Path(__file__), source_snapshot)
        tcl_snapshot = folder / "measurement_source.tcl"
        shutil.copyfile(ROOT / "scripts/tcl/gate10a_measure.tcl", tcl_snapshot)
        env_overrides = {"GATE10A_LIBERTY": provenance["platform_inputs"]["lib/NangateOpenCellLibrary_typical.lib"]["path"],
            "GATE10A_ODB": str(resolve(row["routed_archive"]["path"])), "GATE10A_SDC": str(resolve(row["SDC"]["path"])),
            "GATE10A_SPEF": str(resolve(row["exact_inputs"]["extracted.spef"]["path"])),
            "GATE10A_SET_RC": provenance["platform_inputs"]["setRC.tcl"]["path"],
            "GATE10A_ACTIVITY_TCL": str(activity_path), "GATE10A_OUTPUT": str(folder),
            "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"}
        env = dict(os.environ)
        env.update(env_overrides)
        argv = ["/usr/bin/time", "-v", "-o", str(folder / "resources.txt"), "/usr/bin/openroad", "-no_init", "-exit", str(tcl_snapshot)]
        receipt.update(command=argv, environment_overrides=env_overrides,
                       execution_source_snapshots=[binding(source_snapshot), binding(tcl_snapshot), binding(activity_path)])
        before = time.monotonic()
        with (folder / "openroad.log").open("wb") as stream:
            proc = subprocess.run(argv, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
        receipt["wall_seconds"] = time.monotonic() - before
        receipt["returncode"] = proc.returncode
        raw_resources = (folder / "resources.txt").read_text()
        stats = {}
        for text, field, factor in (("User time (seconds)", "CPU_user_seconds", 1),
                                    ("System time (seconds)", "CPU_system_seconds", 1),
                                    ("Maximum resident set size (kbytes)", "peak_RSS_bytes", 1024)):
            match = re.search(re.escape(text) + r":\s*([\d.]+)", raw_resources)
            if match:
                stats[field] = float(match[1]) * factor
        receipt["runtime"] = stats
        if proc.returncode:
            raise RuntimeError("OpenROAD process failed")
        receipt["result"] = parse_outputs(folder, row, protocol)
        receipt["status"] = "QUALIFIED"
    except Exception as exc:
        if receipt["status"] == "STARTED":
            receipt["status"] = "IMPLEMENTATION_OR_QUALIFICATION_FAILURE"
        receipt["error"] = str(exc)
    finally:
        if locked:
            lock.unlink()
        receipt["completed_utc"] = datetime.now(timezone.utc).isoformat()
        receipt["outputs"] = [binding(p) for p in sorted(folder.iterdir()) if p.is_file()]
        receipt["disk_bytes"] = sum(item["bytes"] for item in receipt["outputs"])
        (folder / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"status": receipt["status"], "receipt": str((folder / "receipt.json").relative_to(ROOT)), "error": receipt.get("error")}))
    return receipt["status"] == "QUALIFIED"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--design", required=True)
    parser.add_argument("--architecture", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--density-scale", type=float, default=1.0, choices=[0.0, 1.0, 2.0])
    parser.add_argument("--preregistered-commit", required=True)
    raise SystemExit(0 if run(parser.parse_args()) else 2)
