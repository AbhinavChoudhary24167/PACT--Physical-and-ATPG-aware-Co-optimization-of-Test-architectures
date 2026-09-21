#!/usr/bin/env python3
"""Run/resume and report the frozen PACT Optimizer-v1 experiment."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import time
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pact.phase0d.campaign import atomic_write_json, file_sha256  # noqa: E402
from pact.phase0d.funnel import FrozenProxyContext, proxy_objectives  # noqa: E402
from pact.phase0d.optimizer_v1 import (  # noqa: E402
    Bounds2D,
    CONSTRUCTION_SPECS,
    LNS_DESTROY_OPERATORS,
    LNS_REPAIR_STRATEGIES,
    ParetoArchive2D,
    PhysicalCostModel,
    TargetCompatibility,
    candidate_features,
    construct_architecture,
    dominates2,
    freeze_bounds2,
    lns_candidate,
    nondominated2,
)
from pact.phase0d.search import Evaluation  # noqa: E402
from pact.scan.model import ScanArchitecture  # noqa: E402


CONTRACT_PATH = ROOT / "config/phase0d_optimizer_v1_contract.json"
DEFAULT_ARTIFACT_ROOT = ROOT / "artifacts/derived/phase0d/optimizer_v1/s5378/s11/k2"
REPORT_ROOT = ROOT / "reports/phase0d/optimizer_v1"
ROUTE_ROOT = ROOT / "artifacts/raw/phase0d/optimizer_v1/s5378/s11/k2"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def stable_sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path).replace("\\", "/")


def source_hashes() -> dict[str, str]:
    paths = [
        CONTRACT_PATH,
        ROOT / "scripts/phase0d_optimizer_v1.py",
        ROOT / "src/pact/phase0d/optimizer_v1.py",
        ROOT / "src/pact/phase0d/funnel.py",
        ROOT / "src/pact/analysis/phase0c_activity.py",
        ROOT / "src/pact/physical/phase0c_scan_geometry.py",
        ROOT / "src/pact/physical/phase0c_port_policy.py",
        ROOT / "src/pact/scan/phase0d_operators.py",
    ]
    return {relative(path): file_sha256(path) for path in paths}


def portfolio_entry(row: Mapping[str, Any]) -> dict[str, Any]:
    method = str(row.get("method") or Path(str(row["architecture_path"])).name.split(".")[0])
    return {
        "architecture_sha256": row["architecture_sha256"],
        "objectives": list(proxy_objectives(dict(row))),
        "source_kind": "phase0c_reference",
        "source_name": method,
        "architecture_path": row["architecture_path"],
        "metrics": {
            "H_eff16": row["activity"]["grids"]["16"]["H_eff"],
            "H_eff32": row["activity"]["grids"]["32"]["H_eff"],
            "total_shift_toggles": row["activity"]["total_shift_toggles"],
            "peak_simultaneous_toggles": row["activity"]["peak_simultaneous_toggles"],
            "normalized_chain_imbalance": row["chain_statistics"]["normalized_imbalance"],
            "parallel_shift_cycles": row["chain_statistics"]["parallel_shift_cycles"],
        },
    }


class ExactEvaluator:
    """Reuse qualified Phase-0C rows by hash, otherwise call the exact funnel."""

    def __init__(self, context: FrozenProxyContext, artifact_root: Path) -> None:
        self.context = context
        self.artifact_root = artifact_root / "candidates"
        self.portfolio = {row["architecture_sha256"]: row for row in context.portfolio_rows}

    def evaluate(self, architecture: ScanArchitecture, move: Mapping[str, Any]) -> Evaluation:
        sha = architecture.sha256()
        if sha in self.portfolio:
            row = self.portfolio[sha]
            return Evaluation(proxy_objectives(row), {
                "status": "REUSED_VERIFIED",
                "reuse_source": "qualified_phase0c_proxy",
                "architecture_path": row["architecture_path"],
                "evaluation_wall_seconds": 0.0,
                "H_eff16": row["activity"]["grids"]["16"]["H_eff"],
                "H_eff32": row["activity"]["grids"]["32"]["H_eff"],
                "total_shift_toggles": row["activity"]["total_shift_toggles"],
                "peak_simultaneous_toggles": row["activity"]["peak_simultaneous_toggles"],
                "normalized_chain_imbalance": row["chain_statistics"]["normalized_imbalance"],
                "parallel_shift_cycles": row["chain_statistics"]["parallel_shift_cycles"],
            })
        evaluated = self.context.evaluate(architecture, dict(move), self.artifact_root)
        lengths = [len(chain.cells) for chain in architecture.chains]
        mean_length = sum(lengths) / len(lengths)
        return Evaluation(evaluated.objectives, {
            **dict(evaluated.metadata),
            "architecture_path": f"{evaluated.metadata['candidate_directory']}/architecture.json",
            "normalized_chain_imbalance": (max(lengths) - min(lengths)) / mean_length,
            "parallel_shift_cycles": evaluated.objectives[2],
        })


def initial_state(
    context: FrozenProxyContext,
    contract_sha256: str,
    implementation_hashes: Mapping[str, str],
    budget_seconds: float,
) -> dict[str, Any]:
    references = [portfolio_entry(row) for row in context.portfolio_rows]
    bounds = freeze_bounds2(row["objectives"][:2] for row in references)
    archive = ParetoArchive2D(references)
    return {
        "schema_version": "pact-optimizer-v1-state-1",
        "status": "RUNNING",
        "context": context.context_id,
        "contract_sha256": contract_sha256,
        "implementation_sha256": dict(implementation_hashes),
        "run_signature": stable_sha([context.context_id, contract_sha256, implementation_hashes]),
        "started_utc": utc_now(),
        "completed_utc": None,
        "budget_seconds": budget_seconds,
        "search_wall_seconds": 0.0,
        "process_invocations": [],
        "reference_entries": references,
        "bounds": {"ideal": list(bounds.ideal), "reference": list(bounds.reference)},
        "archive": archive.entries,
        "global_completed_methods": [],
        "lanes": [],
        "lns_iterations_attempted": 0,
        "counters": {
            "candidates_proposed": 0,
            "unique_candidates": 0,
            "unique_exact_proxy_evaluations": 0,
            "executed_new_exact_proxy_evaluations": 0,
            "cache_hits": 0,
            "duplicate_candidates": 0,
            "invalid_candidates": 0,
            "accepted_lane_moves": 0,
        },
        "candidate_records": [],
        "checkpoints": [],
        "stop_reason": None,
    }


def _bounds(state: Mapping[str, Any]) -> Bounds2D:
    return Bounds2D(tuple(state["bounds"]["ideal"]), tuple(state["bounds"]["reference"]))


def _archive(state: Mapping[str, Any]) -> ParetoArchive2D:
    return ParetoArchive2D(state["archive"])


def _architecture(path: str) -> ScanArchitecture:
    candidate = Path(path)
    return ScanArchitecture.from_json(candidate if candidate.is_absolute() else ROOT / candidate)


def _snapshot(state: dict[str, Any], target: float) -> dict[str, Any]:
    archive = _archive(state)
    bounds = _bounds(state)
    return {
        "target_seconds": target,
        "observed_search_wall_seconds": state["search_wall_seconds"],
        **state["counters"],
        "archive_size": len(archive.entries),
        "best_physical_proxy_um": min(row["objectives"][0] for row in archive.entries),
        "best_H_eff8": min(row["objectives"][1] for row in archive.entries),
        "normalized_hypervolume": archive.hypervolume(bounds),
    }


def _capture_checkpoints(state: dict[str, Any], targets: list[float], *, final: bool = False) -> None:
    captured = {row["target_seconds"] for row in state["checkpoints"]}
    for target in targets:
        if target not in captured and (state["search_wall_seconds"] >= target or final):
            state["checkpoints"].append(_snapshot(state, target))


def _save_state(path: Path, state: dict[str, Any]) -> None:
    state["archive"] = _archive(state).entries
    atomic_write_json(path, state)


def _existing_record(state: Mapping[str, Any], sha: str) -> dict[str, Any] | None:
    return next((row for row in state["candidate_records"] if row["architecture_sha256"] == sha), None)


def _record_candidate(
    state: dict[str, Any],
    architecture: ScanArchitecture,
    evaluation: Evaluation,
    physical: PhysicalCostModel,
    activity: TargetCompatibility,
    move: Mapping[str, Any],
    source_kind: str,
    source_name: str,
    parent_record: Mapping[str, Any] | None,
) -> dict[str, Any]:
    archive = _archive(state)
    bounds = _bounds(state)
    old_hv = archive.hypervolume(bounds)
    metadata = dict(evaluation.metadata)
    record = {
        "evaluation_index": len(state["candidate_records"]) + 1,
        "architecture_sha256": architecture.sha256(),
        "architecture_path": metadata["architecture_path"],
        "source_kind": source_kind,
        "source_name": source_name,
        "parent_sha256": parent_record.get("architecture_sha256") if parent_record else None,
        "parent_objectives": parent_record.get("objectives") if parent_record else None,
        "objectives": list(evaluation.objectives),
        "metrics": {
            "H_eff16": metadata["H_eff16"],
            "H_eff32": metadata["H_eff32"],
            "total_shift_toggles": metadata["total_shift_toggles"],
            "peak_simultaneous_toggles": metadata["peak_simultaneous_toggles"],
            "normalized_chain_imbalance": metadata["normalized_chain_imbalance"],
            "parallel_shift_cycles": metadata["parallel_shift_cycles"],
        },
        "evaluation_status": metadata["status"],
        "evaluation_wall_seconds": float(metadata.get("evaluation_wall_seconds", 0.0)),
        "move": dict(move),
        "features": candidate_features(architecture, physical, activity, move),
        "labels": {
            "delta_physical_proxy_um": (
                evaluation.objectives[0] - float(parent_record["objectives"][0]) if parent_record else None
            ),
            "delta_H_eff8": (
                evaluation.objectives[1] - float(parent_record["objectives"][1]) if parent_record else None
            ),
            "pareto_acceptance": False,
            "routed_qualification": None,
        },
        "search_wall_seconds": state["search_wall_seconds"],
    }
    changed = archive.insert(record)
    record["labels"]["pareto_acceptance"] = changed
    state["archive"] = archive.entries
    record["hypervolume_before"] = old_hv
    record["hypervolume_after"] = archive.hypervolume(bounds)
    state["candidate_records"].append(record)
    counters = state["counters"]
    counters["unique_candidates"] += 1
    counters["unique_exact_proxy_evaluations"] += 1
    if metadata["status"] == "EXECUTED_NEW":
        counters["executed_new_exact_proxy_evaluations"] += 1
    else:
        counters["cache_hits"] += 1
    return record


def _evaluate_proposal(
    state: dict[str, Any],
    architecture: ScanArchitecture,
    evaluator: ExactEvaluator,
    physical: PhysicalCostModel,
    activity: TargetCompatibility,
    move: Mapping[str, Any],
    source_kind: str,
    source_name: str,
    parent_record: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], bool]:
    state["counters"]["candidates_proposed"] += 1
    existing = _existing_record(state, architecture.sha256())
    if existing is not None:
        state["counters"]["duplicate_candidates"] += 1
        return existing, False
    evaluation = evaluator.evaluate(architecture, move)
    record = _record_candidate(
        state, architecture, evaluation, physical, activity, move,
        source_kind, source_name, parent_record,
    )
    return record, True


def _lane_accept(
    current: Mapping[str, Any], candidate: Mapping[str, Any], alpha: float, bounds: Bounds2D,
) -> bool:
    current_point = current["objectives"][:2]
    candidate_point = candidate["objectives"][:2]
    if dominates2(candidate_point, current_point):
        return True
    old = bounds.normalize(current_point)
    new = bounds.normalize(candidate_point)
    return alpha * new[0] + (1.0 - alpha) * new[1] <= alpha * old[0] + (1.0 - alpha) * old[1]


def run_optimizer(
    context: FrozenProxyContext,
    artifact_root: Path,
    budget_seconds: float,
    checkpoint_targets: list[float],
) -> dict[str, Any]:
    artifact_root.mkdir(parents=True, exist_ok=True)
    state_path = artifact_root / "optimizer_state.json"
    contract_sha = file_sha256(CONTRACT_PATH)
    hashes = source_hashes()
    run_signature = stable_sha([context.context_id, contract_sha, hashes])
    if state_path.is_file():
        state = read_json(state_path)
        if state.get("run_signature") != run_signature or state.get("budget_seconds") != budget_seconds:
            raise ValueError("Existing optimizer state has different frozen inputs or budget")
        if state.get("status") == "COMPLETE":
            return state
    else:
        state = initial_state(context, contract_sha, hashes, budget_seconds)

    context.input_sha256 = {**context.start_proxy.get("input_sha256", {}), **hashes}
    evaluator = ExactEvaluator(context, artifact_root)
    physical = PhysicalCostModel.from_architecture(context.start_architecture, context.frozen_def)
    activity = TargetCompatibility(context.patterns, context.weights)
    prior_wall = float(state["search_wall_seconds"])
    invocation_started = time.monotonic()

    def update_time() -> None:
        state["search_wall_seconds"] = prior_wall + (time.monotonic() - invocation_started)

    def persist() -> None:
        update_time()
        _capture_checkpoints(state, checkpoint_targets)
        _save_state(state_path, state)

    for method, alpha, regret in CONSTRUCTION_SPECS:
        if method in state["global_completed_methods"]:
            continue
        update_time()
        if state["search_wall_seconds"] >= budget_seconds:
            break
        architecture = construct_architecture(
            context.start_architecture, physical, activity, alpha, regret=regret,
        )
        move = {
            "schema_version": "pact-optimizer-v1-construction-1",
            "type": "global_construction",
            "construction_method": method,
            "physical_weight": alpha,
            "activity_weight": 1.0 - alpha,
            "insertion": "regret" if regret else "cheapest",
            "origin": "empty_balanced_chains",
            "activity_ranking_metric": "static_direct_sink_weighted_target_compatibility_not_H_eff8",
        }
        record, _ = _evaluate_proposal(
            state, architecture, evaluator, physical, activity, move,
            "global_construction", method, None,
        )
        update_time()
        record["search_wall_seconds"] = state["search_wall_seconds"]
        state["lanes"].append({
            "name": method,
            "alpha": alpha,
            "current_sha256": record["architecture_sha256"],
            "current_architecture_path": record["architecture_path"],
            "current_objectives": record["objectives"],
            "trajectory": [record["architecture_sha256"]],
        })
        state["global_completed_methods"].append(method)
        persist()

    fractions = [0.05, 0.10, 0.20]
    strategies = [row[0] for row in LNS_REPAIR_STRATEGIES]
    while state["lanes"]:
        update_time()
        if state["search_wall_seconds"] >= budget_seconds:
            break
        iteration = int(state["lns_iterations_attempted"])
        lane_index = iteration % len(state["lanes"])
        lane = state["lanes"][lane_index]
        operator = LNS_DESTROY_OPERATORS[(iteration // len(state["lanes"])) % len(LNS_DESTROY_OPERATORS)]
        fraction = fractions[(iteration // (len(state["lanes"]) * len(LNS_DESTROY_OPERATORS))) % len(fractions)]
        strategy = strategies[(iteration // (len(state["lanes"]) * len(LNS_DESTROY_OPERATORS) * len(fractions))) % len(strategies)]
        state["lns_iterations_attempted"] += 1
        try:
            parent_architecture = _architecture(lane["current_architecture_path"])
            child, move = lns_candidate(
                parent_architecture, physical, activity,
                operator=operator, fraction=fraction, repair_strategy=strategy,
                iteration=iteration, seed=20260921,
            )
            parent_record = {
                "architecture_sha256": lane["current_sha256"],
                "objectives": lane["current_objectives"],
            }
            record, evaluated = _evaluate_proposal(
                state, child, evaluator, physical, activity, move,
                "lns", f"{operator}+{strategy}", parent_record,
            )
            update_time()
            record["search_wall_seconds"] = state["search_wall_seconds"]
            if evaluated:
                exact_delta = record["objectives"][0] - lane["current_objectives"][0]
                if not math.isclose(
                    exact_delta, float(move["incremental_physical_delta_um"]), abs_tol=1e-6,
                ):
                    raise AssertionError("Incremental physical delta disagrees with exact proxy")
            if _lane_accept(parent_record, record, float(lane["alpha"]), _bounds(state)):
                lane["current_sha256"] = record["architecture_sha256"]
                lane["current_architecture_path"] = record["architecture_path"]
                lane["current_objectives"] = record["objectives"]
                lane["trajectory"].append(record["architecture_sha256"])
                state["counters"]["accepted_lane_moves"] += 1
        except (ValueError, AssertionError, IndexError) as error:
            state["counters"]["invalid_candidates"] += 1
            state.setdefault("invalid_records", []).append({
                "iteration": iteration, "operator": operator, "fraction": fraction,
                "repair_strategy": strategy, "reason": str(error),
            })
        persist()

    update_time()
    state["status"] = "COMPLETE"
    state["stop_reason"] = "SEARCH_WALL_CLOCK_BUDGET_REACHED"
    state["completed_utc"] = utc_now()
    state["process_invocations"].append({
        "completed_utc": state["completed_utc"],
        "search_wall_seconds_before": prior_wall,
        "search_wall_seconds_after": state["search_wall_seconds"],
        "invocation_search_wall_seconds": time.monotonic() - invocation_started,
    })
    _capture_checkpoints(state, checkpoint_targets, final=True)
    _save_state(state_path, state)
    return state


def new_front_entries(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    reference_hashes = {row["architecture_sha256"] for row in state["reference_entries"]}
    combined = nondominated2(
        list(state["reference_entries"]) + list(state["candidate_records"]),
        key=lambda row: row["objectives"][:2],
    )
    return sorted(
        [row for row in combined if row["architecture_sha256"] not in reference_hashes],
        key=lambda row: (row["objectives"][0], row["objectives"][1], row["architecture_sha256"]),
    )


def select_route_candidates(state: Mapping[str, Any], limit: int = 2) -> list[dict[str, Any]]:
    candidates = new_front_entries(state)
    if not candidates:
        return []
    bounds = _bounds(state)
    balanced = min(candidates, key=lambda row: (
        sum(bounds.normalize(row["objectives"][:2])), row["architecture_sha256"]
    ))
    selected = [balanced]
    activity_extreme = min(candidates, key=lambda row: (row["objectives"][1], row["objectives"][0]))
    if activity_extreme["architecture_sha256"] != balanced["architecture_sha256"] and limit > 1:
        selected.append(activity_extreme)
    return selected[:limit]


def _correlation(state: Mapping[str, Any]) -> dict[str, Any]:
    pairs = []
    for row in state["candidate_records"]:
        if row["source_kind"] != "lns" or row["parent_objectives"] is None:
            continue
        move = row["move"]
        heuristic_delta = float(move["activity_heuristic_child"]) - float(move["activity_heuristic_parent"])
        exact_delta = float(row["labels"]["delta_H_eff8"])
        pairs.append((heuristic_delta, exact_delta))
    if len(pairs) < 2:
        return {"sample_count": len(pairs), "pearson_r": None}
    xs, ys = zip(*pairs)
    mean_x, mean_y = statistics.mean(xs), statistics.mean(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
    denom = math.sqrt(sum((x - mean_x) ** 2 for x in xs) * sum((y - mean_y) ** 2 for y in ys))
    return {"sample_count": len(pairs), "pearson_r": numerator / denom if denom else None}


def route_results(selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for row in selected:
        path = ROUTE_ROOT / row["architecture_sha256"] / "route_result.json"
        if path.is_file():
            results.append({"path": relative(path), **read_json(path)})
    return results


def write_metrics(state: Mapping[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "evaluation_index", "search_wall_seconds", "source_kind", "source_name",
        "architecture_sha256", "parent_sha256", "physical_proxy_um", "H_eff8",
        "H_eff16", "H_eff32", "parallel_shift_cycles", "total_shift_toggles",
        "peak_simultaneous_toggles", "evaluation_status", "evaluation_wall_seconds",
        "pareto_acceptance", "hypervolume_after", "move_type", "neighborhood_fraction",
    ]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in state["candidate_records"]:
            writer.writerow({
                "evaluation_index": row["evaluation_index"],
                "search_wall_seconds": row["search_wall_seconds"],
                "source_kind": row["source_kind"], "source_name": row["source_name"],
                "architecture_sha256": row["architecture_sha256"], "parent_sha256": row["parent_sha256"],
                "physical_proxy_um": row["objectives"][0], "H_eff8": row["objectives"][1],
                "H_eff16": row["metrics"]["H_eff16"], "H_eff32": row["metrics"]["H_eff32"],
                "parallel_shift_cycles": row["metrics"]["parallel_shift_cycles"],
                "total_shift_toggles": row["metrics"]["total_shift_toggles"],
                "peak_simultaneous_toggles": row["metrics"]["peak_simultaneous_toggles"],
                "evaluation_status": row["evaluation_status"],
                "evaluation_wall_seconds": row["evaluation_wall_seconds"],
                "pareto_acceptance": row["labels"]["pareto_acceptance"],
                "hypervolume_after": row["hypervolume_after"],
                "move_type": row["move"]["type"],
                "neighborhood_fraction": row["move"].get("neighborhood_fraction", 1.0),
            })


def make_figures(state: Mapping[str, Any], report_root: Path) -> list[Path]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure_root = report_root / "figures"
    figure_root.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    plt.rcParams.update({"font.size": 8.5, "axes.grid": True, "grid.alpha": 0.22})

    def save(name: str) -> None:
        target = figure_root / name
        plt.tight_layout()
        plt.savefig(target, dpi=165, metadata={"Software": "PACT Optimizer v1"})
        plt.close()
        outputs.append(target)

    references = state["reference_entries"]
    candidates = state["candidate_records"]
    new_front = new_front_entries(state)
    fig, ax = plt.subplots(figsize=(7.4, 4.7))
    ax.scatter([r["objectives"][0] for r in references], [r["objectives"][1] for r in references],
               marker="s", label="Phase-0C reference", color="#4c78a8")
    ax.scatter([r["objectives"][0] for r in candidates], [r["objectives"][1] for r in candidates],
               alpha=.65, label="PACT generated", color="#f28e2b")
    if new_front:
        ax.scatter([r["objectives"][0] for r in new_front], [r["objectives"][1] for r in new_front],
                   s=70, facecolors="none", edgecolors="#d62728", label="new combined-front point")
    ax.set(xlabel="Port-aware scan HPWL proxy (µm)", ylabel="Exact H_eff8",
           title="Phase-0C reference versus PACT Optimizer v1")
    ax.legend()
    save("01_reference_vs_pact_front.png")

    checkpoints = state["checkpoints"]
    fig, ax = plt.subplots(figsize=(7.4, 4.3))
    ax.step([r["observed_search_wall_seconds"] for r in checkpoints],
            [r["archive_size"] for r in checkpoints], where="post")
    ax.set(xlabel="Search wall time (s)", ylabel="Combined archive size", title="Pareto archive evolution")
    save("02_archive_evolution.png")

    fig, ax = plt.subplots(figsize=(7.4, 4.3))
    times = [0.0] + [r["search_wall_seconds"] for r in candidates]
    hv = [ParetoArchive2D(references).hypervolume(_bounds(state))] + [r["hypervolume_after"] for r in candidates]
    ax.step(times, hv, where="post")
    ax.set(xlabel="Search wall time (s)", ylabel="Normalized 2-D hypervolume", title="Hypervolume versus wall time")
    save("03_hypervolume_vs_time.png")

    fig, ax = plt.subplots(figsize=(7.4, 4.7))
    for source, color in (("global_construction", "#59a14f"), ("lns", "#e15759")):
        rows = [r for r in candidates if r["source_kind"] == source]
        ax.scatter([r["objectives"][0] for r in rows], [r["objectives"][1] for r in rows],
                   label=source.replace("_", " "), alpha=.7, color=color)
    ax.set(xlabel="Port-aware scan HPWL proxy (µm)", ylabel="Exact H_eff8",
           title="Exact outcomes by generation source")
    ax.legend()
    save("04_candidates_by_source.png")

    counters = state["counters"]
    fig, ax = plt.subplots(figsize=(7.4, 4.3))
    labels = ["proposed", "unique exact", "archive accepted", "new combined front"]
    values = [counters["candidates_proposed"], counters["unique_exact_proxy_evaluations"],
              sum(r["labels"]["pareto_acceptance"] for r in candidates), len(new_front)]
    ax.bar(labels, values, color=["#4c78a8", "#72b7b2", "#f28e2b", "#e15759"])
    ax.set(ylabel="Architectures", title="Candidate funnel")
    save("05_candidate_funnel.png")

    contributions: dict[str, int] = {}
    for row in candidates:
        if row["source_kind"] == "lns" and row["labels"]["pareto_acceptance"]:
            name = row["source_name"].split("+")[0]
            contributions[name] = contributions.get(name, 0) + 1
    fig, ax = plt.subplots(figsize=(7.4, 4.3))
    names = list(LNS_DESTROY_OPERATORS)
    ax.bar(names, [contributions.get(name, 0) for name in names], color="#b07aa1")
    ax.set(ylabel="Archive-changing exact candidates", title="Destroy/repair operator contribution")
    save("06_operator_contribution.png")

    fig, ax = plt.subplots(figsize=(7.4, 4.3))
    ax.plot([r["observed_search_wall_seconds"] for r in checkpoints],
            [r["unique_candidates"] for r in checkpoints], marker="o", label="unique candidates")
    ax.plot([r["observed_search_wall_seconds"] for r in checkpoints],
            [r["duplicate_candidates"] for r in checkpoints], marker="s", label="duplicates")
    ax.plot([r["observed_search_wall_seconds"] for r in checkpoints],
            [r["cache_hits"] for r in checkpoints], marker="^", label="verified cache hits")
    ax.set(xlabel="Search wall time (s)", ylabel="Count", title="Unique generation and reuse")
    ax.legend()
    save("07_unique_duplicate_cache.png")
    return outputs


def finalize(state: dict[str, Any], artifact_root: Path, process_invocation_seconds: float) -> dict[str, Any]:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    metrics_path = REPORT_ROOT / "optimizer_v1_metrics.csv"
    write_metrics(state, metrics_path)
    figures = make_figures(state, REPORT_ROOT)
    new_front = new_front_entries(state)
    selected = select_route_candidates(state, 2)
    routes = route_results(selected)
    status = "PACT_OPTIMIZER_V1_PROXY_ADVANCE" if new_front else "PACT_OPTIMIZER_V1_PROXY_NO_ADVANCE"
    route_status = (
        "PACT_OPTIMIZER_V1_ROUTE_QUALIFIED"
        if routes and all(row.get("status") == "QUALIFIED" for row in routes) and len(routes) == len(selected)
        else "ROUTE_NOT_PERFORMED" if not routes else "ROUTE_NOT_QUALIFIED"
    )
    reference_front = ParetoArchive2D(state["reference_entries"]).entries
    accumulated_proxy = sum(
        float(row["evaluation_wall_seconds"]) for row in state["candidate_records"]
        if row["evaluation_status"] == "EXECUTED_NEW"
    )
    route_seconds = sum(float(row.get("route_wall_seconds") or 0.0) for row in routes)
    correlation = _correlation(state)
    summary = {
        "schema_version": "pact-optimizer-v1-status-1",
        "status": status,
        "route_status": route_status,
        "context": state["context"],
        "contract_sha256": state["contract_sha256"],
        "run_signature": state["run_signature"],
        "counters": state["counters"],
        "runtime": {
            "process_invocation_wall_seconds": process_invocation_seconds,
            "search_wall_clock_seconds": state["search_wall_seconds"],
            "accumulated_new_proxy_wall_seconds": accumulated_proxy,
            "route_wall_seconds": route_seconds,
            "total_campaign_elapsed_seconds": process_invocation_seconds + route_seconds,
            "historical_pilot_erratum": (
                "pilot STATUS elapsed measured its current/finalization invocation; summed proxy wall time "
                "measured cached work created across earlier invocations. Neither historical value was rewritten."
            ),
        },
        "phase0c_reference_front": reference_front,
        "new_pact_front": new_front,
        "new_nondominated_point_found": bool(new_front),
        "activity_heuristic_validation": correlation,
        "selected_route_candidates": selected,
        "route_results": routes,
        "checkpoints": state["checkpoints"],
        "phase0c_status_preserved": "PACT_PHASE0C_LEARNING_GATE_FAIL",
        "phase0d_pilot_status_preserved": "PILOT_COMPLETE_NO_ROUTE_QUALIFIED",
    }
    atomic_write_json(REPORT_ROOT / "optimizer_v1_status.json", summary)
    atomic_write_json(REPORT_ROOT / "route_shortlist.json", {
        "status": "SELECTED" if selected else "EMPTY_NO_PROXY_ADVANCE",
        "selection_rule": "balanced normalized compromise, then activity extreme; maximum two",
        "candidates": selected,
    })

    method = f"""# PACT Optimizer v1 Method

