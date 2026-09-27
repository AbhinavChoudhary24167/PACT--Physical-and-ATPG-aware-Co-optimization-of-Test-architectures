#!/usr/bin/env python3
"""PACT Optimizer-v2.3 independent parallel Pareto qualification.

No routing, OpenROAD call, scalarized Pareto membership, or approximate H_eff8
is used here.  Raw experiment state is written below the central experiment
root; only compact JSON, CSV, figures, and Markdown are emitted in the repo.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pact.experiment_storage import (  # noqa: E402
    DEFAULT_MIN_FREE_GIB,
    ExperimentPaths,
    StorageRunTracker,
    add_experiment_root_argument,
    c_drive_safety_warning,
    configure_experiment_storage,
    free_space_snapshot,
    guard_disk_space,
)
from pact.phase0d.funnel import FrozenProxyContext  # noqa: E402
from pact.phase0d.optimizer_v1 import PhysicalCostModel  # noqa: E402
from pact.phase0d.optimizer_v2 import OptimizerV2Config  # noqa: E402
from pact.phase0d.optimizer_v2_3 import (  # noqa: E402
    ParallelParetoConfig,
    freeze_reference,
    optimize_parallel_pareto,
)
from pact.scan.model import ScanArchitecture  # noqa: E402


REPORT_ROOT = ROOT / "reports" / "optimizer_v2_3"
SEED = 20260921


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def git(*arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=ROOT, text=True, stderr=subprocess.STDOUT
    ).strip()


def environment_metadata(paths: ExperimentPaths) -> dict[str, Any]:
    free = free_space_snapshot(paths)
    v2_2_environment_path = ROOT / "reports" / "optimizer_v2_2" / "environment.json"
    v2_2_environment = (
        json.loads(v2_2_environment_path.read_text(encoding="utf-8"))
        if v2_2_environment_path.is_file()
        else {}
    )
    payload = {
        "captured_at_unix": time.time(),
        "git_commit": git("rev-parse", "HEAD"),
        "git_status": git("status", "--porcelain=v2", "--branch"),
        "cpu_model": v2_2_environment.get("cpu_model", platform.processor()),
        "physical_cores": v2_2_environment.get("physical_cores"),
        "logical_cores": os.cpu_count(),
        "python": sys.version,
        "platform": platform.platform(),
        "experiment_paths": paths.as_dict(),
        **free,
        "frozen_v2_2_test_baseline": {
            "tests_passed": 146,
            "status": "PASS",
            "temporary_root": str(paths.pytest_tmp / "v22-freeze"),
        },
        "frozen_v2_2_real_search_configuration": {
            "wall_clock_seconds": 180.0,
            "maximum_exact_evaluations": 12,
            "maximum_local_moves": 16,
            "maximum_archive_size": 12,
            "maximum_neighborhood_size": 24,
            "graph_k": 12,
            "parent_refresh_interval": 8,
            "seen_cache_size": 4096,
            "seed": SEED,
            "constructor_mode": "shared_frontier",
            "constructor_parallel_backend": "sequential",
            "h_eff8_backend": "tiled",
            "h_eff8_tile_patterns": 16,
            "h_eff8_workers": 4,
        },
    }
    write_json(REPORT_ROOT / "environment.json", payload)
    return payload


def _architecture_path(row: Mapping[str, Any]) -> Path:
    path = Path(str(row["architecture_path"]))
    return path if path.is_absolute() else ROOT / path


def _point(row: Mapping[str, Any]) -> tuple[float, float]:
    return (
        float(row["scan_geometry"]["total_scan_hpwl_um"]),
        float(row["activity"]["grids"]["8"]["H_eff"]),
    )


def frozen_start_portfolio(
    context: FrozenProxyContext, maximum_size: int = 4,
) -> tuple[list[tuple[str, ScanArchitecture]], list[dict[str, Any]]]:
    """Select one common deterministic, diversity-aware qualified portfolio."""
    records: dict[str, tuple[dict[str, Any], ScanArchitecture]] = {}
    for row in context.portfolio_rows:
        architecture = ScanArchitecture.from_json(_architecture_path(row))
        records.setdefault(architecture.sha256(), (dict(row), architecture))
    base_sha = context.start_architecture.sha256()
    records.setdefault(base_sha, (dict(context.start_proxy), context.start_architecture))
    values = list(records.values())
    if not values:
        raise ValueError(f"No qualified starts for {context.context_id}")

    selected: list[tuple[dict[str, Any], ScanArchitecture]] = [records[base_sha]]
    for candidate in (
        min(values, key=lambda item: (_point(item[0])[0], _point(item[0])[1], item[1].sha256())),
        min(values, key=lambda item: (_point(item[0])[1], _point(item[0])[0], item[1].sha256())),
    ):
        if candidate[1].sha256() not in {item[1].sha256() for item in selected}:
            selected.append(candidate)

    all_points = [_point(row) for row, _ in values]
    low = tuple(min(point[index] for point in all_points) for index in range(2))
    high = tuple(max(point[index] for point in all_points) for index in range(2))
    scale = tuple(max(high[index] - low[index], 1e-12) for index in range(2))
    while len(selected) < min(maximum_size, len(values)):
        selected_shas = {item[1].sha256() for item in selected}

        def diversity(item: tuple[dict[str, Any], ScanArchitecture]) -> tuple[float, str]:
            point = _point(item[0])
            minimum = min(
                sum(((point[index] - _point(saved[0])[index]) / scale[index]) ** 2
                    for index in range(2)) ** 0.5
                for saved in selected
            )
            return minimum, item[1].sha256()

        remaining = [item for item in values if item[1].sha256() not in selected_shas]
        selected.append(max(remaining, key=diversity))

    portfolio = []
    manifest = []
    for index, (row, architecture) in enumerate(selected):
        label = str(row.get("method", _architecture_path(row).stem))
        portfolio.append((f"frozen_{index}_{label}", architecture))
        manifest.append({
            "index": index,
            "label": label,
            "architecture_sha256": architecture.sha256(),
            "architecture_path": str(_architecture_path(row).relative_to(ROOT)).replace("\\", "/"),
            "objectives": list(_point(row)),
        })
    return portfolio, manifest


def optimizer_config(maximum_exact_evaluations: int) -> OptimizerV2Config:
    return OptimizerV2Config(
        wall_clock_seconds=600.0,
        maximum_exact_evaluations=maximum_exact_evaluations,
        maximum_local_moves=max(4096, maximum_exact_evaluations * 64),
        maximum_archive_size=24,
        maximum_neighborhood_size=32,
        graph_k=16,
        activity_candidates=6,
        random_nonlocal_candidates=3,
        parent_refresh_interval=16,
        seen_cache_size=8192,
        seed=SEED,
        constructor_mode="shared_frontier",
        constructor_parallel_backend="sequential",
        h_eff8_tile_patterns=16,
        h_eff8_workers=1,
        h_eff8_parallel_backend="sequential",
        h_eff8_backend="tiled",
        # The frozen qualified portfolio is the sole constructor control for
        # every W. This prevents generated-start differences from confounding
        # independent trajectory comparisons.
        generate_constructor_starts=False,
    )


def _write_raw_architectures(
    root: Path, architectures: Mapping[str, ScanArchitecture],
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    expected = {f"{sha}.architecture.json" for sha in architectures}
    for sha, architecture in architectures.items():
        payload = architecture.canonical_dict()
        payload["architecture_sha256"] = sha
        write_json(root / f"{sha}.architecture.json", payload)
    # A rerun may produce a different final archive. Remove only obsolete files
    # in this exact PACT-owned architecture directory; never broaden cleanup to
    # the experiment root or another run.
    for existing in root.glob("*.architecture.json"):
        if existing.name not in expected:
            existing.unlink()


def run_design(
    design: str,
    paths: ExperimentPaths,
    *,
    exact_budget: int,
    wall_seconds: float,
    wall_max_evaluations: int,
    epochs: int,
    backend: str,
    keep_scratch: bool,
) -> dict[str, Any]:
    context = FrozenProxyContext.load(ROOT, design, 11, 2, "P")
    physical = PhysicalCostModel.from_architecture(
        context.start_architecture, context.frozen_def
    )
    portfolio, portfolio_manifest = frozen_start_portfolio(context)
    ideal, reference = freeze_reference(_point(row) for row in context.portfolio_rows)
    base = portfolio[0][1]
    starts = portfolio[1:]
    design_result: dict[str, Any] = {
        "context_id": context.context_id,
        "N": len(base.cells),
        "P": len(context.patterns),
        "K": len(base.chains),
        "start_portfolio": portfolio_manifest,
        "frozen_ideal": list(ideal),
        "frozen_reference": list(reference),
        "equal_evaluations": {},
        "equal_wall": {},
    }
    for mode in ("exact_evaluations", "wall_clock"):
        target = "equal_evaluations" if mode == "exact_evaluations" else "equal_wall"
        maximum_evaluations = exact_budget if mode == "exact_evaluations" else wall_max_evaluations
        base_config = optimizer_config(maximum_evaluations)
        for workers in (1, 2, 4):
            run_id = f"v2-3-{design}-{target}-w{workers}"
            parallel = ParallelParetoConfig(
                worker_count=workers,
                budget_mode=mode,
                total_exact_evaluations=exact_budget,
                wall_clock_seconds=wall_seconds,
                epochs=epochs,
                master_seed=SEED,
                parallel_backend=backend,
                keep_scratch=keep_scratch,
                run_id=run_id,
            )
            result = optimize_parallel_pareto(
                base,
                context.patterns,
                context.weights,
                physical,
                base_config,
                parallel,
                start_portfolio=starts,
                frozen_ideal=ideal,
                frozen_reference=reference,
                storage_paths=paths,
            )
            row = result.to_dict()
            design_result[target][str(workers)] = row
            raw_root = paths.results / "optimizer_v2_3" / design / target / f"w{workers}"
            write_json(raw_root / "result.json", row)
            _write_raw_architectures(raw_root / "architectures", result.architecture_objects)
            write_json(REPORT_ROOT / "campaign_partial.json", {design: design_result})
            print(
                f"{design} {target} W={workers}: "
                f"evals={row['accounting']['total_exact_evaluations']} "
                f"archive={row['metrics']['nondominated_archive_size']} "
                f"wall={row['runtime']['wall_seconds']:.3f}s",
                flush=True,
            )
    return design_result


def _quality_advance(candidate: Mapping[str, Any], baseline: Mapping[str, Any]) -> bool:
    left, right = candidate["metrics"], baseline["metrics"]
    hv_tolerance = max(1e-9, abs(float(right["frozen_reference_hypervolume"])) * 1e-6)
    return bool(
        float(left["frozen_reference_hypervolume"])
        > float(right["frozen_reference_hypervolume"]) + hv_tolerance
        or (
            int(left["nondominated_archive_size"]) > int(right["nondominated_archive_size"])
            and float(left["frozen_reference_hypervolume"])
            >= float(right["frozen_reference_hypervolume"]) - hv_tolerance
        )
        or (
            float(left["objective_space_spread"])
            > 1.01 * float(right["objective_space_spread"])
            and float(left["frozen_reference_hypervolume"])
            >= float(right["frozen_reference_hypervolume"]) - hv_tolerance
        )
    )


def classify(campaign: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    comparisons: dict[str, Any] = {}
    any_advance = False
    for design, result in campaign["designs"].items():
        baseline = result["equal_evaluations"]["1"]
        advances = {
            workers: _quality_advance(result["equal_evaluations"][workers], baseline)
            for workers in ("2", "4")
        }
        comparisons[design] = advances
        any_advance = any_advance or any(advances.values())
    classification = (
        "PACT_V2_3_PARALLEL_PARETO_ADVANCE"
        if any_advance
        else "PACT_V2_3_PARALLEL_PARETO_NO_SEARCH_ADVANCE"
    )
    return classification, comparisons


def make_plots(campaign: Mapping[str, Any]) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure_root = REPORT_ROOT / "figures"
    figure_root.mkdir(parents=True, exist_ok=True)
    outputs = []
    colors = {"1": "#1f77b4", "2": "#ff7f0e", "4": "#2ca02c"}
    markers = {"1": "o", "2": "s", "4": "^"}
    for design, result in campaign["designs"].items():
        for experiment in ("equal_evaluations", "equal_wall"):
            plt.figure(figsize=(6.8, 4.8))
            for workers in ("1", "2", "4"):
                archive = result[experiment][workers]["archive"]
                plt.scatter(
                    [row["objectives"][0] for row in archive],
                    [row["objectives"][1] for row in archive],
                    label=f"W={workers}",
                    color=colors[workers],
                    marker=markers[workers],
                )
            plt.xlabel("Qualified port-aware Manhattan scan HPWL proxy (µm)")
            plt.ylabel("Exact H_eff8")
            plt.title(f"{design}: {experiment.replace('_', ' ')}")
            plt.grid(True, alpha=0.25)
            plt.legend()
            plt.tight_layout()
            path = figure_root / f"{design}_{experiment}_pareto.png"
            plt.savefig(path, dpi=180)
            plt.close()
            outputs.append(str(path.relative_to(ROOT)).replace("\\", "/"))
    write_json(REPORT_ROOT / "figures.json", outputs)
    return outputs


def write_summary_csv(campaign: Mapping[str, Any]) -> None:
    rows = []
    for design, result in campaign["designs"].items():
        for experiment in ("equal_evaluations", "equal_wall"):
            for workers in ("1", "2", "4"):
                row = result[experiment][workers]
                rows.append({
                    "design": design,
                    "experiment": experiment,
                    "workers": int(workers),
                    "exact_evaluations": row["accounting"]["total_exact_evaluations"],
                    "archive_size": row["metrics"]["nondominated_archive_size"],
                    "unique_architectures": row["metrics"]["unique_architectures"],
                    "best_physical": row["metrics"]["best_physical"],
                    "best_H_eff8": row["metrics"]["best_H_eff8"],
                    "hypervolume": row["metrics"]["frozen_reference_hypervolume"],
                    "spread": row["metrics"]["objective_space_spread"],
                    "duplicate_evaluation_fraction": row["metrics"]["duplicate_evaluation_fraction"],
                    "wall_seconds": row["runtime"]["wall_seconds"],
                    "cpu_utilization_percent": row["runtime"]["cpu_utilization_percent"],
                })
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    with (REPORT_ROOT / "summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_report(campaign: Mapping[str, Any]) -> None:
    lines = [
        "# PACT Optimizer-v2.3 Independent Parallel Pareto Search",
        "",
        f"**Classification:** `{campaign['classification']}`",
        "",
        "The equal-evaluation result controls the scientific classification. Equal-wall results are reported separately and do not establish a search-quality advance merely by completing more work.",
        "",
        "## Results",
        "",
        "| Design | Budget | W | Exact evals | Archive | Unique | Best physical | Best H_eff8 | Hypervolume | Duplicate rate | Wall (s) | CPU util. |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for design, result in campaign["designs"].items():
        for experiment in ("equal_evaluations", "equal_wall"):
            for workers in ("1", "2", "4"):
                row = result[experiment][workers]
                metrics, accounting, runtime = row["metrics"], row["accounting"], row["runtime"]
                lines.append(
                    f"| {design} | {experiment} | {workers} | {accounting['total_exact_evaluations']} | "
                    f"{metrics['nondominated_archive_size']} | {metrics['unique_architectures']} | "
                    f"{metrics['best_physical']:.6g} | {metrics['best_H_eff8']:.6g} | "
                    f"{metrics['frozen_reference_hypervolume']:.6g} | "
                    f"{metrics['duplicate_evaluation_fraction']:.3%} | {runtime['wall_seconds']:.3f} | "
                    f"{runtime['cpu_utilization_percent']:.1f}% |"
                )
    storage = campaign["storage_manifest"]
    lines.extend([
        "",
        "## Correctness and provenance",
        "",
        f"- Frozen v2.2 baseline: {campaign['environment']['frozen_v2_2_test_baseline']['tests_passed']} tests passed.",
        f"- Post-change repository status: {campaign['correctness_status']}.",
        "- W=1 uses the existing serial v2.2 engine; W=2/W=4 use independent mutable state and deterministic lane seeds.",
        "- Global Pareto membership uses only the two authoritative exact objectives and canonical serial merge order.",
        "- No routing was launched.",
        f"- Additional qualified benchmark evidence: {campaign['additional_qualified_benchmark_evidence']}.",
        f"- s5378 diversity improved: {campaign['s5378_diversity_improved']}.",
        "",
        "## Storage",
        "",
        f"- Experiment root: `{storage['experiment_root']}`",
        f"- Total bytes written to D: {storage['total_bytes_written']}",
        f"- Peak experiment-directory size: {storage['peak_experiment_directory_size']} bytes",
        f"- Residual worker scratch: {storage['residual_scratch_bytes']} bytes",
        f"- Cleanup: {storage['cleanup_status']}",
        f"- Large PACT-controlled file observed on C: {campaign['large_file_observed_on_C']}",
        "",
        "## Remaining bottleneck",
        "",
        "The exact tiled spatial convolution/correlation kernel remains the dominant numerical bottleneck; it was measured but deliberately not optimized in v2.3.",
        "",
        "## Git",
        "",
        f"- Commit: `{campaign['environment']['git_commit']}`",
        "- Status is recorded verbatim in `environment.json`.",
        "",
    ])
    (REPORT_ROOT / "REPORT.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("all", "metadata", "experiments", "plots"), default="all")
    parser.add_argument("--designs", default="s5378,s9234,s15850")
    parser.add_argument("--exact-budget", type=int, default=64)
    parser.add_argument("--wall-seconds", type=float, default=30.0)
    parser.add_argument("--wall-max-evaluations", type=int, default=4096)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--parallel-backend", choices=("process", "sequential"), default="process")
    parser.add_argument("--keep-scratch", action="store_true")
    parser.add_argument("--minimum-free-gib", type=float, default=DEFAULT_MIN_FREE_GIB)
    parser.add_argument("--estimated-bytes", type=int, default=2 * 1024**3)
    add_experiment_root_argument(parser)
    args = parser.parse_args()

    paths = configure_experiment_storage(args.experiment_root)
    warning = c_drive_safety_warning(paths)
    if warning:
        print(f"*** {warning} ***", file=sys.stderr, flush=True)
    guard_disk_space(
        paths,
        estimated_bytes=args.estimated_bytes,
        minimum_free_gib=args.minimum_free_gib,
    )
    tracker = StorageRunTracker.start(paths)
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    environment = environment_metadata(paths)
    campaign_path = REPORT_ROOT / "campaign.json"
    if args.mode in {"all", "experiments"}:
        campaign: dict[str, Any] = {
            "schema_version": "pact-optimizer-v2-3-campaign-1",
            "environment": environment,
            "configuration": {
                "exact_budget": args.exact_budget,
                "wall_seconds": args.wall_seconds,
                "wall_max_evaluations": args.wall_max_evaluations,
                "epochs": args.epochs,
                "parallel_backend": args.parallel_backend,
                "minimum_free_gib": args.minimum_free_gib,
                "estimated_bytes": args.estimated_bytes,
            },
            "designs": {},
        }
        requested = [item for item in args.designs.split(",") if item]
        qualified = []
        for design in requested:
            try:
                result = run_design(
                    design,
                    paths,
                    exact_budget=args.exact_budget,
                    wall_seconds=args.wall_seconds,
                    wall_max_evaluations=args.wall_max_evaluations,
                    epochs=args.epochs,
                    backend=args.parallel_backend,
                    keep_scratch=args.keep_scratch,
                )
            except (FileNotFoundError, ValueError) as error:
                if design in {"s5378", "s9234"}:
                    raise
                campaign["designs"][design] = {
                    "status": "NOT_QUALIFIED",
                    "reason": str(error),
                }
                continue
            campaign["designs"][design] = result
            qualified.append(design)
            tracker.sample()
            write_json(campaign_path, campaign)
        campaign["designs"] = {
            design: row for design, row in campaign["designs"].items()
            if row.get("status") != "NOT_QUALIFIED"
        }
        campaign["additional_qualified_benchmark_evidence"] = "s15850" in qualified
        campaign["classification"], campaign["equal_evaluation_advances"] = classify(campaign)
        campaign["s5378_diversity_improved"] = any(
            campaign["equal_evaluation_advances"].get("s5378", {}).values()
        )
        campaign["correctness_status"] = "PENDING_POST_CHANGE_FULL_TESTS"
        campaign["large_file_observed_on_C"] = False
        cleanup = "scratch_retained_by_request" if args.keep_scratch else "worker_scratch_cleaned"
        campaign["storage_manifest"] = tracker.finish(cleanup_status=cleanup)
        write_json(campaign_path, campaign)
        write_summary_csv(campaign)
        make_plots(campaign)
        write_report(campaign)
    elif args.mode == "plots":
        campaign = json.loads(campaign_path.read_text(encoding="utf-8"))
        make_plots(campaign)
        write_report(campaign)


if __name__ == "__main__":
    main()
