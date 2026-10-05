#!/usr/bin/env python3
"""Physical/FAN/exact-activity continuation of already preselected cold candidates."""
import argparse
import gzip
import os
from pathlib import Path
import shutil
import sys
import time
from pact_generalization import ROOT,binding,read,write,sha,now
from pact_generalization_infrastructure import external_binding,REPAIRED
from pact_cold_start_measure import execute_stage,validate_row,LIB,RULES,CELLS
from pact_cpu_gates import require_continuation_allowed
from pact_cpu_continue_search import OUT,RUN


def frozen_tools():
    require_continuation_allowed()
    if sha('/usr/bin/openroad')!=read(ROOT/'results/pact_oss_benchmark/protocol/tool_versions.json')['implementation_binary_sha256']:
        raise ValueError('Frozen OpenROAD binary changed')
    if sha(REPAIRED)!=read(ROOT/'results/pact_end_to_end_20261004/upstream_repair/qualification.json')['repaired_executable_sha256']:
        raise ValueError('Qualified repaired FAN binary changed')


def physical(design):
    frozen_tools()
    import pact_cold_start_physical as old
    old.OUT,old.RUN=OUT,RUN
    final=old.qualify(OUT/f'selections/{design}/preselected_candidates.json',stop_on_correctness_failure=True)
    if any(r.get('scientific_stop') for r in final):raise ValueError('Candidate scientific correctness failure; preserve evidence and stop')


def prepare_activity(row,deadline):
    """Only the existing export/RCX/stimulus operations, in a new namespace."""
    arch=validate_row(row)
    root=RUN/'activity_inputs'/row['design']/row['role'];folder=root/row['design']/row['role']
    if root.exists():raise ValueError('Preserve prior candidate activity preparation')
    folder.mkdir(parents=True)
    if shutil.disk_usage(root).free<20*1024**3:raise RuntimeError('Registered 20-GiB scratch reserve unavailable')
    from pact.integration.patterns import fan_workload,serialize
    _,states=fan_workload(Path(row['inputs']['patterns']['path']),read(row['inputs']['identity_map']['path'])['records'],arch)
    workload=dict(architecture_sha256=arch.sha256(),cycles=max(len(c.cells) for c in arch.chains),
        patterns=[dict(pattern=s['pattern'],source_fields=s['source_fields'],load=serialize(arch,s['load_state']),
            unload=serialize(arch,s['response_state'],response=True)) for s in states])
    expected=read(row['workload']['path'])
    if any(workload[k]!=expected[k] for k in ('architecture_sha256','cycles','patterns')):
        raise ValueError('Stimulus differs from serial/FAN-qualified workload')
    write(folder/'workload.json',workload,immutable=True)
    row=dict(row,workload=external_binding(folder/'workload.json'),patterns=len(states),
        shift_cycles=2*len(states)*workload['cycles'])
    write(root/'manifest.json',dict(rows=[row],library=external_binding(LIB),
        simulation_cells=external_binding(CELLS),extraction_rules=external_binding(RULES),
        created_utc=now(),purpose='NEW_CPU_CONTINUATION_CANDIDATE_ACTIVITY',
        configured_timeout_seconds=7200,timeout_regime='normal'),immutable=True)
    os.environ['PACT_PHYSICAL_EFFECT_OUT']=str(root)
    import physical_effect as frozen
    frozen.OUT=root
    with gzip.open(row['routed_archive']['path'],'rb') as src,(folder/'routed.odb').open('wb') as dst:shutil.copyfileobj(src,dst)
    if sha(folder/'routed.odb')!=read(row['qualification']['path'])['routed_odb_sha256']:
        raise ValueError('Routed archive uncompressed hash mismatch')
    execute_stage(['/usr/bin/openroad','-python','-no_init','-exit',ROOT/'scripts/pact_generalization_export.py',folder],folder,'export',deadline)
    (folder/'extract.tcl').write_text(f'''read_liberty {LIB}
read_db {folder/'routed.odb'}
write_verilog {folder/'routed_raw.v'}
define_process_corner -ext_model_index 0 X
extract_parasitics -ext_model_file {RULES} -coupling_threshold 0.1 -cc_model 10 -context_depth 5 -version 1.0
write_spef {folder/'extracted.spef'}
write_db {folder/'extracted.odb'}
exit
''')
    execute_stage(['/usr/bin/openroad','-no_init','-exit',folder/'extract.tcl'],folder,'extract',deadline)
    for name in ('topology_verification.json','functional_verification.json'):
        if read(folder/name)['status']!='PASS':raise ValueError('Exact candidate export gate failed')
    mapping=read(folder/'net_mapping.json')
    frozen.repair_input_aliases(folder,mapping);frozen.stimulus(row,folder,mapping)
    write(folder/'simulation_manifest.json',dict(inputs={p:external_binding(folder/p) for p in (
        'routed.odb','routed.v','routed_raw.v','stimulus.v','net_mapping.json','cycles.json','extracted.spef','workload.json')},
        cells=external_binding(CELLS),architecture_sha256=arch.sha256(),
        simulation='Same Icarus -g2012 -DTETRAMAX functional workload; zero delay; no SDF'),immutable=True)
    from pact.analysis.phase2b_reference import parse_spef
    evidence=None
    if set(mapping['nets'])-set(parse_spef((folder/'extracted.spef').read_text())):
        evidence=folder/'implementation_evidence.json'
        execute_stage(['/usr/bin/openroad','-python','-no_init','-exit',ROOT/'scripts/pact_spef_evidence_export.py',
            '--source',folder,'--inspection-db',folder/'extracted.odb','--reproduced-spef',folder/'extracted.spef',
            '--output',evidence],folder,'evidence_export',deadline)
    write(folder/'result.json',dict(status='PREPARED_NOT_MEASURED',design=row['design'],role=row['role'],
        architecture_sha256=arch.sha256(),activity_metrics_available=False,
        extraction_inspection='Fresh candidate RCX database; same frozen binary/parameters as the separately reproduced reference omission',
        missing_SPEF_evidence=external_binding(evidence) if evidence else None,
        created_utc=now()),immutable=True)
    return folder,evidence