## Fixed context and objectives

The frozen development context is `s5378 / seed11 / K2`. All six qualified
Phase-0C proxy rows were discovered from the context directory and reused by
verified architecture/input hashes. Placement, ATPG patterns, FF identity, K,
and SI/SO identities remain fixed.

For fixed K the primary minimization archive is exactly:

1. the qualified port-aware FF-origin scan HPWL proxy; and
2. exact H_eff8 from the existing no-capture, fully clocked parallel-shift model.

Exact H_eff16/H_eff32, total and peak toggles, chain imbalance, and shift cycles
are reported only. Equal final capacities keep exact shift cycles constant.

## Construction and activity relation

Five chains-from-scratch starts use physical weights 1.0, 0.8, 0.5, 0.2, and
0.0. Endpoint-aware Manhattan insertion uses the identical additive terms as
the Phase-0C proxy. The balanced 0.5 start uses regret insertion; the others use
cheapest insertion. Every final candidate receives exact structural and ATPG
reconstruction proof before metric evaluation.

H_eff8 is a maximum over cycle-aligned, spatially convolved,
direct-sink-weighted toggle fields, so it is not an independent pairwise-edge
sum. Construction therefore uses a labeled heuristic: for directed adjacency
`i -> j`, static target compatibility is the fraction of frozen ATPG targets
where bits i and j differ, multiplied by j's direct-sink weight normalized by
the mean weight. This score is never reported as H_eff8. Final candidates are
always evaluated by exact H_eff8. On the evaluated LNS sample, heuristic delta
versus exact H_eff8 delta has Pearson r={correlation['pearson_r']} over
{correlation['sample_count']} points; this is validation evidence, not an
identity claim.

