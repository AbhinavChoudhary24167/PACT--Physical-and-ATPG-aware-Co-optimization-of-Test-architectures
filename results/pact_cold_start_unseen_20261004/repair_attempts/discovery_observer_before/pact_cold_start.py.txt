#!/usr/bin/env python3
"""Register, prepare, and search prospective manifest-driven PACT inputs."""
import argparse
import csv
from dataclasses import asdict
import gzip
import inspect
import io
import math
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import time
import traceback
import numpy as np

from pact_generalization import ROOT, sha, binding, read, write, now
from pact_generalization_infrastructure import execute, external_binding
from pact_generalization_physical import LIB
from pact.optimizer import stage_b as solver
from pact.optimizer import candidate_stateful as sf
from pact.optimizer.cold_start import load
from pact.analysis.phase2b_reference import parse_spef

OUT=ROOT/'results/pact_cold_start_unseen_20261004'
RUN=Path('/mnt/d/PACT_EXPERIMENTS/results/pact_cold_start_unseen_20261004')
PREVIOUS=ROOT/'results/pact_generalization_20261004'
METRICS=sf.METRICS
SOURCE_NAMES=('src/pact/optimizer/stage_b.py','src/pact/optimizer/search.py',
    'src/pact/optimizer/stage_b_inputs.py','src/pact/optimizer/implementation_v2.py',
    'src/pact/optimizer/candidate_sensitive.py','src/pact/optimizer/candidate_physical.py',
    'src/pact/optimizer/candidate_stateful.py','src/pact/optimizer/stateful_geometry.py',
    'src/pact/optimizer/cold_start.py','scripts/pact_cold_start.py','scripts/pact_cold_start_export.py')


def register():
    benchmark=read(PREVIOUS/'manifests/generalization_benchmark_manifest.json')
    previous=read(PREVIOUS/'manifests/campaign_preregistration.json')
    references=read(PREVIOUS/'baselines/generalization_baselines.json')['records']
    rows=[]
    for row in benchmark['designs']:
        reference=next((r for r in references if r['design']==row['design']),None)
        rows.append(dict(row,eligible=reference is not None,
            reference=reference,blocked_reason=None if reference else 'Frozen K=2 minimum eight FFs per chain'))
    write(OUT/'manifests/campaign_preregistration.json',dict(
        schema='pact_cold_start_campaign_v1',created_utc=now(),
        starting_SHA=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        classification='INITIALIZATION_PLUMBING_CHANGE_EXPLICITLY_AUTHORIZED',
        benchmark_manifest=binding(PREVIOUS/'manifests/generalization_benchmark_manifest.json'),
        frozen_core=binding(PREVIOUS/'manifests/pact_v1_frozen_manifest.json'),
        previous_checkpoint=binding(PREVIOUS/'completion.json'),designs=rows,
        execution_order=['s953','s1196','s1238','s35932','s38417','s38584'],
        method=previous['fixed_method'],resource_limits=previous['safety_limits'],
        initialization='Sole selected minimum-qualified-routed-WL B0/B1/B2/B3T reference; no historical P0, archive, precursor or other seed',
        independent_units=True,scientific_method_changes=0,
        selection='Unchanged Stage-B balanced, best_E, best_H4, best_H8 roles; deduplicate across epsilons; max3; only new architectures',
        outcome_threshold='Relative1e-10 equality; strong=E/H4/H8 all improve; mixed=activity improvement with any regression; no benefit=none improve; negligible=all equal',
        scope='Prospective results separate from historical qualified core'),immutable=True)
    print('COLD_START_PREREGISTERED',len(rows),sum(r['eligible'] for r in rows),flush=True)


def preparation_path(design):
    base=PREVIOUS/f'physical/{design}'
    return base/('preparation_repaired.json' if (base/'preparation_repaired.json').exists() else 'preparation.json')


