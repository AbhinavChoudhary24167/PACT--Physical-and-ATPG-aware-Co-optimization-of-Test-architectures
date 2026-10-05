"""Complete transition-count storage and bounded-memory exact reanalysis."""
import ast
import gzip
import json
from pathlib import Path
import struct
import numpy as np
from pact import physical_effect as oracle


def read_counts(path, names, cycles, mmap_path=None):
    def exact(stream, size):
        value = stream.read(size)
        if len(value) != size:
            raise ValueError('Incomplete compact activity output')
        return value
    with gzip.open(path, 'rb') as stream:
        if exact(stream, 8) != b'PACTCN01':
            raise ValueError('Unsupported compact activity format')
        width, recorded_cycles = struct.unpack('<II', exact(stream, 8))
        if width != len(names) or recorded_cycles != cycles:
            raise ValueError('Compact activity dimensions differ from workload')
        recorded = [exact(stream, struct.unpack('<I', exact(stream, 4))[0]).decode('utf-8') for _ in names]
        if recorded != list(names):
            raise ValueError('Compact activity net mapping differs')
        if mmap_path is None:
            counts = np.empty((cycles, width), np.uint8)
        else:
            counts = np.memmap(mmap_path, mode='w+', shape=(cycles, width), dtype=np.uint8)
        for start in range(0, cycles, 1024):
            length = min(1024, cycles-start)
            counts[start:start+length] = np.frombuffer(exact(stream, length*width), np.uint8).reshape(length, width)
        if exact(stream, 8) != b'PACTDONE' or stream.read(1):
            raise ValueError('Missing completion footer or trailing activity output')
    if isinstance(counts, np.memmap):
        counts.flush()
    return counts, dict(backend='icarus_vpi_settled_counts_v1', complete=True,
        mapped_nets=width, cycles=cycles, storage='gzip uint8 per-net/per-cycle counts')


def net_totals(counts):
    total = np.zeros(counts.shape[1], np.uint64)
    for first in range(0, len(counts), 1024):
        total += counts[first:first+1024].sum(axis=0, dtype=np.uint64)
    return total


def ff_check(folder, counts, names, mapping, arch, lookup, fan, workload):
    """Same independent simultaneous chain replay, with vector FF comparison."""
    qcols = {v['source'][:-2]: i for i, n in enumerate(names)
             if (v := mapping['nets'][n])['source'].endswith('/Q')}
    expected = sorted(c['name'] for c in arch['cells'])
    if set(qcols) != set(expected):
        raise ValueError('Incomplete FF Q measurement map')
    index = {n: i for i, n in enumerate(expected)}
    columns = np.array([qcols[n] for n in expected])
    chains = [np.array([index[n] for n in chain['cells']]) for chain in arch['chains']]
    state = np.zeros(len(expected), np.uint8)
    cursor = 0
    for pattern, source in zip(workload['patterns'], fan.patterns, strict=True):
        for phase in ('load', 'unload'):
            if phase == 'unload':
                for signal, bit in zip(fan.pseudo_primary_inputs, source.ppo, strict=True):
                    state[index[lookup[signal]]] = int(bit)
            for t in range(workload['cycles']):
                nxt = np.empty_like(state)
                for chain, nodes in zip(arch['chains'], chains, strict=True):
                    nxt[nodes[0]] = int(pattern['load'][chain['chain_id']][t]) if phase == 'load' else 0
                    nxt[nodes[1:]] = state[nodes[:-1]]
                if not np.array_equal(counts[cursor, columns], state ^ nxt):
                    raise ValueError(f'Independent Q toggle mismatch {cursor}')
                state = nxt
                cursor += 1
    if cursor != len(counts):
        raise ValueError('FF workload length differs')
    (folder/'FF_transition_crosscheck.json').write_text(json.dumps(dict(status='PASS',
        FF_cycle_values_checked=cursor*len(expected), cycles=cursor,
        scope='Every physical FF Q against independent simultaneous chain replay; compact simulator counts are measurement source'), indent=2)+'\n')


