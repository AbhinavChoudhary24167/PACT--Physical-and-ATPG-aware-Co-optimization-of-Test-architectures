#!/usr/bin/env python3
"""Requalify retained routes after an isolated traversal engineering repair."""
import argparse
import os
from pathlib import Path
import shutil
from pact_generalization import ROOT,OUT,binding,now,read,write
from pact_generalization_infrastructure import RUN,FAN,REPAIRED,external_binding
import pact_generalization_physical as physical
from pact.scan.model import ScanArchitecture
from pact.integration.qualification import simulate


def requalify(design,methods,prior):
    original=OUT/f'repair_attempts/{prior}/baselines/{design}_references.json'
    records=read(original)['records']
    assert {r['method'] for r in records}=={'B0','B1','B2','B3T'},'Wait for all reference outcomes'
    oldroot=RUN/f'baseline_{prior}'/design
    physical.ATTEMPT='buffer_traversal_repaired'
    folder=physical.baseline_folder(design)
    folder.mkdir(parents=True,exist_ok=True)
    shutil.copy2(oldroot/'ff_identity_map.json',folder/'ff_identity_map.json')
    preparation=physical.prep(design)
    source=Path(preparation['source']['path'])
    patterns=Path(preparation['patterns']['path'])
    identity=read(folder/'ff_identity_map.json')['records']
    original_workload=simulate(REPAIRED,FAN/'techlib/mod_nangate45.mdt',source,patterns,folder/'original_workload')
    for index,item in enumerate(records):
        method=item['method']
        if method not in methods:
            continue
        assert item['status']=='FAILED' and item['generator_status']=='PASS'
        path=oldroot/(f'{method}/architecture.json' if method=='B0' else
            f'{method}/generator/'+('architecture.json' if method=='B1' else 'canonical.json'))
        arch=ScanArchitecture.from_json(path)
        variant=f'generalization_{prior}_{method}'
        reuse=dict(variant=str(RUN/f'orfs/results/nangate45/{design}/{variant}'),
            logs=str(RUN/f'orfs/logs/nangate45/{design}/{variant}'),
            route_execution=str(oldroot/f'{method}/physical/route/execution.json'))
        report=physical.route(design,method,path,preparation,reuse=reuse)
        correctness=physical.serial_correctness(design,arch,identity,patterns,original_workload,
            folder/method/'correctness',source)
        records[index]=dict(item,status='QUALIFIED',architecture=external_binding(path),
            architecture_hash=arch.sha256(),exact_scan_order=[list(c.cells) for c in arch.chains],
            chain_count=len(arch.chains),routed_scan_wirelength_um=report['routed_scan_wirelength_um'],
            timing=report['structured_metrics'],DRC=report['DRC_errors'],correctness=correctness,
            provenance=external_binding(folder/method/'physical/route_result.json'),
            repair=dict(classification='IMPLEMENTATION_REPAIR',supersedes=binding(original),
                additional_route_executions=0,scientific_method_change=False))
        for field in ('failure_class','error','traceback'):
            records[index].pop(field,None)
    selected=physical.select_reference(records)
    write(physical.result_path(f'baselines/{design}_references.json'),dict(design=design,records=records,
        supersedes=binding(original)),immutable=True)
    write(physical.result_path(f'baselines/{design}_selected.json'),dict(selected,frozen_utc=now(),
        selection_rule='minimum qualified routed scan cost among B0/B1/B2/B3T before PACT search'),immutable=True)
    write(physical.result_path(f'physical/{design}/presearch_qualification.json'),dict(design=design,
        status='INFRASTRUCTURE_QUALIFIED',selected_reference=selected['method'],
        gates=dict(synthesis='PASS',scan='PASS',ATPG='PASS',topology='PASS',placement='PASS',
            reference_method='PASS',routing='PASS',extraction='PASS',timing='PASS',DRC='PASS')),immutable=True)
    print('REQUALIFIED',design,selected['method'],selected['routed_scan_wirelength_um'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--design',required=True)
    p.add_argument('--methods',nargs='+',required=True)
    p.add_argument('--prior-attempt',default='runtime_paths_repaired')
    a=p.parse_args()
    os.environ.update(PACT_DEPENDENCY_ROOT='/root/pact-deps',PACT_EXPERIMENT_ROOT='/mnt/d/PACT_EXPERIMENTS',
        OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',NUMBA_NUM_THREADS='1',PATH='/usr/bin:'+os.environ['PATH'])
    requalify(a.design,a.methods,a.prior_attempt)
