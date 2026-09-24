"""Versioned selected-architecture SI/SO predictor, using placed inputs only.

Historical phase2b_loads remains unchanged. Geometry is always evaluated from
net point sets; no scalar HPWL correction or routed reference is accepted.
"""
from copy import deepcopy
import numpy as np
from pact.analysis.phase2b_loads import hpwl, manhattan

CAP_PER_UM = 0.103981
GRAPH_KEYS = {'stage', 'FFs', 'nets', 'transparent', 'scan_endpoints', 'scan_ports'}
ENDPOINT_KEYS = {'port', 'buffer_instance', 'buffer_master', 'input_pin', 'output_pin',
    'buffer_xy', 'output_net', 'original_source_net', 'original_owner_ff',
    'port_xy', 'inherited_port_xy'}
METRICS = ('M0', 'M2_scan', 'M2_port', 'M3_load', 'M4_fanout', 'M4_pin',
    'M4_functional_fanout', 'M4_functional_pin', 'M5_hpwl', 'M5_star', 'M5_functional_hpwl')


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _point(xy):
    _require(isinstance(xy, (list, tuple)) and len(xy) == 2
             and all(isinstance(v, (int, float)) and np.isfinite(v) for v in xy),
             'Expected finite placed XY point')


def validate(arch, graph, loads):
    """Fail closed on unknown fields at every placed-data schema level."""
    _require(set(graph) == GRAPH_KEYS and graph['stage'] == 'POST-PLACEMENT',
             'Requires placed-only schema; unexpected fields may leak targets')
    names = [c.name for c in arch.cells]
    flat = [n for c in arch.chains for n in c.cells]
    _require(len(arch.chains) == 2 and all(c.cells for c in arch.chains), 'Requires frozen K=2')
    _require(len(names) == len(set(names)) and sorted(flat) == sorted(names)
             and set(graph['FFs']) == set(names), 'FF inventory/bijection mismatch')
    _require(len({c.chain_id for c in arch.chains}) == 2, 'Duplicate chain ID')
    for c in arch.cells:
        _point((c.x_um, c.y_um))
        f = graph['FFs'][c.name]
        _require(set(f) == {'master', 'roots'} and 'Q' in f['roots']
                 and set(f['roots']) <= {'Q', 'QN'}, 'Unexpected FF fields')
        q = graph['nets'][f['roots']['Q']]
        _require(list(q['driver_xy']) == [c.x_um, c.y_um], 'Architecture coordinate mismatch')
    for net in graph['nets'].values():
        _require(set(net) == {'driver_xy', 'sinks', 'ports'}, 'Unexpected net feature')
        _point(net['driver_xy'])
        for p in net['ports']:
            _point(p)
        for s in net['sinks']:
            _require(set(s) == {'master', 'pin', 'xy'}, 'Unexpected sink feature')
            _point(s['xy'])
            _require((s['master'], s['pin']) in loads, 'Missing Liberty pin')
    for key, value in loads.items():
        _require(isinstance(key, tuple) and len(key) == 2 and all(isinstance(k,str) for k in key)
                 and isinstance(value, (int,float)) and np.isfinite(value) and value >= 0,
                 'Expected Liberty (master,pin) -> finite nonnegative fF only')
    for source, children in graph['transparent'].items():
        _require(source in graph['nets'] and len(set(children)) == len(children)
                 and all(n in graph['nets'] for n in children), 'Invalid transparent edges')
    _require(set(graph['scan_endpoints']) == {'chain0_so'}, 'Unexpected scan endpoints')
    ep = graph['scan_endpoints']['chain0_so']
    _require(set(ep) == ENDPOINT_KEYS, 'Unexpected endpoint feature')
    _require(ep['port'] == 'test_so' and ep['buffer_master'] == 'BUF_X1'
             and ep['input_pin'] == 'A' and ep['output_pin'] == 'Z', 'Unsupported inherited buffer')
    _require(isinstance(ep['buffer_instance'],str) and bool(ep['buffer_instance']), 'Missing buffer identity')
    for k in ('buffer_xy', 'port_xy', 'inherited_port_xy'):
        _point(ep[k])
    _require(set(graph['scan_ports']) == {'test_si','test_so','test_si_1','test_so_1'},
             'Unexpected port schema')
    for xy in graph['scan_ports'].values():
        _point(xy)
    _require(ep['port_xy'] == graph['scan_ports']['test_so'], 'Placed SO policy mismatch')
    source, child = ep['original_source_net'], ep['output_net']
    _require(graph['FFs'][ep['original_owner_ff']]['roots']['Q'] == source, 'Original owner mismatch')
    sink = dict(master=ep['buffer_master'], pin=ep['input_pin'], xy=ep['buffer_xy'])
    _require(graph['nets'][source]['sinks'].count(sink) == 1, 'Ambiguous inherited buffer input')
    _require(sum(children.count(child) for children in graph['transparent'].values()) == 1
             and graph['transparent'].get(source,[]).count(child) == 1, 'Ambiguous inherited branch')
    _require(graph['nets'][child]['driver_xy'] == ep['buffer_xy'], 'Buffer output driver mismatch')
    # The legacy exporter excluded the BTerm. Do not silently accept an already-added SO.
    _require(ep['port_xy'] not in graph['nets'][child]['ports'], 'SO geometry already present')


