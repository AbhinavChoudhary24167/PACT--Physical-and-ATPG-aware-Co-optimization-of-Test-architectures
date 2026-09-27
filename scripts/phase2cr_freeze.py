"""Freeze existing primary evidence before corrected measurements."""
from phase2cr_common import *
from collections import Counter
from pact.scan.model import ScanArchitecture

def main():
    if (REPORT / 'freeze.json').exists():
        integrity()
        print('Existing preregistration verified; not overwritten')
        return
    assert read(REPORT / 'bug_reproduction.json')['status'] == 'PACT_PHASE2CR_BUG_REPRODUCED'
    original = read(B / 'provenance.json')['inputs']
    measured = read(B / 'measurement_provenance.json')['files']
    result = read(B / 'result_provenance.json')['files']
    inputs = {}
    def add(p, expected=None):
        p = Path(p)
        inputs[str(p)] = check(p, expected) if expected else sha(p)
    # Preserve historical compact reports, existing source and tests (including user work).
    for folder in (B, C, ROOT / 'scripts', ROOT / 'src', ROOT / 'tests'):
        for p in folder.rglob('*'):
            if p.is_file() and '__pycache__' not in str(p) and 'phase2cr' not in p.name:
                add(p, result.get(p.name) if p.parent == B else None)
    for p, expected in read(REPORT / 'bug_reproduction.json')['verified_inputs'].items():
        add(p, expected)
    for q in read(A / 'test_quality.json').values():
        for key in ('placed_def', 'pattern_path', 'identity_path'):
            add(q[key], original[q[key]])
    for n in ('test_quality.json', 'shift_reconstruction.json', 'physical_weighting.json'):
        add(A / n)
    rows = read(B / 'architecture_set.json')
    assert Counter(r['design'] for r in rows) == {'s5378': 9, 's9234': 6, 's15850': 6}
    phy = {(r['design'],r['label']):r for r in read(A/'physical_weighting.json')['rows']}
    trace = {(r['design'],r['label']):r for r in read(A/'shift_reconstruction.json')['rows']}
    ext = {(r['design'],r['label']):r for r in read(B/'extraction_audit.json')['rows']}
    frozen = []
    for r in rows:
        key = r['design'],r['label']; a = ScanArchitecture.from_json(Path(r['architecture_path']))
        assert a.sha256() == r['architecture_sha256'] and len(a.chains) == 2
        names = sorted(c.name for c in a.cells)
        flat = [n for c in a.chains for n in c.cells]
        assert sorted(flat) == names and len(set(flat)) == len(names)
        for k in ('architecture_path','proof_path','odb_archive','route_path'):
            add(r[k], original[r[k]])
        p = phy[key]; add(p['physical_path'], p['physical_sha256'])
        p = trace[key]; add(p['trace_path'], p['trace_sha256'])
        p = ext[key]
        assert p['status'] == 'QUALIFIED_LOAD_REFERENCE'
        for pk,hk in (('weights_path','weights_sha256'),('spef_path','spef_sha256')):
            add(p[pk],p[hk])
        for f in ('predictor_weights.json','frozen.odb'):
            p = WORK/r['architecture_sha256']/f; add(p, measured[str(p)])
        frozen.append(dict(r, scan_order_sha256=order_hash(a), K=2, FFs=names,
            cells=[dict(name=c.name,x_um=c.x_um,y_um=c.y_um) for c in a.cells],
            chains=[dict(chain_id=c.chain_id,cells=list(c.cells)) for c in a.chains]))
    for d in DESIGNS:
        add(REPORT / f'{d}.placed_graph.json')
    for n in ('bug_reproduction.json','BUG_REPRODUCTION.md','initial_repository_state.json'):
        add(REPORT/n)
    write(REPORT/'freeze.json',dict(frozen_utc=now(),contract_sha256=sha(REPORT/'EXPERIMENT_CONTRACT.md'),
        inputs=inputs,architectures=frozen,coefficient_ff_per_um=0.103981,
        corrected_metrics_computed=False,seed=11,K=2,new_routes=0))
    print('FROZEN',len(frozen),'architectures;',len(inputs),'hash-verified/preserved files')

if __name__ == '__main__': main()
