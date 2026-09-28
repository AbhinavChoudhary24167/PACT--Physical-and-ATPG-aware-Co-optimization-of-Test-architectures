"""ATPG load/unload synthesis using measured implementation loads.

The reference replay deliberately does not use transition diagonals. Search
reuses the working optimizer's operators and Pareto archive, not its M3/M5.
"""
from dataclasses import dataclass
import hashlib
import time
import numpy as np
from numba import njit
from scipy.spatial import cKDTree
from pact.physical_effect import spatial_bin
from pact.scan.model import ScanArchitecture, ScanChain
from pact.scan.validate import validate_scan
from .search import Archive, dominates, locate, proposal, update_locations

METRICS = ('wire_um', 'activity_ff_transitions', 'spatial_peak_8_ff',
           'timing_max_edge_um', 'spatial_peak_4_ff')


@dataclass(frozen=True)
class Config:
    seconds: float = 180.
    max_evaluations: int = 100000
    wire_allowance: float = .10
    timing_allowance: float = .10
    seed: int = 11
    archive_size: int = 32
    neighbors: int = 16
    segment: int = 8
    restart_interval: int = 250

    def __post_init__(self):
        if not all(np.isfinite(x) and x >= 0 for x in
                   (self.seconds, self.wire_allowance, self.timing_allowance)) or self.seconds == 0:
            raise ValueError('Invalid budget/allowance')
        if min(self.max_evaluations, self.neighbors, self.restart_interval) < 1 or self.archive_size < 3 or self.segment < 2:
            raise ValueError('Invalid search bounds')


class Model:
    def __init__(self, architecture, load, response, caps, bounds, inputs, outputs):
        validate_scan(architecture)
        self.architecture = architecture
        self.names = tuple(c.name for c in architecture.cells)
        self.index = {n: i for i, n in enumerate(self.names)}
        self.xy = np.array([(c.x_um, c.y_um) for c in architecture.cells])
        self.capacities = tuple(len(c.cells) for c in architecture.chains)
        self.longest = max(self.capacities)
        self.domains = np.array([c.clock_domain for c in architecture.cells])
        self.inputs, self.outputs = np.asarray(inputs, float), np.asarray(outputs, float)
        self.caps = np.asarray(caps, float)
        load, response = np.asarray(load), np.asarray(response)
        if load.ndim != 2 or load.shape != response.shape or load.shape[1] != len(self.names) or not len(load):
            raise ValueError('Invalid state dimensions')
        if not np.isin(load, [0, 1]).all() or not np.isin(response, [0, 1]).all():
            raise ValueError('Complete binary ATPG states required; unknowns are not filled')
        self.load, self.response = load.astype(np.uint8), response.astype(np.uint8)
        for value, shape in ((self.caps, (len(self.names),)), (self.inputs, (len(self.capacities), 2)),
                             (self.outputs, (len(self.capacities), 2))):
            if value.shape != shape or not np.isfinite(value).all():
                raise ValueError('Invalid physical arrays')
        if np.any(self.caps < 0):
            raise ValueError('Invalid capacitance')
        self.bins = np.array([spatial_bin(xy, bounds, 8) for xy in self.xy], np.int32)
        self.bins4 = np.array([spatial_bin(xy, bounds, 4) for xy in self.xy], np.int32)

    def orders(self, arch):
        if arch.cells != self.architecture.cells or [(c.chain_id, c.scan_in, c.scan_out) for c in arch.chains] != [
                (c.chain_id, c.scan_in, c.scan_out) for c in self.architecture.chains]:
            raise ValueError('Changed inventory/placement/ports')
        orders = [np.array([self.index[n] for n in c.cells], np.int32) for c in arch.chains]
        self.validate(orders)
        return orders

    def validate(self, orders):
        if tuple(map(len, orders)) != self.capacities or not np.array_equal(np.sort(np.concatenate(orders)), np.arange(len(self.names))):
            raise ValueError('Not a fixed-capacity FF bijection')
        if any(len(set(self.domains[o])) != 1 for o in orders):
            raise ValueError('Mixed clock domains')

    def architecture_from(self, orders):
        self.validate(orders)
        return ScanArchitecture(self.architecture.cells, tuple(
            ScanChain(c.chain_id, tuple(self.names[int(n)] for n in o), c.scan_in, c.scan_out)
            for c, o in zip(self.architecture.chains, orders, strict=True)))

    def physical(self, orders):
        edges = np.concatenate([np.abs(np.diff(np.vstack((self.inputs[ci], self.xy[o], self.outputs[ci])), axis=0)).sum(axis=1)
                                for ci, o in enumerate(orders)])
        return float(edges.sum()), float(edges.max())


def order_id(orders):
    h = hashlib.sha256()
    for o in orders:
        h.update(np.asarray([len(o)], dtype='<i4').tobytes())
        h.update(np.asarray(o, dtype='<i4').tobytes())
    return h.hexdigest()


