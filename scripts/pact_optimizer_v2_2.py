#!/usr/bin/env python3
"""Qualification harness for PACT Optimizer-v2.2.

This script runs no routing, OpenROAD, ML, or approximate activity model. It
measures the frozen retained v2.1 evaluator against exact deterministic tiled
execution and writes restartable JSON evidence under ``reports/optimizer_v2_2``.
"""
from __future__ import annotations

import argparse
import cProfile
import csv
import gc
import io
import json
import os
from pathlib import Path
import pickle
import platform
import pstats
import subprocess
import sys
import time
import tracemalloc
from typing import Any, Mapping, Sequence

import numpy as np
import scipy
from threadpoolctl import threadpool_info, threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from pact.phase0d.funnel import FrozenProxyContext  # noqa: E402
from pact.experiment_storage import (  # noqa: E402
    DEFAULT_MIN_FREE_GIB,
    ExperimentPaths,
    add_experiment_root_argument,
    configure_experiment_storage,
    free_space_snapshot,
    guard_disk_space,
)
from pact.phase0d.optimizer_v1 import PhysicalCostModel, TargetCompatibility  # noqa: E402
from pact.phase0d.optimizer_v2 import (  # noqa: E402
    OptimizerV2Config,
    PhysicalArcCost,
    optimize_v2,
)
from pact.phase0d.v2_activity import (  # noqa: E402
    IncrementalHEff8,
    RetainedIncrementalHEff8,
)
from pact.phase0d.v2_architecture import MutableScanArchitecture  # noqa: E402
from pact.phase0d.v2_shared_frontier import construct_architectures_v2_1  # noqa: E402
from pact.phase0d.v2_sparse import SparsePhysicalGraph  # noqa: E402
from pact.scan.model import ScanArchitecture  # noqa: E402
from pact_optimizer_v2 import synthetic_problem  # noqa: E402


REPORT_ROOT = ROOT / "reports" / "optimizer_v2_2"
SEED = 20260921
EXPERIMENT_PATHS: ExperimentPaths | None = None


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def git(*arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=ROOT, text=True, stderr=subprocess.STDOUT
    ).strip()


def metadata() -> dict[str, Any]:
    cpu = platform.processor()
    try:
        cpu = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command",
             "(Get-ItemProperty 'HKLM:\\HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0').ProcessorNameString"],
            text=True,
        ).strip() or cpu
    except (OSError, subprocess.SubprocessError):
        pass
    payload = {
        "captured_at_unix": time.time(),
        "git_commit": git("rev-parse", "HEAD"),
        "git_status": git("status", "--porcelain=v2", "--branch"),
        "cpu_model": cpu,
        "physical_cores": 8,
        "logical_cores": os.cpu_count(),
        "python": sys.version,
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "experiment_paths": (
            EXPERIMENT_PATHS.as_dict()
            if EXPERIMENT_PATHS is not None
            else configure_experiment_storage().as_dict()
        ),
        "free_space": free_space_snapshot(
            EXPERIMENT_PATHS or configure_experiment_storage()
        ),
        "blas_threadpools": threadpool_info(),
        "outer_worker_policy": [1, 2, 4, min(8, 8)],
        "inner_blas_threads_during_tiled_work": 1,
        "platform": platform.platform(),
    }
    write_json(REPORT_ROOT / "environment.json", payload)
    return payload


def architecture_orders(base: ScanArchitecture) -> tuple[tuple[int, ...], ...]:
    return MutableScanArchitecture.from_scan_architecture(base).orders()


