"""Independent coarse-grained Pareto search for PACT Optimizer-v2.3.

Each lane delegates one bounded epoch to the qualified v2.2 engine.  Mutable
architectures, RNG streams, proposal preferences, and seen sets remain local to
that worker.  Only immutable problem inputs and deterministically selected
archive restart points cross synchronization boundaries.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field, replace
import hashlib
import json
import math
from pathlib import Path
import time
from typing import Any, Iterable, Mapping, Sequence

from pact.experiment_storage import (
    ExperimentPaths,
    configure_experiment_storage,
    remove_owned_tree,
    worker_scratch,
)
from pact.phase0d.optimizer_v1 import PhysicalCostModel, dominates2
from pact.phase0d.optimizer_v2 import (
    ArchiveEntry,
    BoundedParetoArchive,
    OptimizerV2Config,
    OptimizerV2Result,
    _scales,
    optimize_v2,
)
from pact.phase0d.v2_architecture import ArchitectureSnapshot, MutableScanArchitecture
from pact.scan.model import ScanArchitecture


Point2D = tuple[float, float]


@dataclass(frozen=True)
class LaneProfile:
    lane_id: str
    label: str
    proposal_weights: tuple[float, ...]
    random_nonlocal_candidates: int


LANE_PROFILES = (
    LaneProfile("L0", "physical_biased", (1.0, 0.85, 0.70), 2),
    LaneProfile("L1", "balanced_physical_activity", (0.60, 0.50, 0.40), 3),
    LaneProfile("L2", "activity_biased", (0.0, 0.15, 0.30), 3),
    LaneProfile("L3", "diversity_perturbation", (0.75, 0.25, 0.50, 0.0, 1.0), 8),
)


def lane_profiles(worker_count: int) -> tuple[LaneProfile, ...]:
    if worker_count == 1:
        return (LaneProfile("L0", "serial_v2_2", (0.5,), 3),)
    if worker_count == 2:
        return (LANE_PROFILES[0], LANE_PROFILES[2])
    if worker_count == 4:
        return LANE_PROFILES
    raise ValueError("Optimizer-v2.3 qualifies exactly 1, 2, or 4 workers")


@dataclass(frozen=True)
class ParallelParetoConfig:
    worker_count: int
    budget_mode: str = "exact_evaluations"
    total_exact_evaluations: int = 64
    wall_clock_seconds: float = 30.0
    epochs: int = 2
    master_seed: int = 20260921
    parallel_backend: str = "process"
    keep_scratch: bool = False
    run_id: str = "optimizer-v2-3"

    def __post_init__(self) -> None:
        lane_profiles(self.worker_count)
        if self.budget_mode not in {"exact_evaluations", "wall_clock"}:
            raise ValueError("budget_mode must be exact_evaluations or wall_clock")
        if self.total_exact_evaluations < 1 or self.wall_clock_seconds <= 0:
            raise ValueError("Search budgets must be positive")
        if self.epochs < 1:
            raise ValueError("epochs must be positive")
        if self.parallel_backend not in {"process", "sequential"}:
            raise ValueError("parallel_backend must be process or sequential")
        if self.budget_mode == "exact_evaluations":
            jobs = self.worker_count * self.epochs
            if self.worker_count > 1 and self.total_exact_evaluations < jobs:
                raise ValueError("Exact budget must fund at least one evaluation per lane and epoch")


@dataclass(frozen=True)
class _LaneJob:
    epoch: int
    profile: LaneProfile
    seed: int
    exact_budget: int
    wall_seconds: float
    start_architecture: ScanArchitecture
    additional_starts: tuple[tuple[str, ScanArchitecture], ...] = ()


@dataclass
class _WorkerOutcome:
    epoch: int
    lane_id: str
    lane_label: str
    seed: int
    result: OptimizerV2Result | None
    process_cpu_seconds: float
    scratch_path: str
    cleanup_status: str
    error: str | None = None


@dataclass(frozen=True)
class _GlobalCandidate:
    architecture_sha256: str
    architecture_key: int
    objectives: Point2D
    source: str
    move_index: int
    epoch: int
    lane_id: str
    architecture: ScanArchitecture

    def order_key(self) -> tuple[Any, ...]:
        return (
            self.objectives[0],
            self.objectives[1],
            self.architecture_sha256,
            self.lane_id,
            self.epoch,
            self.move_index,
        )


@dataclass
class ParallelParetoResult:
    config: ParallelParetoConfig
    optimizer_config: OptimizerV2Config
    archive: list[Mapping[str, Any]]
    metrics: Mapping[str, Any]
    runtime: Mapping[str, Any]
    accounting: Mapping[str, Any]
    epochs: list[Mapping[str, Any]]
    frozen_reference: Point2D
    frozen_ideal: Point2D
    stop_reason: str
    architecture_objects: dict[str, ScanArchitecture] = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "pact-optimizer-v2-3-result-1",
            "config": asdict(self.config),
            "optimizer_config": asdict(self.optimizer_config),
            "archive": [dict(row) for row in self.archive],
            "metrics": dict(self.metrics),
            "runtime": dict(self.runtime),
            "accounting": dict(self.accounting),
            "epochs": [dict(row) for row in self.epochs],
            "frozen_reference": list(self.frozen_reference),
            "frozen_ideal": list(self.frozen_ideal),
            "stop_reason": self.stop_reason,
        }


def _lane_seed(master_seed: int, lane_id: str, epoch: int) -> int:
    digest = hashlib.sha256(f"{master_seed}:{lane_id}:{epoch}".encode("ascii")).digest()
    return int.from_bytes(digest[:8], "big") & 0x7FFF_FFFF


def _split_budget(total: int, pieces: int) -> tuple[int, ...]:
    quotient, remainder = divmod(total, pieces)
    return tuple(quotient + int(index < remainder) for index in range(pieces))


def freeze_reference(points: Iterable[Sequence[float]], margin_fraction: float = 0.25) -> tuple[Point2D, Point2D]:
    checked = [tuple(map(float, point[:2])) for point in points]
    if not checked:
        raise ValueError("Cannot freeze a reference from an empty portfolio")
    ideal = tuple(min(point[index] for point in checked) for index in range(2))
    high = tuple(max(point[index] for point in checked) for index in range(2))
    reference = tuple(
        high[index] + (
            margin_fraction * (high[index] - ideal[index])
            if high[index] > ideal[index]
            else max(abs(high[index]) * 0.10, 1.0)
        )
        for index in range(2)
    )
    return ideal, reference  # type: ignore[return-value]


def hypervolume_2d(points: Iterable[Sequence[float]], reference: Sequence[float]) -> float:
    ref_x, ref_y = map(float, reference[:2])
    values = sorted({tuple(map(float, point[:2])) for point in points})
    front = [
        point for index, point in enumerate(values)
        if point[0] < ref_x and point[1] < ref_y
        and not any(dominates2(other, point) for other_index, other in enumerate(values)
                    if other_index != index)
    ]
    area = 0.0
    best_y = ref_y
    for x, y in sorted(front):
        if y < best_y:
            area += max(0.0, ref_x - x) * (best_y - y)
            best_y = y
    return area


def _objective_spread(points: Sequence[Point2D], ideal: Point2D, reference: Point2D) -> float:
    if len(points) < 2:
        return 0.0
    normalized_ranges = []
    for index in range(2):
        span = max(reference[index] - ideal[index], 1e-12)
        normalized_ranges.append(
            (max(point[index] for point in points) - min(point[index] for point in points)) / span
        )
    return math.hypot(*normalized_ranges)


def _write_worker_record(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run_lane_job(
    job: _LaneJob,
    base: ScanArchitecture,
    patterns: Sequence[Mapping[str, int]],
    weights: Mapping[str, int],
    physical_model: PhysicalCostModel,
    optimizer_config: OptimizerV2Config,
    experiment_root_value: str,
    run_id: str,
    keep_scratch: bool,
) -> _WorkerOutcome:
    paths = configure_experiment_storage(experiment_root_value)
    scratch = worker_scratch(paths, run_id, job.profile.lane_id)
    started_cpu = time.process_time()
    _write_worker_record(scratch / "worker.json", {
        "epoch": job.epoch,
        "lane_id": job.profile.lane_id,
        "lane_label": job.profile.label,
        "seed": job.seed,
        "experiment_root": str(paths.root),
    })
    try:
        local_config = replace(
            optimizer_config,
            wall_clock_seconds=job.wall_seconds,
            maximum_exact_evaluations=job.exact_budget,
            maximum_local_moves=max(
                optimizer_config.maximum_local_moves,
                job.exact_budget * 64,
            ),
            seed=job.seed,
            constructor_lambdas=job.profile.proposal_weights,
            random_nonlocal_candidates=job.profile.random_nonlocal_candidates,
            constructor_parallel_backend="sequential",
            h_eff8_workers=1,
            generate_constructor_starts=False,
            parent_refresh_interval=0,
        )
        result = optimize_v2(
            job.start_architecture,
            patterns,
            weights,
            physical_model,
            local_config,
            seed_architectures=job.additional_starts,
            trace_limit=0,
        )
        cpu = time.process_time() - started_cpu
        cleanup = "retained_by_request" if keep_scratch else "cleaned"
        outcome = _WorkerOutcome(
            job.epoch,
            job.profile.lane_id,
            job.profile.label,
            job.seed,
            result,
            cpu,
            str(scratch),
            cleanup,
        )
        if not keep_scratch:
            remove_owned_tree(paths, scratch)
        return outcome
    except BaseException as error:  # preserve failed worker diagnostics on D:
        cpu = time.process_time() - started_cpu
        _write_worker_record(scratch / "failure.json", {
            "error_type": type(error).__name__,
            "error": str(error),
            "scratch_path": str(scratch),
        })
        return _WorkerOutcome(
            job.epoch,
            job.profile.lane_id,
            job.profile.label,
            job.seed,
            None,
            cpu,
            str(scratch),
            "preserved_after_failure",
            f"{type(error).__name__}: {error}",
        )


def _candidate_rows(outcomes: Sequence[_WorkerOutcome]) -> list[_GlobalCandidate]:
    candidates: list[_GlobalCandidate] = []
    for outcome in outcomes:
        if outcome.result is None:
            continue
        for row in outcome.result.archive:
            sha = str(row["architecture_sha256"])
            candidates.append(_GlobalCandidate(
                architecture_sha256=sha,
                architecture_key=int(str(row["architecture_key"]), 16),
                objectives=tuple(map(float, row["objectives"][:2])),  # type: ignore[arg-type]
                source=str(row["source"]),
                move_index=int(row["move_index"]),
                epoch=outcome.epoch,
                lane_id=outcome.lane_id,
                architecture=outcome.result.architecture_objects[sha],
            ))
    return candidates


def deterministic_archive_merge(
    candidates: Iterable[_GlobalCandidate],
    *,
    maximum_size: int,
    epsilon_fraction: float,
    ideal: Point2D,
    scale: Point2D,
) -> list[_GlobalCandidate]:
    """Canonical serial merge used regardless of worker completion order."""
    unique: dict[int, _GlobalCandidate] = {}
    for candidate in sorted(candidates, key=_GlobalCandidate.order_key):
        unique.setdefault(candidate.architecture_key, candidate)
    archive = BoundedParetoArchive(maximum_size, epsilon_fraction, ideal, scale)
    metadata: dict[int, _GlobalCandidate] = {}
    for candidate in sorted(unique.values(), key=_GlobalCandidate.order_key):
        mutable = MutableScanArchitecture.from_scan_architecture(candidate.architecture)
        row = ArchiveEntry(
            candidate.architecture_key,
            candidate.objectives,
            f"{candidate.lane_id}:{candidate.source}",
            candidate.move_index,
            ArchitectureSnapshot.capture(mutable),
            candidate.architecture_sha256,
        )
        archive.insert(row)
        metadata[candidate.architecture_key] = candidate
    return [metadata[row.architecture_key] for row in archive.entries]


def _restart_parents(
    archive: Sequence[_GlobalCandidate], profiles: Sequence[LaneProfile], epoch: int
) -> dict[str, ScanArchitecture]:
    if not archive:
        raise ValueError("Cannot assign parents from an empty global archive")
    physical = min(archive, key=lambda row: (row.objectives[0], row.objectives[1], row.architecture_sha256))
    activity = min(archive, key=lambda row: (row.objectives[1], row.objectives[0], row.architecture_sha256))
    ordered = sorted(archive, key=lambda row: (
        row.objectives[0], row.objectives[1], row.architecture_sha256
    ))
    protected_keys = {physical.architecture_key, activity.architecture_key}
    interior = [row for row in ordered if row.architecture_key not in protected_keys]
    if not interior:
        interior = ordered
    assignments: dict[str, ScanArchitecture] = {}
    for lane_index, profile in enumerate(profiles):
        if profile.lane_id == "L0":
            selected = physical
        elif profile.lane_id == "L2":
            selected = activity
        else:
            selected = interior[(epoch + lane_index) % len(interior)]
        assignments[profile.lane_id] = selected.architecture
    return assignments


def _portfolio(base: ScanArchitecture,
               starts: Sequence[tuple[str, ScanArchitecture]]) -> tuple[ScanArchitecture, ...]:
    result: list[ScanArchitecture] = []
    seen: set[str] = set()
    for architecture in (base, *(row[1] for row in starts)):
        sha = architecture.sha256()
        if sha not in seen:
            seen.add(sha)
            result.append(architecture)
    return tuple(result)


def _metrics(
    archive: Sequence[_GlobalCandidate],
    evaluation_keys: Sequence[str],
    exact_evaluations: int,
    ideal: Point2D,
    reference: Point2D,
) -> dict[str, Any]:
    points = [row.objectives for row in archive]
    unique_evaluations = len(set(evaluation_keys))
    return {
        "nondominated_archive_size": len(archive),
        "unique_architectures": len({row.architecture_sha256 for row in archive}),
        "best_physical": min(point[0] for point in points),
        "best_H_eff8": min(point[1] for point in points),
        "frozen_reference_hypervolume": hypervolume_2d(points, reference),
        "objective_space_spread": _objective_spread(points, ideal, reference),
        "unique_exact_evaluations": unique_evaluations,
        "duplicate_exact_evaluations": max(0, exact_evaluations - unique_evaluations),
        "duplicate_evaluation_fraction": (
            max(0, exact_evaluations - unique_evaluations) / exact_evaluations
            if exact_evaluations else 0.0
        ),
    }


def _single_worker_result(
    base: ScanArchitecture,
    patterns: Sequence[Mapping[str, int]],
    weights: Mapping[str, int],
    physical_model: PhysicalCostModel,
    optimizer_config: OptimizerV2Config,
    parallel_config: ParallelParetoConfig,
    start_portfolio: Sequence[tuple[str, ScanArchitecture]],
    ideal: Point2D,
    reference: Point2D,
) -> ParallelParetoResult:
    effective = replace(
        optimizer_config,
        maximum_exact_evaluations=(
            parallel_config.total_exact_evaluations
            if parallel_config.budget_mode == "exact_evaluations"
            else optimizer_config.maximum_exact_evaluations
        ),
        wall_clock_seconds=(
            parallel_config.wall_clock_seconds
            if parallel_config.budget_mode == "wall_clock"
            else optimizer_config.wall_clock_seconds
        ),
        seed=parallel_config.master_seed,
    )
    cpu_started = time.process_time()
    result = optimize_v2(
        base, patterns, weights, physical_model, effective,
        seed_architectures=start_portfolio, trace_limit=0,
    )
    cpu_seconds = time.process_time() - cpu_started
    candidates = []
    for row in result.archive:
        sha = str(row["architecture_sha256"])
        candidates.append(_GlobalCandidate(
            sha,
            int(str(row["architecture_key"]), 16),
            tuple(map(float, row["objectives"][:2])),  # type: ignore[arg-type]
            str(row["source"]),
            int(row["move_index"]),
            0,
            "L0",
            result.architecture_objects[sha],
        ))
    exact = int(result.counters["exact_evaluations"])
    archive_rows = [
        {
            **dict(row),
            "lane_id": "L0",
            "epoch": 0,
        }
        for row in result.archive
    ]
    wall = float(result.runtime["optimizer_wall_seconds"])
    return ParallelParetoResult(
        parallel_config,
        effective,
        archive_rows,
        _metrics(candidates, result.evaluation_keys, exact, ideal, reference),
        {
            "wall_seconds": wall,
            "process_cpu_seconds": cpu_seconds,
            "cpu_utilization_percent": 100.0 * cpu_seconds / max(wall, 1e-12),
        },
        {
            "total_exact_evaluations": exact,
            "requested_exact_evaluations": parallel_config.total_exact_evaluations,
            "local_duplicate_proposals": int(result.counters["duplicate_candidates"]),
            "evaluation_budget_exact": (
                parallel_config.budget_mode != "exact_evaluations"
                or exact == parallel_config.total_exact_evaluations
            ),
        },
        [{
            "epoch": 0,
            "lanes": [{
                "lane_id": "L0",
                "lane_label": "serial_v2_2",
                "seed": parallel_config.master_seed,
                "exact_evaluations": exact,
                "stop_reason": result.stop_reason,
            }],
        }],
        reference,
        ideal,
        result.stop_reason,
        dict(result.architecture_objects),
    )


def optimize_parallel_pareto(
    base: ScanArchitecture,
    patterns: Sequence[Mapping[str, int]],
    weights: Mapping[str, int],
    physical_model: PhysicalCostModel,
    optimizer_config: OptimizerV2Config,
    parallel_config: ParallelParetoConfig,
    *,
    start_portfolio: Sequence[tuple[str, ScanArchitecture]] = (),
    frozen_ideal: Sequence[float] | None = None,
    frozen_reference: Sequence[float] | None = None,
    storage_paths: ExperimentPaths | None = None,
) -> ParallelParetoResult:
    """Run deterministic epoch search with independent coarse-grained lanes."""
    portfolio = _portfolio(base, start_portfolio)
    if frozen_ideal is None or frozen_reference is None:
        raise ValueError("A common frozen ideal/reference is required for fair comparisons")
    ideal = tuple(map(float, frozen_ideal[:2]))
    reference = tuple(map(float, frozen_reference[:2]))
    if any(reference[index] <= ideal[index] for index in range(2)):
        raise ValueError("Frozen reference must be worse than the ideal")
    paths = storage_paths or configure_experiment_storage()
    original_sha = base.sha256()
    started = time.perf_counter()
    if parallel_config.worker_count == 1:
        answer = _single_worker_result(
            base, patterns, weights, physical_model, optimizer_config,
            parallel_config, start_portfolio, ideal, reference,
        )
        if base.sha256() != original_sha:
            raise AssertionError("Serial optimizer mutated its immutable input")
        return answer

    profiles = lane_profiles(parallel_config.worker_count)
    total_jobs = parallel_config.worker_count * parallel_config.epochs
    exact_budgets = _split_budget(parallel_config.total_exact_evaluations, total_jobs)
    if parallel_config.budget_mode == "exact_evaluations":
        initial_group_sizes = [
            len(portfolio[lane_index::len(profiles)])
            for lane_index in range(len(profiles))
        ]
        if any(
            exact_budgets[lane_index] < group_size
            for lane_index, group_size in enumerate(initial_group_sizes)
        ):
            raise ValueError(
                "Exact budget is too small to evaluate the common frozen start portfolio"
            )
    initial_points: list[Point2D] = [(ideal[0], ideal[1]), (reference[0], reference[1])]
    archive_ideal, archive_scale = _scales(initial_points)
    global_archive: list[_GlobalCandidate] = []
    evaluation_keys: list[str] = []
    epoch_rows: list[Mapping[str, Any]] = []
    total_exact = 0
    total_cpu = 0.0
    local_duplicates = 0
    restart_assignments: dict[str, ScanArchitecture] = {}
    all_success = True

    executor: ProcessPoolExecutor | None = None
    if parallel_config.parallel_backend == "process":
        executor = ProcessPoolExecutor(max_workers=parallel_config.worker_count)
    try:
        for epoch in range(parallel_config.epochs):
            elapsed = time.perf_counter() - started
            remaining_wall = max(1e-6, parallel_config.wall_clock_seconds - elapsed)
            epoch_wall = (
                remaining_wall / (parallel_config.epochs - epoch)
                if parallel_config.budget_mode == "wall_clock"
                else optimizer_config.wall_clock_seconds
            )
            jobs: list[_LaneJob] = []
            initial_groups = tuple(
                portfolio[lane_index::len(profiles)]
                for lane_index in range(len(profiles))
            )
            for lane_index, profile in enumerate(profiles):
                if epoch == 0:
                    group = initial_groups[lane_index]
                    if group:
                        start_architecture = group[0]
                        additional_starts = tuple(
                            (f"frozen_start_{lane_index}_{index}", architecture)
                            for index, architecture in enumerate(group[1:], start=1)
                        )
                    else:
                        start_architecture = portfolio[lane_index % len(portfolio)]
                        additional_starts = ()
                else:
                    start_architecture = restart_assignments[profile.lane_id]
                    additional_starts = ()
                budget = exact_budgets[epoch * len(profiles) + lane_index]
                if parallel_config.budget_mode == "wall_clock":
                    budget = optimizer_config.maximum_exact_evaluations
                jobs.append(_LaneJob(
                    epoch,
                    profile,
                    _lane_seed(parallel_config.master_seed, profile.lane_id, epoch),
                    budget,
                    epoch_wall,
                    start_architecture,
                    additional_starts,
                ))

            if executor is None:
                outcomes = [
                    _run_lane_job(
                        job, base, patterns, weights, physical_model, optimizer_config,
                        str(paths.root), parallel_config.run_id,
                        parallel_config.keep_scratch,
                    )
                    for job in jobs
                ]
            else:
                futures = [
                    executor.submit(
                        _run_lane_job,
                        job, base, patterns, weights, physical_model, optimizer_config,
                        str(paths.root), parallel_config.run_id,
                        parallel_config.keep_scratch,
                    )
                    for job in jobs
                ]
                # Completion order is intentionally discarded below.
                outcomes = [future.result() for future in as_completed(futures)]
            outcomes.sort(key=lambda row: row.lane_id)
            failures = [row for row in outcomes if row.error]
            if failures:
                all_success = False
                detail = "; ".join(
                    f"{row.lane_id}: {row.error} (scratch {row.scratch_path})" for row in failures
                )
                raise RuntimeError(f"Parallel lane failure: {detail}")

            new_candidates = _candidate_rows(outcomes)
            global_archive = deterministic_archive_merge(
                [*global_archive, *new_candidates],
                maximum_size=optimizer_config.maximum_archive_size,
                epsilon_fraction=optimizer_config.archive_epsilon_fraction,
                ideal=archive_ideal,
                scale=archive_scale,
            )
            for outcome in outcomes:
                assert outcome.result is not None
                total_exact += int(outcome.result.counters["exact_evaluations"])
                total_cpu += outcome.process_cpu_seconds
                local_duplicates += int(outcome.result.counters["duplicate_candidates"])
                evaluation_keys.extend(outcome.result.evaluation_keys)
            restart_assignments = _restart_parents(global_archive, profiles, epoch + 1)
            epoch_rows.append({
                "epoch": epoch,
                "global_archive_size": len(global_archive),
                "lanes": [
                    {
                        "lane_id": outcome.lane_id,
                        "lane_label": outcome.lane_label,
                        "seed": outcome.seed,
                        "exact_evaluations": outcome.result.counters["exact_evaluations"],
                        "archive_size": len(outcome.result.archive),
                        "stop_reason": outcome.result.stop_reason,
                        "process_cpu_seconds": outcome.process_cpu_seconds,
                        "scratch_path": outcome.scratch_path,
                        "cleanup_status": outcome.cleanup_status,
                    }
                    for outcome in outcomes
                    if outcome.result is not None
                ],
            })
    except BaseException:
        all_success = False
        raise
    finally:
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=True)
        run_scratch = paths.workers / parallel_config.run_id
        if all_success and not parallel_config.keep_scratch and run_scratch.exists():
            remove_owned_tree(paths, run_scratch)

    if base.sha256() != original_sha:
        raise AssertionError("A worker mutated the immutable base architecture")
    wall = time.perf_counter() - started
    archive_rows = [
        {
            "architecture_sha256": row.architecture_sha256,
            "architecture_key": f"{row.architecture_key:032x}",
            "objectives": list(row.objectives),
            "source": row.source,
            "move_index": row.move_index,
            "lane_id": row.lane_id,
            "epoch": row.epoch,
            "chain_lengths": [len(chain.cells) for chain in row.architecture.chains],
        }
        for row in global_archive
    ]
    budget_exact = (
        parallel_config.budget_mode != "exact_evaluations"
        or total_exact == parallel_config.total_exact_evaluations
    )
    stop_reason = (
        "EXACT_EVALUATION_BUDGET_EXHAUSTED"
        if parallel_config.budget_mode == "exact_evaluations" and budget_exact
        else "WALL_CLOCK_BUDGET_EXHAUSTED"
        if parallel_config.budget_mode == "wall_clock"
        else "INCOMPLETE_EXACT_EVALUATION_BUDGET"
    )
    return ParallelParetoResult(
        parallel_config,
        optimizer_config,
        archive_rows,
        _metrics(global_archive, evaluation_keys, total_exact, ideal, reference),
        {
            "wall_seconds": wall,
            "process_cpu_seconds": total_cpu,
            "cpu_utilization_percent": (
                100.0 * total_cpu / max(wall * parallel_config.worker_count, 1e-12)
            ),
        },
        {
            "total_exact_evaluations": total_exact,
            "requested_exact_evaluations": parallel_config.total_exact_evaluations,
            "local_duplicate_proposals": local_duplicates,
            "evaluation_budget_exact": budget_exact,
        },
        epoch_rows,
        reference,
        ideal,
        stop_reason,
        {row.architecture_sha256: row.architecture for row in global_archive},
    )