def activity(design):
    frozen_tools()
    from pact_cpu_activity import run as compact
    records=read(OUT/f'physical/{design}/qualification_pending_activity.json')['records']
    for record in records:
        if record.get('scientific_stop'):raise ValueError('Scientific stop prohibits activity')
        if record['status']!='PHYSICAL_AND_ATPG_PASS_ACTIVITY_PENDING':continue
        row=read(record['measurement_row']['path']);began=time.perf_counter();deadline=began+7200
        folder,evidence=prepare_activity(row,deadline)
        remaining=deadline-time.perf_counter()
        if remaining<=0:raise RuntimeError('Normal activity ceiling exhausted during preparation')
        compact(folder,'continuation','normal',remaining,spef_evidence=evidence)
        target=OUT/f'activity_workflows/{design}/{row["role"]}.json'
        measured_path=ROOT/'results/pact_cpu_scalability_20261005/activity/continuation'/design/row['role']/'normal/result.json'
        result=read(measured_path);stages={p.name.removesuffix('.execution.json'):read(p) for p in folder.glob('*.execution.json')}
        write(target,dict(design=design,candidate=row['role'],configured_timeout_seconds=7200,timeout_regime='normal',
            preparation_stages=stages,measurement=binding(measured_path),wall_seconds=time.perf_counter()-began,
            CPU_seconds=result['CPU_seconds']+sum(r['CPU_seconds'] for r in stages.values()),
            peak_RSS_KiB=max([result['peak_RSS_KiB']]+[r['peak_RSS_KiB'] for r in stages.values()]),
            simulator_seconds=result['simulator_seconds'],trace_bytes=result['trace_bytes'],complete=result['complete'],
            status=result['status'],termination_reason=result['termination_reason'],
            resource_scope='Preparation child CPU plus compact workflow; small preparation launcher CPU excluded'),immutable=True)


