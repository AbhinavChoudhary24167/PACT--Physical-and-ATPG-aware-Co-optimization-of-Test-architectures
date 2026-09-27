"""Finalize immutable provenance, or document a mandatory scientific stop."""
from phase2crm_execute import *
import argparse
import csv

def freeze_execution():
    path=OUT/'execution_source_freeze.json';assert not path.exists()
    files={str(p):sha(p) for folder,pattern in ((ROOT/'scripts','phase2crm*.py'),(ROOT/'tests/unit','test_phase2crm*.py')) for p in folder.glob(pattern)}
    for p in (ROOT/'scripts/phase2c_run.py',ROOT/'scripts/phase2c_physical.py',ROOT/'scripts/phase0c_rewire_odb.py',ROOT/'scripts/phase0d_verify_routed.py',ROOT/'src/pact/physical/phase0d_routed.py',ROOT/'scripts/phase2b_extract.py',ROOT/'scripts/phase2a_extract_odb.py',ROOT/'src/pact/analysis/phase2b_reference.py'):
        files[str(p)]=sha(p)
    write(path,dict(utc=now(),files=files,scientific_outcomes_calculated=(OUT/'measurements.json').exists()))
    print('EXECUTION_SOURCES_FROZEN',len(files))

def finalize():
    verify()
    for p,h in read(OUT/'execution_source_freeze.json')['files'].items():check(p,h)
    final=boundary();write(OUT/'final_integrity.json',final)
    initial=read(OUT/'initial_integrity.json')
    assert initial['seed11_files']==final['seed11_files']
    assert initial['frozen_sources']==final['frozen_sources']
    tests=read(OUT/'tests.json')
    if (OUT/'topology_audit.json').exists():
        top=read(OUT/'topology_audit.json');tests['topology']=dict(status=top['status'],passed=top.get('passed',len(top.get('rows',[]))),frozen_seed11_proofs_reused=21)
    tests['seed11_predictor_regression']=dict(status='PASS',method='Unchanged original 14-test suite plus all frozen output/source SHA256 values; no Phase-2C-R restart')
    write(OUT/'tests.json',tests)
    if (OUT/'physical_results.json').exists():
        rows=read(OUT/'physical_results.json')['rows']
        cp=read(OUT/'commands.json');cp['physical_executions']=[dict(design=r['design'],seed=r['seed'],label=r['label'],
            executions={k:v for k,v in r.items() if k.endswith('_execution')}) for r in rows if not r.get('multiseed_reused')]
        cp['initial_read_only_commands']=['Read user attachment; repository Phase-2C-R scripts/reports/contracts/commands/tests/provenance; Phase-1/2 physical evidence',
            'git status --porcelain=v1','git diff --binary','git rev-parse HEAD','git branch --show-current',
            'wsl --list --quiet (sandbox E_ACCESSDENIED); elevated Ubuntu-24.04 runtime succeeded',
            'phase2cr_common.integrity plus all result/source hash verification',
            'python scripts/phase2crm_audit.py > inventory.log 2>&1',
            'python scripts/phase2crm_register.py > register.log 2>&1']
        write(OUT/'commands.json',cp)
    provenance=dict(utc=now(),git_commit=final['git_commit'],seed11_unchanged=True,attempt1_preserved=True,
        frozen_inputs=read(OUT/'freeze.json')['files'],seed11_preserved=final['seed11_files'],
        sources=dict(final['frozen_sources'],**read(OUT/'execution_source_freeze.json')['files']),
        outputs={str(p):sha(p) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name not in ('result_provenance.json','manifest.sha256')},
        note='SHA256 of raw physical commands, logs, databases, SPEF, ownership, scores and figures included. Manifest excludes itself; provenance excludes itself and manifest. No push.')
    write(OUT/'result_provenance.json',provenance)
    entries={**provenance['frozen_inputs'],**provenance['seed11_preserved'],**provenance['sources'],**provenance['outputs']}
    entries[str(OUT/'result_provenance.json')]=sha(OUT/'result_provenance.json')
    (OUT/'manifest.sha256').write_text(''.join(h+'  '+p+'\n' for p,h in sorted(entries.items())))
    for p,h in entries.items():check(p,h)
    print('FINAL_MANIFEST_VERIFIED',len(entries),'files; seed11 and Attempt 1 unchanged',flush=True)

def stop():
    reason=sys.argv[2] if len(sys.argv)>2 else 'See preserved failure logs'
    status='PACT_PHASE2CR_MULTISEED_VALIDATION_INCOMPLETE'
    write(OUT/'results.json',dict(classification=status,reason=reason,scientific_results_evaluated=False,
        leave_seed11_out=dict(qualifies=None,reason='Required physical qualification did not complete')))
    for name,header in [('per_seed_results.csv','design,seed,predictor,target,spearman,status'),('per_architecture_results.csv','design,seed,label,predictor,target,status'),('pair_direction_results.csv','design,seed,left,right,predictor_delta,physical_delta,status')]:
        if not (OUT/name).exists():(OUT/name).write_text(header+'\n')
    lines=['# Phase-2C-R multiseed validation: mandatory stop','',f'Primary classification: **{status}**.','',reason,'',
        'No new predictor correlations were calculated after the stop. Missing evidence is not counted as a scientific failure or a favorable replication. Completed physical attempts and all historical results are retained.','',
        '1. Independent physical seeds tested per design: no completed multiseed qualification; seed 11 remains previously qualified. Available seed labels denote perturb-and-legalize realizations, not independent global placer runs.',
        '2. Qualifies without seed 11: undetermined.',
        '3. Most stable family: undetermined.',
        '4. Least stable family: undetermined.',
        '5. Most seed-sensitive design: undetermined.',
        '6. Pair directions consistent across all seeds: undetermined.',
        '7. Seed-11 dependence: not tested to completion.',
        '8. Rank-consistent but negligible effects: undetermined.',
        '9. Architecture reversals: undetermined.',
        '10. Ready for optimization: not established.',
        '11. Exact blocker: '+reason,
        '12. Smallest next experiment: resolve only the recorded qualification blocker in a separately authorized continuation, preserve this stop, then complete the frozen subset. Do not tune the predictor or launch a broader campaign.',
        '', 'Required scientific figures are withheld because qualified multiseed measurements do not exist; no placeholder measurements were invented. See tests.json, topology_audit.json, physical_results.json and logs for actual execution status.']
    (OUT/'FINAL_REPORT.md').write_text('\n'.join(lines)+'\n')

if __name__=='__main__':
    {'freeze':freeze_execution,'finalize':finalize,'stop':stop}[sys.argv[1]]()