def selected_graph(arch, graph, loads):
    """Transfer the complete inherited branch; never mutate the supplied graph."""
    validate(arch, graph, loads)
    selected = deepcopy(graph)
    ep = selected['scan_endpoints']['chain0_so']
    source, child = ep['original_source_net'], ep['output_net']
    tail = arch.chains[0].cells[-1]
    target = selected['FFs'][tail]['roots']['Q']
    sink = dict(master=ep['buffer_master'], pin=ep['input_pin'], xy=ep['buffer_xy'])
    if target != source:
        selected['nets'][source]['sinks'].remove(sink)
        selected['transparent'][source].remove(child)
        selected['nets'][target]['sinks'].append(sink)
        selected['transparent'].setdefault(target, []).append(child)
    selected['nets'][child]['ports'].append(ep['port_xy'])
    return selected


def construct_with_audit(arch, graph, loads):
    selected = selected_graph(arch, graph, loads)
    names = sorted(c.name for c in arch.cells)
    xy = {c.name: [c.x_um,c.y_um] for c in arch.cells}
    extra = {n: [] for n in names}
    internal = dict.fromkeys(names, 0.)
    output = dict.fromkeys(names, 0.)
    for ci, chain in enumerate(arch.chains):
        for a, b in zip(chain.cells, chain.cells[1:]):
            internal[a] = manhattan(xy[a], xy[b])
            extra[a].append(dict(xy=xy[b], master=graph['FFs'][b]['master'], pin='SI'))
        tail = chain.cells[-1]
        so = 'test_so' if ci == 0 else f'test_so_{ci}'
        output[tail] = manhattan(xy[tail], graph['scan_ports'][so])
        if ci > 0:
            extra[tail].append(dict(xy=graph['scan_ports'][so], master=None, pin=so))
    values = {k: [] for k in METRICS}
    owners, details = {}, {}
    for name in names:
        roots = selected['FFs'][name]['roots']
        pending, seen = list(roots.values()), set()
        fan = pin = wire = star = ffan = fpin = fwire = 0.
        records = []
        while pending:
            netname = pending.pop()
            if netname in seen:
                continue
            seen.add(netname)
            _require(netname not in owners or owners[netname] == name, 'Competing FF owners')
            owners[netname] = name
            net = selected['nets'][netname]
            sinks = net['sinks']
            points = [net['driver_xy']] + [s['xy'] for s in sinks] + net['ports']
            ffan += len(sinks)
            fpin += sum(loads[s['master'],s['pin']] for s in sinks)
            fwire += hpwl(points)
            additions = extra[name] if netname == roots['Q'] else []
            all_sinks = sinks + [s for s in additions if s['master'] is not None]
            points += [s['xy'] for s in additions]
            pincap = sum(loads[s['master'],s['pin']] for s in all_sinks)
            length = hpwl(points)
            fan += len(all_sinks); pin += pincap; wire += length
            star += sum(manhattan(points[0],p) for p in points[1:])
            records.append(dict(net=netname, points=deepcopy(points), sinks=deepcopy(all_sinks),
                ports=deepcopy(net['ports']), additions=deepcopy(additions), pin_ff=pincap, hpwl_um=length))
            pending.extend(selected['transparent'].get(netname, []))
        row = (1., internal[name], internal[name]+output[name], pin+CAP_PER_UM*wire,
               fan, pin, ffan, fpin, wire, star, fwire)
        for k,v in zip(values,row):
            values[k].append(v)
        details[name] = records
    return {k:np.asarray(v) for k,v in values.items()}, dict(
        owners=owners, FFs=details, selected_graph=selected,
        buffer_owner=owners[graph['scan_endpoints']['chain0_so']['output_net']])


def construct_weights(arch, graph, loads):
    """Only architecture, strict placed graph, and Liberty pin loads are inputs."""
    return construct_with_audit(arch, graph, loads)[0]