## Large-neighborhood refinement

Deterministic LNS removes 5%, 10%, or 20% of FFs using spatial-region,
activity-hotspot, contiguous-segment, cross-chain-segment, or seeded guided
destroy. Repair uses physical-best, activity-best, balanced, or regret
insertion while restoring exact capacities. Five weighted lanes retain moves
that dominate their current point or improve their lane-normalized scalar.
Every unique repaired architecture receives exact proxy evaluation and is
offered to the combined Phase-0C plus PACT two-objective archive.

## Exact incremental physical evaluation and complexity

The Manhattan proxy decomposes into chain-local SI/FF, FF/FF, and FF/SO edges.
Replacement delta is computed only for changed chains and is asserted against
the full qualified proxy after every new LNS evaluation (absolute tolerance
1e-6 µm). Exact H_eff is not incrementally substituted.

Construction uses no dense FF-pair matrix: relations are computed on demand.
Cheapest/regret insertion is O(N^3) worst-case time and O(N) working memory in
this v1 research implementation. Each LNS proposal removes qN FFs and repairs
in O(qN^2) worst-case time with O(N) state; exact activity evaluation retains
the existing streamed pattern/cycle implementation. The lack of a sparse
activity-neighbor index is a known scale limitation, so no 100K-FF scalability
claim is made.

