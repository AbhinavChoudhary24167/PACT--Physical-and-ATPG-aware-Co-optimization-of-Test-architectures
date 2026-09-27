"""Read-only boundary verification and physical inventory for the new experiment."""
from phase2cr_common import *
import platform
import subprocess
import time
from collections import Counter

OUT = ROOT/'results/phase2c_repair_multiseed'
CW = Path('/mnt/d/PACT_EXPERIMENTS/results/phase2c')

def boundary():
    start=time.perf_counter()
    f=integrity(); p=read(REPORT/'result_provenance.json')
    for k,v in p['files'].items(): check(REPORT/k,v)
    for k,v in p['sources'].items(): check(k,v)
    q=read(REPORT/'qualification.json'); t=read(REPORT/'tests.json')['continuation']
    assert q['final_classification']=='PACT_PHASE2CR_SEED11_REQUALIFIED'
    assert q['multiseed_decision']=='MULTISEED_REPAIR_RERUN_JUSTIFIED'
    assert read(REPORT/'topology_equivalence.json')['passed']==21
    assert read(REPORT/'weight_change_audit.json')['unexplained_changes']==0
    assert t['focused']['passed']==14 and t['regression_isolated']['passed']==217
    return dict(status='PASS',utc=now(),frozen_inputs=len(f['inputs']),result_files=len(p['files']),
        sources=len(p['sources']),topology_pass=21,prior_focused_pass=14,prior_regression_pass=217,
        unexplained_weight_changes=0,runtime_seconds=time.perf_counter()-start,
        seed11_files={str(x):sha(x) for x in REPORT.rglob('*') if x.is_file()},
        frozen_sources=p['sources'],frozen_inputs_sha256=f['inputs'],
        git_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        python=sys.version,platform=platform.platform())

def inventory():
    assert not (OUT/'seed_inventory.json').exists()
    b=boundary(); write(OUT/'initial_integrity.json',b)
    matrix=read(C/'architecture_matrix.json')['rows']; seeds=read(C/'seed_inventory.json')
    old=read(REPORT/'freeze.json')['architectures']; files={}; rows=[]; cells=[]
    def keep(p,expected=None):
        p=Path(p)
        if not p.is_file():return False
        h=check(p,expected) if expected else sha(p); files[str(p)]=h;return True
    for sr in seeds:
        d,s=sr['design'],sr['seed']
        placement=all([keep(p,h) for p,h in sr['placed_inputs'].items()])
        prep=CW/d/f's{s}'/'prepared.json'; keep(prep)
        jobs=read(prep)['jobs']; count=Counter()
        for j in jobs:
            folder=Path(j['architecture_path']).parent
            mr=next(r for r in matrix if (r['design'],r['seed'],r['label'])==(d,s,j['label']))
            mapping=keep(j['architecture_path'])
            tr=next(r for r in read(A/'shift_reconstruction.json')['rows'] if (r['design'],r['label'])==(d,j['label']))
            activity=keep(tr['trace_path'],tr['trace_sha256'])
            ref=next(r for r in old if r['design']==d and r['label']==j['label'])
            assert j['scan_order_sha256']==ref['scan_order_sha256']
            route=spef=timing=False; provenance=[]
            if mr['status']=='QUALIFIED':
                if s==11:
                    route=keep(ref['odb_archive']); spef=keep(mr['extraction']['spef_path'],mr['extraction']['spef_sha256'])
                    timing=keep(ref['route_path'])
                    keep(mr['physical_path']);keep(mr['reference_path'])
                else:
                    route=keep(mr['routed_path'],mr['route_sha256'])
                    ex=mr['extraction']
                    for p,h in dict(ex['inputs'],**ex['outputs']).items():keep(p,h)
                    spef=keep(folder/'extracted.spef');timing=all(k in mr.get('structured_metrics',{}) for k in ('setup_wns_ns','hold_wns_ns'))
                    for name in ('result.json','extraction.json','routed_verification.json','job.json'):keep(folder/name)
                provenance=[str(C/'architecture_matrix.json'),str(folder/'result.json')]
            cell=dict(design=d,seed=s,label=j['label'],architecture_path=j['architecture_path'],
                architecture_sha256=j['architecture_sha256'],scan_order_sha256=j['scan_order_sha256'],
                placement_available=placement,route_available=route,spef_available=spef,timing_available=timing,
                mapping_available=mapping,activity_available=activity,prior_status=mr['status'],
                new_route_required=not route,upstream_provenance=provenance)
            cells.append(cell)
            for k in ('route_available','spef_available','timing_available','mapping_available','activity_available'):
                count[k]+=int(cell[k])
        rows.append(dict(design=d,seed=s,placement_available=placement,architectures=len(jobs),
            placement_fingerprint=sr['placement_fingerprint'],counts=dict(count),
            new_routes_required=len(jobs)-count['route_available'],upstream_placement=sr['placed_inputs']))
    for p in (C/'architecture_matrix.json',C/'seed_inventory.json',ROOT/'config/phase0b_seed_method.json'):keep(p)
    write(OUT/'seed_inventory.json',dict(utc=now(),rows=rows,cells=cells,files=files,
        physical_seed_method=read(ROOT/'config/phase0b_seed_method.json'),independent_global_placement_runs=0))
    lines=['# Physical seed inventory','',
        'All listed placements and qualified existing physical files were checked against upstream hashes. Seeds are distinct coordinate perturbation/legalization realizations from a common placement, NOT independent global placer runs. No outcomes were scored and no route was launched. Exact per-architecture paths and hashes are in seed_inventory.json.','',
        '| Design | Seed | Placement | Architectures | Route | SPEF | Timing | Mapping | Activity | New routes needed |',
        '|---|---:|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        c=r['counts']; lines.append(f"| {r['design']} | {r['seed']} | {r['placement_available']} | {r['architectures']} | {c['route_available']} | {c['spef_available']} | {c['timing_available']} | {c['mapping_available']} | {c['activity_available']} | {r['new_routes_required']} |")
    lines+=['','Existing per-seed regenerated architecture orders are not interchangeable with the fixed seed-11 orders. New routing counts concern the exact frozen orders only. Missing extraction may be regenerated from an existing valid route; it is not a reason to reroute.']
    (OUT/'SEED_INVENTORY.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(rows,indent=2))

if __name__=='__main__': inventory()