def make_swap(base: ScanArchitecture, physical_model: PhysicalCostModel):
    mutable = MutableScanArchitecture.from_scan_architecture(base)
    physical = PhysicalArcCost(base, physical_model)
    order = mutable.order(0)
    patch = mutable.swap(order[len(order) // 3], order[(2 * len(order)) // 3], physical)
    after = {chain: mutable.order(chain) for chain in patch.affected_chains}
    return mutable, patch, after


def measure_evaluator(
    base: ScanArchitecture,
    physical: PhysicalCostModel,
    patterns: Sequence[Mapping[str, int]],
    weights: Mapping[str, int],
    *,
    backend: str,
    tile_patterns: int = 16,
    workers: int = 1,
) -> dict[str, Any]:
    if backend == "retained_v2_1":
        evaluator = RetainedIncrementalHEff8(base, patterns, weights)
    elif backend == "tiled":
        evaluator = IncrementalHEff8(
            base, patterns, weights,
            tile_patterns=tile_patterns,
            workers=workers,
            parallel_backend="thread",
        )
    else:
        raise ValueError(backend)
    orders = architecture_orders(base)
    tracemalloc.start()
    wall_started = time.perf_counter()
    cpu_started = time.process_time()
    with threadpool_limits(limits=1, user_api="blas"):
        state = evaluator.full_state(orders)
    full_wall = time.perf_counter() - wall_started
    full_cpu = time.process_time() - cpu_started
    mutable, patch, after = make_swap(base, physical)
    wall_started = time.perf_counter()
    cpu_started = time.process_time()
    with threadpool_limits(limits=1, user_api="blas"):
        candidate = evaluator.evaluate(
            state, patch.before_orders, after, mutable.lengths
        )
    incremental_wall = time.perf_counter() - wall_started
    incremental_cpu = time.process_time() - cpu_started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "backend": backend,
        "tile_patterns": tile_patterns if backend == "tiled" else None,
        "workers": workers if backend == "tiled" else 1,
        "inner_blas_threads": 1,
        "full_seconds": full_wall,
        "full_cpu_seconds": full_cpu,
        "full_average_cpu_cores": full_cpu / max(full_wall, 1e-12),
        "incremental_seconds": incremental_wall,
        "incremental_cpu_seconds": incremental_cpu,
        "incremental_average_cpu_cores": incremental_cpu / max(incremental_wall, 1e-12),
        "incremental_evaluations_per_second": 1.0 / max(incremental_wall, 1e-12),
        "value": state.value,
        "candidate_value": candidate.value,
        "candidate_architecture_sha256": mutable.to_scan_architecture().sha256(),
        "persistent_global_bytes": evaluator.persistent_global_bytes(state),
        "persistent_per_chain_bytes": evaluator.persistent_per_chain_bytes(state),
        "persistent_total_bytes": evaluator.memory_bytes(state),
        "estimated_peak_transient_tile_bytes": evaluator.peak_transient_tile_bytes,
        "peak_traced_backend_bytes": int(peak),
    }


def run_tile_sweep(n: int, pattern_count: int) -> list[dict[str, Any]]:
    base, physical, patterns, weights = synthetic_problem(n, patterns=pattern_count)
    rows = []
    for tile in (4, 8, 16, 32):
        for workers in (1, 2, 4, 8):
            row = measure_evaluator(
                base, physical, patterns, weights,
                backend="tiled", tile_patterns=tile, workers=workers,
            )
            row.update({"N": n, "P": pattern_count, "K": len(base.chains),
                        "Lmax": max(len(chain.cells) for chain in base.chains)})
            rows.append(row)
            write_json(REPORT_ROOT / "tile_sweep_partial.json", rows)
            print(f"tile sweep B={tile} W={workers}: {row['full_seconds']:.6f}s", flush=True)
    baseline = next(row for row in rows if row["tile_patterns"] == 4 and row["workers"] == 1)
    for row in rows:
        row["speedup_over_B4_W1"] = baseline["full_seconds"] / row["full_seconds"]
        row["parallel_efficiency_over_B4_W1"] = (
            row["speedup_over_B4_W1"] / row["workers"]
        )
    write_json(REPORT_ROOT / "tile_sweep.json", rows)
    return rows


def old_state_estimate(base: ScanArchitecture, pattern_count: int) -> int:
    longest = max(len(chain.cells) for chain in base.chains)
    return (len(base.chains) + 1) * pattern_count * longest * 64 * 8


def run_scaling(sizes: Sequence[int], pattern_counts: Sequence[int],
                tile_patterns: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for n in sizes:
        for pattern_count in pattern_counts:
            base, physical, patterns, weights = synthetic_problem(n, patterns=pattern_count)
            row: dict[str, Any] = {
                "N": n,
                "P": pattern_count,
                "K": len(base.chains),
                "Lmax": max(len(chain.cells) for chain in base.chains),
                "synthetic_performance_only": True,
                "old_estimated_persistent_bytes": old_state_estimate(base, pattern_count),
                "measurements": {},
            }
            # Keep a hard 512 MiB state guard: the intentionally retained old
            # backend is not allowed to allocate a multi-GiB baseline.
            if row["old_estimated_persistent_bytes"] <= 512 * 2**20:
                row["measurements"]["retained_v2_1"] = measure_evaluator(
                    base, physical, patterns, weights, backend="retained_v2_1"
                )
            else:
                row["measurements"]["retained_v2_1"] = {
                    "skipped": True,
                    "reason": "hard_512_MiB_persistent_state_cap",
                }
            for workers in (1, 2, 4, 8):
                row["measurements"][f"tiled_W{workers}"] = measure_evaluator(
                    base, physical, patterns, weights,
                    backend="tiled", tile_patterns=tile_patterns, workers=workers,
                )
                gc.collect()
            one = row["measurements"]["tiled_W1"]["full_seconds"]
            for workers in (1, 2, 4, 8):
                item = row["measurements"][f"tiled_W{workers}"]
                item["speedup_over_tiled_W1"] = one / item["full_seconds"]
                item["parallel_efficiency"] = item["speedup_over_tiled_W1"] / workers
            old = row["measurements"]["retained_v2_1"]
            if not old.get("skipped"):
                for workers in (1, 2, 4, 8):
                    item = row["measurements"][f"tiled_W{workers}"]
                    item["speedup_over_retained_v2_1"] = (
                        old["full_seconds"] / item["full_seconds"]
                    )
                    if item["value"] != old["value"] or item["candidate_value"] != old["candidate_value"]:
                        raise AssertionError("Tiled and retained exact objectives differ")
            rows.append(row)
            write_json(REPORT_ROOT / "scaling_partial.json", rows)
            print(f"scaling N={n} P={pattern_count} complete", flush=True)
    write_json(REPORT_ROOT / "scaling_results.json", rows)
    with (REPORT_ROOT / "scaling_summary.csv").open("w", newline="", encoding="utf-8") as stream:
        fields = ["N", "P", "K", "Lmax", "backend", "full_seconds",
                  "incremental_seconds", "persistent_total_bytes", "peak_traced_backend_bytes",
                  "speedup", "efficiency"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            for name, item in row["measurements"].items():
                if item.get("skipped"):
                    continue
                writer.writerow({
                    "N": row["N"], "P": row["P"], "K": row["K"], "Lmax": row["Lmax"],
                    "backend": name, "full_seconds": item["full_seconds"],
                    "incremental_seconds": item["incremental_seconds"],
                    "persistent_total_bytes": item["persistent_total_bytes"],
                    "peak_traced_backend_bytes": item["peak_traced_backend_bytes"],
                    "speedup": item.get("speedup_over_tiled_W1"),
                    "efficiency": item.get("parallel_efficiency"),
                })
    return rows


def constructor_input_pickle_bytes(base: ScanArchitecture, graph: SparsePhysicalGraph,
                                   physical: PhysicalCostModel) -> int:
    activity_neighbors = np.empty((len(base.cells), 8), dtype=np.int32)
    return len(pickle.dumps((base, graph, physical, activity_neighbors, SEED), protocol=5))


def run_constructors(sizes: Sequence[int]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for n in sizes:
        base, physical, patterns, weights = synthetic_problem(n)
        graph = SparsePhysicalGraph.build(
            np.asarray([(cell.x_um, cell.y_um) for cell in base.cells]), 12
        )
        activity = TargetCompatibility(patterns, weights)
        row: dict[str, Any] = {
            "N": n,
            "K": len(base.chains),
            "process_serialized_input_bytes_estimate": constructor_input_pickle_bytes(
                base, graph, physical
            ),
            "modes": {},
        }
        for mode in ("sequential", "thread", "process"):
            tracemalloc.start()
            started = time.perf_counter()
            starts, stats = construct_architectures_v2_1(
                base, graph, physical, activity, seed=SEED, parallel_backend=mode
            )
            elapsed = time.perf_counter() - started
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            row["modes"][mode] = {
                "wall_seconds": elapsed,
                "peak_main_process_traced_bytes": int(peak),
                "architecture_hashes": [item.canonical_digest() for _, item in starts],
                "stats": stats.to_dict(),
            }
            print(f"constructor N={n} {mode}: {elapsed:.6f}s", flush=True)
        expected = row["modes"]["sequential"]["architecture_hashes"]
        if any(item["architecture_hashes"] != expected for item in row["modes"].values()):
            raise AssertionError("Constructor concurrency changed the portfolio")
        row["thread_speedup"] = (
            row["modes"]["sequential"]["wall_seconds"]
            / row["modes"]["thread"]["wall_seconds"]
        )
        row["process_speedup"] = (
            row["modes"]["sequential"]["wall_seconds"]
            / row["modes"]["process"]["wall_seconds"]
        )
        if n == min(sizes):
            vector_rows = {}
            for vectorized in (False, True):
                started = time.perf_counter()
                starts, _ = construct_architectures_v2_1(
                    base, graph, physical, activity, seed=SEED,
                    vectorized_records=vectorized,
                )
                vector_rows[str(vectorized)] = {
                    "wall_seconds": time.perf_counter() - started,
                    "architecture_hashes": [item.canonical_digest() for _, item in starts],
                }
            if vector_rows["False"]["architecture_hashes"] != vector_rows["True"]["architecture_hashes"]:
                raise AssertionError("Vectorized record features changed constructor output")
            row["vectorized_record_experiment"] = vector_rows
        rows.append(row)
        write_json(REPORT_ROOT / "constructor_results_partial.json", rows)
    write_json(REPORT_ROOT / "constructor_results.json", rows)
    return rows


def optimizer_config(backend: str, patterns: int, workers: int) -> OptimizerV2Config:
    return OptimizerV2Config(
        wall_clock_seconds=180.0,
        maximum_exact_evaluations=12,
        maximum_local_moves=16,
        maximum_archive_size=12,
        maximum_neighborhood_size=24,
        graph_k=12,
        activity_candidates=6,
        random_nonlocal_candidates=3,
        parent_refresh_interval=8,
        seen_cache_size=4096,
        seed=SEED,
        constructor_mode="shared_frontier",
        constructor_parallel_backend="sequential",
        h_eff8_backend=backend,
        h_eff8_tile_patterns=min(16, patterns),
        h_eff8_workers=workers,
    )


def compact_optimizer(result) -> dict[str, Any]:
    return {
        "runtime": dict(result.runtime),
        "memory": dict(result.memory),
        "counters": dict(result.counters),
        "archive": [dict(row) for row in result.archive],
        "stop_reason": result.stop_reason,
    }


def comparable_archive(result: Mapping[str, Any]) -> list[tuple[str, tuple[float, float]]]:
    return sorted(
        (str(row["architecture_sha256"]), tuple(map(float, row["objectives"])))
        for row in result["archive"]
    )


def run_optimizer_baselines(sizes: Sequence[int]) -> list[dict[str, Any]]:
    rows = []
    for n in sizes:
        base, physical, patterns, weights = synthetic_problem(n, patterns=4)
        row = {"N": n, "P": 4, "K": len(base.chains),
               "Lmax": max(len(chain.cells) for chain in base.chains), "results": {}}
        for backend, workers in (("retained_v2_1", 1), ("tiled", 4)):
            result = optimize_v2(
                base, patterns, weights, physical,
                optimizer_config(backend, len(patterns), workers), trace_limit=0,
            )
            row["results"][backend] = compact_optimizer(result)
            print(f"optimizer baseline N={n} {backend} complete", flush=True)
        old = row["results"]["retained_v2_1"]
        new = row["results"]["tiled"]
        row["exact_equivalence"] = comparable_archive(old) == comparable_archive(new)
        row["speedup"] = (
            old["runtime"]["optimizer_wall_seconds"]
            / new["runtime"]["optimizer_wall_seconds"]
        )
        if not row["exact_equivalence"] or old["stop_reason"] != new["stop_reason"]:
            raise AssertionError("Synthetic optimizer result changed across exact backends")
        rows.append(row)
        write_json(REPORT_ROOT / "baseline_partial.json", rows)
    write_json(REPORT_ROOT / "baseline_results.json", rows)
    return rows


def qualified_seeds(context: FrozenProxyContext) -> list[tuple[str, ScanArchitecture]]:
    seeds = []
    for row in context.portfolio_rows:
        path = Path(row["architecture_path"])
        if not path.is_absolute():
            path = ROOT / path
        seeds.append((f"qualified_{row.get('method', path.stem)}", ScanArchitecture.from_json(path)))
    return seeds


def run_real() -> dict[str, Any]:
    payload: dict[str, Any] = {"routing_calls": 0, "designs": {}}
    for design in ("s5378", "s9234"):
        context = FrozenProxyContext.load(ROOT, design, 11, 2, "P")
        physical = PhysicalCostModel.from_architecture(
            context.start_architecture, context.frozen_def
        )
        design_row: dict[str, Any] = {
            "N": len(context.start_architecture.cells),
            "P": len(context.patterns),
            "K": len(context.start_architecture.chains),
            "Lmax": max(len(chain.cells) for chain in context.start_architecture.chains),
            "results": {},
        }
        for backend, workers in (("retained_v2_1", 1), ("tiled", 4)):
            result = optimize_v2(
                context.start_architecture, context.patterns, context.weights, physical,
                optimizer_config(backend, len(context.patterns), workers),
                seed_architectures=qualified_seeds(context), trace_limit=0,
            )
            design_row["results"][backend] = compact_optimizer(result)
            print(f"real {design} {backend} complete", flush=True)
        old = design_row["results"]["retained_v2_1"]
        new = design_row["results"]["tiled"]
        design_row["exact_equivalence"] = comparable_archive(old) == comparable_archive(new)
        design_row["same_stop_reason"] = old["stop_reason"] == new["stop_reason"]
        if not design_row["exact_equivalence"] or not design_row["same_stop_reason"]:
            raise AssertionError(f"Real optimizer result changed for {design}")
        payload["designs"][design] = design_row
        write_json(REPORT_ROOT / "real_partial.json", payload)
    write_json(REPORT_ROOT / "real_benchmark.json", payload)
    return payload


def run_profile() -> str:
    base, physical, patterns, weights = synthetic_problem(5000, patterns=128)
    profiler = cProfile.Profile()
    profiler.enable()
    measure_evaluator(
        base, physical, patterns, weights,
        backend="tiled", tile_patterns=16, workers=4,
    )
    profiler.disable()
    paths = EXPERIMENT_PATHS or configure_experiment_storage()
    profiler.dump_stats(paths.profiles / "optimizer_v2_2.prof")
    output = io.StringIO()
    stats = pstats.Stats(profiler, stream=output).strip_dirs()
    output.write("CUMULATIVE TIME\n")
    stats.sort_stats("cumulative").print_stats(30)
    output.write("\nSELF CPU TIME\n")
    stats.sort_stats("tottime").print_stats(30)
    text = output.getvalue().rstrip() + "\n"
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    (REPORT_ROOT / "profile_top.txt").write_text(text, encoding="utf-8")
    return text


def main() -> None:
    global EXPERIMENT_PATHS
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("all", "metadata", "tiles", "scaling", "constructor", "baseline", "real", "profile"),
        default="all",
    )
    parser.add_argument("--sizes", default="1000,5000,10000")
    parser.add_argument("--patterns", default="4,32,128,256")
    parser.add_argument("--tile-patterns", type=int, default=16)
    parser.add_argument("--minimum-free-gib", type=float, default=DEFAULT_MIN_FREE_GIB)
    parser.add_argument("--estimated-bytes", type=int, default=2 * 1024**3)
    add_experiment_root_argument(parser)
    args = parser.parse_args()
    EXPERIMENT_PATHS = configure_experiment_storage(args.experiment_root)
    guard_disk_space(
        EXPERIMENT_PATHS,
        estimated_bytes=args.estimated_bytes,
        minimum_free_gib=args.minimum_free_gib,
    )
    sizes = tuple(int(value) for value in args.sizes.split(",") if value)
    pattern_counts = tuple(int(value) for value in args.patterns.split(",") if value)
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    if args.mode in {"all", "metadata"}:
        metadata()
    if args.mode in {"all", "tiles"}:
        run_tile_sweep(1000, 128)
    if args.mode in {"all", "scaling"}:
        run_scaling(sizes, pattern_counts, args.tile_patterns)
    if args.mode in {"all", "constructor"}:
        run_constructors(sizes)
    if args.mode in {"all", "baseline"}:
        run_optimizer_baselines(sizes)
    if args.mode in {"all", "real"}:
        run_real()
    if args.mode in {"all", "profile"}:
        run_profile()


if __name__ == "__main__":
    main()
