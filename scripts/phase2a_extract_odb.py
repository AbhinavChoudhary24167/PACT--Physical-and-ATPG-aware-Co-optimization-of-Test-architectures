#!/usr/bin/env python3
"""Read-only routed ODB extraction; invoke with openroad -python -exit."""
import gzip
import json
from pathlib import Path
import shutil
import sys
import odb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from pact.experiment_storage import configure_experiment_storage, guard_disk_space
from pact.phase0d.campaign import file_sha256, atomic_write_json as write
from pact.physical.phase0d_routed import verify_routed

REPORT = ROOT / 'reports/phase2a_shift_activity'
def read(p): return json.loads(Path(p).read_text())

def extract(block, architecture):
    """Whole routed nets, uniquely owned by a toggling FF, through unary gates."""
    units = block.getDbUnitsPerMicron()
    cells = {c['name']:c for c in architecture['cells']}
    ff = {i.getName():i for i in block.getInsts() if i.getMaster().getName() == 'SDFF_X1'}
    assert set(ff) == set(cells)
    transparent = {}
    for inst in block.getInsts():
        master = inst.getMaster().getName()
        if master.startswith(('BUF_X', 'CLKBUF_X', 'INV_X')):
            inp = inst.findITerm('A')
            out = inst.findITerm('ZN' if master.startswith('INV_X') else 'Z')
            assert inp is not None and out is not None
            if inp.getNet() is not None and out.getNet() is not None:
                transparent.setdefault(inp.getNet().getName(), []).append(
                    (out.getNet().getName(), inst.getName(), master))
    owners, ff_rows, nets = {}, {}, {}
    for name, inst in sorted(ff.items()):
        x, y = inst.getLocation()
        assert abs(x/units-cells[name]['x_um']) < 1e-6
        assert abs(y/units-cells[name]['y_um']) < 1e-6
        roots = {}
        for pin in ('Q','QN'):
            term = inst.findITerm(pin)
            if term is not None and term.getNet() is not None:
                roots[pin] = term.getNet().getName()
        assert 'Q' in roots
        pending = list(roots.values())
        visited, branches = set(), []
        while pending:
            net_name = pending.pop()
            if net_name in visited: continue
            visited.add(net_name)
            assert net_name not in owners or owners[net_name] == name, 'Multiple FF owners'
            owners[net_name] = name
            net = block.findNet(net_name)
            terms = list(net.getITerms())
            drivers = [t for t in terms if str(t.getIoType()) == 'OUTPUT']
            assert len(drivers) == 1, ('Non-single-driver net', net_name)
            sinks = [t for t in terms if str(t.getIoType()) == 'INPUT']
            wire = net.getWire()
            has_load = bool(sinks or list(net.getBTerms()))
            assert wire is not None or not has_load, ('Missing routed wire', net_name)
            length = int(wire.getLength())/units if wire is not None else 0.0
            scan_sinks = [t for t in sinks if t.getInst().getName() in ff and t.getMTerm().getName() == 'SI']
            nets[net_name] = dict(owner=name, length_um=length,
                driver=[drivers[0].getInst().getName(), drivers[0].getMTerm().getName()],
                sinks=[[t.getInst().getName(),t.getMTerm().getName()] for t in sinks],
                scan_si_sinks=len(scan_sinks), other_sink_terminals=len(sinks)-len(scan_sinks),
                bterms=[t.getName() for t in net.getBTerms()],
                cap_node_count=len(list(net.getCapNodes())) if hasattr(net,'getCapNodes') else None,
                rseg_count=len(list(net.getRSegs())) if hasattr(net,'getRSegs') else None)
            for child, buf, master in transparent.get(net_name, []):
                pending.append(child)
                branches.append(dict(instance=buf, master=master, source_net=net_name, output_net=child))
        ff_rows[name] = dict(x_um=x/units, y_um=y/units, source_pins=roots,
            nets=sorted(visited), transparent_branches=branches,
            wire_length_um=sum(nets[n]['length_um'] for n in visited))
    return dict(FFs=ff_rows, nets=nets, summary=dict(
        ff_count=len(ff_rows), unique_driven_nets=len(nets),
        total_driven_wire_um=sum(n['length_um'] for n in nets.values()),
        scan_si_terminals=sum(n['scan_si_sinks'] for n in nets.values()),
        other_sink_terminals=sum(n['other_sink_terminals'] for n in nets.values()),
        nets_with_scan_and_other_sinks=sum(n['scan_si_sinks']>0 and n['other_sink_terminals']>0 for n in nets.values()),
        connected_QN_outputs=sum('QN' in f['source_pins'] for f in ff_rows.values()),
        transparent_branches=sum(len(f['transparent_branches']) for f in ff_rows.values()),
        cap_nodes=sum(n['cap_node_count'] or 0 for n in nets.values()),
        rsegs=sum(n['rseg_count'] or 0 for n in nets.values()),
        cap_api_available=all(n['cap_node_count'] is not None and n['rseg_count'] is not None for n in nets.values())))

def main():
    paths = configure_experiment_storage()
    guard_disk_space(paths, estimated_bytes=200*1024**2)
    work = paths.results / 'phase2a_shift_activity'
    work.mkdir(parents=True,exist_ok=True)
    for name, sha in read(REPORT/'freeze.json')['files'].items():
        assert file_sha256(REPORT/name) == sha
    quality = read(REPORT/'test_quality.json')
    summaries = []
    for row in read(REPORT/'architecture_set.json'):
        sha = row['architecture_sha256']
        archive = Path(row['odb_archive'])
        assert file_sha256(archive) == read(REPORT/'provenance.json')[str(archive)]
        temp = work / (sha + '.odb')
        with gzip.open(archive,'rb') as src, temp.open('wb') as dst: shutil.copyfileobj(src,dst)
        assert file_sha256(temp) == row['odb_sha256']
        proof = verify_routed(temp,Path(row['architecture_path']),Path(quality[row['design']]['placed_def']))
        assert proof['status'] == 'PASS'
        db = odb.dbDatabase.create()
        odb.read_db(db,str(temp))
        data = extract(db.getChip().getBlock(),read(row['architecture_path']))
        data.update(design=row['design'],label=row['label'], architecture_sha256=sha,
                    odb_sha256=row['odb_sha256'], postroute_proof=proof)
        target = work/(sha+'.physical.json')
        write(target,data)
        summaries.append(dict(design=row['design'],label=row['label'],**data['summary'],
                              physical_path=str(target),physical_sha256=file_sha256(target)))
        odb.dbDatabase.destroy(db)
        temp.unlink()
        print(row['design'],row['label'],data['summary'],flush=True)
    write(REPORT/'physical_weighting.json',dict(method='routed_unique_FF_driven_net_tree_wirelength',
        units='micrometre-transitions',capacitance_qualified=False,energy_portion='INCOMPLETE',
        rows=summaries))

if __name__ == '__main__': main()