## Runtime and reuse

Search uses a resumable {state['budget_seconds']:.0f}-second cumulative monotonic
wall-clock budget with checkpoints at 5/10/20/30/60 seconds. Process invocation,
search wall time, accumulated new-proxy time, route time, and total campaign time
are distinct fields. No OpenROAD command runs inside construction or LNS.
"""
    (REPORT_ROOT / "OPTIMIZER_V1_METHOD.md").write_text(method, encoding="utf-8", newline="\n")

    def table(rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "| none | — | — |\n"
        return "\n".join(
            f"| {row['source_name']} | `{row['architecture_sha256'][:12]}` | "
            f"{row['objectives'][0]:.6f} | {row['objectives'][1]:.6f} |"
            for row in rows
        )

    report = f"""# PACT Optimizer v1 Report

**Decision:** `{status}`

**Routed decision:** `{route_status}`

**Frozen prior decisions:** `PACT_PHASE0C_LEARNING_GATE_FAIL` and
`PILOT_COMPLETE_NO_ROUTE_QUALIFIED`

## Result

The bounded s5378/seed11/K2 experiment proposed
{state['counters']['candidates_proposed']} architectures and performed
{state['counters']['unique_exact_proxy_evaluations']} unique exact proxy
evaluations, including {state['counters']['cache_hits']} verified cache reuses.
Search wall time was {state['search_wall_seconds']:.6f} seconds; accumulated new
proxy computation was {accumulated_proxy:.6f} seconds.

