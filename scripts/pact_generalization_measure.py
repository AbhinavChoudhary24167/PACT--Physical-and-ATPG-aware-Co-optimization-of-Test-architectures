#!/usr/bin/env python3
"""Use the frozen routed/extracted/VCD path on a qualified new reference."""
import argparse
import os
from pathlib import Path
import shutil
import sys
import traceback

from pact_generalization import ROOT,OUT,binding,now,read,sha,write
from pact_generalization_infrastructure import RUN,FAN,execute,external_binding,DESIGNS
from pact_generalization_physical import LIB,FLOW,prep
from pact.scan.model import ScanArchitecture
from pact.integration.patterns import fan_workload,serialize


def selected(design):
    path=OUT/f'repair_attempts/runtime_paths_repaired/baselines/{design}_selected.json'
    gate=OUT/f'repair_attempts/runtime_paths_repaired/physical/{design}/presearch_qualification.json'
    if not gate.is_file() or read(gate)['status']!='INFRASTRUCTURE_QUALIFIED':
        raise ValueError('New design has not completed pre-search infrastructure gates')
    return read(path)


def prepare(design):
    reference=selected(design)
    preparation=prep(design)
    route=read(reference['provenance']['path'])
    arch=ScanArchitecture.from_json(Path(reference['architecture']['path']))
    assert arch.sha256()==reference['architecture_hash']
    assert sha(reference['architecture']['path'])==reference['architecture']['sha256']
    baseline_root=Path(reference['provenance']['path']).parents[2]
    identity=baseline_root/'ff_identity_map.json'
    patterns=Path(preparation['patterns']['path'])
    fan,states=fan_workload(patterns,read(identity)['records'],arch)
    root=RUN/'reference_measurement'/design
    folder=root/design/reference['method']
    folder.mkdir(parents=True,exist_ok=True)
    workload=dict(architecture_sha256=arch.sha256(),cycles=max(len(c.cells) for c in arch.chains),
        patterns=[dict(pattern=s['pattern'],source_fields=s['source_fields'],load=serialize(arch,s['load_state']),
            unload=serialize(arch,s['response_state'],response=True)) for s in states])
    write(folder/'workload.json',workload,immutable=True)
    row=dict(design=design,role=reference['method'],architecture=reference['architecture'],
        architecture_sha256=arch.sha256(),routed_archive=route['archive'],
        source_placed_database=preparation['source_placed_database'],
        source_netlist=external_binding(patterns.parent/'compatible.v'),SDC=preparation['SDC'],
        qualification=reference['provenance'],workload=external_binding(folder/'workload.json'),
        prior_integration=reference['correctness']['serial'],
        inputs=dict(patterns=preparation['patterns'],identity_map=external_binding(identity),placement=preparation['placed_def']),
        chain_lengths=[len(c.cells) for c in arch.chains])
    sources={name:binding(ROOT/name) for name in ('scripts/physical_effect.py','scripts/physical_effect_export.py','src/pact/physical_effect.py')}
    write(root/'manifest.json',dict(schema='pact_generalization_reference_measurement_v1',rows=[row],
        library=external_binding(LIB),simulation_cells=external_binding(FAN/'techlib/NangateOpenCellLibrary.v'),
        extraction_rules=external_binding(FLOW/'platforms/nangate45/rcx_patterns.rules'),
        executed_sources=sources,created_utc=now(),metric_scope=read(ROOT/'results/pact_end_to_end_20261004/canonical_results.json')['records'][0]['metric_scope']),immutable=True)
    return root,folder


def run(design):
    root,folder=prepare(design)
    record=dict(design=design,phase='REFERENCE_MEASUREMENT',manifest=external_binding(root/'manifest.json'),
        selected_reference=selected(design)['method'],status='PENDING')
    try:
        print('REFERENCE_MEASUREMENT_STARTED',design,flush=True)
        env=dict(os.environ,PACT_PHYSICAL_EFFECT_OUT=str(root))
        result=execute(['/usr/bin/time','-v','-o',folder/'resources.txt',sys.executable,
            ROOT/'scripts/physical_effect.py','run','--design',design],root/'execution',timeout=1800,env=env)
        for name in ('topology_verification.json','functional_verification.json','FF_transition_crosscheck.json'):
            assert read(folder/name)['status']=='PASS'
        summary=read(folder/'activity_summary.json')
        all_data=summary['scopes']['all_data']
        record.update(status='QUALIFIED',wall_seconds=result['wall_seconds'],
            E=all_data['cap_weighted_ff_transitions']['total'],
            H4=all_data['grids']['4']['cap_peak_per_cycle']['max'],
            H8=all_data['grids']['8']['cap_peak_per_cycle']['max'],
            folder=str(folder),resources=external_binding(folder/'resources.txt'),
            summary=external_binding(folder/'activity_summary.json'))
    except Exception as error:
        execution=read(root/'execution/execution.json') if (root/'execution/execution.json').exists() else {}
        resource_failure=execution.get('timed_out') or execution.get('exit_code') in (-9,137)
        record.update(status='FAILED',failure_class='RESOURCE_LIMIT' if resource_failure else 'PHYSICAL_BACKEND_FAIL',
            error=str(error),traceback=traceback.format_exc(),execution=execution)
        write(OUT/f'failures/{design}_reference_measurement.json',record,immutable=True)
    receipt=OUT/f'physical/{design}/reference_measurement'
    receipt.mkdir(parents=True,exist_ok=True)
    for name in ('activity_summary.json','FF_transition_crosscheck.json','spatial_bins.json','topology_verification.json',
        'functional_verification.json','simulation_manifest.json','simulate.log','resources.txt','export.execution.json',
        'extract.execution.json','compile.execution.json','simulate.execution.json'):
        if (folder/name).exists():
            shutil.copy2(folder/name,receipt/name.replace('.log','.txt'))
    write(receipt/'result.json',record,immutable=True)
    print('REFERENCE_MEASUREMENT',design,record['status'],record.get('error',''),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--design',choices=DESIGNS,required=True)
    args=p.parse_args()
    os.environ.update(PACT_DEPENDENCY_ROOT='/root/pact-deps',PACT_EXPERIMENT_ROOT='/mnt/d/PACT_EXPERIMENTS',
        OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',NUMBA_NUM_THREADS='1',PATH='/usr/bin:'+os.environ['PATH'])
    run(args.design)


if __name__=='__main__':
    main()
