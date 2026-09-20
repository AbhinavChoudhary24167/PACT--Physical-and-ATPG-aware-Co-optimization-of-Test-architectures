"""Equal-budget deterministic multi-objective search baselines for Phase-0D."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import random
import time
from typing import Any, Callable, Mapping

from pact.phase0d.pareto import ObjectiveBounds, ObjectiveVector, dominates, nondominated, normalized_hypervolume
from pact.scan.model import ScanArchitecture
from pact.scan.phase0d_operators import OperatorConstraints, apply_operator, sample_operations


SEARCH_METHODS = (
    "greedy_best_improvement",
    "greedy_first_improvement",
    "beam_search",
    "simulated_annealing",
)


@dataclass(frozen=True)
class Evaluation:
    objectives: ObjectiveVector
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvaluatedArchitecture:
    architecture: ScanArchitecture
    evaluation: Evaluation


@dataclass(frozen=True)
class SearchConfig:
    proxy_budget: int
    candidate_batch_size: int = 8
    beam_width: int = 3
    plateau_legal_evaluations: int = 16
    hypervolume_window: int = 16
    minimum_relative_hypervolume_improvement: float = 0.005
    wall_clock_seconds: float = 600.0
    proposal_seed: int = 101
    annealing_initial_temperature: float = 0.25
    annealing_final_temperature: float = 0.01

    def __post_init__(self) -> None:
        if self.proxy_budget < 1 or self.proxy_budget > 128:
            raise ValueError("proxy_budget must be in [1,128]")
        if min(self.candidate_batch_size, self.beam_width, self.plateau_legal_evaluations,
               self.hypervolume_window) < 1:
            raise ValueError("Search sizes and windows must be positive")
        if self.wall_clock_seconds <= 0:
            raise ValueError("wall-clock budget must be positive")
        if not 0 <= self.minimum_relative_hypervolume_improvement < 1:
            raise ValueError("Invalid hypervolume improvement threshold")


@dataclass
class SearchState:
    method: str
    start_time: float
    proposed_candidates: int = 0
    legal_candidates: int = 0
    proxy_evaluations: int = 0
    routed_evaluations: int = 0
    accepted_moves: int = 0
    rejected_moves: int = 0
    duplicate_candidates: int = 0
    invalid_candidates: int = 0
    consecutive_without_pareto_improvement: int = 0
    stop_reason: str | None = None
    trace: list[dict[str, Any]] = field(default_factory=list)


Evaluator = Callable[[ScanArchitecture, Mapping[str, Any]], Evaluation]


def _archive_insert(archive: list[EvaluatedArchitecture], candidate: EvaluatedArchitecture) -> bool:
    sha = candidate.architecture.sha256()
    if any(item.architecture.sha256() == sha for item in archive):
        return False
    objectives = candidate.evaluation.objectives
    if any(dominates(item.evaluation.objectives, objectives) for item in archive):
        return False
    archive[:] = [item for item in archive if not dominates(objectives, item.evaluation.objectives)]
    archive.append(candidate)
    archive.sort(key=lambda item: (item.evaluation.objectives, item.architecture.sha256()))
    return True


def _archive_hv(archive: list[EvaluatedArchitecture], bounds: ObjectiveBounds) -> float:
    return normalized_hypervolume((item.evaluation.objectives for item in archive), bounds)


def _early_stop(state: SearchState, config: SearchConfig, hv_history: list[float]) -> str | None:
    if state.proxy_evaluations >= config.proxy_budget:
        return "PROXY_BUDGET_EXHAUSTED"
    if time.monotonic() - state.start_time >= config.wall_clock_seconds:
        return "WALL_CLOCK_BUDGET_EXCEEDED"
    if state.consecutive_without_pareto_improvement >= config.plateau_legal_evaluations:
        return "PARETO_PLATEAU"
    if len(hv_history) > config.hypervolume_window:
        old = hv_history[-config.hypervolume_window - 1]
        new = hv_history[-1]
        relative = (new - old) / max(abs(old), 1e-12)
        if relative < config.minimum_relative_hypervolume_improvement:
            return "HYPERVOLUME_PLATEAU"
    return None


def _evaluate(
    parent: EvaluatedArchitecture,
    operation: Mapping[str, Any],
    evaluator: Evaluator,
    constraints: OperatorConstraints,
    archive: list[EvaluatedArchitecture],
    bounds: ObjectiveBounds,
    state: SearchState,
    hv_history: list[float],
    seen: set[str],
) -> EvaluatedArchitecture | None:
    state.proposed_candidates += 1
    try:
        child_arch, operator_record = apply_operator(parent.architecture, operation, constraints)
    except (ValueError, IndexError) as error:
        state.invalid_candidates += 1
        state.trace.append({"event": "INVALID", "operation": dict(operation), "reason": str(error)})
        return None
    sha = child_arch.sha256()
    if sha in seen:
        state.duplicate_candidates += 1
        state.trace.append({"event": "DUPLICATE", "operation": dict(operation), "child_sha256": sha})
        return None
    seen.add(sha)
    state.legal_candidates += 1
    try:
        started = time.monotonic()
        evaluation = evaluator(child_arch, operator_record)
        evaluation_seconds = time.monotonic() - started
    except (ValueError, AssertionError) as error:
        state.invalid_candidates += 1
        state.trace.append({"event": "INVALID_EVALUATION", "operation": dict(operation),
                            "child_sha256": sha, "reason": str(error)})
        return None
    state.proxy_evaluations += 1
    candidate = EvaluatedArchitecture(child_arch, evaluation)
    old_hv = _archive_hv(archive, bounds)
    pareto_improved = _archive_insert(archive, candidate)
    new_hv = _archive_hv(archive, bounds)
    if pareto_improved:
        state.consecutive_without_pareto_improvement = 0
    else:
        state.consecutive_without_pareto_improvement += 1
    hv_history.append(new_hv)
    state.trace.append({
        "event": "PROXY_EVALUATION",
        "evaluation_index": state.proxy_evaluations,
        "operation": dict(operation),
        "operator_record": operator_record,
        "parent_sha256": parent.architecture.sha256(),
        "child_sha256": sha,
        "objectives": list(evaluation.objectives),
        "metadata": dict(evaluation.metadata),
        "evaluation_seconds": evaluation_seconds,
        "pareto_archive_changed": pareto_improved,
        "hypervolume_before": old_hv,
        "hypervolume_after": new_hv,
        "accepted_move": False,
    })
    return candidate


def _mark_accepted(state: SearchState, candidate: EvaluatedArchitecture) -> None:
    sha = candidate.architecture.sha256()
    for record in reversed(state.trace):
        if record.get("child_sha256") == sha and record.get("event") == "PROXY_EVALUATION":
            record["accepted_move"] = True
            break
    state.accepted_moves += 1


def _proposals(parent: EvaluatedArchitecture, count: int, config: SearchConfig, round_index: int,
               constraints: OperatorConstraints) -> list[dict[str, Any]]:
    return sample_operations(parent.architecture, count, config.proposal_seed, round_index, constraints=constraints)


def _greedy(
    best: bool,
    start: EvaluatedArchitecture,
    evaluator: Evaluator,
    bounds: ObjectiveBounds,
    config: SearchConfig,
    constraints: OperatorConstraints,
    state: SearchState,
    archive: list[EvaluatedArchitecture],
    hv_history: list[float],
    seen: set[str],
) -> None:
    current = start
    round_index = 0
    while not state.stop_reason:
        remaining = config.proxy_budget - state.proxy_evaluations
        if remaining <= 0:
            state.stop_reason = "PROXY_BUDGET_EXHAUSTED"
            break
        operations = _proposals(current, min(config.candidate_batch_size, remaining), config, round_index, constraints)
        archive_before_batch = list(archive)
        evaluated: list[EvaluatedArchitecture] = []
        for operation in operations:
            candidate = _evaluate(current, operation, evaluator, constraints, archive, bounds, state, hv_history, seen)
            if candidate is not None:
                evaluated.append(candidate)
                improvement = not dominates(current.evaluation.objectives, candidate.evaluation.objectives)
                if not best and improvement:
                    current = candidate
                    _mark_accepted(state, candidate)
                    break
            state.stop_reason = _early_stop(state, config, hv_history)
            if state.stop_reason:
                break
        if state.stop_reason:
            break
        if best and evaluated:
            viable = [candidate for candidate in evaluated
                      if not dominates(current.evaluation.objectives, candidate.evaluation.objectives)]
            if viable:
                current = min(
                    viable,
                    key=lambda candidate: (
                        -normalized_hypervolume(
                            [item.evaluation.objectives for item in archive_before_batch]
                            + [candidate.evaluation.objectives], bounds
                        ),
                        candidate.evaluation.objectives,
                        candidate.architecture.sha256(),
                    ),
                )
                _mark_accepted(state, current)
        round_index += 1


def _crowding_key(candidate: EvaluatedArchitecture, population: list[EvaluatedArchitecture],
                  bounds: ObjectiveBounds) -> tuple[float, ObjectiveVector, str]:
    normalized = [bounds.normalize(item.evaluation.objectives) for item in population]
    target_index = next(index for index, item in enumerate(population)
                        if item.architecture.sha256() == candidate.architecture.sha256())
    distance = 0.0
    for objective in range(3):
        order = sorted(range(len(population)), key=lambda index: (normalized[index][objective],
                                                                  population[index].architecture.sha256()))
        position = order.index(target_index)
        if position in {0, len(order) - 1}:
            distance += 1.0
        else:
            distance += normalized[order[position + 1]][objective] - normalized[order[position - 1]][objective]
    return (-distance, candidate.evaluation.objectives, candidate.architecture.sha256())


def _beam(
    start: EvaluatedArchitecture,
    evaluator: Evaluator,
    bounds: ObjectiveBounds,
    config: SearchConfig,
    constraints: OperatorConstraints,
    state: SearchState,
    archive: list[EvaluatedArchitecture],
    hv_history: list[float],
    seen: set[str],
) -> None:
    beam = [start]
    round_index = 0
    while not state.stop_reason:
        generated: list[EvaluatedArchitecture] = []
        for parent_index, parent in enumerate(beam):
            remaining = config.proxy_budget - state.proxy_evaluations
            if remaining <= 0:
                break
            count = min(max(1, math.ceil(config.candidate_batch_size / len(beam))), remaining)
            for operation in _proposals(parent, count, config, round_index * config.beam_width + parent_index, constraints):
                candidate = _evaluate(parent, operation, evaluator, constraints, archive, bounds, state, hv_history, seen)
                if candidate is not None:
                    generated.append(candidate)
                state.stop_reason = _early_stop(state, config, hv_history)
                if state.stop_reason:
                    break
            if state.stop_reason:
                break
        if state.stop_reason:
            break
        population_by_sha = {item.architecture.sha256(): item for item in beam + generated}
        front = nondominated(population_by_sha.values(), key=lambda item: item.evaluation.objectives)
        next_beam = sorted(front, key=lambda item: _crowding_key(item, front, bounds))[:config.beam_width]
        old_shas = {item.architecture.sha256() for item in beam}
        for candidate in next_beam:
            if candidate.architecture.sha256() not in old_shas:
                _mark_accepted(state, candidate)
        beam = next_beam
        round_index += 1


def _anneal(
    start: EvaluatedArchitecture,
    evaluator: Evaluator,
    bounds: ObjectiveBounds,
    config: SearchConfig,
    constraints: OperatorConstraints,
    state: SearchState,
    archive: list[EvaluatedArchitecture],
    hv_history: list[float],
    seen: set[str],
) -> None:
    current = start
    rng = random.Random(config.proposal_seed)
    round_index = 0
    while not state.stop_reason:
        remaining = config.proxy_budget - state.proxy_evaluations
        if remaining <= 0:
            state.stop_reason = "PROXY_BUDGET_EXHAUSTED"
            break
        operation = _proposals(current, 1, config, round_index, constraints)[0]
        candidate = _evaluate(current, operation, evaluator, constraints, archive, bounds, state, hv_history, seen)
        if candidate is not None:
            progress = state.proxy_evaluations / max(1, config.proxy_budget)
            temperature = config.annealing_initial_temperature * (
                config.annealing_final_temperature / config.annealing_initial_temperature
            ) ** progress
            current_normalized = bounds.normalize(current.evaluation.objectives)
            candidate_normalized = bounds.normalize(candidate.evaluation.objectives)
            worst_deterioration = max(new - old for old, new in zip(current_normalized, candidate_normalized))
            accept = dominates(candidate.evaluation.objectives, current.evaluation.objectives)
            accept = accept or (not dominates(current.evaluation.objectives, candidate.evaluation.objectives)
                                and worst_deterioration <= 0)
            if not accept:
                accept = rng.random() < math.exp(-max(0.0, worst_deterioration) / max(temperature, 1e-12))
            if accept:
                current = candidate
                _mark_accepted(state, candidate)
        state.stop_reason = _early_stop(state, config, hv_history)
        round_index += 1


def run_search(
    method: str,
    start: EvaluatedArchitecture,
    evaluator: Evaluator,
    bounds: ObjectiveBounds,
    config: SearchConfig,
    constraints: OperatorConstraints = OperatorConstraints(),
) -> dict[str, Any]:
    """Run one baseline under a strict proxy and wall-clock budget."""
    if method not in SEARCH_METHODS:
        raise ValueError(f"Unknown search method: {method}")
    state = SearchState(method, time.monotonic())
    archive = [start]
    hv_history = [_archive_hv(archive, bounds)]
    seen = {start.architecture.sha256()}
    if method == "greedy_best_improvement":
        _greedy(True, start, evaluator, bounds, config, constraints, state, archive, hv_history, seen)
    elif method == "greedy_first_improvement":
        _greedy(False, start, evaluator, bounds, config, constraints, state, archive, hv_history, seen)
    elif method == "beam_search":
        _beam(start, evaluator, bounds, config, constraints, state, archive, hv_history, seen)
    else:
        _anneal(start, evaluator, bounds, config, constraints, state, archive, hv_history, seen)
    elapsed = time.monotonic() - state.start_time
    state.rejected_moves = state.proxy_evaluations - state.accepted_moves
    return {
        "schema_version": "phase0d-search-result-1",
        "method": method,
        "config": config.__dict__,
        "start_architecture_sha256": start.architecture.sha256(),
        "start_objectives": list(start.evaluation.objectives),
        "proposed_candidates": state.proposed_candidates,
        "legal_candidates": state.legal_candidates,
        "proxy_evaluations": state.proxy_evaluations,
        "routed_evaluations": state.routed_evaluations,
        "accepted_moves": state.accepted_moves,
        "rejected_moves": state.rejected_moves,
        "duplicate_candidates": state.duplicate_candidates,
        "invalid_candidates": state.invalid_candidates,
        "wall_clock_seconds": elapsed,
        "stop_reason": state.stop_reason or "COMPLETED",
        "final_hypervolume": hv_history[-1],
        "unique_pareto_solutions": len(archive),
        "pareto_archive": [
            {"architecture_sha256": item.architecture.sha256(),
             "objectives": list(item.evaluation.objectives), "metadata": dict(item.evaluation.metadata)}
            for item in archive
        ],
        "trace": state.trace,
    }
