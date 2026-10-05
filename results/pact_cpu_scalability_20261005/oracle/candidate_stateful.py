"""Bounded exact simultaneous-state propagation with shared-net capacitance."""
import ast
import hashlib
import heapq
import itertools
import json
import time
import numpy as np
from numba import njit
from pact.physical_effect import spatial_bin
from . import implementation_v2 as v2
from .candidate_sensitive import diagonals, change_diagonals
from .stateful_geometry import Geometry
from .search import locate

METRICS = ('wire_um', 'E_stateful_ff', 'H8_stateful_ff', 'timing_max_edge_um', 'H4_stateful_ff')


def expression(text):
    tree = ast.parse(text.replace('!', '~').replace('*', '&').replace('+', '|'), mode='eval').body
    def convert(n):
        if isinstance(n, ast.Name): return ('pin', n.id)
        if isinstance(n, ast.Constant) and n.value in (0, 1): return ('const', int(n.value))
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Invert): return ('not', convert(n.operand))
        if isinstance(n, ast.BinOp):
            kind = {ast.BitAnd: 'and', ast.BitOr: 'or', ast.BitXor: 'xor'}.get(type(n.op))
            if kind: return (kind, convert(n.left), convert(n.right))
        raise ValueError('Unsupported exact library function: '+text)
    program = convert(tree)
    pins = sorted({n.id for n in ast.walk(tree) if isinstance(n, ast.Name)})
    # Independent truth-table reference uses scalar evaluation during compilation.
    def scalar(p, values):
        if p[0] == 'pin': return values[p[1]]
        if p[0] == 'const': return p[1]
        if p[0] == 'not': return 1-scalar(p[1], values)
        a, b = scalar(p[1], values), scalar(p[2], values)
        return {'and': a & b, 'or': a | b, 'xor': a ^ b}[p[0]]
    truth = np.zeros(2**len(pins), np.uint8)
    for bits in itertools.product((0, 1), repeat=len(pins)):
        index = sum(bit << j for j, bit in enumerate(bits))
        truth[index] = scalar(program, dict(zip(pins, bits)))
    return program, pins, truth


def packed_function(program, values, size):
    kind = program[0]
    if kind == 'pin': return values[program[1]]
    if kind == 'const': return np.full(size, 255 if program[1] else 0, np.uint8)
    if kind == 'not': return np.bitwise_not(packed_function(program[1], values, size))
    a, b = packed_function(program[1], values, size), packed_function(program[2], values, size)
    if kind == 'and': return a & b
    if kind == 'or': return a | b
    return a ^ b


