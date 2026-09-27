"""Freeze seed selection and decision rules before new scientific outcomes."""
from phase2crm_audit import *
from pact.scan.model import ScanArchitecture

def main():
    assert not (OUT/'multiseed_contract.json').exists()
    inv=read(OUT/'seed_inventory.json'); selected=[]
    # Check every exact physical architecture against the older route archives.
    for cell in inv['cells']:
        if not cell['route_available']:
            d,s=cell['design'],cell['seed']
            for ap in (ROOT/f'artifacts/derived/phase0c/{d}/s{s}/k2').glob('*.architecture.json'):
                if ScanArchitecture.from_json(ap).sha256()!=cell['architecture_sha256']:continue
                folder=ROOT/f'artifacts/raw/phase0c/physical/{d}/s{s}/k2'/ap.name.split('.')[0]
                rp=folder/'route_metrics.json'; r=read(rp)
                if r['status']!='QUALIFIED':continue
                archive=folder/'5_2_route.odb.gz'; check(archive,r['routed_odb_gzip_sha256'])
                cell.update(route_available=True,new_route_required=False,timing_available=True,
                    reuse_archive=str(archive),reuse_route_metrics=str(rp))
                for p in (archive,rp,ap,folder/'routed_verification.json'):inv['files'][str(p)]=sha(p)
        if cell['seed'] in (11,13,17):selected.append(cell)
    for row in inv['rows']:
        cs=[c for c in inv['cells'] if (c['design'],c['seed'])==(row['design'],row['seed'])]
        row['counts']={k:sum(c[k] for c in cs) for k in ('route_available','spef_available','timing_available','mapping_available','activity_available')}
        row['new_routes_required']=sum(c['new_route_required'] for c in cs)
    write(OUT/'seed_inventory.json',inv)
    with (OUT/'SEED_INVENTORY.md').open('a') as f:
        f.write('\n## Exact-order archive reuse audit\n\n')
        for row in inv['rows']:f.write(f"- {row['design']} seed {row['seed']}: {row['counts']['route_available']} exact-order routes, {row['counts']['spef_available']} SPEFs; {row['new_routes_required']} new routes required.\n")
        f.write('\nThe table above describes Phase-2C extraction-ready evidence; this addendum also checks every Phase-0C route archive by canonical physical architecture identity.\n')
    n=sum(c['new_route_required'] for c in selected); assert n<=30
    alln=sum(c['new_route_required'] for c in inv['cells'])
    contract=dict(registered_utc=now(),seeds=[11,13,17],new_seeds=[13,17],designs=list(DESIGNS),
        architecture_set='All 21 repaired seed-11 scan orders, K=2, 9/6/6; only coordinates vary by seed',
        cells=selected,source_hashes=read(OUT/'initial_integrity.json')['frozen_sources'],
        predictor='Unmodified phase2cr_loads.construct_with_audit; CAP_PER_UM=0.103981; unmodified score_packed',
        endpoint_pairs=[['M3_load','cap_total'],['M3_load_local','cap_local_peak'],['M5_hpwl','wire_total'],['M5_hpwl_local','wire_local_peak']],
        topology='Unchanged repaired ownership/schema rules and topology assertions; adapter only parameterizes seed and evidence paths. All topology gates precede scientific scoring.',
        statistics='Inherited correlations and compare_pairs; exact ties, ascending average ranks, all unordered pairs; raw Spearman/Kendall/Pearson; no p-values or CI',
        gates=dict(rho=.7,non_tied_accuracy=.75,both_endpoints=True,undefined_fails=True),
        classification=dict(CONFIRMED='All six design/family cells pass both endpoints at every registered seed and leave-11-out. Scope limited to registered perturb-and-legalize physical realizations.',
            PARTIAL='At least one complete design/family/new-seed cell passes, but not all required cells pass.',
            FAIL='No complete design/family/new-seed cell passes; seed 11 never rescues failure.',
            INCOMPLETE='Required physical evidence cannot be recovered/generated, or a mandatory integrity/topology stop prevents qualification. Observed failures remain visible.'),
        materiality=dict(relative_physical_difference_percent=1.0,formula='100*abs(right-left)/abs(left)',
            purpose='Preregistered descriptive engineering tolerance only, not a significance, accuracy, or power threshold. Zero left denominator => undefined.'),
        cross_seed='Mean/median/min/max/sample SD/sign consistency per endpoint, gate counts; leave-11-out separately. Pair reversals and leave-one-pair/architecture/seed/design descriptive sensitivities cannot rescue gates.',
        exclusions='Seeds 19/23 excluded solely by pre-outcome balanced route budget; all unqualified selected cells remain visible. No replacement, no cherry-picking, no architecture expansion.',
        routing=dict(new_routes_max=n,physical_jobs_max=sum(c['seed']!=11 and not c['spef_available'] for c in selected),
            workers=2,one_attempt_per_cell=True,route_timeout_s=600,rewire_timeout_s=120,verify_timeout_s=90,extraction_timeout_s=180),
        stopping='Any frozen hash/source/seed11 change, topology/identity ambiguity, leakage, missing provenance, or need to change metric/threshold stops scientific execution immediately. No tuning, retries, optimizer, ATPG, ML, Phase-2D, or push.',
        seed_limitation=inv['physical_seed_method']['limitation'],independent_global_placement_runs=0)
    write(OUT/'multiseed_contract.json',contract)
    doc='''# Phase-2C-R multiseed validation contract

Registered before any new corrected scores, correlations, ranks, or physical jobs.
The machine-readable multiseed_contract.json is authoritative and freezes A-J:
predictor, topology, architectures, metrics, statistics, all-pair directions,
thresholds, exclusions, seed identities and stopping rules.

Use all 21 repaired architecture orders on seeds 11, 13, 17 (63 cells).
The two new seeds are chosen by existing complete s5378 evidence and a balanced
route budget, without viewing corrected outcomes. Seeds 19/23 remain inventoried.
Frozen chain membership/order is held constant while physical coordinates vary.
The seed-11 baseline is referenced byte-for-byte, not rerun or overwritten.

M3 and M5 use the exact repaired implementation. Frozen packed activity,
carry-loaded/no-capture/no-final-unload semantics, Liberty, coefficient, 10x10
bins and all 81 contained 2x2 windows remain unchanged. SPEF/routed wire targets
are labels only. All topology and electrical ownership checks precede scoring.
Existing topology assertions may be parameterized only for seed/evidence paths;
predictor definitions and arithmetic must not change.

Every design/seed/family requires rho >= 0.7 and non-tied pair accuracy >= 0.75
on BOTH total and local endpoints. Undefined fails. All unordered pairs and exact
ties are reported. CONFIRMED requires every cell including leave-11-out;
PARTIAL requires at least one complete new-seed cell; FAIL means no complete
new-seed cell passes. INCOMPLETE is reserved for missing required physical
evidence or a mandatory integrity/topology stop. No pooled rescue.

Describe effect sizes with signed and percentage deltas. Physical differences
below 1% of the left endpoint are descriptively negligible for this validation;
this new, pre-outcome reporting tolerance does not alter any qualification gate.
No significance claims, bootstrap, permutation p-values or confidence intervals.
Report sample SD across seeds and raw failures; small architecture/seed counts
and shared placement ancestry preclude broad population inference.

These are independently seeded perturb-and-legalize realizations from ONE global
placement per design, not independent global-placement optimizations. Any positive
classification is conditional on this physical-seed regime; independent placer
generalization remains untested. No seed-11-only result can establish replication.

Stop immediately on source/frozen-evidence changes, topology or identity failure,
target leakage, absent provenance or any need to alter a metric/threshold.
One bounded physical attempt per missing cell; no automatic retry or expansion.
Do not launch the next experiment, optimizer, ML, ATPG, Phase-2D or GitHub push.
'''
    (OUT/'MULTISEED_CONTRACT.md').write_text(doc)
    # Existing route helper expects this filename; it is an identical frozen alias.
    (OUT/'EXPERIMENT_CONTRACT.md').write_text(doc)
    (OUT/'ROUTE_BUDGET.md').write_text(f'''# Bounded route budget

Inventory complete before launch. Full five-seed exact-order campaign would
need {alln} new routes. Choose balanced seeds 13 and 17 for all three designs,
retaining the complete 9/6/6 architecture sets. Seed 11 is reference-only.
Required new routes: exactly {n}; hard maximum {n}. Existing routes and SPEF
are reused wherever canonical architecture/input hashes match. At most two
physical workers, one attempt per cell; 600-second route limit. No broad sweep.
The extra two s5378/19 completed cases remain preserved but outside this balanced
preregistration; their outcomes are not used to select seeds or architectures.
''')
    deps=dict(inv['files'])
    for p in (OUT/'MULTISEED_CONTRACT.md',OUT/'EXPERIMENT_CONTRACT.md',OUT/'multiseed_contract.json',OUT/'seed_inventory.json',OUT/'ROUTE_BUDGET.md',ROOT/'src/pact/analysis/phase2b_scoring.py',ROOT/'scripts/phase2b_report.py',ROOT/'scripts/phase2a_validate.py'):
        deps[str(p)]=sha(p)
    write(OUT/'freeze.json',dict(utc=now(),files=deps,scientific_outcomes_calculated=False,new_routes_launched=0))
    print('REGISTERED',len(selected),'cells;',n,'new routes maximum;',contract['routing'])

if __name__=='__main__':main()
