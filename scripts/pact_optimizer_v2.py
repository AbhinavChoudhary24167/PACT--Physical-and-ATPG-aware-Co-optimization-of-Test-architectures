#!/usr/bin/env python3
"""Reproducible real and software-scaling benchmarks for PACT Optimizer-v2.

No OpenROAD executable or routing API is imported or invoked by this script.
Synthetic cases characterize software scaling only and are labelled accordingly.
"""
from __future__ import annotations

import argparse
import cProfile
import csv
import io
import json
import math
from pathlib import Path
import pstats
import sys
import time
import tracemalloc
from typing import Any, Mapping, Sequence

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pact.analysis.phase0c_activity import parallel_activity_metrics  # noqa: E402
from pact.phase0d.funnel import FrozenProxyContext  # noqa: E402
from pact.phase0d.optimizer_v1 import (  # noqa: E402
    CONSTRUCTION_SPECS,
    LNS_DESTROY_OPERATORS,
    LNS_REPAIR_STRATEGIES,
    ParetoArchive2D,
    PhysicalCostModel,
    TargetCompatibility,
    construct_architecture,
    dominates2,
    lns_candidate,
)
from pact.phase0d.optimizer_v2 import OptimizerV2Config, optimize_v2  # noqa: E402
from pact.scan.model import ScanArchitecture, ScanCell, ScanChain  # noqa: E402


REPORT_ROOT = ROOT / "reports/optimizer_v2"
ARTIFACT_ROOT = ROOT / "artifacts/derived/optimizer_v2"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def write_architecture(path: Path, architecture: ScanArchitecture) -> None:
    payload = architecture.canonical_dict()
    payload["architecture_sha256"] = architecture.sha256()
    write_json(path, payload)


