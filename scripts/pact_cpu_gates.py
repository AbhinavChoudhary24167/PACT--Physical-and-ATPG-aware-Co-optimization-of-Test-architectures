"""Fail-closed development gates and CPU resource policy for continuations."""
from pathlib import Path
import os
from pact_generalization import ROOT, read, sha, write, now
from pact_generalization_infrastructure import external_binding, REPAIRED

OUT = ROOT/'results/pact_cpu_scalability_20261005'
CORE_SOURCES = ('src/pact/activity/counts_vpi.cpp','src/pact/activity/compact.py','src/pact/physical_effect.py')


def require_continuation_allowed():
    if (OUT/'scientific_stop.json').exists():
        require_spef_patch()
    require_activity_equivalence()


def require_spef_patch():
    path=OUT/'spef_patch/qualification.json'
    if not path.exists():
        raise ValueError('Recorded scientific stop prohibits continuation; preserve the failed experiment')
    qualification=read(path)
    if qualification['status']!='PASS':raise ValueError('Missing-SPEF repair is not qualified')
    for item in qualification['core_sources'].values():
        if sha(item['path'])!=item['sha256']:raise ValueError('Qualified missing-SPEF repair source changed')
    item=qualification['requalified_reference']
    if sha(item['path'])!=item['sha256']:raise ValueError('Requalified reference receipt changed')
    result=read(item['path'])
    if result['status']!='QUALIFIED' or not result['complete']:
        raise ValueError('Repaired exact reference activity is not qualified')
    return qualification


def require_activity_equivalence():
    if read(OUT/'evaluator_equivalence.json')['status'] != 'PASS':
        raise ValueError('CPU evaluator equivalence has not passed')
    for design in ('s953','s1196','s35932'):
        folder = OUT/'activity/equivalence'/design/'CS_C1/normal'
        result, manifest = read(folder/'result.json'), read(folder/'manifest.json')
        if result['status'] != 'QUALIFIED' or result['equivalence']['status'] != 'PASS':
            raise ValueError('Compact equivalence has not passed: '+design)
        for name in CORE_SOURCES:
            if sha(ROOT/name) != manifest['sources'][name]['sha256']:
                if name!='src/pact/activity/compact.py':
                    raise ValueError('Validated activity core changed: '+name)
                patch=require_spef_patch()
                if patch['baseline_compact_sha256']!=manifest['sources'][name]['sha256']:
                    raise ValueError('Missing-SPEF patch does not bind the validated activity baseline')


def register_policy():
    require_activity_equivalence()
    path = OUT/'cpu_worker_policy.json'
    if path.exists(): return read(path)
    total = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemTotal:')))
    measured = read(OUT/'profile_incremental_128_sparse.json')['peak_RSS_KiB']
    background, reserve = 567*1024, 512*1024
    maximum = max(1, min(os.cpu_count(), (total-background-reserve)//measured))
    repaired = read(ROOT/'results/pact_end_to_end_20261004/upstream_repair/qualification.json')
    if sha(REPAIRED) != repaired['repaired_executable_sha256']:
        raise ValueError('Qualified repaired FAN executable changed')
    policy = dict(created_utc=now(), available_CPUs=os.cpu_count(), memory_total_KiB=total,
        observed_evaluator_peak_RSS_KiB=measured, background_allowance_KiB=background,
        RAM_reserve_KiB=reserve, maximum_evaluator_workers_from_observed_memory=maximum,
        configured_CPU_workers=1, native_threads=1, simulator_jobs=1, OpenROAD_jobs=1,
        OpenROAD_threads=2, simultaneously_active_job_groups=1,
        parallelism_status='NOT_IMPLEMENTED; full evaluator jobs capped by measured RSS and RAM reserve',
        swap_counted_as_parallel_worker_capacity=False,
        actual_FAN=external_binding(REPAIRED), actual_FAN_qualification=external_binding(ROOT/'results/pact_end_to_end_20261004/upstream_repair/qualification.json'),
        normal_activity_ceiling_seconds=7200, diagnostic_activity_ceiling_seconds=14400)
    write(path,policy,immutable=True)
    return policy
