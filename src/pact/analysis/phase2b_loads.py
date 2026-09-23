"""Pre-route load construction. This module never opens routed data or labels."""
from __future__ import annotations
import re
import numpy as np


def liberty_groups(text, kind):
    """Balanced Liberty groups; quoted braces and comments are ignored."""
    text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
    pattern = re.compile(r'\b' + re.escape(kind) + r'\s*\(\s*"?([^"()]+?)"?\s*\)\s*\{')
    for match in pattern.finditer(text):
        depth, quoted, escaped = 1, False, False
        for end in range(match.end(), len(text)):
            ch = text[end]
            if ch == '"' and not escaped: quoted = not quoted
            if not quoted:
                depth += (ch == '{') - (ch == '}')
            if depth == 0: break
            escaped = ch == '\\' and not escaped
        else: raise ValueError('Unbalanced Liberty group')
        yield match[1].strip(), text[match.end():end]


def pin_loads(text):
    unit = re.search(r'capacitive_load_unit\s*\(\s*([\d.eE+-]+)\s*,\s*(\w+)\s*\)', text)
    if unit is None or unit[2].lower() not in ('ff', 'pf'):
        raise ValueError('Unsupported/missing Liberty capacitance unit')
    scale = float(unit[1]) * (1000 if unit[2].lower() == 'pf' else 1)
    loads = {}
    for cell, body in liberty_groups(text, 'cell'):
        for pin, data in liberty_groups(body, 'pin'):
            if re.search(r'\bdirection\s*:\s*input\s*;', data):
                m = re.search(r'(?m)^\s*capacitance\s*:\s*([\d.eE+-]+)\s*;', data)
                if m is None:
                    raise ValueError(f'Missing input capacitance {cell}/{pin}')
                value = float(m[1]) * scale
                if not np.isfinite(value) or value < 0: raise ValueError('Invalid capacitance')
                loads[cell, pin] = value
    return loads


def hpwl(points):
    a = np.asarray(points, dtype=float)
    if len(a) < 2: return 0.
    return float(np.ptp(a, axis=0).sum())


def manhattan(a, b):
    return sum(abs(x-y) for x,y in zip(a,b))


def construct_weights(arch, graph, loads, ports, cap_per_um=0.103981):
    """Sparse FF-source weights, from a schema restricted to placed input data.

    Nets contain a driver and input sinks with cell-origin coordinates. Existing
    SI and scan-output terminals were removed during the placed-only export.
    Functional transparent branches remain distinct nets, with unique ownership.
    """
    if graph.get('stage') != 'POST-PLACEMENT' or set(graph) != {'stage','FFs','nets','transparent'}:
        raise ValueError('Predictor requires a placed-only graph, no route fields')
    for net in graph['nets'].values():
        if set(net) != {'driver_xy','sinks','ports'}:
            raise ValueError('Unexpected feature (possible target leakage)')
    names = sorted(c.name for c in arch.cells)
    xy = {c.name:(c.x_um,c.y_um) for c in arch.cells}
    extra = {n:[] for n in names}
    internal = dict.fromkeys(names, 0.)
    output = dict.fromkeys(names, 0.)
    for ci, chain in enumerate(arch.chains):
        for a,b in zip(chain.cells, chain.cells[1:]):
            internal[a] = manhattan(xy[a], xy[b])
            extra[a].append(dict(xy=xy[b], master=graph['FFs'][b]['master'], pin='SI'))
        tail = chain.cells[-1]
        so = 'test_so' if ci == 0 else f'test_so_{ci}'
        output[tail] = manhattan(xy[tail], ports[so])
        extra[tail].append(dict(xy=ports[so], master=None, pin=so))
    values = {key:[] for key in ('M0','M2_scan','M2_port','M3_load','M4_fanout','M4_pin',
        'M4_functional_fanout','M4_functional_pin','M5_hpwl','M5_star','M5_functional_hpwl')}
    owners = {}
    for name in names:
        roots = graph['FFs'][name]['roots']
        pending, seen = list(roots.values()), set()
        fan = pin = wire = star = ffan = fpin = fwire = 0.
        while pending:
            netname = pending.pop()
            if netname in seen: continue
            seen.add(netname)
            if netname in owners and owners[netname] != name: raise ValueError('Competing FF owners')
            owners[netname] = name
            net = graph['nets'][netname]
            sinks = net['sinks']
            points = [net['driver_xy']] + [s['xy'] for s in sinks] + net['ports']
            ffan += len(sinks)
            fpin += sum(loads[s['master'],s['pin']] for s in sinks)
            fwire += hpwl(points)
            additions = extra[name] if netname == roots['Q'] else []
            all_sinks = sinks + [s for s in additions if s['master'] is not None]
            points += [s['xy'] for s in additions]
            fan += len(all_sinks)
            pin += sum(loads[s['master'],s['pin']] for s in all_sinks)
            wire += hpwl(points)
            star += sum(manhattan(points[0], p) for p in points[1:])
            pending.extend(graph['transparent'].get(netname, []))
        row = (1., internal[name], internal[name]+output[name], pin+cap_per_um*wire,
               fan, pin, ffan, fpin, wire, star, fwire)
        for key,value in zip(values,row): values[key].append(value)
    return {k:np.asarray(v) for k,v in values.items()}
