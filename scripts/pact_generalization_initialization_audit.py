"""Bind the history-dependent warm-start contract without running a search."""
from pact_generalization import ROOT,OUT,binding,now,read,write

records=[]
for design in ('s5378','s9234','s15850'):
    stages=[]
    for namespace in ('pact_v2','pact_candidate_sensitive','pact_candidate_stateful'):
        search=ROOT/f'results/{namespace}/{design}/search.json'
        inputs=ROOT/f'results/{namespace}/{design}/inputs.json'
        data=read(search)
        stages.append(dict(stage=namespace,search=binding(search),inputs=binding(inputs),
            config=read(inputs)['config'],
            selected_architecture_hashes=[r['architecture_sha256'] for r in data['selected']],
            starting_architecture_labels=[r.get('label') for r in data['baselines']]))
    records.append(dict(design=design,precursor_stages=stages))
paths=('scripts/pact_stage_b.py','scripts/pact_v2.py','scripts/pact_candidate_sensitive.py',
    'scripts/pact_candidate_stateful.py','scripts/pact_oss_benchmark.py',
    'results/pact_oss_benchmark/stage_a/P0_FREEZE.json',
    'results/pact_oss_benchmark/stage_a/P0_SELECTION.json',
    'results/pact_oss_benchmark/topology_recovery_20261004/stage_a/comparison_policy.json')
write(OUT/'searches/initialization_audit.json',dict(schema='pact_generalization_initialization_audit_v1',
    created_utc=now(),classification='ENGINEERING_SCALABILITY_BLOCKER',failure_class='TOOL_BUG',
    subtype='UNSEEN_INPUT_INITIALIZATION',PACT_searches_executed=0,scientific_method_changes=0,
    evidence={p:binding(ROOT/p) for p in paths},historical_precursor_records=records,
    frozen_starts='Stage-B starts from measured B2, B3T, and the pre-existing representative P0 endpoint',
    P0_selection='Predicted minimax normalized-regret point from the sealed stateful archive; retained without reselection',
    predecessor_dependency='Stateful starts include candidate-sensitive selections; candidate-sensitive starts include qualified v2 selections; v2 starts include historical P/T, J50, and an earlier working PACT architecture',
    missing_new_design_contract=['P/T physical-input role on an unseen circuit',
        'Earlier working-PACT architecture construction and budget',
        'Precursor qualification and warm-start propagation through v2 and candidate-sensitive stages',
        'How the full precursor routing workload fits the requested per-design candidate routing limit'],
    preserved_action='No seed omitted or substituted; no PACT search executed',
    requested_resolution='Reproduce the full frozen precursor pipeline only under a defined unseen-input policy, or stop at the initialization blocker'),immutable=True)
print('INITIALIZATION_AUDIT_BOUND_WITHOUT_SEARCH',flush=True)
