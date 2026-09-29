"""Candidate-sensitive extension of the v2 transition-diagonal evaluator."""
import time
import numpy as np
from numba import njit
from pact.physical_effect import spatial_bin
from . import implementation_v2 as v2
from .search import locate, dominates

METRICS = ('wire_um', 'candidate_E_ff', 'propagated_H8_ff', 'timing_max_edge_um', 'propagated_H4_ff')


class Model(v2.Model):
    def __init__(self, frozen, physical, bounds):
        self.__dict__.update(frozen.__dict__)
        self.frozen = frozen
        self.rho = float(physical['rho'])
        self.sink = np.asarray(physical['sink'], float)
        self.static = np.asarray(physical['spatial'], float)
        self.si_extra = np.asarray(physical['si_extra'], float)
        self.so_extra = np.asarray(physical['so_extra'], float)
        if self.static.shape != (len(self.names), 64) or self.sink.shape != (len(self.names),):
            raise ValueError('Invalid physical model dimensions')
        if self.si_extra.shape != (len(self.capacities),) or self.so_extra.shape != self.si_extra.shape:
            raise ValueError('Invalid port capacitance dimensions')
        if any(not np.isfinite(a).all() or np.any(a < 0) for a in
               (self.static, self.sink, self.si_extra, self.so_extra, np.asarray(self.rho))):
            raise ValueError('Invalid physical capacitance')
        self.port_bins = np.array([spatial_bin(xy, bounds, 8) for xy in self.inputs], np.int32)
        # Slot 0 is always the FF origin, where candidate scan demand is added.
        lists = [[int(self.bins[i])]+[b for b in np.flatnonzero(row) if b != self.bins[i]]
                 for i, row in enumerate(self.static)]
        width = max(map(len, lists))
        self.influence_bins = np.zeros((len(self.names), width), np.int32)
        self.influence_weights = np.zeros((len(self.names), width))
        for i, bs in enumerate(lists):
            self.influence_bins[i, :len(bs)] = bs
            self.influence_weights[i, :len(bs)] = self.static[i, bs]
        self.profile = dict(transition_update_seconds=0., candidate_load_update_seconds=0.,
                            spatial_update_seconds=0., reduction_geometry_seconds=0., changed_edges=0)

    def weights(self, ci, order, positions):
        ids = order[positions]
        dest = np.array([self.xy[order[j+1]] if j+1 < len(order) else self.outputs[ci] for j in positions])
        pin = np.array([self.sink[order[j+1]] if j+1 < len(order) else self.so_extra[ci] for j in positions])
        edge = pin+self.rho*np.abs(self.xy[ids]-dest).sum(axis=1)
        weights = self.influence_weights[ids].copy()
        weights[:, 0] += edge
        return self.influence_bins[ids].copy(), weights

    def input_weight(self, ci, order):
        return self.si_extra[ci]+self.sink[order[0]]+self.rho*np.abs(self.inputs[ci]-self.xy[order[0]]).sum()


@njit(cache=True)
def diagonals(load, response, order, longest):
    m = len(order)
    d = np.empty((len(load), 2, longest+m-1), np.int8)
    for p in range(len(load)):
        for phase in range(2):
            for r in range(1-m, longest):
                d[p, phase, r+m-1] = v2.coefficient(load, response, order, p, phase, r, longest)
    return d


@njit(cache=True)
def add_chain(field, d, bins, weights):
    m = len(bins)
    for p in range(len(field)):
        for phase in range(2):
            for j in range(m):
                for t in range(field.shape[2]):
                    if d[p, phase, t-j+m-1]:
                        for k in range(weights.shape[1]):
                            field[p, phase, t, bins[j, k]] += weights[j, k]


@njit(cache=True)
def change_diagonals(d, load, response, order, dirty, longest):
    delta = np.empty((len(load), 2, len(dirty)), np.int8)
    m = len(order)
    for p in range(len(load)):
        for phase in range(2):
            for z in range(len(dirty)):
                r = dirty[z]
                value = v2.coefficient(load, response, order, p, phase, r, longest)
                delta[p, phase, z] = value-d[p, phase, r+m-1]
                d[p, phase, r+m-1] = value
    return delta


@njit(cache=True)
def change_field(field, d, delta, dirty, bins, weights, positions, new_bins, new_weights):
    m, longest = len(bins), field.shape[2]
    for p in range(len(field)):
        for phase in range(2):
            for z in range(len(dirty)):
                r, change = dirty[z], delta[p, phase, z]
                if change:
                    for j in range(max(0, -r), min(m, longest-r)):
                        for k in range(weights.shape[1]):
                            field[p, phase, r+j, bins[j, k]] += change*weights[j, k]
            for z in range(len(positions)):
                j = positions[z]
                for t in range(longest):
                    if d[p, phase, t-j+m-1]:
                        for k in range(weights.shape[1]):
                            field[p, phase, t, bins[j, k]] -= weights[j, k]
                            field[p, phase, t, new_bins[z, k]] += new_weights[z, k]
    for z in range(len(positions)):
        bins[positions[z]] = new_bins[z]
        weights[positions[z]] = new_weights[z]


def input_transitions(model, order):
    serial = np.pad(model.load[:, order[::-1]], ((0, 0), (model.longest-len(order), 0)))
    values = np.zeros((len(model.load), 2, model.longest), np.uint8)
    values[:, 0] = serial ^ np.pad(serial[:, :-1], ((0, 0), (1, 0)))
    # SI retains its final load value through capture, then switches to zero.
    values[:, 1, 0] = serial[:, -1]
    return values


