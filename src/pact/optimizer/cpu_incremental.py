"""Exact CPU tile updates and reversible stateful transactions.

The original candidate_stateful evaluator remains the independent oracle.
Physical source bins and the represented Boolean graph are unchanged. Columns
are contiguous so a changed source walks one tile, without striding across 64
tiles. Rejection restores affected tiles once, without replaying every source.
"""
import heapq
import time
import numpy as np
from numba import njit

from . import candidate_stateful as oracle
from .candidate_sensitive import change_diagonals


@njit(cache=True)
def transition_count(wave, cycles):
    count = 0
    for t in range(cycles):
        a = t*3
        before = (wave[a//8] >> (a%8)) & 1
        middle = (wave[(a+1)//8] >> ((a+1)%8)) & 1
        after = (wave[(a+2)//8] >> ((a+2)%8)) & 1
        count += (before ^ middle) + (middle ^ after)
    return count


@njit(cache=True)
def update_tile(tile, old, new, oldcap, newcap, count):
    """Skip equal packed blocks, preserving every changed cycle's arithmetic."""
    for first in range(0, len(old), 3):
        ob, nb = 0, 0
        for byte in range(min(3, len(old)-first)):
            ob |= int(old[first+byte]) << (8*byte)
            nb |= int(new[first+byte]) << (8*byte)
        if ob == nb and oldcap == newcap:
            continue
        start = (first//3)*8
        for j in range(min(8, len(tile)-start)):
            offset = j*3
            oc = ((ob >> offset) ^ (ob >> (offset+1))) & 1
            oc += ((ob >> (offset+1)) ^ (ob >> (offset+2))) & 1
            nc = ((nb >> offset) ^ (nb >> (offset+1))) & 1
            nc += ((nb >> (offset+1)) ^ (nb >> (offset+2))) & 1
            delta = nc*newcap-oc*oldcap
            if delta:
                tile[start+j] += delta
            count += nc-oc
    return count


class State(oracle.State):
    def __init__(self, model, orders):
        super().__init__(model, orders)
        self.field = np.asfortranarray(self.field)
        self.transitions = {n: transition_count(self.waves[n], model.cycles) for n in model.represented}
        self.tile_total = np.zeros(64)
        self.tile_peak = np.zeros(64)
        self.coarse_peak = np.zeros(16)
        self.dirty_tiles = set(range(64))
        self._reduce_dirty()

    def _reduce_dirty(self):
        for b in sorted(self.dirty_tiles):
            self.tile_total[b] = self.field[:, b].sum()
            self.tile_peak[b] = max(0., self.field[:, b].max())
        # H4 uses the same four adjacent H8 cells and the same left-to-right
        # arithmetic as implementation_v2.reduce. No spatial approximation.
        coarse = {(b // 16) * 4 + (b % 8) // 2 for b in self.dirty_tiles}
        for c in sorted(coarse):
            b = (c // 4) * 16 + (c % 4) * 2
            values = self.field[:, b] + self.field[:, b+1] + self.field[:, b+8] + self.field[:, b+9]
            self.coarse_peak[c] = max(0., values.max())
        self.dirty_tiles.clear()

    def change(self, patch):
        model = self.costs
        model.current_state = self
        if isinstance(patch, oracle.Transaction):
            tick = time.perf_counter()
            for b, values in patch.tiles.items():
                self.field[:, b] = values
            for n, wave in patch.waves.items():
                self.waves[n] = wave
            self.caps.update(patch.caps)
            self.energy.update(patch.energy)
            self.transitions.update(patch.transitions)
            for ci, (positions, nodes) in patch.items():
                self.orders[ci][positions] = nodes
            for ci, d in patch.ds.items():
                self.ds[ci] = d
            self.endpoints = patch.endpoints
            self.tile_total[:], self.tile_peak[:], self.coarse_peak[:] = patch.reductions
            self.dirty_tiles = patch.dirty_tiles
            model.profile['rollback_seconds'] += time.perf_counter() - tick
            return None
        undo = oracle.Transaction()
        undo.waves, undo.caps, undo.ds, undo.endpoints = {}, {}, {}, self.endpoints
        undo.reductions = (self.tile_total.copy(), self.tile_peak.copy(), self.coarse_peak.copy())
        undo.dirty_tiles = self.dirty_tiles.copy()
        stats = dict(FF_waveform_changes=0, root_waveform_changes=0, gate_recomputations=0,
                     propagated_waveform_changes=0, cancellation_events=0, geometry_changes=0)
        changed = set()
        tick = time.perf_counter()
        for ci, (positions, nodes) in patch.items():
            positions = np.asarray(positions, np.int32)
            undo[ci] = (positions, self.orders[ci][positions].copy())
            undo.ds[ci] = self.ds[ci].copy()
            self.orders[ci][positions] = nodes
            dirty = np.array(sorted({r for j in positions for r in
                (model.longest-1-int(j), model.longest-int(j), -int(j)-1, -int(j))
                if 1-len(self.orders[ci]) <= r < model.longest}), np.int32)
            change_diagonals(self.ds[ci], model.load, model.response, self.orders[ci], dirty, model.longest)
        def put(n, wave):
            if not np.array_equal(self.waves[n], wave):
                undo.waves[n] = self.waves[n]
                self.waves[n] = wave
                changed.add(n)
                return True
            return False
        for ci in patch:
            o = self.orders[ci]
            waves = oracle.packed_scan(model.load, model.response, o, model.longest)
            for j, node in enumerate(o):
                ff_changed = False
                for n in model.ff_roots[int(node)]:
                    parity = model.roots[n][2]
                    ff_changed |= put(n, ~waves[j] if parity else waves[j])
                stats['FF_waveform_changes'] += int(ff_changed)
            put(model.si_roots[ci], oracle.packed_input(model, o))
        for n, (ci, parity) in model.so_roots.items():
            if ci in patch:
                q = self.waves[model.geometry.q[model.names[self.orders[ci][-1]]]]
                put(n, ~q if parity else q)
        stats['root_waveform_changes'] = len(changed)
        model.profile['scan_waveform_seconds'] += time.perf_counter()-tick
        tick = time.perf_counter()
        pending = sorted({g for n in changed for g in model.consumers[n]})
        queued = set(pending)
        heapq.heapify(pending)
        while pending:
            k = heapq.heappop(pending)
            g = model.gates[k]
            n = g['net']
            wave = oracle.packed_function(g['program'], {p: self.waves[v] for p, v in g['fanins'].items()}, model.wave_bytes)
            stats['gate_recomputations'] += 1
            if put(n, wave):
                stats['propagated_waveform_changes'] += 1
                for child in model.consumers[n]:
                    if child not in queued:
                        queued.add(child)
                        heapq.heappush(pending, child)
            else:
                stats['cancellation_events'] += 1
        model.profile['stateful_propagation_seconds'] += time.perf_counter()-tick
        tick = time.perf_counter()
        endpoints = model.geometry.terminal_sets(self.orders)
        changes = []
        for n, term in endpoints.items():
            if term != self.endpoints[n]:
                undo.caps[n] = self.caps[n]
                self.caps[n], audit = model.geometry.evaluate(n, term)
                changes.append(audit)
        self.endpoints = endpoints
        stats['geometry_changes'] = len(changes)
        model.profile['geometry_seconds'] += time.perf_counter()-tick
        tick = time.perf_counter()
        sources = sorted(changed | (set(undo.caps) & set(self.waves)))
        bins = sorted({model.bins_by_net[n] for n in sources})
        copy_tick = time.perf_counter()
        undo.tiles = {b: self.field[:, b].copy() for b in bins}
        undo.energy = {n: self.energy[n] for n in sources}
        undo.transitions = {n: self.transitions[n] for n in sources}
        model.profile['spatial_tile_copy_seconds'] = model.profile.get('spatial_tile_copy_seconds', 0.) + time.perf_counter()-copy_tick
        for n in sources:
            self.transitions[n] = update_tile(self.field[:, model.bins_by_net[n]],
                undo.waves.get(n, self.waves[n]), self.waves[n],
                undo.caps.get(n, self.caps[n]), self.caps[n], self.transitions[n])
            self.energy[n] = self.transitions[n]*self.caps[n]
        self.dirty_tiles.update(bins)
        model.profile['spatial_seconds'] += time.perf_counter()-tick
        model.last_mutation, model.last_geometry = stats, changes
        return undo

    def score(self):
        tick = time.perf_counter()
        self._reduce_dirty()
        total = self.tile_total.sum()
        peak, peak4 = self.tile_peak.max(), self.coarse_peak.max()
        wire, timing = self.costs.physical(self.orders)
        self.costs.profile['reduction_seconds'] += time.perf_counter()-tick
        return np.array([wire, total, peak, timing, peak4])