def metrics(counts, caps, mapping, names, schedule):
    """Retain frozen arithmetic, percentile populations and first-maximum ties.

    Only 1024-row data subsets are materialized. Per-cycle scalar arrays remain
    complete, so percentiles and phase summaries are unchanged.
    """
    results, series, spatial = {}, {}, {}
    for scope in ('scan_data', 'all_data'):
        sel = np.asarray([mapping['nets'][n]['scan_data'] or scope == 'all_data' for n in names])
        c, ns = caps[sel], np.asarray(names)[sel]
        total = np.empty(len(counts), np.uint64)
        cw = np.empty(len(counts))
        grids = {}
        for resolution in (4, 8):
            bins = np.asarray([oracle.spatial_bin(mapping['nets'][n]['xy_um'], mapping['bounds_um'], resolution) for n in ns])
            grids[resolution] = dict(bins=bins, peak=np.empty(len(counts), np.int32), cap_peak=np.empty(len(counts)),
                total=np.zeros(resolution**2, np.int64), maximum=-1, cap_maximum=-1.)
        for first in range(0, len(counts), 1024):
            last = min(first+1024, len(counts))
            a = counts[first:last, sel]
            total[first:last], cw[first:last] = a.sum(axis=1), oracle.weighted(a, c)
            for resolution, grid in grids.items():
                local = np.zeros((last-first, resolution**2), np.int32)
                localcap = np.zeros_like(local, dtype=float)
                for b in range(resolution**2):
                    mask = grid['bins'] == b
                    local[:, b] = a[:, mask].sum(axis=1)
                    localcap[:, b] = oracle.weighted(a[:, mask], c[mask])
                grid['peak'][first:last] = local.max(axis=1)
                grid['cap_peak'][first:last] = localcap.max(axis=1)
                grid['total'] += local.sum(axis=0)
                ic, ib = np.unravel_index(local.argmax(), local.shape)
                ec, eb = np.unravel_index(localcap.argmax(), localcap.shape)
                if local[ic, ib] > grid['maximum']:
                    grid.update(maximum=int(local[ic, ib]), ic=first+int(ic), ib=int(ib), transition_map=local[ic].tolist())
                if localcap[ec, eb] > grid['cap_maximum']:
                    grid.update(cap_maximum=float(localcap[ec, eb]), ec=first+int(ec), eb=int(eb), cap_map=localcap[ec].tolist())
        result = dict(nets=len(ns), transitions=oracle.stats(total), cap_weighted_ff_transitions=oracle.stats(cw), grids={})
        series[scope] = dict(transitions=total, cap_weighted=cw)
        for resolution, grid in grids.items():
            result['grids'][str(resolution)] = dict(peak_per_cycle=oracle.stats(grid['peak']), cap_peak_per_cycle=oracle.stats(grid['cap_peak']),
                max_transition_cycle=grid['ic'], max_transition_bin=grid['ib'], max_cap_cycle=grid['ec'], max_cap_bin=grid['eb'],
                percentile_population='per-cycle maximum over spatial bins')
            series[scope][f'local_{resolution}'] = grid['peak']
            series[scope][f'cap_local_{resolution}'] = grid['cap_peak']
            spatial[f'{scope}_{resolution}'] = dict(transition_cycle=grid['ic'], transition_map=grid['transition_map'],
                cap_cycle=grid['ec'], cap_map=grid['cap_map'], bins_total=grid['total'].tolist())
        result['phases'] = {phase: dict(transitions=oracle.stats(total[[r['phase'] == phase for r in schedule]]),
            cap_weighted=oracle.stats(cw[[r['phase'] == phase for r in schedule]])) for phase in ('load', 'unload')}
        results[scope] = result
    return results, series, spatial


def analyze(folder):
    """Adapt the preserved analyzer's I/O and memory use; keep its cap policy."""
    folder = Path(folder)
    source = Path(oracle.__file__).read_text()
    tree = ast.parse(source)
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'analyze')
    body = function.body
    def index(fragment):
        matches = [i for i, node in enumerate(body) if ast.unparse(node).splitlines()[0].startswith(fragment)]
        if len(matches) != 1:
            raise ValueError('Frozen compact-analysis anchor ambiguous: '+fragment)
        return matches[0]
    first, last = index('metrics ='), index("write('spatial_bins.json'")
    body[first:last] = ast.parse('caps = np.asarray(caps)\nmetrics, series, spatial = __compact_metrics(counts, caps, mapping, names, schedule)').body
    first, last = index('qcols ='), index('spef =')
    body[first:last] = ast.parse('__compact_ff(folder, counts, names, mapping, arch, lookup, fan, workload)').body
    i = index('counts, vcd =')
    body[i+1:i+1] = ast.parse('net_counts = __net_totals(counts)').body
    class StorageAdapter(ast.NodeTransformer):
        def visit_Constant(self, node):
            return ast.copy_location(ast.Constant('activity.counts.gz'), node) if node.value == 'activity.vcd' else node
        def visit_Call(self, node):
            text = ast.unparse(node)
            if text == 'counts[:, len(caps)].any()':
                return ast.parse('net_counts[len(caps)] != 0', mode='eval').body
            if text == 'counts[:, len(caps) - 1].sum()':
                return ast.parse('net_counts[len(caps)-1]', mode='eval').body
            return self.generic_visit(node)
        def visit_Expr(self, node):
            if ast.unparse(node).startswith('np.savez_compressed('):
                return None  # complete compressed counts already retained
            return self.generic_visit(node)
    tree = StorageAdapter().visit(tree)
    namespace = dict(__compact_metrics=metrics, __compact_ff=ff_check, __net_totals=net_totals)
    exec(compile(ast.fix_missing_locations(tree), str(oracle.__file__), 'exec'), namespace)
    namespace['vcd_transitions'] = lambda path, names, cycles: read_counts(path, names, cycles, folder/'transitions.u8')
    namespace['analyze'](folder)
    summary_path = folder/'activity_summary.json'
    summary = json.loads(summary_path.read_text())
    summary['activity_trace'] = summary.pop('VCD')
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True)+'\n')
    return summary
