"""Bounded physical replication, with an immutable attempt ledger per cell."""
from phase2c_common import *
import argparse
import gzip
import math
import shutil
from datetime import datetime, timezone
from pact.phase0d.external import run_bounded, extract_structured_metrics
from pact.scan.model import ScanArchitecture
from pact.experiment_storage import configure_experiment_storage, guard_disk_space

def ok(ex):
    return ex['exit_code']==0 and not ex['timed_out'] and ex['required_outputs_present']

def prepare():
    integrity()
    for d in DESIGNS:
        for s in SEEDS:
            p=WORK/d/f's{s}'/'prepared.json'
            ex=run_bounded(['openroad','-python','-no_init','-exit',str(ROOT/'scripts/phase2c_physical.py'),
                'prepare','--design',d,'--seed',str(s)],p.parent/'prepare',ROOT,120,[p])
            if not ok(ex):raise RuntimeError('PLACEMENT_FAILURE: '+str(p.parent))
            print('PREPARED',d,s,flush=True)

def run_one(job):
    d,s,label=job['design'],job['seed'],job['label'];folder=Path(job['architecture_path']).parent
    result_path=folder/'result.json'
    if result_path.exists():return read(result_path)
    result=dict(job,status='PENDING',wire_cap_per_um=.103981,contract_sha256=file_sha256(REPORT/'EXPERIMENT_CONTRACT.md'))
    def done(status,**extra):
        result.update(status=status,**extra);write(result_path,result)
        print(status,d,s,label,flush=True);return result
    if s==11:
        old=next(r for r in read(REPORT/'architecture_set.json') if r['design']==d and r['label']==label)
        assert job['architecture_sha256']==old['architecture_sha256']
        ext=next(r for r in read(OLD/'extraction_audit.json')['rows'] if r['design']==d and r['label']==label)
        phy=next(r for r in read(A/'physical_weighting.json')['rows'] if r['design']==d and r['label']==label)
        for p,h in [(ext['weights_path'],ext['weights_sha256']),(phy['physical_path'],phy['physical_sha256'])]:
            assert file_sha256(Path(p))==h
        return done('QUALIFIED',reused=True,reference_path=ext['weights_path'],physical_path=phy['physical_path'],
                    route_sha256=old['odb_sha256'],extraction=ext,route_proof=read(old['proof_path']))
    if (folder/'attempt.json').exists():
        return done('TOOL_FAILURE',reason='Interrupted attempt; no automatic retry')
    guard_disk_space(configure_experiment_storage(),estimated_bytes=1024**3)
    write(folder/'attempt.json',dict(job,launched_utc=datetime.now(timezone.utc).isoformat()))
    variant_name=f'phase2c_s{s}_{job["architecture_sha256"][:12]}'
    variant=WORK/'orfs/results/nangate45'/BLOCK[d]/variant_name
    logs=WORK/'orfs/logs/nangate45'/BLOCK[d]/variant_name
    variant.mkdir(parents=True,exist_ok=True)
    # Reuse only genuinely identical orders at this seed, never family names.
    reuse=None
    for candidate in (ROOT/f'artifacts/derived/phase0c/{d}/s{s}/k2').glob('*.architecture.json'):
        arch=ScanArchitecture.from_json(candidate)
        if arch.sha256()==job['architecture_sha256']:
            evidence=ROOT/f'artifacts/raw/phase0c/physical/{d}/s{s}/k2'/candidate.name.split('.')[0]
            rec=read(evidence/'route_metrics.json')
            if rec['status']=='QUALIFIED':reuse=(evidence,rec);break
    routed=variant/'5_2_route.odb'
    if reuse:
        evidence,rec=reuse;archive=evidence/'5_2_route.odb.gz'
        assert file_sha256(archive)==rec['routed_odb_gzip_sha256']
        with gzip.open(archive,'rb') as src,routed.open('wb') as dst:shutil.copyfileobj(src,dst)
        assert file_sha256(routed)==rec['routed_odb_sha256']
        result.update(reused_route=True,reuse_source=str(evidence),structured_metrics=rec['structured_metrics'])
    else:
        ex=run_bounded(['openroad','-python','-no_init','-exit',str(ROOT/'scripts/phase0c_rewire_odb.py'),
            '--source',str(base(d,s)/'3_place.odb'),'--architecture',job['architecture_path'],
            '--output',str(variant/'3_place.odb')],folder/'rewire',ROOT,120,[variant/'3_place.odb'],resume=False)
        result['rewire_execution']=ex
        if not ok(ex):return done('PLACEMENT_FAILURE',reason='Rewire failed')
        shutil.copy2(base(d,s)/'3_place.sdc',variant/'3_place.sdc')
        config=ROOT/('experiments/phase0b/s15850_orfs/config.mk' if d=='s15850' else f'experiments/phase0/{d}_orfs/config.mk')
        required=[logs/'5_1_grt.json',logs/'5_2_route.json',routed]
        ex=run_bounded(['make','-o',str(variant/'3_place.odb'),'-o',str(variant/'3_place.sdc'),
            f'DESIGN_CONFIG={config}',f'FLOW_VARIANT={variant_name}',f'WORK_HOME={WORK/"orfs"}',
            f'GRT_SEED={s}','OPENROAD_EXE=/usr/bin/openroad','YOSYS_EXE=/usr/bin/yosys','route'],
            folder/'route',FLOW,600,required,resume=False)
        result['route_execution']=ex
        if not ok(ex):return done('ROUTE_FAILURE',reason='Route process failed/timeout/missing output')
        try:
            metrics=extract_structured_metrics(read(required[0]),read(required[1]))
            assert all(math.isfinite(float(metrics[k])) for k in ('setup_wns_ns','hold_wns_ns'))
        except (ValueError,AssertionError,TypeError) as e:return done('TIMING_FAILURE',reason=str(e))
        result.update(structured_metrics=metrics,reused_route=False)
        if metrics['detailed_route_drc_errors']!=0:return done('ROUTE_FAILURE',reason='Nonzero DRC')
    result.update(routed_path=str(routed),route_sha256=file_sha256(routed))
    # Verify structure BEFORE spending extraction time.
    proof=folder/'routed_verification.json'
    ex=run_bounded(['openroad','-python','-no_init','-exit',str(ROOT/'scripts/phase0d_verify_routed.py'),
        '--routed',str(routed),'--architecture',job['architecture_path'],'--frozen-def',str(placed_def(d,s)),
        '--output',str(proof)],folder/'verify',ROOT,90,[proof],resume=False)
    result['verification_execution']=ex
    if not ok(ex) or read(proof).get('status')!='PASS':return done('PROVENANCE_FAILURE',reason='Routed structural proof failed')
    spef=folder/'extracted.spef';tcl=folder/'extract.tcl'
    tcl.write_text(f'read_db {routed}\ndefine_process_corner -ext_model_index 0 X\nextract_parasitics -ext_model_file {RULES} -coupling_threshold 0.1 -cc_model 10 -context_depth 5 -version 1.0\nwrite_spef {spef}\nexit\n')
    ex=run_bounded(['openroad','-no_init','-exit',str(tcl)],folder/'extract',ROOT,180,[spef],resume=False)
    result['extraction_execution']=ex
    if not ok(ex):return done('EXTRACTION_FAILURE',reason='OpenRCX extraction failed')
    write(folder/'job.json',result)
    ex=run_bounded(['openroad','-python','-no_init','-exit',str(ROOT/'scripts/phase2c_physical.py'),
        'reference','--job',str(folder/'job.json')],folder/'reference',ROOT,90,[folder/'extraction.json'],resume=False)
    if not ok(ex):return done('EXTRACTION_FAILURE',reason='Reference coverage/accounting failed')
    return done('QUALIFIED',reused=False,reference_path=str(folder/'reference_weights.json'),
                physical_path=str(folder/'physical.json'),extraction=read(folder/'extraction.json'))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','smoke','baseline','snapshot','run'])
    parser.add_argument('--workers',type=int,default=1);args=parser.parse_args()
    if args.stage!='snapshot':require_open_experiment()
    if args.stage=='prepare':prepare();return
    integrity()
    jobs=[j for d in DESIGNS for s in SEEDS for j in read(WORK/d/f's{s}'/'prepared.json')['jobs']]
    if args.stage=='smoke':jobs=[next(j for j in jobs if j['seed']==13 and j['design']=='s5378')]
    if args.stage=='baseline':jobs=[j for j in jobs if j['seed']==11]
    if args.stage=='snapshot':jobs=[]
    if args.workers==1:
        for job in jobs:run_one(job)
    else:
        # Independent physical jobs, never optimizer agents or candidate search.
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(run_one,jobs))
    matrix=[]
    for d in DESIGNS:
        for s in SEEDS:
            for j in read(WORK/d/f's{s}'/'prepared.json')['jobs']:
                p=Path(j['architecture_path']).parent/'result.json'
                matrix.append(read(p) if p.exists() else dict(j,status='NOT_RUN'))
    write(REPORT/'architecture_matrix.json',dict(rows=matrix))
    write(REPORT/'seed_matrix.json',dict(rows=[dict(design=d,seed=s,
        qualified=sum(r['status']=='QUALIFIED' for r in matrix if r['design']==d and r['seed']==s),
        failures=[dict(label=r['label'],status=r['status']) for r in matrix if r['design']==d and r['seed']==s and r['status']!='QUALIFIED'])
        for d in DESIGNS for s in SEEDS]))

if __name__=='__main__':main()