def prepare(design):
    campaign=read(OUT/'manifests/campaign_preregistration.json')
    entry=next(r for r in campaign['designs'] if r['design']==design)
    if not entry['eligible']:
        write(OUT/f'failures/{design}_structural.json',dict(design=design,status='PACT_EXECUTION_BLOCKED',
            failure_class='SCAN_TOPOLOGY_FAIL',reason=entry['blocked_reason'],created_utc=now()),immutable=True)
        return
    reference=entry['reference']
    ref_path=ROOT/reference['selection_receipt']['path'].removeprefix('repo://')
    assert sha(ref_path)==reference['selection_receipt']['sha256']
    selected=read(ref_path)
    route=read(selected['provenance']['path'])
    preparation=read(preparation_path(design))
    input_root=RUN/'inputs'/design
    input_root.mkdir(parents=True,exist_ok=True)
    frozen_ref=OUT/f'references/{design}/reference_frozen.json'
    write(frozen_ref,dict(reference,created_utc=now(),cold_start_initial_architecture=True,
        all_method_qualification=binding(PREVIOUS/'physical/reference_export_gates.json')),immutable=True)
    selected_export=read(PREVIOUS/f'physical/{design}/reference_export_gates/{selected["method"]}/receipt.json')
    export_root=Path(selected_export['outputs']['net_mapping.json']['path']).parent
    shutil.copy2(export_root/'net_mapping.json',input_root/'net_mapping.json')
    with gzip.open(route['archive']['path'],'rb') as src,(input_root/'routed.odb').open('wb') as dst:
        shutil.copyfileobj(src,dst)
    previous_measurement=Path('/mnt/d/PACT_EXPERIMENTS/results/pact_generalization_20261004/reference_measurement')/design/design/selected['method']
    old_caps=previous_measurement/'net_activity_capacitance.csv'
    provenance=dict(mapping=external_binding(export_root/'net_mapping.json'),route_archive=route['archive'])
    if old_caps.exists():
        shutil.copy2(old_caps,input_root/'net_activity_capacitance.csv')
        provenance['caps']=external_binding(old_caps)
    else:
        # Only electrical input rows; no activity is inferred from incomplete simulation.
        mapping=read(input_root/'net_mapping.json')
        spef=parse_spef(Path(route['extraction']['path']).read_text())
        caps=[]
        for name,info in sorted(mapping['nets'].items()):
            electrical=spef.get(name)
            caps.append(dict(net=name,source=info['source'],x_um=info['xy_um'][0],y_um=info['xy_um'][1],
                pin_ff=info['pin_cap_ff'],ground_ff=electrical['ground_ff'] if electrical else None))
        with (input_root/'net_activity_capacitance.csv').open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(caps[0]));writer.writeheader();writer.writerows(caps)
        provenance.update(caps_source='Frozen SPEF ground plus frozen Liberty sink pins; activity columns absent',
            SPEF=route['extraction'])
    execute(['/usr/bin/openroad','-no_init','-exit','-python',ROOT/'scripts/pact_cold_start_export.py',
        input_root,input_root/'topology.json'],input_root/'topology_export',timeout=1200)
    identity=Path(selected['provenance']['path']).parents[2]/'ff_identity_map.json'
    artifacts=dict(architecture=selected['architecture'],patterns=preparation['patterns'],
        identity_map=external_binding(identity),placement=preparation['placed_def'],
        mapping=external_binding(input_root/'net_mapping.json'),caps=external_binding(input_root/'net_activity_capacitance.csv'),
        topology=external_binding(input_root/'topology.json'),source_placed_database=preparation['source_placed_database'],
        source_netlist=external_binding(Path(preparation['patterns']['path']).parent/'compatible.v'),
        SDC=preparation['SDC'],qualification=selected['provenance'],
        reference_fault_export=selected['correctness']['export'],reference_serial=selected['correctness']['serial'])
    manifest=OUT/f'inputs/{design}/cold_start_input.json'
    write(manifest,dict(schema='pact_cold_start_input_v1',design=design,created_utc=now(),
        reference_method=selected['method'],reference_architecture_hash=selected['architecture_hash'],
        reference=binding(frozen_ref),preparation=binding(preparation_path(design)),artifacts=artifacts,
        provenance=provenance,FF_count=entry['FF_count'],K=2,ATPG_pattern_count=entry['ATPG_pattern_count'],
        target_fault_count=entry['ATPG_target_fault_count'],
        fields=dict(automatically_generated=['identity_map','patterns','topology'],
            physically_derived=['mapping','caps','placement','source_placed_database','SDC'],
            external_reference=['architecture','qualification','reference_fault_export','reference_serial'],
            optional=['provenance']),historical_state_required=False),immutable=True)
    print('COLD_START_INPUT_READY',design,selected['method'],flush=True)


