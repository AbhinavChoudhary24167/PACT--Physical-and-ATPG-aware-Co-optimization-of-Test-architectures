#!/usr/bin/env python3
"""Campaign-level Gate-09 report, including every admitted and held design."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
import pact_gate09_admission as admission
import pact_gate09_reference as references
from pact_gate09_report import number
from pact_experiment_receipts import atomic_write


def classify_campaign(reports, holds, families):
    primary = [next((row for row in report['rows'] if row['role']==report['primary_candidate']), None)
               for report in reports]
    qualified = bool(primary) and all(row and row['qualification_status']=='QUALIFIED' for row in primary)
    strong = bool(reports) and all(set((report['reference_method'],'B4','B5')) <=
                                  set(report['summary']['PACT_DOMINATES']) for report in reports)
    if any(report['summary']['PACT_DOMINATED_BY'] for report in reports):
        status = 'PACT_GATE09_COMPETITOR_DOMINANCE_OBSERVED'
    elif not holds and len(families)>=2 and qualified and strong:
        status = 'PACT_GATE09_COMPETITIVE_GENERALIZATION_CONFIRMED'
    elif qualified and any(report['classification'] in ('PACT_ACTIVITY_MIXED','PACT_ACTIVITY_IMPROVEMENT_ALL_COORDINATES')
                           for report in reports):
        status = 'PACT_GATE09_MIXED_GENERALIZATION'
    else:
        status = 'PACT_GATE09_INCONCLUSIVE'
    if holds or len(families)<2:
        generalization = 'PACT_GATE09_INCONCLUSIVE_RESOURCE_OR_ADMISSION_LIMITED'
    elif status == 'PACT_GATE09_COMPETITIVE_GENERALIZATION_CONFIRMED':
        generalization = 'PACT_GATE09_UNSEEN_GENERALIZATION_CONFIRMED_WITHIN_FIXED_COHORT'
    elif qualified:
        generalization = 'PACT_GATE09_UNSEEN_QUALIFICATION_OBSERVED_WITHIN_FIXED_COHORT'
    else:
        generalization = 'PACT_GATE09_INCONCLUSIVE'
    return status, generalization


def create(output, ledger_path=None):
    if output.exists():
        raise ValueError('Preserve prior campaign report')
    ledger_path = ledger_path or references.BASE_META / 'cohort_execution.json'
    ledger = admission.read(ledger_path)
    if ledger['state'] != 'COHORT_TERMINAL':
        raise ValueError('Wait for terminal cohort admission/comparison outcomes')
    protocol = admission.read(admission.INTAKE)
    definitions = admission.read(references.BASE_META / 'manifests/competitive_method_definitions.json')
    reports = [admission.read(r['report']['path']) for r in ledger['records']
               if r['status']=='COMPETITIVE_COMPARISON_TERMINAL']
    rows = [dict(row) for report in reports for row in report['rows']]
    dominated_by = {r['design']:r['summary']['PACT_DOMINATED_BY'] for r in reports}
    dominates = {r['design']:r['summary']['PACT_DOMINATES'] for r in reports}
    mutual = {r['design']:r['summary']['MUTUALLY_NONDOMINATED'] for r in reports}
    holds = [r for r in ledger['records'] if r['status']!='COMPETITIVE_COMPARISON_TERMINAL']
    families = sorted({r['design_family'] for r in rows if r['design'] in ('b14_opt','b15_opt')})
    status, generalization = classify_campaign(reports, holds, families)
    if holds:
        next_action = 'Resolve the documented source/reference/resource admission hold, then test further unseen base-family designs with the same frozen method and controls; keep any new campaign separate.'
    elif any(dominated_by.values()):
        next_action = 'Study the observed baseline dominance after freezing this result set; any method changes belong to POST_GATE09_METHOD_DEVELOPMENT and need a new independent evaluation.'
    else:
        next_action = 'Run a preregistered multi-seed robustness study using the same seed set for all relevant methods, followed by an independent technology or family replication.'
    summary = dict(GATE09_STATUS=status, PACT_FROZEN=True, PACT_SHA='71b059d9d1a00735d79b6a428693eaba549a5f33',
        OPENROAD_SHA='08f67ee5ecd14db5a42be8c610bbfd1ccf079299',
        FAN_ATPG_SHA='4c253bfa613e5827f17c42a5fce8be7bea779e1e', ORFS_SHA='5e8b1450d19263f797a27c4f371b9dd19f32a3aa',
        CAPACITY_GATE='FIXED_FLOORS_ENFORCED_AT_EVERY_HEAVY_STAGE', B14_REFERENCE_STATUS='QUALIFIED',
        BASELINES_IMPLEMENTED=['B0','B1','B2','B3T','B4','B5'],
        BASELINES_QUALIFIED={r['design']:r['summary']['BASELINES_QUALIFIED'] for r in reports},
        PACT_SEARCH_STATUS={r['design']:'SEARCH_COMPLETE' for r in reports},
        PACT_CANDIDATES_FROZEN={r['design']:r['summary']['PACT_CANDIDATES_FROZEN'] for r in reports},
        COMMON_BACKEND_QUALIFIED={r['design']:r['fairness']['status'] for r in reports},
        ATPG_QUALIFIED={r['design']:r['summary']['ATPG_QUALIFIED'] for r in reports},
        EXACT_ACTIVITY_QUALIFIED={r['design']:r['summary']['EXACT_ACTIVITY_QUALIFIED'] for r in reports},
        COMPETITIVE_RESULTS={r['design']:r['classification'] for r in reports},
        PARETO_RESULTS={r['design']:r['summary']['PARETO_RESULTS'] for r in reports},
        PACT_DOMINATES=dominates, PACT_DOMINATED_BY=dominated_by, MUTUALLY_NONDOMINATED=mutual,
        GENERALIZATION_CLASSIFICATION=generalization, COMPETITIVE_CLASSIFICATION=status,
        PR_NUMBER=None, PR_URL=None, MERGED=False, MERGED_SHA=None, WORKTREE_CLEAN=None,
        SCIENTIFIC_BLOCKERS=holds, NEXT_ACTION=next_action,
        publication_note='Post-merge GitHub/branch/cleanliness provenance is recorded in a separate immutable publication receipt.')
    for held in holds:
        entry = next(r for r in protocol['cohort'] if r['design']==held['design'])
        for method in ('B0','B1','B2','B3T','B4','B5','PACT'):
            rows.append(dict(gate='GATE09', design=entry['design'], design_family=entry['family'], method=method, role=method,
                source_FF_count=entry['source_FF_count'], ff_count=None, chain_count=None, patterns=None,
                architecture_hash=None, reference_hash=None, seed=11, E=None,H4=None,H8=None,
                routed_scan_wirelength_um=None, delta_routed_WL_percent=None, delta_E_percent=None,
                delta_H4_percent=None, delta_H8_percent=None,WNS=None,hold_WNS=None,DRC=None,fault_coverage=None,
                runtime_seconds=None, qualification_status='NOT_ADMITTED', classification=held['status'],
                reason=held['reason'], receipt_paths=[held['receipt']] if held.get('receipt') else []))
    report = dict(schema='pact_gate09_campaign_report_v1', created_utc=datetime.now(timezone.utc).isoformat(),
        summary=summary, rows=rows, design_admission=ledger['records'], cohort=protocol['cohort'],
        ledger=admission.binding(ledger_path), definitions=definitions,
        upstream_issue=admission.binding(references.BASE_META / 'publication/FAN_upstream_issue.json'),
        design_reports=[r['report'] for r in ledger['records'] if r['status']=='COMPETITIVE_COMPARISON_TERMINAL'],
        observed_base_families=families, independent_family_count=len(families),
        classification_rule='Four-objective relative1e-10 dominance; primary balanced candidate retained; held designs never scored as PACT losses',
        claims=dict(established='The source, qualification, runtime and final measurement receipts for admitted designs',
            observed='The stated single-seed, single-technology Pareto relations within admitted designs',
            hypothesis='Mechanistic explanations or improvements require a separately registered follow-up',
            not_established='Universal superiority, physical power reduction, industry-tool comparison, arbitrary scaling, four independent families'))
    output.mkdir(parents=True)
    atomic_write(output / 'campaign_report.json', report, immutable=True)
    atomic_write(output / 'machine_summary.json', summary, immutable=True)
    text = ['# Gate 09: frozen PACT unseen-design and open-source comparison', '',
        '## A. Executive classification', '', status, '',
        f'Generalization: {generalization}. The primary balanced candidate is preserved for every design; alternatives remain separate. '
        'Admission and resource holds are reported without treating unexecuted designs as PACT losses.', '',
        '## B. Admission', '',
        'C≥6 GiB and D≥25 GiB remained fixed. Per-design D admission adds the registered 20 GiB scratch reserve '
        'plus max(5 GiB, retained packages, projected complete traces and one complete count cache). '
        'The inactive 16 GiB build image was relocated to F with copy/rehash verification and a D symlink; required evidence was preserved. '
        'A later projected-capacity hold was resolved by relocating 37 inactive build-source fixtures (1,083,340,023 bytes) to F, '
        'rehashing each copy, removing only its verified duplicate and retaining a byte-identical D-path symlink. '
        'All deletion/relocation receipts remain in the campaign. Qualified uncompressed count caches were removed only after gzip evidence and crosschecks passed. '
        'The prospective source-registration adapter binds a failed predecessor only when one exists; its first failed launch performed no scientific work. '
        'Both b15 continuations reused the admitted source; the capacity continuation also reused identical qualified patterns and placement without repeating ATPG or placement. '
        'The later cold-input directory collision stopped before any search: source preparation and prospective input had shared a directory. '
        'A qualified adapter allocates a fresh PACT_primary child and retains the original complete input validation. '
        'All six b15 baseline results and original preparation bytes were preserved; no baseline or PACT search was repeated. '
        'The failed launch, focused controls and complete production audit remain recorded separately.', '',
        '| Design | Base/composition family | Source FFs | Admission/comparison outcome |', '|---|---|---:|---|']
    for entry in protocol['cohort']:
        state = next(r for r in ledger['records'] if r['design']==entry['design'])
        text.append(f"| {entry['design']} | {entry['family']} ({entry['independence_role']}) | {entry['source_FF_count']} | {state['status']} |")
    text += ['', 'Sources: cad-polito-it/I99T commit 8a2c3b500ee7ff20e7031de92592b737bedc6d8c, EUPL-1.2. '
        'BENCH/BLIF and mapped all-state next-state equivalence precede ATPG/placement/reference admission. '
        'A first source/reference/resource hold stops the fixed cohort order; deferred rows make no source-compatibility claim.', '',
        '## C. Frozen methodology', '',
        'K=2; primary seed 11; ε=0.02/0.05/0.10; 900 seconds per mutation loop; 7200-second search worker ceiling. '
        '20,000 maximum evaluations, stagnation 2000, lane attempts 150, neighbors 16, segment 8, archive 16, equal normalized E/H4/H8 weights. '
        'Existing operators, archive, depth-3 stateful model, CPU evaluator and independent replay remain frozen. '
        'The budget adapter changes only the legacy seconds expression and its receipt text to the already preregistered 900 seconds. '
        'The sole initial state is the minimum-qualified-routed-WL B0/B1/B2/B3T reference, selected before search. '
        'Balanced/best E/best H4/best H8 roles, exact hash deduplication, at most three new candidates before routing. '
        'An in-flight exact mutation can finish past a loop deadline. No extra seed, weight sweep, GPU, hidden route or post-result tuning was used.', '',
        '## D. Competitors', '']
    for name, method in definitions['methods'].items():
        text.append('- **'+name+'**: '+method.get('algorithm',method.get('status',''))+
            (' Source SHA '+method['source_SHA']+'.' if 'source_SHA' in method else '')+
            (' Parameters '+json.dumps(method['parameters'],sort_keys=True)+'.' if 'parameters' in method else ''))
    text += ['', 'B1 uses native Cartesian Euclidean nearest ranking and an x+y lower-left start. B2 uses the established endpoint-inclusive Manhattan refinement. '
        'B3T is OPENROAD_QUALIFIED_PATCHED, with its source/STA repairs, binaries, build commands and tests preserved. '
        'B4 A and B5 J50 reuse the frozen phase0c code; B5 weights are 0.5/0.5 for every design. '
        'B6 discovery preserved repository/commit/license/adapter exclusions; no additional direct competitor was admitted, '
        'and no claim is made that no other open implementation exists.', '',
        '## E. Fairness', '',
        'Admitted comparisons share the mapped source, FF population and placement, clocks, K, fixed endpoint policy, '
        'seed 11, scan enable, patterns, compression/X-fill policy, fault model, two-thread routing, extraction and one-worker CPU measurement. '
        'Per-design machine audits verify source/placement/identity/workload hashes and candidate selection. '
        'Timing is from global route; DRC is from detailed route. The routed scan-path net-length upper bound includes functional branches. '
        'OpenROAD common binary SHA fcd7dcfc37d329bd43a7ede75805319a2e70e6879da11d42b4fd1c2e50e645c3 and ORFS SHA '
        '5e8b1450d19263f797a27c4f371b9dd19f32a3aa are fixed. Common backend component provenance records associated '
        'OpenSTA/OpenRCX source identities without claiming an independently reproduced binary linkage.', '',
        '## F. Search', '',
        'Per-design reports retain each lane, configuration, archive/discovery statistics, exact mutation counts, '
        'CPU/wall/RSS, termination reason, independent endpoint winner replay, architectures and selection receipt. '
        'Mutation evaluator metrics are separate from final routed netlist measurements. The primary is never promoted after final results.', '',
        '## G. Physical', '', 'All selected architectures, routing failures, topology proofs, timing and DRC outcomes remain in the per-design receipts. '
        'The launch-path repair reused four completed b14 reference routes and added zero reference reroutes.', '',
        '## H. ATPG', '',
        'All methods share the qualified generic FAN repair 4c253bfa613e5827f17c42a5fce8be7bea779e1e. '
        'Compound primitive levels/arity, shared-net drivers and internal-fault identities were minimally repaired with ASAN/truth/reporter controls. '
        'The earlier b14 446-pattern workload was invalidated and preserved; the qualified workload has 453 patterns, '
        '36,236 full weighted stuck-at targets and 35,688 detected (98.49%). '
        'Coverage is for the frozen mapped-source collapsed-fault universe; post-route inserted buffers do not create new target classes. '
        'Serial recovery and source FAN simulation preserve identities, weights and status. '
        'The initial upstream connector attempt returned GitHub 403 “Resource not accessible by integration”; its drafts and evidence remain saved. '
        'A browser submission subsequently published the construction defects as '
        '[FAN_ATPG issue #5](https://github.com/NTU-LaDS-II/FAN_ATPG/issues/5). '
        'The submitted body and visible proof are bound by publication/FAN_upstream_issue.json.', '',
        '## I. Exact activity', '',
        'E is capacitance-weighted settled data-net transitions, not joules. H4/H8 are the per-cycle maximum '
        'source-localized capacitance-weighted bins on 4×4/8×8 grids. OpenRCX ground plus Liberty sink pin capacitance is used; coupling is excluded from the primary proxy. '
        'Every qualified netlist replay must finish all patterns and pass every FF-Q/cycle crosscheck. '
        'The normal CPU exact ceiling is 7200 seconds; diagnostic 14400 seconds is separate and does not replace primary outcomes.', '',
        '## J. Complete comparative table', '',
        '| Design | Method | Scan WL µm | ΔWL % | E | ΔE % | H4 | ΔH4 % | H8 | ΔH8 % | WNS ns | Hold ns | DRC | FC % | Runtime s | Status |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for row in rows:
        values = [row[k] for k in ('routed_scan_wirelength_um','delta_routed_WL_percent','E','delta_E_percent','H4',
            'delta_H4_percent','H8','delta_H8_percent','WNS','hold_WNS','DRC','fault_coverage','runtime_seconds')]
        text.append('| '+row['design']+' | '+row['role']+' | '+' | '.join(number(v,6 if i==9 else 3) for i,v in enumerate(values))+' | '+row['qualification_status']+' |')
    text += ['', 'Deltas use each design’s frozen selected external reference. Runtime includes measured generation, route, exact, '
        'and shared design search for PACT rows. Search is charged once per design, not separately for each candidate. '
        'Shared source preparation and ATPG costs, stage CPU/RSS and machine details appear in the receipts. '
        'Display values are rounded; dominance uses full-precision JSON. No losing or held method is removed.', '',
        '## K. Pareto', '',
        'Four costs: routed scan WL, E, H4, H8. Relative 1e-10 equality, at least one strict reduction, '
        'with timing/DRC/topology/workload/exact replay as hard qualification gates. Primary relationships:', '',
        '```json',json.dumps(dict(PACT_DOMINATES=dominates,PACT_DOMINATED_BY=dominated_by,MUTUALLY_NONDOMINATED=mutual),indent=2),'```','',
        '## L. Generalization', '', generalization+'. ',
        'Established: admitted-design measurements and qualification. Observed: the exact Pareto relationships at one seed and technology. '
        'Hypothesis: reasons for proxy/final differences need later experiments. Not established: universal superiority, '
        'power reduction, industry-tool superiority, guaranteed routed cost or arbitrary scaling. '
        'Related b17/b18 compositions are scaling checks and do not make four independent families.', '',
        '## M. Limitations', '',
        'Finite fixed CPU budgets, one primary seed, Nangate45, zero-delay settled activity, no glitch/power/current model, '
        'ground-plus-pin proxy excluding coupling, depth-3 search approximation, HPWL constraint without a routed-WL guarantee, '
        'bounded B6 search, and every source/reference/resource admission hold listed below.', '']
    text += ['- '+r['design']+': '+r['status']+'. '+r['reason'] for r in holds]
    text += ['', '## N. Next scientific step', '', next_action, '', 'Per-design evidence:', '']
    for record in ledger['records']:
        if record['status']=='COMPETITIVE_COMPARISON_TERMINAL':
            text.append('- ['+record['design']+']('+str(Path(record['report']['path']).parent / 'report.md')+')')
    text += ['', '```json',json.dumps(summary,indent=2),'```','']
    (output / 'report.md').write_text('\n'.join(text))
    print('GATE09_CAMPAIGN_REPORT',status,generalization,flush=True)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--ledger',type=Path,help='Explicit preserved continuation ledger; never replace the original')
    args=parser.parse_args()
    create(args.output,args.ledger)