def synthetic_problem(n: int, *, patterns: int = 4, maximum_chain_length: int = 500):
    """Deterministic performance-only case; never scientific benchmark evidence."""
    k = max(2, math.ceil(n / maximum_chain_length))
    cells = tuple(
        ScanCell(
            f"synthetic_ff_{index:06d}",
            float((index * 2654435761 % 100003) / 100.0),
            float((index * 2246822519 % 99991) / 100.0),
            "synthetic_clk",
        )
        for index in range(n)
    )
    capacities = [n // k + int(chain < n % k) for chain in range(k)]
    chains = []
    cursor = 0
    for chain, length in enumerate(capacities):
        names = tuple(cell.name for cell in cells[cursor:cursor + length])
        chains.append(ScanChain(
            f"C{chain:04d}", names,
            "test_si" if chain == 0 else f"test_si_{chain}",
            "test_so" if chain == 0 else f"test_so_{chain}",
        ))
        cursor += length
    architecture = ScanArchitecture(cells, tuple(chains))
    targets = [
        {cell.name: int(((index * 1103515245 + pattern * 12345 + index // 7) >> 8) & 1)
         for index, cell in enumerate(cells)}
        for pattern in range(patterns)
    ]
    weights = {cell.name: 1 + ((index * 7) % 5) for index, cell in enumerate(cells)}
    coordinates = {cell.name: (cell.x_um, cell.y_um) for cell in cells}
    input_ports = tuple((-10.0, 1000.0 * (chain + 1) / (k + 1)) for chain in range(k))
    output_ports = tuple((1010.0, 1000.0 * (chain + 1) / (k + 1)) for chain in range(k))
    physical = PhysicalCostModel(coordinates, input_ports, output_ports, 2000.0)
    return architecture, physical, targets, weights


def nondominated_points(points: Sequence[Sequence[float]]) -> list[tuple[float, float]]:
    checked = [tuple(map(float, point[:2])) for point in points]
    return [point for index, point in enumerate(checked)
            if not any(dominates2(other, point) for j, other in enumerate(checked) if j != index)]


def run_v1_compact(context: FrozenProxyContext, wall_seconds: float,
                   exact_budget: int, local_move_budget: int, seed: int,
                   seed_architectures: Sequence[tuple[str, ScanArchitecture]] = ()) -> dict[str, Any]:
    """Comparable in-process v1 structure benchmark; it creates no evidence cache."""
    started = time.perf_counter()
    tracemalloc.start()
    physical = PhysicalCostModel.from_architecture(context.start_architecture, context.frozen_def)
    activity = TargetCompatibility(context.patterns, context.weights)
    archive = ParetoArchive2D()
    records: list[dict[str, Any]] = []
    objective_recomputations = 0
    complete_copies = 0

    def evaluate(architecture: ScanArchitecture, source: str) -> dict[str, Any]:
        nonlocal objective_recomputations
        physical_value = physical.architecture_cost(architecture)
        h = parallel_activity_metrics(
            architecture, context.patterns, context.weights, grid_sizes=(8,)
        )["grids"]["8"]["H_eff"]
        objective_recomputations += 1
        row = {
            "architecture_sha256": architecture.sha256(),
            "objectives": [float(physical_value), float(h)],
            "source": source,
            "architecture": architecture,
        }
        archive.insert(row)
        records.append(row)
        return row

    starts = [("input_architecture", context.start_architecture), *seed_architectures]
    evaluated_starts = []
    seen_starts: set[str] = set()
    for label, architecture in starts:
        sha = architecture.sha256()
        if sha in seen_starts:
            continue
        seen_starts.add(sha)
        if objective_recomputations >= exact_budget:
            break
        evaluated_starts.append(evaluate(architecture, label))
    complete_copies += len(starts)
    # V1 constructors are themselves unbounded O(N^3 log N) operations. Check
    # the common wall budget between constructors and record a single-operation
    # overrun rather than launching every constructor unconditionally.
    for label, alpha, regret in CONSTRUCTION_SPECS:
        if (objective_recomputations >= exact_budget
                or time.perf_counter() - started >= wall_seconds):
            break
        architecture = construct_architecture(
            context.start_architecture, physical, activity, alpha, regret=regret
        )
        complete_copies += 1
        if time.perf_counter() - started >= wall_seconds:
            break
        sha = architecture.sha256()
        if sha in seen_starts:
            continue
        seen_starts.add(sha)
        evaluated_starts.append(evaluate(architecture, label))
    lows = [min(row["objectives"][i] for row in evaluated_starts) for i in range(2)]
    highs = [max(row["objectives"][i] for row in evaluated_starts) for i in range(2)]
    spans = [max(highs[i] - lows[i], abs(lows[i]) * 0.05, 1.0) for i in range(2)]
    scalar = lambda row, weight=0.5: (
        weight * (row["objectives"][0] - lows[0]) / spans[0]
        + (1 - weight) * (row["objectives"][1] - lows[1]) / spans[1]
    )
    current = min(evaluated_starts, key=scalar)
    attempts = 0
    accepted = 0
    invalid = 0
    while (attempts < local_move_budget and objective_recomputations < exact_budget
           and time.perf_counter() - started < wall_seconds):
        operator = LNS_DESTROY_OPERATORS[attempts % len(LNS_DESTROY_OPERATORS)]
        strategy = LNS_REPAIR_STRATEGIES[attempts % len(LNS_REPAIR_STRATEGIES)][0]
        fraction = (0.05, 0.10, 0.20)[attempts % 3]
        attempts += 1
        try:
            child, _ = lns_candidate(
                current["architecture"], physical, activity,
                operator=operator, fraction=fraction, repair_strategy=strategy,
                iteration=attempts, seed=seed,
            )
            complete_copies += 1
            candidate = evaluate(child, f"lns_{operator}_{strategy}")
        except (ValueError, AssertionError):
            invalid += 1
            continue
        weight = (1.0, 0.75, 0.5, 0.25, 0.0)[attempts % 5]
        if dominates2(candidate["objectives"], current["objectives"]) or scalar(candidate, weight) < scalar(current, weight):
            current = candidate
            accepted += 1
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    front = [{key: value for key, value in row.items() if key != "architecture"} for row in archive.entries]
    return {
        "optimizer": "v1_compact_comparison",
        "wall_seconds": elapsed,
        "exact_evaluations": objective_recomputations,
        "architectures_considered": len(records),
        "local_moves_attempted": attempts,
        "local_moves_accepted": accepted,
        "invalid_moves": invalid,
        "archive_size": len(front),
        "best_physical": min(row["objectives"][0] for row in front),
        "best_H_eff8": min(row["objectives"][1] for row in front),
        "peak_memory_bytes": int(peak),
        "complete_architecture_copies_estimate": complete_copies,
        "full_physical_recomputations": objective_recomputations,
        "full_H_eff8_recomputations": objective_recomputations,
        "incremental_physical_evaluations": 0,
        "incremental_H_eff8_evaluations": 0,
        "front": front,
        "stop_reason": (
            "EXACT_EVALUATION_BUDGET_EXHAUSTED" if objective_recomputations >= exact_budget
            else "WALL_CLOCK_BUDGET_EXHAUSTED" if elapsed >= wall_seconds
            else "LOCAL_MOVE_BUDGET_EXHAUSTED"
        ),
    }


def run_real_benchmarks(wall_seconds: float, exact_budget: int,
                        local_move_budget: int, seed: int) -> dict[str, Any]:
    results: dict[str, Any] = {
        "schema_version": "pact-optimizer-v2-real-comparison-1",
        "comparison_policy": {
            "wall_seconds_each": wall_seconds,
            "maximum_exact_evaluations_each": exact_budget,
            "maximum_local_moves_each": local_move_budget,
            "grid": 8,
            "routing_in_inner_loop": False,
        },
        "designs": {},
    }
    for design in ("s5378", "s9234"):
        context = FrozenProxyContext.load(ROOT, design, 11, 2, "P")
        physical = PhysicalCostModel.from_architecture(context.start_architecture, context.frozen_def)
        seeds = []
        for row in context.portfolio_rows:
            architecture_path = Path(row["architecture_path"])
            if not architecture_path.is_absolute():
                architecture_path = ROOT / architecture_path
            seeds.append((f"qualified_{row.get('method', architecture_path.stem)}",
                          ScanArchitecture.from_json(architecture_path)))
        v1 = run_v1_compact(context, wall_seconds, exact_budget, local_move_budget, seed, seeds)
        config = OptimizerV2Config(
            wall_clock_seconds=wall_seconds,
            maximum_exact_evaluations=exact_budget,
            maximum_local_moves=local_move_budget,
            maximum_archive_size=16,
            maximum_neighborhood_size=24,
            graph_k=12,
            activity_candidates=6,
            random_nonlocal_candidates=3,
            parent_refresh_interval=12,
            seed=seed,
        )
        v2_result = optimize_v2(
            context.start_architecture, context.patterns, context.weights, physical, config,
            seed_architectures=seeds,
        )
        v2 = v2_result.to_dict()
        output = ARTIFACT_ROOT / design / "s11" / "k2"
        for sha, architecture in v2_result.architecture_objects.items():
            write_architecture(output / f"{sha}.architecture.json", architecture)
        write_json(output / "result.json", v2)
        v1_points = [row["objectives"] for row in v1["front"]]
        v2_points = [row["objectives"] for row in v2["archive"]]
        relation = {
            "v1_points_dominated_by_any_v2": sum(
                any(dominates2(candidate, point) for candidate in v2_points) for point in v1_points
            ),
            "v2_points_dominated_by_any_v1": sum(
                any(dominates2(candidate, point) for candidate in v1_points) for point in v2_points
            ),
            "v1_front_size": len(v1_points),
            "v2_front_size": len(v2_points),
        }
        results["designs"][design] = {"v1": v1, "v2": v2, "dominance": relation}
    write_json(REPORT_ROOT / "real_benchmark.json", results)
    return results


def run_scaling(sizes: Sequence[int], per_case_wall_seconds: float,
                exact_budget: int, local_move_budget: int, seed: int) -> list[dict[str, Any]]:
    rows = []
    for n in sizes:
        base, physical, patterns, weights = synthetic_problem(n)
        config = OptimizerV2Config(
            wall_clock_seconds=per_case_wall_seconds,
            maximum_exact_evaluations=exact_budget,
            maximum_local_moves=local_move_budget,
            maximum_archive_size=12,
            maximum_neighborhood_size=24,
            graph_k=12,
            activity_candidates=6,
            random_nonlocal_candidates=3,
            parent_refresh_interval=0,
            seen_cache_size=2048,
            seed=seed,
        )
        result = optimize_v2(base, patterns, weights, physical, config)
        counters, memory = result.counters, result.memory
        row = {
            "N": n,
            "K": len(base.chains),
            "pattern_count": len(patterns),
            "maximum_chain_length": max(len(chain.cells) for chain in base.chains),
            "graph_construction_seconds": result.graph["construction_seconds"],
            "graph_directed_edges": result.graph["directed_edge_count"],
            "graph_memory_bytes": result.graph["memory_bytes"],
            "optimizer_runtime_seconds": result.runtime["optimizer_wall_seconds"],
            "peak_memory_bytes": memory["tracemalloc_peak_bytes"],
            "evaluations_per_second": counters["evaluations_per_second"],
            "local_moves_per_second": counters["local_moves_per_second"],
            "average_candidate_neighborhood_size": counters["average_candidate_neighborhood_size"],
            "archive_size": counters["final_archive_size"],
            "incremental_physical_evaluations": counters["incremental_physical_evaluations"],
            "screened_move_options": counters["screened_move_options"],
            "full_physical_recomputations": counters["full_physical_recomputations"],
            "incremental_H_eff8_evaluations": counters["incremental_h_eff8_evaluations"],
            "full_H_eff8_recomputations": counters["full_h_eff8_recomputations"],
            "exact_evaluations": counters["exact_evaluations"],
            "local_moves": counters["local_moves_attempted"],
            "complete_architecture_copies": counters["complete_architecture_copies"],
            "stop_reason": result.stop_reason,
            "synthetic_performance_only": True,
        }
        rows.append(row)
        write_json(REPORT_ROOT / "scaling_partial.json", rows)
    write_json(REPORT_ROOT / "scaling_results.json", rows)
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    with (REPORT_ROOT / "scaling_results.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return rows


def run_profile(seed: int) -> str:
    base, physical, patterns, weights = synthetic_problem(1000)
    config = OptimizerV2Config(
        wall_clock_seconds=30,
        maximum_exact_evaluations=8,
        maximum_local_moves=2,
        maximum_archive_size=8,
        maximum_neighborhood_size=24,
        graph_k=12,
        parent_refresh_interval=0,
        seed=seed,
    )
    profiler = cProfile.Profile()
    profiler.enable()
    optimize_v2(base, patterns, weights, physical, config, trace_limit=0)
    profiler.disable()
    output = io.StringIO()
    stats = pstats.Stats(profiler, stream=output).strip_dirs()
    output.write("CUMULATIVE TIME\n")
    stats.sort_stats("cumulative").print_stats(25)
    output.write("\nSELF CPU TIME\n")
    stats.sort_stats("tottime").print_stats(25)
    text = output.getvalue().rstrip() + "\n"
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    (REPORT_ROOT / "profile_top.txt").write_text(text, encoding="utf-8")
    return text


def make_plots(scaling: Sequence[Mapping[str, Any]], real: Mapping[str, Any]) -> list[str]:
    figure_root = REPORT_ROOT / "figures"
    figure_root.mkdir(parents=True, exist_ok=True)
    paths = []
    n = [row["N"] for row in scaling]

    def save(name: str) -> None:
        path = figure_root / name
        plt.tight_layout()
        plt.savefig(path, dpi=160)
        plt.close()
        paths.append(str(path.relative_to(ROOT)).replace("\\", "/"))

    plt.figure(figsize=(6.2, 4.0))
    plt.plot(n, [row["optimizer_runtime_seconds"] for row in scaling], marker="o")
    plt.xscale("log")
    plt.yscale("log")
    plt.xlabel("Synthetic FF count N")
    plt.ylabel("Bounded optimizer runtime (s)")
    plt.title("Optimizer-v2 runtime scaling")
    plt.grid(True, which="both", alpha=0.25)
    save("01_runtime_vs_n.png")

    plt.figure(figsize=(6.2, 4.0))
    plt.plot(n, [row["peak_memory_bytes"] / 2**20 for row in scaling], marker="o", label="peak traced")
    plt.plot(n, [row["graph_memory_bytes"] / 2**20 for row in scaling], marker="s", label="sparse graph")
    plt.xscale("log")
    plt.yscale("log")
    plt.xlabel("Synthetic FF count N")
    plt.ylabel("Memory (MiB)")
    plt.title("Optimizer-v2 memory scaling")
    plt.grid(True, which="both", alpha=0.25)
    plt.legend()
    save("02_peak_memory_vs_n.png")

    plt.figure(figsize=(6.2, 4.0))
    plt.plot(n, [row["evaluations_per_second"] for row in scaling], marker="o")
    plt.xscale("log")
    plt.xlabel("Synthetic FF count N")
    plt.ylabel("Exact evaluations / second")
    plt.title("Optimizer-v2 evaluation throughput")
    plt.grid(True, which="both", alpha=0.25)
    save("03_evaluations_per_second_vs_n.png")

    designs = list(real["designs"])
    fig, axes = plt.subplots(1, len(designs), figsize=(6.0 * len(designs), 4.3), squeeze=False)
    for axis, design in zip(axes[0], designs):
        item = real["designs"][design]
        for label, marker in (("v1", "x"), ("v2", "o")):
            front = item[label]["front"] if label == "v1" else item[label]["archive"]
            axis.scatter([row["objectives"][0] for row in front],
                         [row["objectives"][1] for row in front], label=label, marker=marker)
        axis.set_title(design)
        axis.set_xlabel("Qualified port-aware HPWL proxy (µm)")
        axis.set_ylabel("Exact H_eff8")
        axis.grid(True, alpha=0.25)
        axis.legend()
    fig.suptitle("Comparable-budget real benchmark fronts")
    save("04_v1_vs_v2_objective_space.png")

    physical_percent = []
    h_percent = []
    for row in scaling:
        # Final capped-archive verification recomputations are correctness work,
        # not candidate objective evaluations, so use exact_evaluations here.
        physical_percent.append(100 * row["incremental_physical_evaluations"] / max(1, row["exact_evaluations"]))
        h_percent.append(100 * row["incremental_H_eff8_evaluations"] / max(1, row["exact_evaluations"]))
    plt.figure(figsize=(6.2, 4.0))
    plt.plot(n, physical_percent, marker="o", label="physical")
    plt.plot(n, h_percent, marker="s", label="H_eff8")
    plt.xscale("log")
    plt.ylim(0, 100)
    plt.xlabel("Synthetic FF count N")
    plt.ylabel("Incremental share of evaluations/recomputations (%)")
    plt.title("Incremental objective work")
    plt.grid(True, which="both", alpha=0.25)
    plt.legend()
    save("05_incremental_evaluation_share.png")
    return paths


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("all", "real", "scaling", "profile", "plots"), default="all")
    parser.add_argument("--real-wall-seconds", type=float, default=20.0)
    parser.add_argument("--real-exact-budget", type=int, default=16)
    parser.add_argument("--real-local-moves", type=int, default=32)
    parser.add_argument("--scaling-wall-seconds", type=float, default=20.0)
    parser.add_argument("--scaling-exact-budget", type=int, default=8)
    parser.add_argument("--scaling-local-moves", type=int, default=2)
    parser.add_argument("--sizes", default="200,500,1000,2000,5000,10000")
    parser.add_argument("--seed", type=int, default=20260921)
    args = parser.parse_args()
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    sizes = [int(value) for value in args.sizes.split(",") if value]
    real_path, scaling_path = REPORT_ROOT / "real_benchmark.json", REPORT_ROOT / "scaling_results.json"
    real = None
    scaling = None
    if args.mode in {"all", "real"}:
        real = run_real_benchmarks(args.real_wall_seconds, args.real_exact_budget,
                                   args.real_local_moves, args.seed)
    if args.mode in {"all", "scaling"}:
        scaling = run_scaling(sizes, args.scaling_wall_seconds, args.scaling_exact_budget,
                              args.scaling_local_moves, args.seed)
    if args.mode in {"all", "profile"}:
        run_profile(args.seed)
    if args.mode in {"all", "plots"}:
        real = real or json.loads(real_path.read_text(encoding="utf-8"))
        scaling = scaling or json.loads(scaling_path.read_text(encoding="utf-8"))
        write_json(REPORT_ROOT / "figures.json", make_plots(scaling, real))


if __name__ == "__main__":
    main()
