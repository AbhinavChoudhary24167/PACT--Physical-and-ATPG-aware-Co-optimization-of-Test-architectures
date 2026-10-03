#!/usr/bin/env python3
"""Read preserved ODB connectivity; never execute or repair scan optimization."""
import argparse
import hashlib
import json
from pathlib import Path
import odb


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def observe(path):
    database = odb.dbDatabase.create()
    odb.read_db(database, str(path))
    block = database.getChip().getBlock()
    ff = {i.getName(): i for i in block.getInsts()
          if i.getMaster().getName() == 'SDFF_X1'}
    def net_name(term):
        net = term.getNet()
        return net.getName() if net is not None else None
    cells = {n: dict(master=i.getMaster().getName(), location=list(i.getLocation()),
                    orientation=str(i.getOrient()),
                    pins={p: net_name(i.findITerm(p)) for p in ('D', 'CK', 'SI', 'Q')})
             for n, i in ff.items()}
    def describe(net):
        return dict(name=net.getName(),
                    ports=[p.getName() for p in net.getBTerms()],
                    iterms=[dict(instance=t.getInst().getName(),
                                 master=t.getInst().getMaster().getName(),
                                 pin=t.getMTerm().getName()) for t in net.getITerms()])
    ports = {}
    traces = []
    for ci in range(2):
        si, so = f'test_si_{ci}', f'test_so_{ci}'
        for name in (si, so):
            term = block.findBTerm(name)
            ports[name] = describe(term.getNet())
        net = block.findBTerm(si).getNet()
        end = block.findBTerm(so).getNet()
        observed, seen, steps = [], set(), []
        error = None
        while True:
            if net.getName() in seen:
                error = 'LOOP'
                break
            seen.add(net.getName())
            matches = [n for n, i in ff.items() if net_name(i.findITerm('SI')) == net.getName()]
            steps.append(dict(net=net.getName(), matches=matches,
                              on_physical_so_net=(net.getName() == end.getName())))
            if len(matches) > 1:
                error = 'BRANCHED_FF_SI'
                break
            if matches:
                observed.append(matches[0])
                net = ff[matches[0]].findITerm('Q').getNet()
                continue
            if net.getName() == end.getName():
                break
            buffers = [t.getInst() for t in net.getITerms()
                       if t.getMTerm().getName() == 'A'
                       and t.getInst().getMaster().getName().startswith('BUF_')]
            if len(buffers) != 1:
                error = 'CANNOT_TRACE_FIXED_SI_SO'
                break
            net = buffers[0].findITerm('Z').getNet()
        traces.append(dict(chain=ci, ff_order=observed, ff_count=len(observed),
                           error=error, terminal_net=describe(net), steps=steps))
    metadata = []
    for chain in block.getDft().getScanChains():
        items = []
        for part in chain.getScanPartitions():
            for scan_list in part.getScanLists():
                items += [s.getInst().getName() for s in scan_list.getScanInsts()]
        metadata.append(dict(name=chain.getName(), list_iteration=items))
    return dict(path=str(path), sha256=digest(path), FF_count=len(ff), cells=cells,
                ports=ports, traces=traces, scan_metadata=metadata)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--generated', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Preserve existing diagnostic evidence')
    before, after = observe(args.input), observe(args.generated)
    invariants = lambda record: {n: {k: v for k, v in cell.items() if k != 'pins'}
                                | {'functional': {p: cell['pins'][p] for p in ('D', 'CK')}}
                                for n, cell in record['cells'].items()}
    result = dict(status='OBSERVATION_ONLY', before=before, after=after,
                  FF_inventory_placement_functional_unchanged=(invariants(before) == invariants(after)),
                  optimizer_executed=False, connectivity_modified=False,
                  diagnostic_source_sha256=digest(Path(__file__)))
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(dict(FF_count=after['FF_count'],
                          traces=[{k: t[k] for k in ('chain', 'ff_count', 'error', 'terminal_net')} for t in after['traces']],
                          FF_invariants_unchanged=result['FF_inventory_placement_functional_unchanged']), indent=2), flush=True)