def reference(model, orders, return_counts=False):
    """Independent simultaneous replay of the exact physical-effect schedule."""
    model.validate(orders)
    p, n = model.load.shape
    counts = np.zeros((p, 2, model.longest, n), np.uint8)
    for pi in range(p):
        for phase in range(2):
            state = np.zeros(n, np.uint8) if phase == 0 else model.response[pi].copy()
            serial = [np.r_[np.zeros(model.longest-len(o), np.uint8), model.load[pi, o[::-1]]] for o in orders]
            for t in range(model.longest):
                nxt = np.empty_like(state)
                for ci, o in enumerate(orders):
                    nxt[o[0]] = serial[ci][t] if phase == 0 else 0
                    nxt[o[1:]] = state[o[:-1]]
                counts[pi, phase, t] = state ^ nxt
                state = nxt
            expected = model.load[pi] if phase == 0 else np.zeros(n, np.uint8)
            np.testing.assert_array_equal(state, expected)
    flat = counts.reshape(-1, n)
    field = np.zeros((len(flat), 64))
    field4 = np.zeros((len(flat), 16))
    for i in range(n):
        field[:, model.bins[i]] += flat[:, i]*model.caps[i]
        field4[:, model.bins4[i]] += flat[:, i]*model.caps[i]
    wire, timing = model.physical(orders)
    score = np.array([wire, field.sum(), field.max(), timing, field4.max()])
    return (score, counts) if return_counts else score


@njit(cache=True)
def coefficient(load, response, order, p, phase, r, longest):
    if phase == 1:
        if r > 0:
            return 0
        if r == 0:
            return int(response[p, order[0]])
        return int(response[p, order[-r-1]] ^ response[p, order[-r]])
    if r < 0:
        return 0
    a = int(load[p, order[longest-1-r]]) if r >= longest-len(order) else 0
    b = int(load[p, order[longest-r]]) if r > 0 and r-1 >= longest-len(order) else 0
    return a ^ b


@njit(cache=True)
def build_chain(field, load, response, order, bins, weights):
    pcount, longest, m = len(load), field.shape[2], len(order)
    d = np.empty((pcount, 2, longest+m-1), np.int8)
    for p in range(pcount):
        for phase in range(2):
            for r in range(1-m, longest):
                d[p, phase, r+m-1] = coefficient(load, response, order, p, phase, r, longest)
            for j in range(m):
                for t in range(longest):
                    field[p, phase, t, bins[j]] += d[p, phase, t-j+m-1]*weights[j]
    return d


@njit(cache=True)
def update_chain(field, d, load, response, order, bins, weights, dirty, positions, new_bins, new_weights):
    longest, m = field.shape[2], len(order)
    for p in range(len(load)):
        for phase in range(2):
            for r in dirty:
                idx = r+m-1
                new = coefficient(load, response, order, p, phase, r, longest)
                delta = new-int(d[p, phase, idx])
                if delta:
                    for j in range(max(0, -r), min(m, longest-r)):
                        field[p, phase, r+j, bins[j]] += delta*weights[j]
                d[p, phase, idx] = new
            for z in range(len(positions)):
                j = positions[z]
                for t in range(longest):
                    if d[p, phase, t-j+m-1]:
                        field[p, phase, t, bins[j]] -= weights[j]
                        field[p, phase, t, new_bins[z]] += new_weights[z]
    for z in range(len(positions)):
        j = positions[z]
        bins[j], weights[j] = new_bins[z], new_weights[z]


@njit(cache=True)
def reduce(field):
    total, peak, peak4 = 0., 0., 0.
    flat = field.reshape((-1, 64))
    for row in flat:
        for b in range(64):
            total += row[b]
            peak = max(peak, row[b])
        for y in range(4):
            for x in range(4):
                b = y*16+x*2
                peak4 = max(peak4, row[b]+row[b+1]+row[b+8]+row[b+9])
    return total, peak, peak4


class State:
    def __init__(self, model, orders):
        model.validate(orders)
        self.costs = model  # existing proposal/locate interface
        self.orders = [o.copy() for o in orders]
        self.field = np.zeros((len(model.load), 2, model.longest, 64))
        self.bins, self.weights, self.ds = [], [], []
        for o in orders:
            b, w = model.bins[o].copy(), model.caps[o].copy()
            self.ds.append(build_chain(self.field, model.load, model.response, o, b, w))
            self.bins.append(b)
            self.weights.append(w)
        locate(self)

    def change(self, patch):
        model, undo = self.costs, {}
        for ci, (positions, nodes) in patch.items():
            o = self.orders[ci]
            positions = np.asarray(positions, np.int32)
            undo[ci] = positions, o[positions].copy()
            o[positions] = nodes
            dirty = np.array(sorted({r for j in positions for r in
                (model.longest-1-int(j), model.longest-int(j), -int(j)-1, -int(j)) if 1-len(o) <= r < model.longest}), np.int32)
            update_chain(self.field, self.ds[ci], model.load, model.response, o, self.bins[ci], self.weights[ci],
                         dirty, positions, model.bins[o[positions]], model.caps[o[positions]])
        return undo

    def score(self):
        total, peak, peak4 = reduce(self.field)
        wire, timing = self.costs.physical(self.orders)
        return np.array([wire, total, peak, timing, peak4])


