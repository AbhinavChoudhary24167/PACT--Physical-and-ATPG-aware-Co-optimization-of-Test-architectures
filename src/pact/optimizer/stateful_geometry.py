"""Deterministic shared-net MMST capacitance on a fixed baseline buffer skeleton."""
import numpy as np


def mmst(points):
    """Prim on sorted unique terminals; O(k²), no routing dependency."""
    pts = sorted(set(tuple(map(float, p)) for p in points))
    if not pts: return 0.
    used = [False]*len(pts)
    distance = [float('inf')]*len(pts)
    distance[0] = 0.
    result = 0.
    for _ in pts:
        i = min((i for i in range(len(pts)) if not used[i]), key=lambda i: (distance[i], i))
        result += distance[i]
        used[i] = True
        for j in range(len(pts)):
            if not used[j]:
                distance[j] = min(distance[j], abs(pts[i][0]-pts[j][0])+abs(pts[i][1]-pts[j][1]))
    return result


def estimate(ground, baseline_length, candidate_length, fallback_rho):
    if ground is None:
        return fallback_rho*candidate_length, None, 'missing_ground_global_scan_rho'
    if not np.isfinite(ground) or ground < 0: raise ValueError('Invalid ground capacitance')
    if baseline_length > 0:
        rho = ground/baseline_length
        return rho*candidate_length, rho, None
    return ground+fallback_rho*candidate_length, None, 'zero_span_retain_ground_plus_global_scan_rho'


class Geometry:
    def __init__(self, model, graph, caprows, fallback_rho):
        self.model, self.graph, self.fallback_rho = model, graph, float(fallback_rho)
        nets, cells = graph['nets'], graph['cells']
        self.ground = {r['net']: float(r['ground_ff']) if r['ground_ff'] else None for r in caprows}
        self.pin = {r['net']: float(r['pin_ff']) for r in caprows}
        self.baseline, self.fixed, self.lengths = {}, {}, {}
        self.by_terminal, self.si, self.q = {}, {}, {}
        for n, net in nets.items():
            terminals = [dict(id='DRIVER/'+net['source'], xy=net['xy'], cap=0.)]
            for s in net['sinks']:
                term = dict(id=s['cell']+'/'+s['pin'], xy=s['xy'], cap=float(s['cap']))
                terminals.append(term)
                self.by_terminal[term['id']] = (n, term)
                if s['cell'] in model.index and s['pin'] == 'SI': self.si[s['cell']] = (n, term)
            for p in net['ports']:
                term = dict(id='PORT/'+p['name'], xy=p['xy'], cap=0.)
                terminals.append(term); self.by_terminal[term['id']] = (n, term)
            self.baseline[n] = sorted(terminals, key=lambda t: t['id'])
            self.fixed[n] = list(self.baseline[n])
            self.lengths[n] = mmst(t['xy'] for t in terminals)
            if not np.isclose(sum(t['cap'] for t in terminals), self.pin[n], rtol=1e-8, atol=1e-8):
                raise ValueError('Baseline topology/Liberty mismatch: '+n)
            if net['source'].endswith('/Q') and net['source'][:-2] in model.index:
                self.q[net['source'][:-2]] = n
        # Actual SI leaf nets retain baseline buffer anchors; SI terminal identities move.
        self.carrier, self.input_carrier, self.output_endpoint = {}, [], []
        self.so_alias = {}  # pure transparent SO branches: net -> (chain, inversion parity)
        for ci, chain in enumerate(model.architecture.chains):
            self.input_carrier.append(self.si[chain.cells[0]][0])
            for a, b in zip(chain.cells, chain.cells[1:]): self.carrier[a] = self.si[b][0]
            so = 'test_so' if chain.scan_out == 'test_so_0' else chain.scan_out
            n, endpoint = self.by_terminal['PORT/'+so]
            # Walk the exclusive terminal buffer branch back to the first shared net.
            reverse = []
            while True:
                source = nets[n]['source']
                cellname, pin = source.rsplit('/', 1)
                cell = cells.get(cellname)
                only_path = all(t['id'] in ('DRIVER/'+source, endpoint['id']) for t in self.baseline[n])
                if not cell or not cell['transparent'] or not only_path: break
                reverse.append((n, int(cell['master'].startswith('INV_X'))))
                n, endpoint = self.by_terminal[cellname+'/A']
            parity = 0
            for out, inv in reversed(reverse):
                parity ^= inv
                self.so_alias[out] = (ci, parity)
            self.output_endpoint.append(endpoint)
            self.carrier[chain.cells[-1]] = n
            self.fixed[n] = [t for t in self.fixed[n] if t['id'] != endpoint['id']]
        for _, (net, term) in self.si.items():
            self.fixed[net] = [t for t in self.fixed[net] if t['id'] != term['id']]
        if len(set(self.carrier.values())) != len(model.names): raise ValueError('Ambiguous FF scan carrier')
        self.variable = set(self.carrier.values()) | set(self.input_carrier)
        self.baseline_orders = model.orders(model.architecture)
        caps, audit = self.capacitances(self.baseline_orders, details=True)
        for n, row in audit.items():
            if row['candidate_terminals'] != self.baseline[n]:
                raise ValueError('Baseline scan topology reconstruction differs: '+n)
            if self.ground[n] is not None:
                np.testing.assert_allclose(row['candidate_ground_ff'], self.ground[n], rtol=1e-12, atol=1e-12)

    def terminal_sets(self, orders):
        additions = {}
        for ci, order in enumerate(orders):
            additions[self.input_carrier[ci]] = self.si[self.model.names[order[0]]][1]
            for j, node in enumerate(order):
                additions[self.carrier[self.model.names[node]]] = (
                    self.si[self.model.names[order[j+1]]][1] if j+1 < len(order) else self.output_endpoint[ci])
        return additions

    def evaluate(self, net, endpoint=None):
        terminals = self.baseline[net] if net not in self.variable else sorted(
            self.fixed[net]+([endpoint] if endpoint else []), key=lambda t: t['id'])
        length = mmst(t['xy'] for t in terminals)
        ground, rho, fallback = estimate(self.ground[net], self.lengths[net], length, self.fallback_rho)
        cap = ground+sum(t['cap'] for t in terminals)
        return cap, dict(net=net, baseline_terminals=self.baseline[net], candidate_terminals=terminals,
            baseline_mmst_um=self.lengths[net], candidate_mmst_um=length,
            baseline_ground_ff=self.ground[net], rho_ff_per_um=rho, candidate_ground_ff=ground,
            candidate_pin_ff=cap-ground, candidate_cap_ff=cap, fallback_reason=fallback)

    def capacitances(self, orders, details=False):
        additions = self.terminal_sets(orders)
        caps, audit = {}, {}
        for n in self.baseline:
            caps[n], audit[n] = self.evaluate(n, additions.get(n))
        return (caps, audit) if details else caps