### Reused Phase-0C proxy Pareto front

| Method | Architecture | HPWL proxy (µm) | Exact H_eff8 |
|---|---|---:|---:|
{table(reference_front)}

### New PACT points on the combined proxy Pareto front

| Source | Architecture | HPWL proxy (µm) | Exact H_eff8 |
|---|---|---:|---:|
{table(new_front)}

New nondominated point found: **{'yes' if new_front else 'no'}**.

## Runtime accounting erratum

The completed pilot is not rewritten. Its STATUS elapsed field measured the
current/finalization process invocation, while its summed proxy times measured
unique cached artifacts created across earlier invocations. Optimizer v1 records
process invocation ({process_invocation_seconds:.6f} s), cumulative search wall
time ({state['search_wall_seconds']:.6f} s), accumulated new-proxy computation
({accumulated_proxy:.6f} s), and route time ({route_seconds:.6f} s) separately.

## Selective routing

Selected candidates: {len(selected)}. Observed route results: {len(routes)}.
No Phase-0C route was rerun. Routing is skipped when the new combined-front set
is empty; otherwise only the balanced representative and optional activity
extreme are eligible.

## Interpretation and next step

{'The optimizer extended the reused proxy front. The scientifically justified next step is selective route qualification of the saved shortlist, without scaling the campaign.' if new_front else 'The optimizer did not extend the reused proxy front. The scientifically justified next step is to inspect constructor sensitivity, activity-relation correlation, duplicate generation, and LNS archive evolution before changing the algorithm; do not scale to another design.'}