def aggregate(design):
    from pact_cold_start_report import activity_category,delta
    selection=read(OUT/f'selections/{design}/preselected_candidates.json')
    reference_path=(ROOT/'results/pact_cpu_scalability_20261005/spef_patch/reanalysis/result.json' if design=='s38584'
        else ROOT/'results/pact_cpu_scalability_20261005/activity/continuation/s38417/REF_B2/normal/result.json')
    reference=read(reference_path);results=[]
    for selected in selection['records']:
        name=selected['candidate'];pf=OUT/f'physical/{design}/{name}';pending=read(pf/'qualification_pending_activity.json')
        r=dict(design=design,candidate=name,status=pending['status'],architecture_hash=selected['architecture_hash'],
            epsilon=selected['epsilon'],route_roles=selected['route_roles'],seed=selected['seed'],
            exact_reference_activity=binding(reference_path),physical_and_ATPG=pending)
        activity_path=ROOT/'results/pact_cpu_scalability_20261005/activity/continuation'/design/name/'normal/result.json'
        if activity_path.exists():
            measured=read(activity_path)
            if measured['status']=='QUALIFIED' and measured['complete']:
                route,atpg=read(pending['physical']['path']),read(pending['atpg']['path'])
                if measured['architecture_sha256']!=r['architecture_hash'] or set(route['gates'].values())!={'PASS'}:
                    raise ValueError('Final architecture/physical gate mismatch')
                if atpg['status']!='ATPG_GATES_PASS' or read(atpg['serial']['path'])['status']!='PASS' or read(atpg['faults']['path'])['status']!='PASS':
                    raise ValueError('Final serial/FAN gates failed')
                r.update(status='QUALIFIED',E=measured['E'],H4=measured['H4'],H8=measured['H8'],
                    activity=binding(activity_path),routed_scan_wirelength_um=route['routed_scan_wirelength_um'],
                    DRC=route['DRC_errors'],structured_metrics=route['structured_metrics'],FAN_statistics=atpg['statistics'],
                    fault_identity_scope=atpg['identity_scope'])
                r['classification'],r['activity_relations']=activity_category(r,reference)
                r['activity_delta_percent']={m:delta(r[m],reference[m]) for m in ('E','H4','H8')}
            else:r.update(status='ACTIVITY_UNQUALIFIED',activity=binding(activity_path))
        results.append(r)
    write(OUT/f'final/{design}.json',dict(status='CONTINUATION_COMPLETE',design=design,created_utc=now(),
        records=results,qualified_candidates=sum(r['status']=='QUALIFIED' for r in results),
        scientific_method_changes=0,reference_activity=reference),immutable=True)
    print('CPU_CONTINUATION_FINAL',design,[r['status'] for r in results],flush=True)


def run(design):
    frozen_tools();logs=RUN/'workers'/design
    logs.mkdir(parents=True,exist_ok=True)
    for action,ceiling in (('physical',14400),('activity',3*7200+3600)):
        try:execute_stage([sys.executable,ROOT/'scripts/pact_cpu_qualify_continuation.py',action,'--design',design],
            logs,action,time.perf_counter()+ceiling)
        finally:
            target=OUT/'workers'/design;target.mkdir(parents=True,exist_ok=True)
            if (logs/(action+'.execution.json')).exists():shutil.copy2(logs/(action+'.execution.json'),target/(action+'.execution.json'))
    aggregate(design)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('run','physical','activity','aggregate'))
    p.add_argument('--design',choices=('s38417','s38584'),required=True);a=p.parse_args()
    os.environ.update(PACT_DEPENDENCY_ROOT='/root/pact-deps',PACT_EXPERIMENT_ROOT='/mnt/d/PACT_EXPERIMENTS',
        OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',NUMBA_NUM_THREADS='1',PATH='/usr/bin:'+os.environ['PATH'])
    globals()[a.action](a.design)