def search(design):
    folder=OUT/'searches'/design
    manifest=OUT/f'inputs/{design}/cold_start_input.json'
    contract_data=read(manifest)
    seconds=300*max(1,math.ceil(contract_data['FF_count']/600))
    configs=[solver.Config(epsilon=e,seconds=seconds,max_evaluations=20000,stagnation_attempts=2000) for e in (.02,.05,.10)]
    write(folder/'search_configuration.json',dict(design=design,created_utc=now(),seed=11,K=2,
        input=binding(manifest),configurations=[asdict(c) for c in configs],
        sources={p:binding(ROOT/p) for p in SOURCE_NAMES},initialization='external reference only',
        runtime_policy='300*max(1,ceil(FF/600)) seconds per unchanged mutation loop'),immutable=True)
    start=time.perf_counter();usage_start=resource.getrusage(resource.RUSAGE_SELF)
    model,starts,contract=load(manifest)
    setup=time.perf_counter()-start
    write(folder/'initialization.json',dict(status='PASS',created_utc=now(),seconds=setup,
        initial_architecture_hash=contract.initial_architecture.sha256(),start_count=len(starts),
        labels=[label for label,_ in starts],historical_state_accesses=0,model=model.metadata),immutable=True)
    original_archive=solver.Archive
    lanes=[]
    for config in configs:
        out=folder/f'budget_{config.epsilon:.2f}'
        counts=dict(state_constructions=0,state_score_calls=0,state_score_seconds=0.,independent_replays=0,independent_replay_seconds=0.)
        archives=[];discoveries={};profile_before=model.profile.copy()
        class CountArchive(original_archive):
            def __init__(self,*args,**kwargs):
                super().__init__(*args,**kwargs);archives.append(self)
            def insert(self,score,orders,label):
                admitted=super().insert(score,orders,label)
                frame=inspect.currentframe().f_back
                row=frame.f_locals.get('row')
                champions=frame.f_locals.get('champions')
                if row is not None and champions is not None:
                    def values(s):return [*s[solver.ACTIVITY],solver.activity_score(s,frame.f_locals['ref']['score'],config.weights)]
                    if any(old is None or value<values(old['score'])[i]-1e-10*max(1.,abs(value))
                           for i,(value,old) in enumerate(zip(values(row['score']),champions))):
                        parent=frame.f_back.f_locals
                        oid=model.canonical_id(orders)
                        discoveries.setdefault(oid,dict(discovered_evaluation=parent.get('evaluations',0),
                            discovered_attempt=parent.get('attempts',0),discovered_utc=now(),
                            discovered_loop_seconds=time.perf_counter()-parent['search_began'] if 'search_began' in parent else 0.))
                return admitted
        class CountState(sf.State):
            def __init__(self,*args,**kwargs):
                counts['state_constructions']+=1;super().__init__(*args,**kwargs)
            def score(self):
                tick=time.perf_counter();value=super().score()
                counts['state_score_calls']+=1;counts['state_score_seconds']+=time.perf_counter()-tick
                return value
        def replay(m,o):
            tick=time.perf_counter();value=sf.reference(m,o)
            counts['independent_replays']+=1;counts['independent_replay_seconds']+=time.perf_counter()-tick
            return value
        last_progress={}
        def progress(row):
            frame=inspect.currentframe().f_back.f_back
            augmented=dict(row,stagnation_attempts=frame.f_locals.get('stagnation'),
                lane=frame.f_locals.get('lane'))
            last_progress.update(augmented)
            write(out/'progress.json',augmented)
            print(design,config.epsilon,'PROGRESS',round(row['seconds'],1),row['evaluations'],row['accepted'],flush=True)
        solver.Archive=CountArchive
        try:
            result=solver.optimize(model,starts,contract.data['reference_method'],config,
                state_type=CountState,reference_evaluator=replay,checkpoint=progress)
        finally:
            solver.Archive=original_archive
        def package(row):
            arch=model.architecture_from(row['orders'])
            path=out/'architectures'/f'{arch.sha256()}.json'
            arch.to_json(path)
            return {k:v for k,v in row.items() if k not in ('orders','score')}|dict(
                architecture=external_binding(path),architecture_sha256=arch.sha256(),
                parent_architecture_sha256=contract.data['reference_architecture_hash'],
                chain_sizes=list(map(len,row['orders'])),metrics=dict(zip(METRICS,map(float,row['score']))),
                **discoveries.get(arch.sha256(),{}))
        result['selected']=[package(r) for r in result['selected']]
        result['baselines']=[package(r) for r in result['baselines']]
        result['reference_score']=result['reference_score'].tolist()
        result.update(config=asdict(config),instrumentation=counts,
            rejected_exact_moves=result['evaluations']-result['accepted'],
            archive_insertions=archives[0].admissions,initial_reference_archive_insertions=1,
            restarts=counts['state_constructions']-len(starts)-1,
            final_stagnation_attempts=last_progress.get('stagnation_attempts'),
            stagnation_termination_events=int(result['termination']=='stagnation'),
            model_profile={k:model.profile[k]-profile_before[k] for k in model.profile})
        write(out/'search.json',result,immutable=True)
        lanes.append(dict(epsilon=config.epsilon,receipt=binding(out/'search.json')))
        print('COLD_START_SEARCH_LANE_COMPLETE',design,config.epsilon,result['evaluations'],result['termination'],flush=True)
    usage=resource.getrusage(resource.RUSAGE_SELF)
    write(folder/'search_results.json',dict(design=design,status='SEARCH_COMPLETE',created_utc=now(),
        lanes=lanes,input=binding(manifest),configuration=binding(folder/'search_configuration.json'),
        initialization=binding(folder/'initialization.json'),model_setup_seconds=setup,
        wall_seconds=time.perf_counter()-start,CPU_seconds=usage.ru_utime+usage.ru_stime-usage_start.ru_utime-usage_start.ru_stime,
        peak_RSS_KiB=usage.ru_maxrss,total_exact_mutation_evaluations=sum(read(ROOT/r['receipt']['path'].removeprefix('repo://'))['evaluations'] for r in lanes)),immutable=True)
    select(design)


