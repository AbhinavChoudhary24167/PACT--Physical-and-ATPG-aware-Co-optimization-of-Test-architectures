#!/usr/bin/env python3
"""Requalify only the blocked analysis using bound complete simulation counts."""
import os
from pathlib import Path
import shutil
import sys
import time
from pact_generalization import ROOT,read,write,sha,now,binding
from pact_generalization_infrastructure import external_binding
from pact_cold_start_measure import execute_stage
from pact.activity.spef_evidence import checked

OUT=ROOT/'results/pact_cpu_scalability_20261005/spef_patch'
RUN=Path('/mnt/d/PACT_EXPERIMENTS/results/pact_cpu_scalability_20261005/spef_patch')


def main():
    began=time.perf_counter();deadline=began+7200
    os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',NUMBA_NUM_THREADS='1')
    failed_path=ROOT/'results/pact_cpu_scalability_20261005/activity/continuation/s38584/REF_B3T/normal/result.json'
    failed=read(failed_path);source=Path(failed['output_folder'])
    if failed['status']!='FAILED' or failed['stages']['simulate']['returncode']!=0 or failed['stages']['simulate']['timed_out']:
        raise ValueError('Only the completed-simulation, failed-analysis point may be resumed')
    stop=read(ROOT/'results/pact_cpu_scalability_20261005/scientific_stop.json')
    checked(stop['complete_counts']);checked(stop['simulation']);checked(stop['FF_crosscheck'])
    source_manifest=read(source.parents[1]/'manifest.json')
    for item in source_manifest['inputs'].values():checked(item)
    log=(source/'simulate.log').read_text()
    if 'PACT_COUNTS_COMPLETE' not in log or 'PASS patterns=' not in log or 'PACT_COUNTS_ERROR' in log:
        raise ValueError('Preserved simulation is not complete and functionally checked')
    if read(source/'FF_transition_crosscheck.json')['status']!='PASS':
        raise ValueError('Preserved independent FF check failed')
    root=RUN/'reanalysis';folder=root/'s38584/REF_B3T'
    if root.exists():raise ValueError('Preserve previous reanalysis')
    folder.mkdir(parents=True)
    # Reanalysis inputs are read only. Same-volume links avoid duplicating the
    # complete 482-MB trace; no link is opened for writing.
    for name in ('routed.v','net_mapping.json','cycles.json','workload.json','extracted.spef','activity.counts.gz'):
        os.link(source/name,folder/name)
    shutil.copy2(source.parents[1]/'manifest.json',root/'manifest.json')
    evidence=RUN/'implementation_evidence.json'
    write(root/'reanalysis_manifest.json',dict(created_utc=now(),design='s38584',role='REF_B3T',
        original_failed_result=binding(failed_path),complete_trace=stop['complete_counts'],
        implementation_evidence=external_binding(evidence),configured_timeout_seconds=7200,timeout_regime='normal',
        simulation_reused=True,simulation_reexecuted=False,
        count_cache_policy='Read-only old cache; every byte rechecked against complete CRC/footer-validated compressed counts',
        sources={p:binding(ROOT/p) for p in ('scripts/pact_spef_reanalyse.py','src/pact/activity/spef_evidence.py',
            'src/pact/activity/compact.py','src/pact/physical_effect.py','scripts/pact_cpu_activity.py')}),immutable=True)
    stage=execute_stage([sys.executable,ROOT/'scripts/pact_cpu_activity.py','--analyze-folder',folder,
        '--spef-evidence',evidence,'--count-cache',source/'transitions.u8'],folder,'reanalyze',deadline)
    summary=read(folder/'activity_summary.json');diagnostics=read(folder/'missing_spef_diagnostics.json')
    if diagnostics['status']!='PASS' or read(folder/'FF_transition_crosscheck.json')['status']!='PASS':
        raise ValueError('Repaired analysis qualification gates failed')
    if {r['net'] for r in diagnostics['records']}!={'net654','net655','net714','net719'}:
        raise ValueError('Actual four-net reproduction does not match the registered blocker')
    data=summary['scopes']['all_data']
    result=dict(status='QUALIFIED',created_utc=now(),design='s38584',role='REF_B3T',complete=True,
        architecture_sha256=failed['architecture_sha256'],E=data['cap_weighted_ff_transitions']['total'],
        H4=data['grids']['4']['cap_peak_per_cycle']['maximum'],H8=data['grids']['8']['cap_peak_per_cycle']['maximum'],
        configured_timeout_seconds=7200,timeout_regime='normal',wall_seconds=time.perf_counter()-began,
        CPU_seconds=stage['CPU_seconds'],peak_RSS_KiB=stage['peak_RSS_KiB'],
        simulator_seconds=0.,original_simulator_seconds=failed['simulator_seconds'],simulation_reused=True,
        trace_bytes=(folder/'activity.counts.gz').stat().st_size,trace=external_binding(folder/'activity.counts.gz'),
        manifest=external_binding(root/'reanalysis_manifest.json'),activity_summary=external_binding(folder/'activity_summary.json'),
        missing_SPEF_diagnostics=external_binding(folder/'missing_spef_diagnostics.json'),
        termination_reason='Complete preserved simulation plus independent FF replay and evidence-qualified capacitances',
        metric_definitions_changed=False,stage=stage,output_folder=str(folder))
    write(folder/'result.json',result,immutable=True)
    target=OUT/'reanalysis';target.mkdir(parents=True,exist_ok=False)
    for name in ('result.json','activity_summary.json','FF_transition_crosscheck.json','missing_spef_diagnostics.json'):
        shutil.copy2(folder/name,target/name)
    shutil.copy2(root/'reanalysis_manifest.json',target/'manifest.json')
    shutil.copy2(evidence,OUT/'implementation_evidence.json')
    print('SPEF_PATCH_REQUALIFIED',result['E'],result['H4'],result['H8'],flush=True)


if __name__=='__main__':main()