ML was not introduced.
"""
    (REPORT_ROOT / "OPTIMIZER_V1_REPORT.md").write_text(report, encoding="utf-8", newline="\n")
    status_md = f"""# PACT Optimizer v1 Status

- Status: `{status}`
- Routed status: `{route_status}`
- Context: `{state['context']}`
- Proposed architectures: {state['counters']['candidates_proposed']}
- Unique exact proxy evaluations: {state['counters']['unique_exact_proxy_evaluations']}
- Verified cache hits: {state['counters']['cache_hits']}
- Search wall time: {state['search_wall_seconds']:.6f} s
- New combined-front points: {len(new_front)}
- Phase-0C: `PACT_PHASE0C_LEARNING_GATE_FAIL` (preserved)
- Phase-0D pilot: `PILOT_COMPLETE_NO_ROUTE_QUALIFIED` (preserved)
"""
    (REPORT_ROOT / "OPTIMIZER_V1_STATUS.md").write_text(status_md, encoding="utf-8", newline="\n")

    outputs = [
        artifact_root / "optimizer_state.json", metrics_path,
        REPORT_ROOT / "optimizer_v1_status.json", REPORT_ROOT / "route_shortlist.json",
        REPORT_ROOT / "OPTIMIZER_V1_METHOD.md", REPORT_ROOT / "OPTIMIZER_V1_REPORT.md",
        REPORT_ROOT / "OPTIMIZER_V1_STATUS.md", *figures,
    ]
    manifest = {
        "schema_version": "pact-optimizer-v1-manifest-1",
        "status": status,
        "contract_sha256": state["contract_sha256"],
        "run_signature": state["run_signature"],
        "inputs": state["implementation_sha256"],
        "artifacts": [
            {"path": relative(path), "sha256": file_sha256(path), "bytes": path.stat().st_size}
            for path in outputs if path.is_file()
        ],
        "phase0c_reference_reuse": "REUSED_VERIFIED",
        "phase0c_routes_executed_new": 0,
        "new_optimizer_routes": len(routes),
    }
    atomic_write_json(REPORT_ROOT / "optimizer_v1_manifest.json", manifest)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--budget-seconds", type=float)
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--finalize-only", action="store_true")
    args = parser.parse_args()
    process_started = time.monotonic()
    contract = read_json(CONTRACT_PATH)
    budget = args.budget_seconds or float(contract["runtime"]["search_wall_clock_seconds"])
    targets = [float(value) for value in contract["runtime"]["checkpoint_targets_seconds"] if value <= budget]
    context = FrozenProxyContext.load(ROOT, "s5378", 11, 2, "P")
    state_path = args.artifact_root / "optimizer_state.json"
    if args.finalize_only:
        if not state_path.is_file():
            raise ValueError("No optimizer state exists to finalize")
        state = read_json(state_path)
    else:
        state = run_optimizer(context, args.artifact_root, budget, targets)
    summary = finalize(state, args.artifact_root, time.monotonic() - process_started)
    print(json.dumps({
        "status": summary["status"],
        "route_status": summary["route_status"],
        "proposed": summary["counters"]["candidates_proposed"],
        "unique_exact_proxy_evaluations": summary["counters"]["unique_exact_proxy_evaluations"],
        "cache_hits": summary["counters"]["cache_hits"],
        "search_wall_seconds": summary["runtime"]["search_wall_clock_seconds"],
        "new_front_points": len(summary["new_pact_front"]),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
