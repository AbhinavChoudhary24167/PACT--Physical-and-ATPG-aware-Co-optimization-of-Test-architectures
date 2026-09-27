#!/usr/bin/env python3
"""Controlled Optimizer-v2 versus v2.1 constructor qualification.

This script never invokes routing or OpenROAD.  Synthetic cases are software-
scaling evidence only; s5378/s9234 starts use the frozen qualified proxy inputs.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
import time
import tracemalloc
from typing import Any, Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from pact.analysis.phase0c_activity import parallel_activity_metrics  # noqa: E402
from pact.experiment_storage import (  # noqa: E402
    DEFAULT_MIN_FREE_GIB,
    add_experiment_root_argument,
    configure_experiment_storage,
    guard_disk_space,
)
from pact.phase0d.funnel import FrozenProxyContext  # noqa: E402
from pact.phase0d.optimizer_v1 import (  # noqa: E402
    PhysicalCostModel,
    TargetCompatibility,
    dominates2,
)
from pact.phase0d.optimizer_v2 import OptimizerV2Config, optimize_v2  # noqa: E402
from pact.phase0d.v2_constructor_metrics import ConstructorStats  # noqa: E402
from pact.phase0d.v2_shared_frontier import construct_architectures_v2_1  # noqa: E402
from pact.phase0d.v2_sparse import (  # noqa: E402
    SparsePhysicalGraph,
    construct_architectures_v2,
)
from pact.scan.model import ScanArchitecture  # noqa: E402
from pact_optimizer_v2 import synthetic_problem  # noqa: E402


REPORT_ROOT = ROOT / "reports/optimizer_v2_1"
FIGURE_ROOT = REPORT_ROOT / "figures"
SEED = 20260921


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def constructor_run(
    base: ScanArchitecture,
    physical: PhysicalCostModel,
    patterns: Sequence[Mapping[str, int]],
    weights: Mapping[str, int],
    graph: SparsePhysicalGraph,
    mode: str,
    seed: int,
) -> tuple[list[tuple[str, Any]], dict[str, Any]]:
    activity = TargetCompatibility(patterns, weights)
    tracemalloc.start()
    started = time.perf_counter()
    if mode == "sequential":
        stats = ConstructorStats("sequential_greedy")
        starts = construct_architectures_v2(
            base, graph, physical, activity, seed=seed, instrumentation=stats
        )
    elif mode == "shared_frontier":
        starts, stats = construct_architectures_v2_1(
            base, graph, physical, activity, seed=seed
        )
    else:
        raise ValueError(mode)
    measured = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    if abs(measured - stats.total_seconds) > max(0.01, measured * 0.05):
        raise AssertionError("Constructor timer and harness timer disagree")
    return starts, {
        "wall_seconds": measured,
        "peak_traced_memory_bytes": int(peak),
        "stats": stats.to_dict(),
    }


def exact_start_rows(
    starts: Sequence[tuple[str, Any]],
    physical: PhysicalCostModel,
    patterns: Sequence[Mapping[str, int]],
    weights: Mapping[str, int],
) -> list[dict[str, Any]]:
    rows = []
    for label, mutable in starts:
        boundary = mutable.to_scan_architecture()
        h_eff8 = parallel_activity_metrics(
            boundary, patterns, weights, grid_sizes=(8,)
        )["grids"]["8"]["H_eff"]
        rows.append({
            "label": label,
            "architecture_sha256": boundary.sha256(),
            "architecture_key": f"{mutable.architecture_key:032x}",
            "objectives": [
                float(physical.architecture_cost(boundary)),
                float(h_eff8),
            ],
            "chain_lengths": list(map(len, mutable.orders())),
        })
    return rows


def optimizer_config(mode: str, seed: int, *, real: bool) -> OptimizerV2Config:
    return OptimizerV2Config(
        wall_clock_seconds=20.0 if real else 90.0,
        maximum_exact_evaluations=24 if real else 8,
        maximum_local_moves=32 if real else 2,
        maximum_archive_size=16 if real else 12,
        maximum_neighborhood_size=24,
        graph_k=12,
        activity_candidates=6,
        random_nonlocal_candidates=3,
        parent_refresh_interval=12 if real else 0,
        seen_cache_size=4096 if real else 2048,
        seed=seed,
        constructor_mode=mode,
        constructor_frontier_bound=4,
    )


def compact_optimizer_result(result) -> dict[str, Any]:
    return {
        "runtime": dict(result.runtime),
        "memory": dict(result.memory),
        "counters": dict(result.counters),
        "archive": [dict(row) for row in result.archive],
        "stop_reason": result.stop_reason,
    }


def run_scaling(sizes: Sequence[int], seed: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for n in sizes:
        base, physical, patterns, weights = synthetic_problem(n)
        coordinates = np.asarray([(cell.x_um, cell.y_um) for cell in base.cells])
        graph = SparsePhysicalGraph.build(coordinates, 12)
        row: dict[str, Any] = {
            "N": n,
            "K": len(base.chains),
            "seed": seed,
            "graph_construction_seconds": graph.stats.construction_seconds,
            "graph_memory_bytes": graph.stats.memory_bytes,
            "synthetic_performance_only": True,
            "constructors": {},
            "optimizers": {},
        }
        for mode in ("sequential", "shared_frontier"):
            starts, constructor = constructor_run(
                base, physical, patterns, weights, graph, mode, seed
            )
            constructor["starts"] = exact_start_rows(starts, physical, patterns, weights)
            row["constructors"][mode] = constructor
            result = optimize_v2(
                base, patterns, weights, physical,
                optimizer_config(mode, seed, real=False),
                trace_limit=0,
            )
            row["optimizers"][mode] = compact_optimizer_result(result)
        old = row["constructors"]["sequential"]
        new = row["constructors"]["shared_frontier"]
        row["comparison"] = {
            "constructor_speedup": old["wall_seconds"] / new["wall_seconds"],
            "constructor_peak_memory_ratio_new_over_old": (
                new["peak_traced_memory_bytes"] / old["peak_traced_memory_bytes"]
            ),
            "candidate_score_reduction_fraction": 1.0 - (
                new["stats"]["insertion_candidates_scored"]
                / old["stats"]["insertion_candidates_scored"]
            ),
            "physical_feature_reduction_fraction": 1.0 - (
                new["stats"]["physical_delta_computations"]
                / old["stats"]["physical_delta_computations"]
            ),
            "total_optimizer_speedup": (
                row["optimizers"]["sequential"]["runtime"]["optimizer_wall_seconds"]
                / row["optimizers"]["shared_frontier"]["runtime"]["optimizer_wall_seconds"]
            ),
        }
        rows.append(row)
        write_json(REPORT_ROOT / "scaling_partial.json", rows)
        print(f"completed scaling N={n}", flush=True)
    write_json(REPORT_ROOT / "scaling_results.json", rows)
    with (REPORT_ROOT / "scaling_summary.csv").open("w", newline="", encoding="utf-8") as stream:
        fields = [
            "N", "K", "old_constructor_seconds", "new_constructor_seconds",
            "constructor_speedup", "candidate_score_reduction_fraction",
            "old_total_seconds", "new_total_seconds", "total_optimizer_speedup",
            "old_peak_bytes", "new_peak_bytes",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "N": row["N"],
                "K": row["K"],
                "old_constructor_seconds": row["constructors"]["sequential"]["wall_seconds"],
                "new_constructor_seconds": row["constructors"]["shared_frontier"]["wall_seconds"],
                "constructor_speedup": row["comparison"]["constructor_speedup"],
                "candidate_score_reduction_fraction": row["comparison"]["candidate_score_reduction_fraction"],
                "old_total_seconds": row["optimizers"]["sequential"]["runtime"]["optimizer_wall_seconds"],
                "new_total_seconds": row["optimizers"]["shared_frontier"]["runtime"]["optimizer_wall_seconds"],
                "total_optimizer_speedup": row["comparison"]["total_optimizer_speedup"],
                "old_peak_bytes": row["constructors"]["sequential"]["peak_traced_memory_bytes"],
                "new_peak_bytes": row["constructors"]["shared_frontier"]["peak_traced_memory_bytes"],
            })
    return rows


def qualified_seeds(context: FrozenProxyContext) -> list[tuple[str, ScanArchitecture]]:
    result = []
    for row in context.portfolio_rows:
        path = Path(row["architecture_path"])
        if not path.is_absolute():
            path = ROOT / path
        result.append((
            f"qualified_{row.get('method', path.stem)}",
            ScanArchitecture.from_json(path),
        ))
    return result


def start_front_comparison(old: Sequence[Mapping[str, Any]],
                           new: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    old_hashes = {str(row["architecture_sha256"]) for row in old}
    new_hashes = {str(row["architecture_sha256"]) for row in new}
    old_points = [row["objectives"] for row in old]
    new_points = [row["objectives"] for row in new]
    combined = [("old", index, row) for index, row in enumerate(old)]
    combined += [("new", index, row) for index, row in enumerate(new)]
    nondominated = [
        (source, index) for source, index, row in combined
        if not any(
            dominates2(other["objectives"], row["objectives"])
            for other_source, other_index, other in combined
            if (other_source, other_index) != (source, index)
        )
    ]
    return {
        "reproduced_old_hashes": sorted(old_hashes & new_hashes),
        "old_starts_dominated_by_any_new": sum(
            any(dominates2(candidate, point) for candidate in new_points)
            for point in old_points
        ),
        "new_starts_dominated_by_any_old": sum(
            any(dominates2(candidate, point) for candidate in old_points)
            for point in new_points
        ),
        "new_nondominated_in_combined_front": sum(
            source == "new" for source, _ in nondominated
        ),
        "old_nondominated_in_combined_front": sum(
            source == "old" for source, _ in nondominated
        ),
    }


def run_real(seed: int) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "pact-optimizer-v2-1-real-start-comparison-1",
        "seed": seed,
        "routing_calls": 0,
        "designs": {},
    }
    for design in ("s5378", "s9234"):
        context = FrozenProxyContext.load(ROOT, design, 11, 2, "P")
        base = context.start_architecture
        physical = PhysicalCostModel.from_architecture(base, context.frozen_def)
        coordinates = np.asarray([(cell.x_um, cell.y_um) for cell in base.cells])
        graph = SparsePhysicalGraph.build(coordinates, 12)
        design_row: dict[str, Any] = {"constructors": {}, "optimizers": {}}
        for mode in ("sequential", "shared_frontier"):
            starts, constructor = constructor_run(
                base, physical, context.patterns, context.weights, graph, mode, seed
            )
            constructor["starts"] = exact_start_rows(
                starts, physical, context.patterns, context.weights
            )
            design_row["constructors"][mode] = constructor
            result = optimize_v2(
                base, context.patterns, context.weights, physical,
                optimizer_config(mode, seed, real=True),
                seed_architectures=qualified_seeds(context),
                trace_limit=0,
            )
            design_row["optimizers"][mode] = compact_optimizer_result(result)
        design_row["start_front_comparison"] = start_front_comparison(
            design_row["constructors"]["sequential"]["starts"],
            design_row["constructors"]["shared_frontier"]["starts"],
        )
        design_row["constructor_speedup"] = (
            design_row["constructors"]["sequential"]["wall_seconds"]
            / design_row["constructors"]["shared_frontier"]["wall_seconds"]
        )
        design_row["total_optimizer_speedup"] = (
            design_row["optimizers"]["sequential"]["runtime"]["optimizer_wall_seconds"]
            / design_row["optimizers"]["shared_frontier"]["runtime"]["optimizer_wall_seconds"]
        )
        payload["designs"][design] = design_row
        print(f"completed real {design}", flush=True)
    write_json(REPORT_ROOT / "real_benchmark.json", payload)
    return payload


def make_plots(scaling: Sequence[Mapping[str, Any]], real: Mapping[str, Any]) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    FIGURE_ROOT.mkdir(parents=True, exist_ok=True)
    outputs: list[str] = []
    n = [row["N"] for row in scaling]
    plt.figure(figsize=(7, 4.5))
    for mode, label in (("sequential", "v2 sequential"), ("shared_frontier", "v2.1 shared frontier")):
        plt.plot(n, [row["constructors"][mode]["wall_seconds"] for row in scaling], marker="o", label=label)
    plt.xscale("log")
    plt.yscale("log")
    plt.xlabel("FF count N")
    plt.ylabel("Constructor wall time (s)")
    plt.title("Constructor runtime")
    plt.grid(True, which="both", alpha=0.25)
    plt.legend()
    path = FIGURE_ROOT / "01_constructor_runtime_vs_n.png"
    plt.tight_layout(); plt.savefig(path, dpi=180); plt.close()
    outputs.append(str(path.relative_to(ROOT)))

    plt.figure(figsize=(7, 4.5))
    for mode, label in (("sequential", "v2 sequential"), ("shared_frontier", "v2.1 shared frontier")):
        plt.plot(n, [row["constructors"][mode]["stats"]["physical_delta_computations"] for row in scaling], marker="o", label=label)
    plt.xscale("log")
    plt.yscale("log")
    plt.xlabel("FF count N")
    plt.ylabel("Candidate physical feature evaluations")
    plt.title("Constructor feature work")
    plt.grid(True, which="both", alpha=0.25)
    plt.legend()
    path = FIGURE_ROOT / "02_candidate_features_vs_n.png"
    plt.tight_layout(); plt.savefig(path, dpi=180); plt.close()
    outputs.append(str(path.relative_to(ROOT)))

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    for axis, design in zip(axes, ("s5378", "s9234")):
        for mode, marker, label in (("sequential", "o", "v2"), ("shared_frontier", "s", "v2.1")):
            starts = real["designs"][design]["constructors"][mode]["starts"]
            axis.scatter(
                [row["objectives"][0] for row in starts],
                [row["objectives"][1] for row in starts],
                marker=marker, label=label,
            )
        axis.set_title(design)
        axis.set_xlabel("Qualified port-aware HPWL proxy (µm)")
        axis.set_ylabel("Exact H_eff8")
        axis.grid(True, alpha=0.25)
        axis.legend()
    path = FIGURE_ROOT / "03_real_start_fronts.png"
    fig.tight_layout(); fig.savefig(path, dpi=180); plt.close(fig)
    outputs.append(str(path.relative_to(ROOT)))
    write_json(REPORT_ROOT / "figures.json", outputs)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("all", "scaling", "real", "plots"), default="all")
    parser.add_argument("--sizes", default="200,500,1000,2000,5000,10000")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--minimum-free-gib", type=float, default=DEFAULT_MIN_FREE_GIB)
    parser.add_argument("--estimated-bytes", type=int, default=1024**3)
    add_experiment_root_argument(parser)
    args = parser.parse_args()
    paths = configure_experiment_storage(args.experiment_root)
    guard_disk_space(
        paths,
        estimated_bytes=args.estimated_bytes,
        minimum_free_gib=args.minimum_free_gib,
    )
    sizes = tuple(int(value) for value in args.sizes.split(",") if value)
    scaling_path = REPORT_ROOT / "scaling_results.json"
    real_path = REPORT_ROOT / "real_benchmark.json"
    scaling = run_scaling(sizes, args.seed) if args.mode in {"all", "scaling"} else None
    real = run_real(args.seed) if args.mode in {"all", "real"} else None
    if args.mode in {"all", "plots"}:
        scaling = scaling or json.loads(scaling_path.read_text(encoding="utf-8"))
        real = real or json.loads(real_path.read_text(encoding="utf-8"))
        make_plots(scaling, real)


if __name__ == "__main__":
    main()