def optimize(model, starts, config, record=None):
    began = time.perf_counter()
    baseline = []
    archive = Archive(config.archive_size)
    for label, orders in starts:
        s = State(model, orders).score()
        baseline.append(dict(label=label, score=s, orders=orders))
    ref = baseline[0]['score']
    cap, timing_cap = ref[0]*(1+config.wire_allowance), ref[3]*(1+config.timing_allowance)
    def feasible(score):
        return bool(score[0] <= cap+1e-8 and score[3] <= timing_cap+1e-8)
    for row in baseline:
        if feasible(row['score']):
            archive.insert(row['score'][:3], row['orders'], row['label'])
    initial_seconds = time.perf_counter()-began
    state = State(model, starts[0][1])
    current = state.score()
    parent_seed = starts[0][0]
    neighbors = np.asarray(cKDTree(model.xy).query(model.xy, k=min(len(model.names), config.neighbors+1))[1], np.int32)
    rng = np.random.default_rng(config.seed)
    evaluations = accepted = attempts = 0
    seen = {order_id(o) for _, o in starts}
    baseline_ids = seen.copy()
    new_ids = set()
    begun = time.perf_counter()
    while evaluations < config.max_evaluations and time.perf_counter()-begun < config.seconds:
        if evaluations and evaluations % config.restart_interval == 0:
            # Every fourth restart can repair an infeasible J50 seed towards the cap.
            epoch = evaluations//config.restart_interval
            if epoch % 4 == 0:
                label, orders = starts[(epoch//4) % len(starts)]
            else:
                row = archive.rows[int(rng.integers(len(archive.rows)))]
                label, orders = row['label'], row['orders']
            state = State(model, orders)
            current = state.score()
            parent_seed = label.split(':')[0]
        parent = order_id(state.orders)
        patch, kind = proposal(state, neighbors, rng, attempts, config.segment)
        attempts += 1
        if patch is None:
            continue
        undo = state.change(patch)
        try:
            model.validate(state.orders)
        except ValueError:
            state.change(undo)
            continue
        score = state.score()
        evaluations += 1
        oid = order_id(state.orders)
        fresh = oid not in seen
        seen.add(oid)
        if oid not in baseline_ids:
            new_ids.add(oid)
        eligible = feasible(score)
        if eligible:
            archive.insert(score[:3], state.orders, parent_seed+':'+kind)
        priority = (1, 2, 0)[(evaluations//config.restart_interval) % 3]
        improving = score[priority] < current[priority]-1e-9*max(1., current[priority])
        old_violation = max(current[0]/cap, current[3]/timing_cap)
        violation = max(score[0]/cap, score[3]/timing_cap)
        take = (eligible and (not feasible(current) or dominates(score[:3], current[:3]) or improving)) or (
            not feasible(current) and violation < old_violation-1e-10)
        if record:
            record(dict(evaluation=evaluations, order_id=oid, parent_order_id=parent,
                        provenance=parent_seed, operator=kind, new_unique=fresh, legal=True,
                        feasible=eligible, accepted=bool(take), seconds=time.perf_counter()-begun,
                        **dict(zip(METRICS, map(float, score)))))
        if take:
            current = score
            accepted += 1
            update_locations(state, patch)
        else:
            state.change(undo)
    rows = []
    for row in archive.rows:
        score = reference(model, row['orders'])
        np.testing.assert_allclose(score[:3], row['score'], rtol=1e-9, atol=1e-6)
        rows.append(dict(row, score=score, new=order_id(row['orders']) not in baseline_ids))
    return dict(archive=rows, baselines=baseline, evaluations=evaluations, new_unique=len(new_ids),
                accepted=accepted, initialization_seconds=initial_seconds,
                search_seconds=time.perf_counter()-begun, runtime_seconds=time.perf_counter()-began,
                wire_ceiling_um=cap, timing_ceiling_um=timing_cap)


def select(rows, reference_score, limit=3):
    if not 1 <= limit <= 3:
        raise ValueError('Route budget must be 1–3 new candidates per design')
    eligible = [r for r in rows if r['new']]
    chosen = []
    for role, key in [('activity', lambda r: r['score'][1]), ('spatial', lambda r: r['score'][2]),
                      ('balanced', lambda r: max(r['score'][:3]/reference_score[:3]))]:
        if not eligible or len(chosen) == limit:
            break
        row = min(eligible, key=key)
        oid = order_id(row['orders'])
        previous = next((r for r in chosen if order_id(r['orders']) == oid), None)
        if previous:
            previous['roles'].append(role)
        else:
            chosen.append(dict(row, roles=[role]))
    return chosen
