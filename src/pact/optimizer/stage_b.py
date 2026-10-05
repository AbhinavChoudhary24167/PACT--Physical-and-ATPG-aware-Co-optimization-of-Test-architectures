"""Epsilon-constrained activity search using the qualified stateful evaluator.

Wire is port-inclusive scan HPWL, not a routed-wire guarantee. The reference
is chosen externally by frozen routed cost, never by candidate activity.
Scores retain the existing [W, E, H8, maximum edge, H4] representation.
"""
from dataclasses import dataclass
import time
import numpy as np
from scipy.spatial import cKDTree
from .search import Archive, proposal, update_locations
from .implementation_v2 import order_id
from .cpu_incremental import State
from .candidate_stateful import reference

ACTIVITY = np.array([1, 4, 2])  # E, H4, H8
ROLES = ('best_E', 'best_H4', 'best_H8', 'balanced')


@dataclass(frozen=True)
class Config:
    epsilon: float = .05
    seconds: float = 600.
    max_evaluations: int = 20000
    stagnation_attempts: int = 2000
    lane_attempts: int = 150
    seed: int = 11
    neighbors: int = 16
    segment: int = 8
    archive_size: int = 16
    weights: tuple = (1., 1., 1.)

    def __post_init__(self):
        if not np.isfinite(self.epsilon) or self.epsilon < 0:
            raise ValueError('Invalid wire epsilon')
        if not np.isfinite(self.seconds) or self.seconds <= 0:
            raise ValueError('Invalid runtime budget')
        if min(self.max_evaluations, self.stagnation_attempts, self.lane_attempts, self.neighbors) < 1:
            raise ValueError('Invalid evaluation/convergence budget')
        if self.segment < 2 or self.archive_size < 4:
            raise ValueError('Invalid operator/archive bound')
        if len(self.weights) != 3 or not np.isfinite(self.weights).all() or min(self.weights) < 0 or sum(self.weights) <= 0:
            raise ValueError('Invalid E/H4/H8 weights')


def activity_score(score, reference_score, weights):
    """Sum_i w_i (metric_i / reference_i) / sum_i w_i; fixed across designs."""
    return float(np.dot(np.asarray(score)[ACTIVITY] / np.maximum(reference_score[ACTIVITY], 1e-12), weights) / sum(weights))


def optimize(model, starts, reference_label, config, *, state_type=State,
             reference_evaluator=reference, checkpoint=None):
    began = time.perf_counter()
    baseline = []
    for label, orders in starts:
        state = state_type(model, orders)
        baseline.append(dict(label=label, score=state.score(), orders=[o.copy() for o in orders], parent=label))
    ref = next(r for r in baseline if r['label'] == reference_label)
    cap = float(ref['score'][0]) * (1 + config.epsilon)
    archive = Archive(config.archive_size)
    champions = [None] * 4
    def values(score):
        return [*score[ACTIVITY], activity_score(score, ref['score'], config.weights)]
    def consider(row):
        changed = False
        if row['score'][0] > cap + 1e-8:
            return changed
        archive.insert(row['score'][ACTIVITY], row['orders'], row['label'])
        for i, value in enumerate(values(row['score'])):
            old = champions[i]
            if old is None or value < values(old['score'])[i] - 1e-10 * max(1., abs(value)):
                champions[i] = dict(row, score=row['score'].copy(), orders=[o.copy() for o in row['orders']])
                changed = True
        return changed
    for row in baseline:
        consider(row)
    feasible_starts = [r for r in baseline if r['score'][0] <= cap + 1e-8]
    initial_seconds = time.perf_counter() - began
    state = state_type(model, ref['orders'])
    current = state.score()
    parent = reference_label
    _, neighbor = cKDTree(model.xy).query(model.xy, k=min(len(model.names), config.neighbors + 1), workers=1)
    neighbor = np.asarray(neighbor, np.int32).reshape(len(model.names), -1)
    rng = np.random.default_rng(config.seed)
    evaluations = accepted = attempts = screened = stagnation = 0
    lane = 0
    convergence = []
    search_began = time.perf_counter()
    next_checkpoint = search_began
    def record():
        nonlocal next_checkpoint
        row = dict(seconds=time.perf_counter()-search_began, evaluations=evaluations,
                   attempts=attempts, screened_infeasible=screened, accepted=accepted,
                   champions=[r['score'].tolist() for r in champions])
        convergence.append(row)
        if checkpoint:
            checkpoint(row)
        next_checkpoint = time.perf_counter() + 30
    while evaluations < config.max_evaluations and time.perf_counter()-search_began < config.seconds and stagnation < config.stagnation_attempts:
        if attempts and attempts % config.lane_attempts == 0:
            lane = (lane + 1) % 4
            # Alternate endpoint champions and all feasible physical starts.
            epoch = attempts // config.lane_attempts
            seed = champions[lane] if epoch % 2 else feasible_starts[(epoch//2) % len(feasible_starts)]
            state = state_type(model, seed['orders'])
            current, parent = state.score(), seed['parent']
        patch, kind = proposal(state, neighbor, rng, attempts, config.segment)
        attempts += 1
        if patch is None:
            continue
        # Geometry-only feasibility screen before any waveform/logic update.
        old_nodes = {ci: state.orders[ci][pos].copy() for ci, (pos, _) in patch.items()}
        for ci, (pos, nodes) in patch.items():
            state.orders[ci][pos] = nodes
        try:
            wire = model.physical(state.orders)[0]
        finally:
            for ci, (pos, _) in patch.items():
                state.orders[ci][pos] = old_nodes[ci]
        if wire > cap + 1e-8:
            screened += 1
            stagnation += 1
        else:
            undo = state.change(patch)
            score = state.score()
            evaluations += 1
            row = dict(label=parent+':'+kind, parent=parent, score=score, orders=state.orders)
            progress = consider(row)
            stagnation = 0 if progress else stagnation + 1
            new_value, old_value = values(score)[lane], values(current)[lane]
            if new_value < old_value - 1e-10 * max(1., abs(old_value)):
                current = score
                accepted += 1
                update_locations(state, patch)
            else:
                state.change(undo)
        if time.perf_counter() >= next_checkpoint:
            record()
    loop_seconds = time.perf_counter() - search_began
    record()
    selected = []
    by_id = {}
    baseline_ids = {order_id(r['orders']) for r in baseline}
    for role, row in zip(ROLES, champions):
        oid = order_id(row['orders'])
        if oid in by_id:
            by_id[oid]['roles'].append(role)
            continue
        # Verify only the retained endpoint winners with independent replay.
        checked = reference_evaluator(model, row['orders'])
        np.testing.assert_allclose(checked, row['score'], rtol=1e-9, atol=1e-6)
        result = dict(row, score=checked, roles=[role], new=oid not in baseline_ids)
        by_id[oid] = result
        selected.append(result)
    reason = 'evaluation_budget' if evaluations >= config.max_evaluations else ('stagnation' if stagnation >= config.stagnation_attempts else 'wall_clock')
    return dict(selected=selected, baselines=baseline, wire_reference_um=float(ref['score'][0]),
                wire_ceiling_um=cap, reference_label=reference_label, reference_score=ref['score'],
                evaluations=evaluations, attempts=attempts, screened_infeasible=screened, accepted=accepted,
                initialization_seconds=initial_seconds, search_seconds=loop_seconds,
                runtime_seconds=time.perf_counter()-began, termination=reason,
                convergence=convergence, archive_size=len(archive.rows))
