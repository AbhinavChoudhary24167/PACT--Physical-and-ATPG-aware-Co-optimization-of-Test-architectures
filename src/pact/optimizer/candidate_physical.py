"""Interpretable, baseline-derived electrical decomposition; no measured labels."""
import ast
from functools import lru_cache
import itertools
import re
import numpy as np
from pact.physical_effect import spatial_bin


def hpwl(points):
    return float(np.ptp(np.asarray(points), axis=0).sum()) if len(points) > 1 else 0.


@lru_cache(None)
def sensitivity(expression):
    """Uniform Boolean input sensitivity from Liberty, with a restricted AST."""
    tree = ast.parse(expression.replace('!', '~').replace('*', '&').replace('+', '|'), mode='eval')
    pins = sorted({n.id for n in ast.walk(tree) if isinstance(n, ast.Name)})
    if len(pins) > 8:
        raise ValueError('Unbounded library function')
    def evaluate(n, values):
        if isinstance(n, ast.Expression): return evaluate(n.body, values)
        if isinstance(n, ast.Name): return values[n.id]
        if isinstance(n, ast.Constant) and n.value in (0, 1): return n.value
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Invert): return 1 ^ evaluate(n.operand, values)
        if isinstance(n, ast.BinOp):
            a, b = evaluate(n.left, values), evaluate(n.right, values)
            if isinstance(n.op, ast.BitAnd): return a & b
            if isinstance(n.op, ast.BitOr): return a | b
            if isinstance(n.op, ast.BitXor): return a ^ b
        raise ValueError('Unsupported Liberty Boolean expression: '+expression)
    result = dict.fromkeys(pins, 0.)
    for bits in itertools.product((0, 1), repeat=len(pins)):
        values = dict(zip(pins, bits))
        a = evaluate(tree, values)
        for pin in pins:
            values[pin] ^= 1
            result[pin] += (a != evaluate(tree, values))/2**len(pins)
            values[pin] ^= 1
    return result