def select(design):
    tick=time.perf_counter();folder=OUT/'searches'/design
    results=read(folder/'search_results.json');rows=[]
    for lane in results['lanes']:
        data=read(ROOT/lane['receipt']['path'].removeprefix('repo://'))
        reference=np.array(data['reference_score'])
        for row in data['selected']:
            if row['new']:
                score=np.array([row['metrics'][m] for m in METRICS])
                rows.append(dict(row,epsilon=lane['epsilon'],
                    normalized=(score[solver.ACTIVITY]/np.maximum(reference[solver.ACTIVITY],1e-12)).tolist(),
                    search_receipt=lane['receipt']))
    chosen=[]
    for role,key in (('balanced',lambda r:sum(r['normalized'])/3),('best_E',lambda r:r['normalized'][0]),
        ('best_H4',lambda r:r['normalized'][1]),('best_H8',lambda r:r['normalized'][2])):
        eligible=[r for r in rows if role in r['roles']]
        if not eligible:continue
        row=min(eligible,key=lambda r:(key(r),r['epsilon'],r['architecture_sha256']))
        prior=next((r for r in chosen if r['architecture_sha256']==row['architecture_sha256']),None)
        if prior:prior['route_roles'].append(role)
        elif len(chosen)<3:chosen.append(dict(row,route_roles=[role]))
    for i,row in enumerate(chosen,1):
        row.update(candidate=f'CS_C{i}',role=row['route_roles'][0],architecture_hash=row['architecture_sha256'],
            parent_reference_hash=row['parent_architecture_sha256'],seed=11,selection_order=i,
            selection_reason='Unchanged Stage-B pre-route role champion; cross-epsilon role order and exact hash deduplication')
    input_path=OUT/f'inputs/{design}/cold_start_input.json'
    write(OUT/f'selections/{design}/preselected_candidates.json',dict(design=design,created_utc=now(),
        cold_start_input=binding(input_path),reference_hash=read(input_path)['reference_architecture_hash'],
        records=chosen,primary_candidate=next((r['candidate'] for r in chosen if 'balanced' in r['route_roles']),None),
        search_results=binding(folder/'search_results.json'),selection_seconds=time.perf_counter()-tick,
        candidate_routes_before_selection=0),immutable=True)
    print('PRESELECTED_BEFORE_ROUTE',design,len(chosen),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('register','prepare','search'));p.add_argument('--design')
    a=p.parse_args()
    os.environ.update(PACT_DEPENDENCY_ROOT='/root/pact-deps',PACT_EXPERIMENT_ROOT='/mnt/d/PACT_EXPERIMENTS',
        OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',NUMBA_NUM_THREADS='1')
    try:
        register() if a.action=='register' else globals()[a.action](a.design)
    except Exception as error:
        if a.design:
            path=OUT/f'failures/{a.design}_{a.action}.json'
            if not path.exists():write(path,dict(design=a.design,status='PACT_EXECUTION_BLOCKED',
                stage=a.action,error=str(error),traceback=traceback.format_exc(),created_utc=now()),immutable=True)
        raise
