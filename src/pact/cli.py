"""Reproducible Phase-0 command line entry points."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import yaml

from pact.analysis.aggregate import compare_results, load_results
from pact.analysis.plots import plot_results
from pact.physical.extract_placement import extract_def_scan_cells
from pact.physical.grid_metrics import placement_grid, spatial_activity
from pact.scan.identity import ff_identity_map
from pact.scan.model import ScanArchitecture
from pact.scan.validate import ScanConstraints, validate_ff_identity_map, validate_scan
from pact.test.activity_metrics import activity_metrics
from pact.test.pattern_parser import map_ppi_patterns, parse_fan_pat
from pact.test.shift_simulator import simulate_shift


ROOT = Path(__file__).resolve().parents[2]


def _doctor() -> int:
    """Check installed tools and external checkout identities with timeouts."""
    commands = {
        "openroad": ["openroad", "-version"], "yosys": ["yosys", "-V"],
        "klayout": ["klayout", "-v"], "git": ["git", "--version"],
        "make": ["make", "--version"], "g++": ["g++", "--version"],
    }
    tools = {}
    for name, command in commands.items():
        executable = shutil.which(command[0])
        if executable is None:
            tools[name] = {"status": "MISSING"}
            continue
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=15, check=False)
            line = (result.stdout + result.stderr).strip().splitlines()
            tools[name] = {"status": "PASS" if result.returncode == 0 else "FAIL",
                           "path": executable, "version": line[0] if line else "", "exit_code": result.returncode}
        except subprocess.TimeoutExpired:
            tools[name] = {"status": "TIMEOUT", "path": executable}
    repositories = {}
    for name, env_name in (("orfs", "PACT_ORFS_ROOT"), ("fan_atpg", "PACT_FAN_ATPG_ROOT")):
        location = os.environ.get(env_name)
        if not location or not Path(location).is_dir():
            repositories[name] = {"status": "MISSING", "environment_variable": env_name}
            continue
        try:
            result = subprocess.run(["git", "-C", location, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=15, check=False)
            repositories[name] = {"status": "PASS" if result.returncode == 0 else "FAIL",
                                  "path": location, "commit": result.stdout.strip()}
        except subprocess.TimeoutExpired:
            repositories[name] = {"status": "TIMEOUT", "path": location}
    print(json.dumps({"tools": tools, "repositories": repositories}, indent=2, sort_keys=True))
    return 0 if all(item["status"] == "PASS" for item in (*tools.values(), *repositories.values())) else 1


def _validate_scan(path: Path) -> int:
    architecture = ScanArchitecture.from_json(path)
    campaign = yaml.safe_load((ROOT / "config/campaign.yaml").read_text(encoding="utf-8"))
    settings = campaign["scan"]
    validate_scan(architecture, ScanConstraints(max_chain_length=settings["max_chain_length"],
                                                enforce_clock_domain=settings["enforce_clock_domain"]))
    print(json.dumps({"status": "PASS", "architecture_sha256": architecture.sha256(),
                      "num_cells": len(architecture.cells), "num_chains": len(architecture.chains)}, sort_keys=True))
    return 0


def _verify_identity(manifest_path: Path, architecture: ScanArchitecture, pattern_path: Path) -> list[dict[str, str]]:
    """Recheck saved hashes, source/placed FFs, and physical coordinates."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "PASS" or not manifest.get("evidence") or not manifest.get("inputs"):
        raise ValueError("FF map is not a verified identity manifest")
    for relative, expected_sha in manifest["evidence"].items():
        path = ROOT / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha:
            raise ValueError(f"FF identity evidence missing or changed: {relative}")
    inputs = {name: ROOT / relative for name, relative in manifest["inputs"].items()}
    if hashlib.sha256(pattern_path.read_bytes()).digest() != hashlib.sha256(inputs["patterns"].read_bytes()).digest():
        raise ValueError("Patterns differ from identity-qualified file")
    parsed = parse_fan_pat(pattern_path)
    records = ff_identity_map(inputs["source_netlist"], inputs["placed_netlist"], parsed)
    if records != manifest["records"]:
        raise ValueError("FF identity records differ from verified source/placement")
    validate_ff_identity_map(records, (cell.name for cell in architecture.cells))
    physical = extract_def_scan_cells(inputs["placed_def"], (r["physical_instance"] for r in records), records[0]["clock_domain"])
    if tuple(sorted(architecture.cells, key=lambda c: c.name)) != physical:
        raise ValueError("Architecture placement differs from identity-qualified DEF")
    return records


def _shift_activity(architecture_path: Path, patterns_path: Path, ff_map_path: Path, output: Path) -> int:
    architecture = ScanArchitecture.from_json(architecture_path)
    validate_scan(architecture)
    records = _verify_identity(ff_map_path, architecture, patterns_path)
    patterns = map_ppi_patterns(parse_fan_pat(patterns_path), records)
    trace = simulate_shift(architecture, patterns)
    result = {
        "schema_version": "0.1", "status": "PASS", "architecture_sha256": architecture.sha256(),
        "pattern_count": len(patterns), "activity": activity_metrics(trace),
        "spatial_by_grid": {str(size): spatial_activity(trace, architecture.cells, placement_grid(architecture.cells, size))
                            for size in (8, 16, 32)},
        "evidence": {str(path.resolve()): hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in (architecture_path, patterns_path, ff_map_path)},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(str(output))
    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse subcommands and return an explicit process status."""
    parser = argparse.ArgumentParser(prog="python -m pact.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    validate_parser = sub.add_parser("validate-scan")
    validate_parser.add_argument("--architecture", type=Path, required=True)
    shift_parser = sub.add_parser("shift-activity")
    for flag in ("architecture", "patterns", "ff-map", "out"):
        shift_parser.add_argument(f"--{flag}", type=Path, required=True)
    compare_parser = sub.add_parser("compare")
    compare_parser.add_argument("--results", type=Path, required=True)
    compare_parser.add_argument("--out", type=Path)
    plot_parser = sub.add_parser("plot")
    plot_parser.add_argument("--results", type=Path, required=True)
    plot_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            return _doctor()
        if args.command == "validate-scan":
            return _validate_scan(args.architecture)
        if args.command == "shift-activity":
            return _shift_activity(args.architecture, args.patterns, args.ff_map, args.out)
        records = load_results(args.results, ROOT / "config/schemas/result.schema.json")
        if args.command == "compare":
            output = json.dumps(compare_results(records), indent=2, sort_keys=True) + "\n"
            if args.out:
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(output, encoding="utf-8")
            else:
                print(output, end="")
            return 0
        paths = plot_results(records, ROOT, args.output)
        print(json.dumps({"status": "PASS", "figures": [str(path) for path in paths]}, indent=2))
        return 0
    except (ValueError, OSError, KeyError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