def construct(model, graph, caprows):
    """Partition mixed nets using retained functional HPWL / total HPWL.

    Pin partition is exact. Ground partition is a documented geometric estimate.
    Scan-exclusive transparent branches are removed, including their buffer pins.
    """
    nets, cells = graph['nets'], graph['cells']
    caps = {r['net']: float(r['pin_ff'])+float(r['ground_ff'] or 0) for r in caprows}
    ground = {r['net']: float(r['ground_ff'] or 0) for r in caprows}
    extracted = {r['net'] for r in caprows if r['ground_ff']}
    for n, d in nets.items():
        if n not in caps or not np.isfinite(caps[n]) or ground[n] < 0:
            raise ValueError('Missing/invalid reference capacitance: '+n)
        if not np.isclose(sum(s['cap'] for s in d['sinks']), caps[n]-ground[n], rtol=1e-8, atol=1e-8):
            raise ValueError('Topology/Liberty pin sum differs from measured reference: '+n)
    roots = {n: [net for net, data in nets.items() if data['source'] in (n+'/Q', n+'/QN')] for n in model.names}
    if any(not any(nets[k]['source'] == n+'/Q' for k in ns) for n, ns in roots.items()):
        raise ValueError('Missing FF Q root')
    def children(sink):
        c = cells[sink['cell']]
        return list(c['outputs'].values()) if c['transparent'] else []
    active = set()
    @lru_cache(None)
    def functional(net):
        if net in active: raise ValueError('Transparent cycle')
        active.add(net)
        d = nets[net]
        kept = [s for s in d['sinks'] if not (s['cell'] in model.index and s['pin'] == 'SI')
                and (not children(s) or any(functional(k) for k in children(s)))]
        ports = [p for p in d['ports'] if not p['name'].startswith('test_so')]
        active.remove(net)
        return bool(kept or ports)
    def closure(net):
        pending, seen = [net], set()
        while pending:
            n = pending.pop()
            if n in seen: continue
            seen.add(n)
            pending.extend(k for s in nets[n]['sinks'] for k in children(s))
        return seen
    owned, source_nets = {}, {}
    for name in model.names:
        ns = set().union(*(closure(n) for n in roots[name]))
        source_nets[name] = ns
        for n in ns:
            if n in owned and owned[n] != name: raise ValueError('Competing transparent owners')
            owned[n] = name
    scan_reachable = set(owned)
    for n, d in nets.items():
        if d['source'].startswith('PORT/test_si'): scan_reachable |= closure(n)
    samples = []
    for n in sorted(scan_reachable):
        d = nets[n]
        if functional(n) or n not in extracted or len(d['sinks'])+len(d['ports']) != 1: continue
        length = hpwl([d['xy']]+[s['xy'] for s in d['sinks']]+[p['xy'] for p in d['ports']])
        if length > 0 and ground[n] > 0:
            samples.append(dict(net=n, ground_ff=ground[n], distance_um=length, ff_per_um=ground[n]/length))
    if not samples: raise ValueError('No qualified scan-only wire-capacitance samples')
    rho = float(np.median([s['ff_per_um'] for s in samples]))
    portions, decomposed = {}, []
    for n in sorted(owned):
        d = nets[n]
        kept = [s for s in d['sinks'] if not (s['cell'] in model.index and s['pin'] == 'SI')
                and (not children(s) or any(functional(k) for k in children(s)))]
        ports = [p for p in d['ports'] if not p['name'].startswith('test_so')]
        full = hpwl([d['xy']]+[s['xy'] for s in d['sinks']]+[p['xy'] for p in d['ports']])
        retained = hpwl([d['xy']]+[s['xy'] for s in kept]+[p['xy'] for p in ports])
        fraction = min(1., retained/full) if full else float(bool(kept or ports))
        value = sum(s['cap'] for s in kept)+ground[n]*fraction
        if value > caps[n]+1e-6: raise ValueError('Functional decomposition exceeds total')
        portions[n] = value
        decomposed.append(dict(net=n, source=owned[n], total_ff=caps[n], functional_ff=value,
            removed_scan_ff=caps[n]-value, functional_wire_fraction=fraction,
            functional_pins=[s['cell']+'/'+s['pin'] for s in kept]))
    influence = {name: {} for name in model.names}
    for n, name in owned.items():
        if portions[n]: influence[name][n] = portions[n]
    # One nontransparent combinational gate after the FF transparent closure.
    # Shared output demand is normalized to avoid counting a full net per input.
    for cname, cell in cells.items():
        if cell['transparent'] or cname in model.index: continue
        for pin, out in cell['outputs'].items():
            expr = graph['functions'].get(cell['master']+'/'+pin)
            if not expr or out not in nets: continue
            sens = sensitivity(expr)
            by_source = {}
            for inp, net in cell['inputs'].items():
                if net in owned and inp in sens:
                    name = owned[net]
                    by_source[name] = min(1., by_source.get(name, 0.)+sens[inp])
            norm = max(1., sum(by_source.values()))
            for name, value in by_source.items():
                for net in closure(out):
                    if net in owned: raise ValueError('Combinational path reaches an FF-driven net')
                    influence[name][net] = max(influence[name].get(net, 0.), caps[net]*value/norm)
    spatial = np.zeros((len(model.names), 64))
    records = []
    for i, name in enumerate(model.names):
        for net, value in sorted(influence[name].items()):
            b = spatial_bin(nets[net]['xy'], graph['bounds'], 8)
            spatial[i, b] += value
            records.append(dict(source=name, net=net, cap_ff=value, bin8=b,
                                kind='functional_transparent' if net in owned else 'one_gate_influence'))
    sink = []
    for name in model.names:
        matches = [s['cap'] for d in nets.values() for s in d['sinks'] if s['cell'] == name and s['pin'] == 'SI']
        if len(matches) != 1: raise ValueError('Missing/ambiguous SI capacitance')
        sink.append(matches[0])
    # Retain real scan-exclusive buffer input capacitance for port chains only.
    # Other scan repair buffers are omitted and may be reinserted by routing.
    si_extra, so_extra = [], []
    for chain in model.architecture.chains:
        # Canonical architecture C00 uses *_0; the frozen physical BTerms omit it.
        si_name = 'test_si' if chain.scan_in == 'test_si_0' else chain.scan_in
        so_name = 'test_so' if chain.scan_out == 'test_so_0' else chain.scan_out
        si_root = next(n for n, d in nets.items() if d['source'] == 'PORT/'+si_name)
        si_ns = closure(si_root)
        si_extra.append(sum(s['cap'] for n in si_ns for s in nets[n]['sinks'] if children(s)))
        tail_ns = source_nets[chain.cells[-1]]
        @lru_cache(None)
        def reaches_so(n):
            return any(p['name'] == so_name for p in nets[n]['ports']) or any(
                reaches_so(k) for s in nets[n]['sinks'] for k in children(s))
        so_extra.append(sum(s['cap'] for n in tail_ns for s in nets[n]['sinks']
                            if children(s) and any(reaches_so(k) for k in children(s))))
    return dict(rho=rho, sink=sink, spatial=spatial.tolist(), si_extra=si_extra, so_extra=so_extra,
        calibration=dict(method='median ground_ff / Manhattan length of extracted scan-only single-sink nets',
                         samples=samples, ff_per_um=rho), decomposition=decomposed, influence=records,
        missing_ground_nets=sorted(set(caps)-extracted),
        assumptions='Ground partition uses functional/total HPWL; one-gate uniform Boolean sensitivity; shared-source normalization; no glitches or resizing prediction')