class State:
    def __init__(self, model, orders):
        model.validate(orders)
        self.costs, self.orders = model, [o.copy() for o in orders]
        self.field = np.zeros((len(model.load), 2, model.longest, 64))
        self.ds, self.bins, self.weights, self.port_fields = [], [], [], []
        for ci, o in enumerate(orders):
            bs, ws = model.weights(ci, o, np.arange(len(o)))
            d = diagonals(model.load, model.response, o, model.longest)
            add_chain(self.field, d, bs, ws)
            pf = input_transitions(model, o)*model.input_weight(ci, o)
            self.field[..., model.port_bins[ci]] += pf
            self.port_fields.append(pf)
            self.ds.append(d); self.bins.append(bs); self.weights.append(ws)
        locate(self)

    def change(self, patch):
        model, undo = self.costs, {}
        for ci, (positions, nodes) in patch.items():
            o = self.orders[ci]
            positions = np.asarray(positions, np.int32)
            undo[ci] = positions, o[positions].copy()
            o[positions] = nodes
            # A moved successor changes its predecessor's load even if that FF stays.
            affected = np.unique(np.r_[positions, positions[positions > 0]-1]).astype(np.int32)
            tick = time.perf_counter()
            bs, ws = model.weights(ci, o, affected)
            model.profile['candidate_load_update_seconds'] += time.perf_counter()-tick
            model.profile['changed_edges'] += len(affected)
            dirty = np.array(sorted({r for j in positions for r in
                (model.longest-1-int(j), model.longest-int(j), -int(j)-1, -int(j))
                if 1-len(o) <= r < model.longest}), np.int32)
            tick = time.perf_counter()
            delta = change_diagonals(self.ds[ci], model.load, model.response, o, dirty, model.longest)
            model.profile['transition_update_seconds'] += time.perf_counter()-tick
            tick = time.perf_counter()
            change_field(self.field, self.ds[ci], delta, dirty, self.bins[ci], self.weights[ci], affected, bs, ws)
            self.field[..., model.port_bins[ci]] -= self.port_fields[ci]
            self.port_fields[ci] = input_transitions(model, o)*model.input_weight(ci, o)
            self.field[..., model.port_bins[ci]] += self.port_fields[ci]
            model.profile['spatial_update_seconds'] += time.perf_counter()-tick
        return undo

    def score(self):
        tick = time.perf_counter()
        total, peak, peak4 = v2.reduce(self.field)
        wire, timing = self.costs.physical(self.orders)
        self.costs.profile['reduction_geometry_seconds'] += time.perf_counter()-tick
        return np.array([wire, total, peak, timing, peak4])


def reference(model, orders, source_local=False):
    """Independent simultaneous FF and SI replay; no diagonal update kernels."""
    _, counts = v2.reference(model.frozen, orders, True)
    flat = counts.reshape(-1, len(model.names))
    weights = model.static.copy()
    for ci, order in enumerate(orders):
        for j, node in enumerate(order):
            if j+1 < len(order):
                target, pin = model.xy[order[j+1]], model.sink[order[j+1]]
            else:
                target, pin = model.outputs[ci], model.so_extra[ci]
            weights[node, model.bins[node]] += pin+model.rho*np.abs(model.xy[node]-target).sum()
    if source_local:
        totals = weights.sum(axis=1)
        weights[:] = 0
        weights[np.arange(len(model.names)), model.bins] = totals
    field = flat @ weights
    for ci, order in enumerate(orders):
        toggles = np.zeros((len(model.load), 2, model.longest))
        for p in range(len(model.load)):
            previous = 0
            for phase in range(2):
                for t in range(model.longest):
                    idx = model.longest-1-t
                    bit = int(model.load[p, order[idx]]) if phase == 0 and idx < len(order) else 0
                    toggles[p, phase, t] = bit ^ previous
                    previous = bit
        cap = model.si_extra[ci]+model.sink[order[0]]+model.rho*np.abs(model.inputs[ci]-model.xy[order[0]]).sum()
        field[:, model.port_bins[ci]] += toggles.reshape(-1)*cap
    total, peak, peak4 = v2.reduce(field.reshape(len(model.load), 2, model.longest, 64))
    wire, timing = model.physical(orders)
    return np.array([wire, total, peak, timing, peak4])


def select(rows, measured_baselines, limit=3):
    """Only strict predicted frontier extensions against every measured seed.

    Greedily cover largest relative improvement over an existing frontier point
    without worsening its other two coordinates. No quota-filling or scalar E/H.
    """
    if not 1 <= limit <= 3: raise ValueError('Route limit must be 1–3')
    base = [r['score'][:3] for r in measured_baselines]
    eligible = [r for r in rows if r['new'] and not any(dominates(b, r['score'][:3]) or
                np.allclose(b, r['score'][:3], rtol=1e-9, atol=1e-8) for b in base)]
    def improvement(row):
        values = [(np.max((b-row['score'][:3])/np.maximum(b, 1e-12)), k)
                  for k, b in enumerate(base) if dominates(row['score'][:3], b)]
        return max(values, default=(0., -1))
    eligible.sort(key=lambda r: (-improvement(r)[0], v2.order_id(r['orders'])))
    chosen = []
    for row in eligible[:limit]:
        gain, k = improvement(row)
        reason = ('predicted_dominates:'+measured_baselines[k]['label']) if k >= 0 else 'predicted_new_tradeoff'
        chosen.append(dict(row, roles=[reason]))
    return chosen
