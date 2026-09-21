#!/usr/bin/env python3
"""Resume bounded, evidence-preserving Phase-0B physical campaigns."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil

from pact.scan.model import ScanArchitecture
from phase0b_run_command import run


ROOT = Path(__file__).resolve().parents[1]
ORFS = Path("/root/pact-deps/OpenROAD-flow-scripts/flow")
VENV = Path("/root/pact-deps/pact-venv/bin/python")
LIBERTY = ORFS / "platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib"
ANNOTATED = ROOT / "artifacts/derived/phase0b/lib/NangateOpenCellLibrary_typical_dft.lib"
BLOCKS = {"s5378": "s5378", "s9234": "s9234f", "s15850": "s15850"}
PHYSICAL_SEEDS = (11, 13, 17, 19, 23)


def design_config(design: str) -> Path:
    if design == "s15850":
        return ROOT / "experiments/phase0b/s15850_orfs/config.mk"
    return ROOT / f"experiments/phase0/{design}_orfs/config.mk"


def invoke(label: str, command: list[str], *, cwd: Path = ROOT,
           timeout: int = 120, required: list[Path] | None = None) -> None:
    result = run(command, ROOT / f"artifacts/raw/phase0b/runs/{label}", cwd,
                 timeout, required or [])
    if result["exit_code"] != 0 or result["timed_out"] or not result["required_outputs_present"]:
        raise RuntimeError(f"{label} failed; inspect its archived execution.json, stdout.log, stderr.log")


def variant(design: str, seed: int, method: str) -> Path:
    return ORFS / f"results/nangate45/{BLOCKS[design]}/phase0b_s{seed}_{method}"


def route_make_command(design: str, seed: int, method: str) -> list[str]:
    """Encode the same physical seed in ORFS variant and global router input."""
    if seed not in PHYSICAL_SEEDS:
        raise ValueError(f"Unregistered physical seed: {seed}")
    block = BLOCKS[design]
    return ["make", "-o", f"./results/nangate45/{block}/phase0b_s{seed}_{method}/3_place.odb",
            "-o", f"./results/nangate45/{block}/phase0b_s{seed}_{method}/3_place.sdc",
            f"DESIGN_CONFIG={design_config(design)}", f"FLOW_VARIANT=phase0b_s{seed}_{method}",
            f"GRT_SEED={seed}", "OPENROAD_EXE=/usr/bin/openroad", "YOSYS_EXE=/usr/bin/yosys", "route"]


def route(design: str, seed: int, method: str) -> None:
    target = variant(design, seed, method)
    metrics = ORFS / f"logs/nangate45/{BLOCKS[design]}/phase0b_s{seed}_{method}"
    cmd = route_make_command(design, seed, method)
    invoke(f"{design}/s{seed}/{method}_route", cmd, cwd=ORFS, timeout=900,
           required=[metrics / "5_1_grt.json", metrics / "5_2_route.json", target / "5_2_route.odb"])
    archived = ROOT / f"artifacts/raw/phase0b/physical/{design}/s{seed}/{method}"
    archived.mkdir(parents=True, exist_ok=True)
    for name in ("5_1_grt.json", "5_2_route.json"):
        shutil.copy2(metrics / name, archived / name)
    shutil.copy2(target / "5_2_route.odb", archived / "5_2_route.odb")


def extract_route(design: str, seed: int, method: str) -> None:
    derived = ROOT / f"artifacts/derived/phase0b/{design}/s{seed}"
    arch = ScanArchitecture.from_json(derived / f"{method}.architecture.json")
    ordered = arch.chains[0].cells
    order_file = derived / f"{method}.scan_order.json"
    order_file.write_text(json.dumps(ordered) + "\n", encoding="utf-8")
    physical = ROOT / f"artifacts/raw/phase0b/physical/{design}/s{seed}/{method}"
    tsv = physical / "scan_edges.tsv"
    invoke(f"{design}/s{seed}/{method}_scan_route_extract", ["env",
           f"PACT_PHASE0B_ROUTED_ODB={physical / '5_2_route.odb'}",
           f"PACT_PHASE0B_ORDER_JSON={order_file}",
           f"PACT_PHASE0B_SCAN_ROUTE_TSV={tsv}", "openroad", "-python", "-no_init", "-exit",
           str(ROOT / "scripts/phase0b_scan_route_extract.py")], timeout=120,
           required=[tsv])
    invoke(f"{design}/s{seed}/{method}_scan_route_parse", [str(VENV),
           str(ROOT / "scripts/phase0b_parse_scan_route.py"),
           "--design", design, "--seed", str(seed), "--method", method],
           required=[physical / "scan_route_metrics.json"])


def one_seed(design: str, seed: int) -> None:
    block = BLOCKS[design]
    source = ORFS / f"results/nangate45/{block}/phase0b_source"
    base = variant(design, seed, "B0")
    place_out = ROOT / f"artifacts/raw/phase0b/placements/{design}/s{seed}"
    place_out.mkdir(parents=True, exist_ok=True)
    base.mkdir(parents=True, exist_ok=True)
    if not all(path.is_file() for path in (base / "3_place.odb", place_out / "placed.def", place_out / "placed.v")):
        invoke(f"{design}/s{seed}/physical_seed", ["env",
            f"PACT_PHASE0B_SOURCE_ODB={source / '3_place.odb'}",
            f"PACT_PHASE0B_PLACED_ODB={base / '3_place.odb'}",
            f"PACT_PHASE0B_PLACEMENT_OUT={place_out}",
            f"PACT_PHASE0B_PHYSICAL_SEED={seed}", "openroad", "-no_init", "-exit",
            str(ROOT / "scripts/tcl/phase0b_seed_placement.tcl")],
            required=[base / "3_place.odb", place_out / "placed.def", place_out / "placed.v"])
    shutil.copy2(source / "3_place.sdc", base / "3_place.sdc")
    route(design, seed, "B0")
    derived = ROOT / f"artifacts/derived/phase0b/{design}/s{seed}"
    plan_path = derived / "plan.json"
    if not (derived / "B0.architecture.json").is_file():
        invoke(f"{design}/s{seed}/architecture_plan", [str(VENV), str(ROOT / "scripts/phase0b_prepare_architectures.py"),
               "--design", design, "--seed", str(seed)], timeout=300, required=[plan_path])
    native_dir = ROOT / f"artifacts/raw/phase0b/dft_annotated/{design}/s{seed}"
    native_dir.mkdir(parents=True, exist_ok=True)
    if not all(path.is_file() for path in (native_dir / "native.v", native_dir / "prescan.v", native_dir / "native.def")):
        invoke(f"{design}/s{seed}/native_dft", ["env", f"PACT_PHASE0B_LIBERTY={ANNOTATED}",
               f"PACT_PHASE0B_BASE_ODB={base / '3_place.odb'}",
               f"PACT_PHASE0B_BASE_SDC={base / '3_place.sdc'}",
               f"PACT_PHASE0B_DFT_OUT={native_dir}", "openroad", "-no_init", "-exit",
               str(ROOT / "scripts/tcl/phase0b_prescan_native.tcl")], timeout=180,
               required=[native_dir / "native.v", native_dir / "prescan.v", native_dir / "native.def"])
    if not (derived / "B1.native_qualification.json").is_file():
        invoke(f"{design}/s{seed}/native_extract", [str(VENV), str(ROOT / "scripts/phase0b_extract_native.py"),
               "--design", design, "--seed", str(seed)],
               required=[derived / "B1.native_qualification.json", derived / "B1.architecture.json"])
    if "B1" not in json.loads(plan_path.read_text(encoding="utf-8"))["route_methods"]:
        shutil.copy2(plan_path, derived / "plan.pre_native.json")
        invoke(f"{design}/s{seed}/architecture_plan_with_native",
               [str(VENV), str(ROOT / "scripts/phase0b_prepare_architectures.py"),
                "--design", design, "--seed", str(seed)], timeout=300,
               required=[plan_path])
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    invoke(f"{design}/s{seed}/B0_verify", [str(VENV), str(ROOT / "scripts/phase0b_verify_baseline.py"),
           "--design", design, "--seed", str(seed)], timeout=180,
           required=[derived / "B0.rewire_verification.json"])
    for method in plan["distinct_route_canonical_methods"]:
        if method == "B0":
            continue
        next_variant = variant(design, seed, method)
        next_variant.mkdir(parents=True, exist_ok=True)
        rewire_out = ROOT / f"artifacts/raw/phase0b/rewire/{design}/s{seed}/{method}"
        rewire_out.mkdir(parents=True, exist_ok=True)
        endpoints = derived / f"{method}.rewire_endpoints.json"
        if not endpoints.is_file():
            invoke(f"{design}/s{seed}/{method}_prepare", [str(VENV), str(ROOT / "scripts/phase0b_prepare_rewire.py"),
                   "--design", design, "--seed", str(seed), "--method", method],
                   required=[endpoints, derived / f"{method}.rewire.tcl"])
        invoke(f"{design}/s{seed}/{method}_rewire", ["env", f"PACT_BASE_ODB={base / '3_place.odb'}",
               f"PACT_VARIANT_ODB={next_variant / '3_place.odb'}",
               f"PACT_REWIRE_TCL={derived / f'{method}.rewire.tcl'}",
               f"PACT_REWIRE_OUT={rewire_out}", "openroad", "-no_init", "-exit",
               str(ROOT / "scripts/tcl/rewire_scan.tcl")],
               required=[next_variant / "3_place.odb", rewire_out / "rewired.v", rewire_out / "rewired.def"])
        invoke(f"{design}/s{seed}/{method}_verify", [str(VENV), str(ROOT / "scripts/phase0b_verify_rewire.py"),
               "--design", design, "--seed", str(seed), "--method", method], timeout=180,
               required=[derived / f"{method}.rewire_verification.json"])
        shutil.copy2(base / "3_place.sdc", next_variant / "3_place.sdc")
        route(design, seed, method)
    for method in plan["distinct_route_canonical_methods"]:
        extract_route(design, seed, method)
        physical = ROOT / f"artifacts/raw/phase0b/physical/{design}/s{seed}/{method}"
        invoke(f"{design}/s{seed}/{method}_structured_metrics", [str(VENV),
               str(ROOT / "scripts/phase0b_extract_structured_metrics.py"),
               "--design", design, "--seed", str(seed), "--method", method],
               required=[physical / "structured_metrics.json"])


def qualify_seeds(design: str) -> None:
    # Distinct SHA alone could reflect non-placement DB metadata; compare the
    # actual DEF COMPONENTS placement tuples instead.
    from verify_rewire_s5378 import def_placements
    placement_hashes = {}
    for seed in PHYSICAL_SEEDS:
        path = ROOT / f"artifacts/raw/phase0b/placements/{design}/s{seed}/placed.def"
        if not path.is_file():
            continue
        placement_hashes[str(seed)] = placement_fingerprint(def_placements(path))
    record = {"design": design, "requested_seeds": list(PHYSICAL_SEEDS),
              "observed_component_placement_hashes": placement_hashes,
              "completed_physical_seeds": len(placement_hashes),
              "all_completed_placements_distinct": len(set(placement_hashes.values())) == len(placement_hashes)}
    target = ROOT / f"artifacts/derived/phase0b/{design}/physical_seed_qualification.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def placement_fingerprint(components: dict[str, tuple[str, str, str, str]]) -> str:
    """Hash actual master/location/orientation tuples, independent of DEF text."""
    encoded = json.dumps(components, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--design", choices=BLOCKS, required=True)
    parser.add_argument("--seeds", nargs="+", type=int, default=[11, 13, 17, 19, 23])
    args = parser.parse_args()
    if any(seed not in PHYSICAL_SEEDS for seed in args.seeds):
        parser.error("Only predeclared physical seeds are allowed")
    if not ANNOTATED.is_file():
        invoke("dft_annotation", ["python3", str(ROOT / "scripts/phase0b_annotate_nangate_dft.py")],
               required=[ANNOTATED])
    config = design_config(args.design)
    source = ORFS / f"results/nangate45/{BLOCKS[args.design]}/phase0b_source/3_place.odb"
    invoke(f"{args.design}/source_place", ["make", f"DESIGN_CONFIG={config}",
           "FLOW_VARIANT=phase0b_source", "OPENROAD_EXE=/usr/bin/openroad",
           "YOSYS_EXE=/usr/bin/yosys", "place"], cwd=ORFS, timeout=600, required=[source])
    if args.design == "s15850":
        source_out = ROOT / "artifacts/raw/phase0b/source_place/s15850"
        source_out.mkdir(parents=True, exist_ok=True)
        if not (source_out / "placed.v").is_file():
            invoke("s15850/source_export", ["env", f"PACT_PHASE0B_EXPORT_ODB={source}",
                   f"PACT_PHASE0B_EXPORT_OUT={source_out}", "openroad", "-no_init", "-exit",
                   str(ROOT / "scripts/tcl/phase0b_export_db.tcl")],
                   required=[source_out / "placed.v", source_out / "placed.def"])
        if not (ROOT / "artifacts/derived/s15850/ff_identity_map.json").is_file():
            invoke("s15850/identity", [str(VENV), str(ROOT / "scripts/phase0b_establish_s15850.py")],
                   required=[ROOT / "artifacts/derived/s15850/ff_identity_map.json",
                             ROOT / "artifacts/derived/s15850/supplied_architecture.json"])
    failures = []
    for seed in args.seeds:
        print(f"PHASE0B_BEGIN {args.design} physical_seed={seed}", flush=True)
        try:
            one_seed(args.design, seed)
            print(f"PHASE0B_COMPLETE {args.design} physical_seed={seed}", flush=True)
        except Exception as exc:
            failures.append((seed, str(exc)))
            print(f"PHASE0B_FAILED {args.design} physical_seed={seed} reason={exc}", flush=True)
        finally:
            qualify_seeds(args.design)
    if failures:
        raise RuntimeError(f"Phase-0B design {args.design} failed seeds: {failures}")


if __name__ == "__main__":
    main()