@njit(cache=True)
def packed_scan(load, response, order, longest):
    """Closed-form shift states, three settled snapshots per measured cycle."""
    cycles = len(load)*2*longest
    packed = np.zeros((len(order), (cycles*3+7)//8), np.uint8)
    for j in range(len(order)):
        for p in range(len(load)):
            for phase in range(2):
                for t in range(longest):
                    if phase == 0:
                        before = int(load[p, order[longest-t+j]]) if 0 <= longest-t+j < len(order) else 0
                        after = int(load[p, order[longest-t-1+j]]) if 0 <= longest-t-1+j < len(order) else 0
                    else:
                        before = int(response[p, order[j-t]]) if j >= t else 0
                        after = int(response[p, order[j-t-1]]) if j > t else 0
                    pos = ((p*2+phase)*longest+t)*3
                    for k in range(3):
                        bit = before if k < 2 else after
                        if bit: packed[j, (pos+k)//8] |= 1 << ((pos+k)%8)
    return packed


def packed_input(model, order):
    serial = np.pad(model.load[:, order[::-1]], ((0, 0), (model.longest-len(order), 0)))
    wave = np.zeros((len(model.load), 2, model.longest, 3), np.uint8)
    wave[:, 0, :, 0] = np.pad(serial[:, :-1], ((0, 0), (1, 0)))
    wave[:, 0, :, 1:] = serial[..., None]
    wave[:, 1, 0, 0] = serial[:, -1]
    return np.packbits(wave.reshape(-1), bitorder='little')


@njit(cache=True)
def update_field(field, old, new, oldcap, newcap, bin_id):
    count = 0
    for t in range(len(field)):
        a = t*3
        ob = (old[a//8] >> (a%8)) & 1
        om = (old[(a+1)//8] >> ((a+1)%8)) & 1
        oa = (old[(a+2)//8] >> ((a+2)%8)) & 1
        nb = (new[a//8] >> (a%8)) & 1
        nm = (new[(a+1)//8] >> ((a+1)%8)) & 1
        na = (new[(a+2)//8] >> ((a+2)%8)) & 1
        nc = (nb ^ nm)+(nm ^ na)
        oc = (ob ^ om)+(om ^ oa)
        field[t, bin_id] += nc*newcap-oc*oldcap
        count += nc
    return count*newcap


class Model(v2.Model):
    def __init__(self, sensitive, graph, caprows, primary, depth=3):
        if not isinstance(depth, int) or depth < 0: raise ValueError('Invalid logic-depth bound')
        self.__dict__.update(sensitive.frozen.__dict__)
        self.sensitive, self.frozen, self.graph, self.depth = sensitive, sensitive.frozen, graph, depth
        self.geometry = Geometry(self, graph, caprows, sensitive.rho)
        self.cycles = len(self.load)*2*self.longest
        self.wave_bytes = (self.cycles*3+7)//8
        self.roots, self.root_depth, self.constant_waves = {}, {}, {}
        self.ff_roots = {i: [] for i in range(len(self.names))}
        self.si_roots = {}
        self.so_roots = self.geometry.so_alias.copy()
        nets = graph['nets']
        for n, d in nets.items():
            source = d['source']
            c, pin = source.rsplit('/', 1)
            if c in self.index and pin in ('Q', 'QN'):
                self.roots[n] = ('ff', self.index[c], int(pin == 'QN'))
                self.ff_roots[self.index[c]].append(n)
            elif c == 'PORT':
                if pin.startswith('test_si'):
                    ci = 0 if pin == 'test_si' else int(pin.rsplit('_', 1)[1])
                    self.roots[n] = ('si', ci, 0); self.si_roots[ci] = n
                else:
                    bits = primary.get(pin)
                    if pin == 'test_se': bits = np.ones(len(self.load), np.uint8)
                    if bits is None: continue
                    bits = np.asarray(bits)
                    if bits.shape != (len(self.load),) or not np.isin(bits, (0, 1)).all():
                        raise ValueError('Complete binary primary input states required: '+pin)
                    wave = np.broadcast_to(bits[:, None, None, None], (len(bits), 2, self.longest, 3))
                    self.constant_waves[n] = np.packbits(wave.reshape(-1), bitorder='little')
                    self.roots[n] = ('constant', 0, 0)
        for n, (ci, parity) in self.so_roots.items(): self.roots[n] = ('so', ci, parity)
        self.root_depth = dict.fromkeys(self.roots, 0)
        candidates = {}
        for cname, cell in graph['cells'].items():
            if cname in self.index: continue
            for pin, net in cell['outputs'].items():
                if net not in nets or net in self.roots: continue
                formula = graph['functions'].get(cell['master']+'/'+pin)
                if formula is None: continue
                program, pins, truth = expression(formula)
                if any(p not in cell['inputs'] for p in pins): raise ValueError('Missing truth-function fanin')
                candidates[net] = dict(net=net, cell=cname, program=program, pins=pins,
                    fanins={p: cell['inputs'][p] for p in pins}, truth=truth,
                    transparent=cell['transparent'])
        self.gates, depths = [], self.root_depth.copy()
        while True:
            ready = []
            for net, gate in candidates.items():
                fan = list(gate['fanins'].values())
                if all(n in depths for n in fan):
                    level = max((depths[n] for n in fan), default=0)+(0 if gate['transparent'] or not fan else 1)
                    if level <= depth: ready.append((level, net))
            if not ready: break
            for level, net in sorted(ready):
                gate = candidates.pop(net)
                gate['depth'] = level; depths[net] = level; self.gates.append(gate)
        self.represented = sorted(depths)
        self.consumers = {n: [] for n in self.represented}
        reach = {n: ({self.roots[n][1]} if self.roots[n][0] == 'ff' else set()) for n in self.roots}
        for k, gate in enumerate(self.gates):
            net = gate['net']
            reach[net] = set().union(*(reach[n] for n in gate['fanins'].values()))
            for n in set(gate['fanins'].values()): self.consumers[n].append(k)
        self.bins_by_net = {n: spatial_bin(nets[n]['xy'], graph['bounds'], 8) for n in self.represented}
        self.metadata = dict(depth_bound=depth, represented_nets=len(self.represented),
            gates_at_depth={str(d): sum(g['depth'] == d for g in self.gates) for d in range(depth+1)},
            transparent_gates=sum(g['transparent'] for g in self.gates), SO_alias_nets=len(self.so_roots),
            excluded_gates={n: 'depth_limit_or_unrepresented_fanin' for n in sorted(candidates)},
            ff_to_gate_reachability={self.names[i]: sum(i in reach[g['net']] for g in self.gates) for i in range(len(self.names))},
            represented_Q=sum(n.endswith('/Q') for n in (nets[k]['source'] for k in self.represented)),
            represented_QN=sum(n.endswith('/QN') for n in (nets[k]['source'] for k in self.represented)),
            simultaneous_inputs=True, transition_schedule='before SI / settled SI / settled FF per shift cycle',
            limitations='No delta-cycle glitches, delay, candidate resizing or buffer insertion; unrepresented fanins excluded; fixed baseline buffer skeleton')
        self.profile = dict(stateful_propagation_seconds=0., scan_waveform_seconds=0.,
            geometry_seconds=0., spatial_seconds=0., reduction_seconds=0., rollback_seconds=0.)
        self.last_mutation = {}
        self.canonical_cells = json.dumps(self.architecture.canonical_dict()['cells'], sort_keys=True, separators=(',', ':'))

    def canonical_id(self, orders):
        chains = [dict(chain_id=c.chain_id, cells=[self.names[int(i)] for i in o], scan_in=c.scan_in, scan_out=c.scan_out)
                  for c, o in zip(self.architecture.chains, orders)]
        body = '{"cells":'+self.canonical_cells+',"chains":'+json.dumps(sorted(chains, key=lambda c: c['chain_id']),
            sort_keys=True, separators=(',', ':'))+',"schema_version":"0.1"}'
        return hashlib.sha256(body.encode()).hexdigest()


class Transaction(dict):
    pass


class State:
    def __init__(self, model, orders):
        model.validate(orders)
        self.costs, self.orders = model, [o.copy() for o in orders]
        self.field = np.zeros((model.cycles, 64))
        self.waves, self.energy = {}, {}
        self.caps = model.geometry.capacitances(orders)
        self.endpoints = model.geometry.terminal_sets(orders)
        self.ds = [diagonals(model.load, model.response, o, model.longest) for o in orders]
        for o in orders:
            waves = packed_scan(model.load, model.response, o, model.longest)
            for j, node in enumerate(o):
                for n in model.ff_roots[int(node)]:
                    parity = model.roots[n][2]
                    self.waves[n] = ~waves[j] if parity else waves[j]
        self.waves.update(model.constant_waves)
        for ci, n in model.si_roots.items(): self.waves[n] = packed_input(model, orders[ci])
        for n, (ci, parity) in model.so_roots.items():
            q = self.waves[model.geometry.q[model.names[orders[ci][-1]]]]
            self.waves[n] = ~q if parity else q
        for g in model.gates:
            self.waves[g['net']] = packed_function(g['program'], {p: self.waves[n] for p, n in g['fanins'].items()}, model.wave_bytes)
        zero = np.zeros(model.wave_bytes, np.uint8)
        for n in model.represented:
            self.energy[n] = update_field(self.field, zero, self.waves[n], 0., self.caps[n], model.bins_by_net[n])
        locate(self)
        model.current_state = self

    def change(self, patch):
        model = self.costs
        model.current_state = self
        if isinstance(patch, Transaction):
            tick = time.perf_counter()
            for n, old in patch.waves.items():
                self.energy[n] = update_field(self.field, self.waves[n], old, self.caps[n], patch.caps.get(n, self.caps[n]), model.bins_by_net[n])
                self.waves[n] = old
            for n, cap in patch.caps.items():
                if n not in patch.waves and n in self.waves:
                    self.energy[n] = update_field(self.field, self.waves[n], self.waves[n], self.caps[n], cap, model.bins_by_net[n])
                self.caps[n] = cap
            for ci, (positions, nodes) in patch.items(): self.orders[ci][positions] = nodes
            for ci, d in patch.ds.items(): self.ds[ci] = d
            self.endpoints = patch.endpoints
            model.profile['rollback_seconds'] += time.perf_counter()-tick
            return None
        undo = Transaction()
        undo.waves, undo.caps, undo.ds, undo.endpoints = {}, {}, {}, self.endpoints
        old_tails = [int(o[-1]) for o in self.orders]
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
            waves = packed_scan(model.load, model.response, o, model.longest)
            for j, node in enumerate(o):
                ff_changed = False
                for n in model.ff_roots[int(node)]:
                    parity = model.roots[n][2]
                    ff_changed |= put(n, ~waves[j] if parity else waves[j])
                stats['FF_waveform_changes'] += int(ff_changed)
            put(model.si_roots[ci], packed_input(model, o))
        for n, (ci, parity) in model.so_roots.items():
            if ci in patch:
                q = self.waves[model.geometry.q[model.names[self.orders[ci][-1]]]]
                put(n, ~q if parity else q)
        stats['root_waveform_changes'] = len(changed)
        model.profile['scan_waveform_seconds'] += time.perf_counter()-tick
        tick = time.perf_counter()
        pending = sorted({g for n in changed for g in model.consumers[n]})
        queued = set(pending); heapq.heapify(pending)
        while pending:
            k = heapq.heappop(pending)
            g = model.gates[k]; n = g['net']
            wave = packed_function(g['program'], {p: self.waves[v] for p, v in g['fanins'].items()}, model.wave_bytes)
            stats['gate_recomputations'] += 1
            if put(n, wave):
                stats['propagated_waveform_changes'] += 1
                for child in model.consumers[n]:
                    if child not in queued: queued.add(child); heapq.heappush(pending, child)
            else: stats['cancellation_events'] += 1
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
        for n in sorted(changed | (set(undo.caps) & set(self.waves))):
            self.energy[n] = update_field(self.field, undo.waves.get(n, self.waves[n]), self.waves[n],
                undo.caps.get(n, self.caps[n]), self.caps[n], model.bins_by_net[n])
        model.profile['spatial_seconds'] += time.perf_counter()-tick
        model.last_mutation, model.last_geometry = stats, changes
        return undo

    def score(self):
        tick = time.perf_counter()
        total, peak, peak4 = v2.reduce(self.field.reshape(len(self.costs.load), 2, self.costs.longest, 64))
        wire, timing = self.costs.physical(self.orders)
        self.costs.profile['reduction_seconds'] += time.perf_counter()-tick
        return np.array([wire, total, peak, timing, peak4])

    def contributions(self):
        result = dict(Q=0., QN=0., SI=0., SO_buffers=0., combinational=0., primary_inputs=0.)
        for n, energy in self.energy.items():
            root = self.costs.roots.get(n)
            kind = 'combinational'
            if root:
                kind = {'ff': 'QN' if root[2] else 'Q', 'si': 'SI', 'so': 'SO_buffers', 'constant': 'primary_inputs'}[root[0]]
            result[kind] += energy
        return result


def reference(model, orders, return_waves=False):
    """Full bounded rebuild: simultaneous scan simulation + Boolean truth lookup.

    No packed state, propagation, diagonal or field-update kernel is reused.
    """
    model.validate(orders)
    pcount, n = model.load.shape
    q = np.zeros((n, pcount, 2, model.longest, 3), np.uint8)
    si = np.zeros((len(orders), pcount, 2, model.longest, 3), np.uint8)
    for p in range(pcount):
        previous_si = np.zeros(len(orders), np.uint8)
        for phase in range(2):
            state = np.zeros(n, np.uint8) if phase == 0 else model.response[p].copy()
            for t in range(model.longest):
                nxt = state.copy()
                q[:, p, phase, t, 0] = state; q[:, p, phase, t, 1] = state
                for ci, order in enumerate(orders):
                    index = model.longest-1-t
                    bit = model.load[p, order[index]] if phase == 0 and index < len(order) else 0
                    si[ci, p, phase, t] = (previous_si[ci], bit, bit)
                    previous_si[ci] = bit
                    nxt[order[0]] = bit; nxt[order[1:]] = state[order[:-1]]
                q[:, p, phase, t, 2] = nxt
                state = nxt
    waves = {}
    for net, (kind, i, polarity) in model.roots.items():
        if kind == 'ff': waves[net] = q[i].reshape(-1, 3) ^ polarity
        elif kind == 'si': waves[net] = si[i].reshape(-1, 3)
        elif kind == 'so': waves[net] = q[orders[i][-1]].reshape(-1, 3) ^ polarity
        else: waves[net] = np.unpackbits(model.constant_waves[net], bitorder='little')[:model.cycles*3].reshape(-1, 3)
    for gate in model.gates:
        index = np.zeros((model.cycles, 3), np.uint8)
        for j, pin in enumerate(gate['pins']): index |= waves[gate['fanins'][pin]] << j
        waves[gate['net']] = gate['truth'][index]
    caps = model.geometry.capacitances(orders)
    field = np.zeros((model.cycles, 64))
    for net, wave in waves.items():
        toggles = (wave[:, 0] ^ wave[:, 1])+(wave[:, 1] ^ wave[:, 2])
        field[:, model.bins_by_net[net]] += toggles*caps[net]
    coarse = field.reshape(-1, 4, 2, 4, 2).sum(axis=(2, 4))
    wire, timing = model.physical(orders)
    score = np.array([wire, field.sum(), field.max(), timing, coarse.max()])
    return (score, waves, field) if return_waves else score
