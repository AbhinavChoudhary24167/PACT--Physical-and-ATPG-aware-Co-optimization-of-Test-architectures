"""Source freeze and final exhaustive artifact-preservation proof."""
from phase2d_common import *
import platform

def freeze():
    assert not (OUT/'execution_source_freeze.json').exists()
    paths=list((ROOT/'scripts').glob('phase2d*'))+[ROOT/'tests/unit/test_phase2d_decision.py']
    write(OUT/'execution_source_freeze.json',dict(utc=now(),files={str(p):sha(p) for p in paths},
        scientific_scores_computed=(OUT/'measurements.json').exists(),contract_sha256=sha(OUT/'contract.json')))
    print('EXECUTION_SOURCES_FROZEN',len(paths),flush=True)

def environment():
    assert not (OUT/'environment.json').exists()
    record=dict(utc=now(),platform=platform.platform(),python=sys.version,
        openroad_version=subprocess.check_output(['openroad','-version'],text=True).strip(),
        openroad_binary='/usr/bin/openroad',openroad_binary_sha256=sha('/usr/bin/openroad'),
        local_source_checkout_commit=subprocess.check_output(['git','-C','/root/pact-deps/OpenROAD','rev-parse','HEAD'],text=True).strip(),
        source_checkout_is_not_installed_binary=True,
        orfs_commit=subprocess.check_output(['git','-C',str(FLOW),'rev-parse','HEAD'],text=True).strip(),
        detail_placement_seed=1,global_routing_seed=29,initialization_seed=29,native_gp_seed=None)
    ex=run('placer_capabilities',['openroad','-no_init','-exit',ROOT/'scripts/phase2d_placer_capabilities.tcl'],60)
    assert ex['exit_code']==0
    upstream={}
    for d in DESIGNS:
        folder=ROOT/'artifacts/raw/phase0b/runs'/d/'source_place'
        execution=read(folder/'execution.json')
        assert execution['exit_code']==0
        for p,h in execution['outputs'].items():assert sha(p)==h,p
        assert sha(folder/'stdout.log')==execution['stdout_sha256']
        assert sha(folder/'stderr.log')==execution['stderr_sha256']
        upstream[d]=dict(execution=execution,files={str(p):sha(p) for p in folder.iterdir() if p.is_file()},
            retained_pregp_files=read(OUT/'contract.json')['pregp_sources'][d],
            original_placement_database_not_an_input_to_phase2d=True,
            note='Historical source GP logs establish the design config and source variant. Pre-GP checkpoints are retained within that source variant and were hashed before Phase-2D; no historical pre-GP content hash is claimed where none was originally recorded.')
    record['historical_source_provenance']=upstream
    write(OUT/'environment.json',record)
    print('ENVIRONMENT_AND_ANCESTRY_RECORDED',flush=True)

def finalize():
    verify_contract()
    for p,h in read(OUT/'execution_source_freeze.json')['files'].items():assert sha(p)==h,p
    initial=read(OUT/'initial_integrity.json');changed=[]
    for p,h in initial['upstream_snapshot'].items():
        if not Path(p).is_file() or sha(p)!=h:changed.append(p)
    current={str(p) for folder in (PRIOR,REPAIRED) for p in folder.rglob('*') if p.is_file()}
    assert not changed and current==set(initial['upstream_snapshot']),changed
    # Reverify every upstream manifest dependency, including archives outside the repository.
    for row in initial['checks']:assert sha(row['path'])==row['expected'],row['path']
    write(OUT/'final_integrity.json',dict(utc=now(),all_upstream_manifests_verified=True,
        verified_dependencies=len(initial['checks']),preserved_prior_result_files=len(current),changed=[],added=[],deleted=[],
        contract_sha256=sha(OUT/'contract.json'),phase2c_repair_and_multiseed_byte_identical=True))
    sources={str(p):sha(p) for p in (ROOT/'scripts').glob('phase2d*') if p.is_file()}
    sources[str(ROOT/'tests/unit/test_phase2d_decision.py')]=sha(ROOT/'tests/unit/test_phase2d_decision.py')
    outputs={str(p):sha(p) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name not in ('manifest.sha256','result_provenance.json')}
    provenance=dict(utc=now(),git_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        phase2c_repair_and_multiseed_byte_identical=True,prior_snapshot=initial['upstream_snapshot'],
        inputs=read(OUT/'contract.json')['frozen_files'],sources=sources,outputs=outputs,
        contract_sha256=sha(OUT/'contract.json'),new_exact_order_implementations=read(OUT/'physical_results.json')['new_exact_order_implementations'],
        optimizer_run=False,atpg_regenerated=False,phase3_started=False,pushed=False,
        manifest_policy='SHA256 manifest covers every Phase-2D output, implementation source, frozen input and historical result. Manifest excludes itself; provenance excludes itself and manifest.')
    write(OUT/'result_provenance.json',provenance)
    entries={**provenance['prior_snapshot'],**provenance['inputs'],**sources,**outputs,
             str(OUT/'result_provenance.json'):sha(OUT/'result_provenance.json')}
    (OUT/'manifest.sha256').write_text(''.join(h+'  '+p+'\n' for p,h in sorted(entries.items())))
    # Every digest above came from the final file bytes; verify exact written manifest parsing.
    assert len((OUT/'manifest.sha256').read_text().splitlines())==len(entries)
    print('FINALIZED',len(entries),'manifest entries;',len(current),'prior files preserved',flush=True)

if __name__=='__main__':{'freeze':freeze,'environment':environment,'finalize':finalize}[sys.argv[1]]()
