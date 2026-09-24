#!/usr/bin/env python3
"""Route at most two new solver outputs/design; reuse B0/P/A exact-order routes.

One invocation consumes an output-local route plan before external execution.
No optimizer or historical experiment contract is modified by this adapter.
"""
import argparse
import gzip
import json
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from pact.optimizer.io import read,write_json
from pact.scan.model import ScanArchitecture
from pact.phase0d.external import run_bounded,extract_structured_metrics
from pact.phase0d.campaign import file_sha256


def run(design,run_dir,output):
    result=read(run_dir/'result.json');output.mkdir(parents=True,exist_ok=True)
    summary=[]
    for label in ('B0','P','A'):
        folder=ROOT/f'artifacts/raw/phase0c/physical/{design}/s11/k2/{label}'
        path=folder/'route_metrics.json';route=read(path)
        arch=ScanArchitecture.from_json(ROOT/f'artifacts/derived/phase0c/{design}/s11/k2/{label}.architecture.json')
        if route['architecture_sha256']!=arch.sha256() or route['status']!='QUALIFIED':raise ValueError('Historical route identity/status mismatch')
        archive=folder/'5_2_route.odb.gz'
        if file_sha256(archive)!=route['routed_odb_gzip_sha256']:raise ValueError('Historical routed archive hash mismatch')
        summary.append(dict(role=label,reused=True,source=str(path),**route))
    chosen=[('recommended',result['selected'])]
    if result['archive']:chosen.append(('physical_extreme',min(result['archive'],key=lambda r:r['metrics']['scan_hpwl_um'])))
    unique=[];seen={r['architecture_sha256'] for r in summary}
    for role,row in chosen:
        if row and row['architecture_sha256'] not in seen:
            seen.add(row['architecture_sha256']);unique.append((role,row))
    assert len(unique)<=2 and len(summary)+len(unique)<=5
    plan=output/'route_plan.json'
    desired=dict(design=design,candidates=[list(item) for item in unique],new_route_limit=2,total_architecture_limit=5)
    if plan.exists() and read(plan)!=desired:raise ValueError('Route output already belongs to a different selection; use a fresh directory')
    write_json(plan,desired)
    flow=Path('/root/pact-deps/OpenROAD-flow-scripts/flow')
    block='s9234f' if design=='s9234' else design
    base=flow/f'results/nangate45/{block}/phase0b_s11_B0'
    frozen_def=ROOT/f'artifacts/raw/phase0b/placements/{design}/s11/placed.def'
    work=output/'orfs';work=work.resolve()
    for role,row in unique:
        sha=row['architecture_sha256'];evidence=output/sha;report=evidence/'route_result.json'
        arch_path=Path(row['architecture']);arch=ScanArchitecture.from_json(arch_path)
        if arch.sha256()!=sha:raise ValueError('Selected architecture changed')
        if report.exists():summary.append(read(report));continue
        if (evidence/'attempt.json').exists():
            summary.append(dict(role=role,architecture_sha256=sha,status='INTERRUPTED_ATTEMPT',reused=False));continue
        evidence.mkdir(parents=True,exist_ok=True)
        write_json(evidence/'attempt.json',dict(role=role,architecture_sha256=sha))
        variant_name='solver_s11_'+sha[:12]
        variant=work/f'results/nangate45/{block}/{variant_name}'
        logs=work/f'logs/nangate45/{block}/{variant_name}'
        variant.mkdir(parents=True,exist_ok=True)
        out=dict(design=design,role=role,architecture_sha256=sha,reused=False,status='FAILED',proxy_metrics=row['metrics'])
        print('REWIRE',design,role,sha[:12],flush=True)
        rewire=run_bounded(['openroad','-python','-no_init','-exit',str(ROOT/'scripts/phase0c_rewire_odb.py'),
            '--source',str(base/'3_place.odb'),'--architecture',str(arch_path),'--output',str(variant/'3_place.odb')],
            evidence/'rewire',ROOT,120,[variant/'3_place.odb'],resume=False)
        out['rewire']=rewire
        if rewire['exit_code']!=0 or not rewire['required_outputs_present']:
            out['stage']='rewire';write_json(report,out);summary.append(out);continue
        shutil.copy2(base/'3_place.sdc',variant/'3_place.sdc')
        config=ROOT/(f'experiments/phase0b/{design}_orfs/config.mk' if design=='s15850' else f'experiments/phase0/{design}_orfs/config.mk')
        required=[logs/'5_1_grt.json',logs/'5_2_route.json',variant/'5_2_route.odb']
        print('ROUTE',design,role,flush=True)
        route=run_bounded(['make','-o',str(variant/'3_place.odb'),'-o',str(variant/'3_place.sdc'),
            f'DESIGN_CONFIG={config}',f'FLOW_VARIANT={variant_name}',f'WORK_HOME={work}',
            'GRT_SEED=11','NUM_CORES=2','OPENROAD_EXE=/usr/bin/openroad','YOSYS_EXE=/usr/bin/yosys','route'],
            evidence/'route',flow,600,required,resume=False)
        out['route']=route
        if route['exit_code']!=0 or not route['required_outputs_present']:
            out['stage']='route';write_json(report,out);summary.append(out);continue
        metrics=extract_structured_metrics(read(required[0]),read(required[1]))
        proof_path=evidence/'routed_verification.json'
        verify=run_bounded(['openroad','-python','-no_init','-exit',str(ROOT/'scripts/phase0d_verify_routed.py'),
            '--routed',str(required[2]),'--architecture',str(arch_path),'--frozen-def',str(frozen_def),'--output',str(proof_path)],
            evidence/'verify',ROOT,90,[proof_path],resume=False)
        proof=read(proof_path) if proof_path.exists() else {}
        qualified=verify['exit_code']==0 and proof.get('status')=='PASS' and metrics['detailed_route_drc_errors']==0
        archive=evidence/'5_2_route.odb.gz'
        with required[2].open('rb') as src,gzip.open(archive,'wb') as dst:shutil.copyfileobj(src,dst)
        out.update(status='QUALIFIED' if qualified else 'POSTROUTE_FAILED',structured_metrics=metrics,
                   DRC_errors=metrics['detailed_route_drc_errors'],postroute_verification=proof,
                   routed_full_scan_path_net_length_upper_bound_um=proof.get('routed_full_scan_path_net_length_upper_bound_um'),
                   exact_scan_only_routed_length_um=proof.get('exact_scan_only_total_um'),
                   routed_odb_gzip_sha256=file_sha256(archive),route_wall_seconds=route['elapsed_s'])
        write_json(report,out);summary.append(out)
        write_json(output/'summary.json',summary)
        print(design,role,out['status'],flush=True)
    write_json(output/'summary.json',summary)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--design',required=True,choices=('s5378','s9234','s15850'))
    parser.add_argument('--run',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.design,args.run.resolve(),args.output.resolve())
