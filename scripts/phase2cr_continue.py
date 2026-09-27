"""Authorized audit-only continuation; preserve attempt 1 and frozen evidence."""
from phase2cr_common import *
import argparse
import platform
import shutil
import numpy as np
from phase2cr_run import load_case, legacy_points
from pact.analysis.phase2b_loads import hpwl, pin_loads


def sanity():
    import importlib.util
    from pact.analysis.phase2cr_loads import construct_with_audit
    from pact.scan.model import ScanArchitecture, ScanChain
    assert read(REPORT/'representative_witness.json')['status'] == 'PASS'
    spec = importlib.util.spec_from_file_location('focused', ROOT/'tests/unit/test_phase2cr_loads.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    a, g, loads = mod.case.__wrapped__()
    a = ScanArchitecture(a.cells, (ScanChain('0', ('b','a')), a.chains[1]))
    before = json.dumps(g, sort_keys=True)
    _, audit = construct_with_audit(a,g,loads)
    selected = audit['selected_graph']
    ep = g['scan_endpoints']['chain0_so']
    sink = dict(master=ep['buffer_master'],pin=ep['input_pin'],xy=ep['buffer_xy'])
    counts = dict(buffer_input=sum(net['sinks'].count(sink) for net in selected['nets'].values()),
        output_branch=sum(children.count(ep['output_net']) for children in selected['transparent'].values()),
        test_so=sum(r['ports'].count(ep['port_xy']) for rr in audit['FFs'].values() for r in rr))
    assert counts == dict(buffer_input=1,output_branch=1,test_so=1)
    assert json.dumps(g,sort_keys=True)==before
    assert selected is not g and selected['nets'] is not g['nets']
    assert selected['transparent']==g['transparent']
    assert not any(s['pin']=='test_so' for rr in audit['FFs'].values() for r in rr for s in r['additions'])
    check(ROOT/'src/pact/analysis/phase2cr_loads.py',read(REPORT/'float_reduction_audit.json')['predictor_source_sha256'])
    write(REPORT/'implementation_sanity.json',dict(status='PASS',source_unchanged=True,
        reviewed_function='phase2cr_loads.selected_graph',
        review=dict(deep_copy=True,remove_old_sink_if_tail_differs=True,remove_old_child_if_tail_differs=True,
            attach_sink_to_tail_Q=True,attach_child_to_tail_Q=True,actual_SO_port_on_buffer_output=True,
            no_chain0_synthetic_SO=True,chain_above_zero_direct_SO_preserved=True),
        same_owner_special_case=dict(fixture='existing focused case, selected_tail == original_owner == a',
            counts=counts,input_graph_unchanged=True,transparent_edges_unchanged=True),
        focused_tests=read(REPORT/'tests.json')['continuation']['focused']))
    print('IMPLEMENTATION_SANITY_PASS',counts,flush=True)


def weights():
    from phase2cr_run import old_graph
    freeze=integrity()
    top=read(REPORT/'topology_equivalence.json')
    assert top['passed']==21 and top['status']=='PACT_PHASE2CR_TOPOLOGY_PASS'
    loads=pin_loads(LIB.read_text())
    rows=[]; manifest=[]
    for row, proof in zip(freeze['architectures'],top['rows']):
        a,g,names,old,new,audit=load_case(row,loads)
        ep=g['scan_endpoints']['chain0_so']; owner=ep['original_owner_ff']; tail=a.chains[0].cells[-1]
        changed={m:[n for i,n in enumerate(names) if new[m][i]!=old[m][i]] for m in ('M3_load','M5_hpwl')}
        unexpected=sorted(set(n for nn in changed.values() for n in nn)-{owner,tail})
        record=dict(design=row['design'],label=row['label'],old_owner=owner,new_owner=tail,
            changed_FFs_by_metric=changed,unexpected_changed_FFs=unexpected,
            explanation='Only old-owner and selected-tail cones can change: transfer buffer sink/transparent branch; actual SO on buffer output replaces synthetic tail endpoint.',
            affected_FFs={n:dict(legacy_points=legacy_points(a,g,n),corrected_points=audit['FFs'][n],
                weights={m:dict(legacy=float(old[m][names.index(n)]),corrected=float(new[m][names.index(n)])) for m in new}) for n in sorted({owner,tail})})
        rows.append(record)
        if unexpected:
            write(REPORT/'weight_change_audit.json',dict(status='UNEXPECTED_WEIGHT_CHANGE',rows=rows))
            raise ValueError('UNEXPECTED_WEIGHT_CHANGE')
        selected=audit['selected_graph']; source=ep['original_source_net']; target=g['FFs'][tail]['roots']['Q']; child=ep['output_net']
        sink=dict(master=ep['buffer_master'],pin=ep['input_pin'],xy=ep['buffer_xy'])
        proof['explicit_witnesses']=dict(original_source_net=source,selected_tail_Q_net=target,buffer_output_net=child,
            buffer_sink=sink,old_source_before=g['nets'][source],old_source_after=selected['nets'][source],
            selected_tail_before=g['nets'][target],selected_tail_after=selected['nets'][target],
            old_transparent_edges=g['transparent'].get(source,[]),new_old_source_transparent_edges=selected['transparent'].get(source,[]),
            tail_transparent_edges=selected['transparent'].get(target,[]),
            output_branch_owners=[n for n,rr in audit['FFs'].items() if any(r['net']==child for r in rr)],
            branch_ownership_count=sum(v.count(child) for v in selected['transparent'].values()),
            buffer_input_count_on_target=selected['nets'][target]['sinks'].count(sink),
            SO_geometry_count=sum(r['ports'].count(ep['port_xy']) for rr in audit['FFs'].values() for r in rr if r['net']==child),
            chain1_tail=a.chains[1].cells[-1],chain1_point_records=audit['FFs'][a.chains[1].cells[-1]],
            K=len(a.chains),chains=row['chains'],FF_inventory=names,
            affected_point_sets=record['affected_FFs'])
        path=REPORT/'weights'/f'{a.sha256()}.json'
        write(path,{m:dict(zip(names,map(float,w))) for m,w in new.items()})
        manifest.append(dict(design=row['design'],label=row['label'],architecture_sha256=a.sha256(),
            scan_order_sha256=order_hash(a),path=str(path),sha256=sha(path),
            legacy_path=str(WORK/a.sha256()/'predictor_weights.json'),legacy_sha256=sha(WORK/a.sha256()/'predictor_weights.json'),
            placed_graph_sha256=sha(REPORT/f"{row['design']}.placed_graph.json"),liberty_sha256=sha(LIB),coefficient_ff_per_um=.103981))
    write(REPORT/'topology_equivalence.json',top)
    write(REPORT/'weight_change_audit.json',dict(status='PASS',rows=rows,unexplained_changes=0,scoring_performed=False))
    write(REPORT/'corrected_weights_manifest.json',dict(rows=manifest,created_before_scoring=True))
    write(REPORT/'pre_scoring_weights_manifest.json',dict(rows=manifest,created_before_scoring=True))
    print('WEIGHT_CHANGE_AUDIT_PASS 21/21; no unexplained changes',flush=True)


def statistics():
    from phase2b_report import compare_pairs
    from phase2a_validate import correlations
    from scipy.stats import rankdata
    from itertools import combinations
    integrity()
    assert read(REPORT/'weight_change_audit.json')['status']=='PASS'
    rows=read(REPORT/'corrected_metrics.json')['rows']
    legacy={(r['design'],r['label']):r for r in read(B/'candidate_metrics.json')['rows']}
    historical=read(B/'correlation.json')['per_design']
    stats={}; ranks={}; pairs={}; comparisons=[]; cells=[]
    targets=('cap_total','cap_local_peak','wire_total','wire_local_peak')
    for design in DESIGNS:
        group=[r for r in rows if r['design']==design]; labels=[r['label'] for r in group]
        stats[design]={}; ranks[design]={}; pairs[design]={}
        for row in group: assert row['targets']==legacy[design,row['label']]['targets']
        for metric in ('M3_load','M3_load_local','M5_hpwl','M5_hpwl_local'):
            x=np.array([r['predictors'][metric] for r in group])
            ox=np.array([legacy[design,r['label']]['predictors'][metric] for r in group])
            nr=rankdata(x); oldr=rankdata(ox)
            ranks[design][metric]=[dict(label=label,legacy_score=float(o),corrected_score=float(n),
                legacy_rank=float(ro),corrected_rank=float(rn),rank_displacement=float(rn-ro))
                for label,o,n,ro,rn in zip(labels,ox,x,oldr,nr)]
            stats[design][metric]={}; pairs[design][metric]={}
            for target in targets:
                y=np.array([r['targets'][target] for r in group])
                pair=compare_pairs(labels,x,y); opair=compare_pairs(labels,ox,y)
                stat=dict(**correlations(x,y),pairwise_non_tied_agreement=pair['non_tied_agreement'],pair_counts=pair['counts'])
                oldstat=dict(**correlations(ox,y),pairwise_non_tied_agreement=opair['non_tied_agreement'],pair_counts=opair['counts'])
                assert oldstat==historical[design][metric][target], 'Inherited legacy statistics failed exact reproduction'
                stats[design][metric][target]=stat
                pairs[design][metric][target]=dict(corrected=pair,legacy=opair)
            target=('cap_' if metric.startswith('M3') else 'wire_')+('local_peak' if metric.endswith('_local') else 'total')
            ns=stats[design][metric][target]; os=historical[design][metric][target]
            direction_changes=[]; flips=[]
            for i,j in combinations(range(len(group)),2):
                od=int(np.sign(ox[j]-ox[i])); nd=int(np.sign(x[j]-x[i]))
                if od!=nd:
                    change=dict(left=labels[i],right=labels[j],legacy_direction=od,corrected_direction=nd)
                    direction_changes.append(change)
                    if od*nd==-1: flips.append(change)
            comparisons.append(dict(design=design,metric=metric,target=target,
                legacy_rho=os['spearman'],corrected_rho=ns['spearman'],delta_rho=ns['spearman']-os['spearman'],
                legacy_pair_direction_accuracy=os['pairwise_non_tied_agreement'],corrected_pair_direction_accuracy=ns['pairwise_non_tied_agreement'],
                old_vs_corrected=correlations(ox,x),kendall_old_rank_corrected_rank=correlations(oldr,nr)['kendall_tau_b'],
                architectures_changing_rank=int(np.count_nonzero(oldr!=nr)),maximum_rank_displacement=float(np.abs(nr-oldr).max()),
                pair_directions_flipped=len(flips),pair_direction_changes_including_ties=len(direction_changes),changed_pairs=direction_changes,
                max_absolute_score_delta=float(np.abs(x-ox).max()),max_relative_score_delta=float(np.max(np.abs((x-ox)/ox)))))
        for family,prefix in [('M3_load','cap'),('M5_hpwl','wire')]:
            endpoints=[]
            for metric,target in [(family,prefix+'_total'),(family+'_local',prefix+'_local_peak')]:
                ns=stats[design][metric][target]; os=historical[design][metric][target]
                def passes(s):
                    return s['spearman'] is not None and s['spearman']>=.7 and s['pairwise_non_tied_agreement'] is not None and s['pairwise_non_tied_agreement']>=.75
                endpoints.append(dict(metric=metric,target=target,legacy_pass=passes(os),corrected_pass=passes(ns),legacy=os,corrected=ns))
            cells.append(dict(design=design,family=family,legacy_pass=all(e['legacy_pass'] for e in endpoints),
                corrected_pass=all(e['corrected_pass'] for e in endpoints),endpoints=endpoints))
    classification='PACT_PHASE2CR_SEED11_'+('REQUALIFIED' if all(c['corrected_pass'] for c in cells) else 'PARTIAL' if any(c['corrected_pass'] for c in cells) else 'INVALIDATED')
    write(REPORT/'corrected_correlations.json',dict(per_design=stats,legacy_comparison=comparisons,
        methodology='Inherited correlations and compare_pairs functions: Spearman, Kendall tau-b, Pearson secondary; exact ties; no pooled rescue.'))
    write(REPORT/'corrected_rankings.json',dict(per_design=ranks,order='ascending; average ranks for ties'))
    write(REPORT/'corrected_pairwise_comparisons.json',dict(per_design=pairs))
    write(REPORT/'legacy_corrected_comparison.json',dict(rows=comparisons))
    write(REPORT/'qualification.json',dict(scientific_seed11_classification=classification,final_classification='PENDING_FULL_REGRESSION',
        cells=cells,gate=dict(minimum_rho=.7,minimum_non_tied_accuracy=.75,both_endpoints_required=True),
        changed_qualification_cells=[c for c in cells if c['legacy_pass']!=c['corrected_pass']],
        multiseed_decision='MULTISEED_REPAIR_RERUN_BLOCKED',generalization_evaluated=False))
    print(classification,'scientific calculation complete; regression pending',flush=True)
    for c in comparisons: print(c['design'],c['metric'],'rho',c['corrected_rho'],'pair_accuracy',c['corrected_pair_direction_accuracy'],'ranks_changed',c['architectures_changing_rank'],flush=True)


def finalize():
    freeze=integrity(); preserve()
    tests=read(REPORT/'tests.json'); q=read(REPORT/'qualification.json')
    assert tests['continuation']['focused']['status']=='PHASE2CR_FOCUSED_TESTS_PASS'
    assert tests['continuation']['regression_isolated']['status']=='COMPLETE_REGRESSION_PASS'
    assert read(REPORT/'topology_equivalence.json')['passed']==21
    assert read(REPORT/'implementation_sanity.json')['status']=='PASS'
    assert read(REPORT/'weight_change_audit.json')['unexplained_changes']==0
    witness=read(REPORT/'representative_witness.json'); assert witness['status']=='PASS'
    assert witness['architecture_sha256']=='bf4923662baa3ce72543bd3ad5092fb514808ffe46ce23173d3c9695ff0c9486'
    # Apply the frozen equivalence convention to independent reductions as
    # well as the stricter exact sequential-reproduction witness assertion.
    numerical_checks=[]
    for row in read(REPORT/'weight_change_audit.json')['rows']:
        for name, ff in row['affected_FFs'].items():
            for version in ('legacy','corrected'):
                points=ff[version+'_points']
                independent=sum(hpwl(r['points']) for r in points)
                stored=ff['weights']['M5_hpwl'][version]
                np.testing.assert_allclose(independent,stored,rtol=1e-12,atol=1e-10)
                numerical_checks.append(dict(design=row['design'],label=row['label'],FF=name,version=version,
                    independent_hpwl=independent,predictor_hpwl=stored,absolute_difference=abs(independent-stored)))
    write(REPORT/'numerical_equivalence.json',dict(status='PASS',rtol=1e-12,atol=1e-10,
        structural_checks='EXACT',sequential_reproduction='EXACT',rows=numerical_checks))
    audit=read(REPORT/'float_reduction_audit.json')
    check(ROOT/'src/pact/analysis/phase2cr_loads.py',audit['predictor_source_sha256'])
    check(ROOT/'tests/unit/test_phase2cr_loads.py',audit['tests_source_sha256'])
    check(REPORT/'witness.log',audit['original_failure_log_sha256'])
    audit['corrected_audit_witness_status']='PACT_PHASE2CR_REPRESENTATIVE_WITNESS_PASS'
    write(REPORT/'float_reduction_audit.json',audit)
    with (REPORT/'FLOAT_REDUCTION_AUDIT.md').open('a') as f:
        f.write('\nAuthorized continuation: corrected_audit_witness_status = PACT_PHASE2CR_REPRESENTATIVE_WITNESS_PASS. Initial witness remains FAIL / FLOAT_REDUCTION_ORDER.\n')
    witness.update(initial_witness_status='FAIL',failure_reason='FLOAT_REDUCTION_ORDER',
        corrected_audit_witness_status='PACT_PHASE2CR_REPRESENTATIVE_WITNESS_PASS',physical_seed=11)
    write(REPORT/'representative_witness.json',witness)
    with (REPORT/'REPRESENTATIVE_WITNESS.md').open('a') as f:
        f.write('\nStatus: PACT_PHASE2CR_REPRESENTATIVE_WITNESS_PASS. Attempt 1 remains FAIL / FLOAT_REDUCTION_ORDER; original witness.log and attempt1/ are preserved.\n')
    # Restore pre-scoring provenance richness, checking every written weight file.
    manifest=read(REPORT/'pre_scoring_weights_manifest.json')
    for r in manifest['rows']: check(r['path'],r['sha256']); check(r['legacy_path'],r['legacy_sha256'])
    write(REPORT/'corrected_weights_manifest.json',manifest)
    q['final_classification']=q['scientific_seed11_classification']
    q['execution_status']='PACT_PHASE2CR_TOPOLOGY_PASS'
    q['multiseed_decision']='MULTISEED_REPAIR_RERUN_JUSTIFIED' if any(c['corrected_pass'] for c in q['cells']) else 'MULTISEED_REPAIR_RERUN_NOT_JUSTIFIED'
    q['multiseed_reason']='All engineering gates pass; retained complete design/family qualification cells justify testing generalization.' if any(c['corrected_pass'] for c in q['cells']) else 'Engineering gates pass, but no complete design/family cell qualifies.'
    q['full_regression']='PASS'
    q['initial_attempt']=dict(status='PACT_PHASE2CR_TOPOLOGY_FAIL',scientific_result='NOT_EVALUATED',initial_witness_status='FAIL',failure_reason='FLOAT_REDUCTION_ORDER')
    write(REPORT/'qualification.json',q)
    comparisons=read(REPORT/'legacy_corrected_comparison.json')['rows']; deltas=read(REPORT/'metric_deltas.json')['rows']
    ftest=tests['continuation']['focused']; reg=tests['continuation']['regression_isolated']
    lines=['# PACT Phase-2C-R authorized continuation','',f'Final classification: **{q["final_classification"]}**.',
        f'Execution: **PACT_PHASE2CR_TOPOLOGY_PASS**. Decision: **{q["multiseed_decision"]}**.','',
        '## Attempt 1 — preserved','',
        'PACT_PHASE2CR_TOPOLOGY_FAIL: the representative audit compared compensated built-in sum with sequential predictor addition. '
        'The run stopped correctly; scientific results were not evaluated. Initial witness remains FAIL / FLOAT_REDUCTION_ORDER. '
        'Original reports, test results and pre-fix runner are in attempt1/; the original witness.log remains at its original path with the same SHA256.','',
        '## Authorized continuation — required answers','',
        '1. The exact failed assertion was built-in sum(audit HPWL terms) == predictor M5. See FLOAT_REDUCTION_AUDIT.md and its JSON.',
        f'2. Yes: {audit["absolute_difference"]!r} um is solely floating reduction algorithm/association; operand order is identical. Sequential recomputation matches exactly.',
        '3. No scientific or predictor definition changed. phase2cr_loads.py, M3, M5, CAP_PER_UM=0.103981, scan semantics, archived orders and activity remain hash-identical. Only the witness reduction was repaired; new scripts record continuation evidence.',
        f'4. Current focused tests: {ftest["passed"]} passed, {ftest["failed"]} failed, {ftest["skipped"]} skipped, {ftest["runtime_seconds"]:.3f} s command runtime. The test file was not edited during continuation.',
        '5. PACT_PHASE2CR_REPRESENTATIVE_WITNESS_PASS for s5378 / physical seed 11 / P; required architecture SHA verified.',
        '6. output38 moved exactly from U_n1588gat to U_n2121gat; unrelated functional sinks are preserved.',
        '7. Exactly one BUF_X1/A input of 0.974659 fF transferred; transparent output branch and test_so geometry each occur once.',
        '8. M5 was recomputed from actual point sets, with exact sequential reproduction. All affected net points and per-FF pin/M3/M5 values are emitted.',
        '9. All 21 topology cases pass: s5378 9, s9234 6, s15850 6. Each row has explicit ownership, count, chain, identity and point witnesses. Same-owner synthetic fixture also has exactly one input, branch and SO point.',
        '10. No unexplained FF-weight changes. Every changed M3/M5 FF lies in the old-owner/selected-tail cone; weight_change_audit.json records every affected FF and its points.',
        '11. M3 total/local changes for every architecture are in the score table and metric_deltas.json.',
        '12. M5 total/local changes for every architecture are in the score table and metric_deltas.json.',
        f'13. Across the 12 design/endpoint predictor vectors, {sum(c["architectures_changing_rank"] for c in comparisons)} architecture-rank entries changed; see the comparison table.',
        f'14. Pair directions flipped: {sum(c["pair_directions_flipped"] for c in comparisons)} across those 12 vectors; changes including transitions to/from ties: {sum(c["pair_direction_changes_including_ties"] for c in comparisons)}.',
        '15. Corrected M3 capacitance total/local correlations are in the endpoint table below.',
        '16. Corrected M5 wire total/local correlations are in the endpoint table below.',
        f'17. Original complete design/family qualification outcomes changed: {len(q["changed_qualification_cells"])}. Undefined values fail; rho >= 0.7 and direction accuracy >= 75% on both endpoints remain mandatory.',
        f'18. Complete regression: {reg["passed"]} passed, {reg["failed"]} failed, {reg["skipped"]} skipped, {reg["runtime_seconds"]:.3f} s command runtime. Fresh Linux temporary directory; no old tests modified. Initial continuation regression had 3 collection errors because threadpoolctl was absent from PYTHONPATH; its log/XML/result are preserved. The isolated rerun restored the historical phase2a_python dependency cache. The earlier Phase-2C filesystem failure also remains in reports/phase2c/tests.json.',
        f'19. {q["multiseed_decision"]}. {q["multiseed_reason"]}',
        f'20. Exact final classification: {q["final_classification"]}. Seed-11 only; this is not multi-seed generalization.','',
        '## Numerical, ranking and qualification effects are distinct','',
        'A. Numerical scores changed beyond representation roundoff: maximum absolute relative changes are '
        f'M3 total {max(c["max_relative_score_delta"] for c in comparisons if c["metric"]=="M3_load"):.6%}, '
        f'M3 local {max(c["max_relative_score_delta"] for c in comparisons if c["metric"]=="M3_load_local"):.6%}, '
        f'M5 total {max(c["max_relative_score_delta"] for c in comparisons if c["metric"]=="M5_hpwl"):.6%}, '
        f'and M5 local {max(c["max_relative_score_delta"] for c in comparisons if c["metric"]=="M5_hpwl_local"):.6%}. '
        'These semantic-repair score changes are distinct from the 1.42e-14 witness-arithmetic discrepancy. No quantitative materiality threshold was preregistered.','',
        f'B. Ranking changed: {sum(c["architectures_changing_rank"] for c in comparisons)} architecture-rank entries across the 12 design/endpoint vectors, '
        f'{sum(c["pair_directions_flipped"] for c in comparisons)} pair flips, and maximum rank displacement '
        f'{max(c["maximum_rank_displacement"] for c in comparisons):g}. These are predictor-vector entries, not a count of distinct architectures.','',
        f'C. Scientific qualification changed in {len(q["changed_qualification_cells"])} of six design/family cells. '
        'The original per-design, two-endpoint gates are applied independently; no aggregation rescues a failure.','',
        '| Design | Predictor | Legacy rho | Corrected rho | Delta rho | Legacy pair accuracy | Corrected pair accuracy | old/new Spearman | old/new rank tau-b | Changed ranks | Max displacement | Pair flips | Max abs score delta | Max abs relative delta |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for c in comparisons:
        lines.append(f'| {c["design"]} | {c["metric"]} | {c["legacy_rho"]:.6f} | {c["corrected_rho"]:.6f} | {c["delta_rho"]:.6f} | {c["legacy_pair_direction_accuracy"]:.6f} | {c["corrected_pair_direction_accuracy"]:.6f} | {c["old_vs_corrected"]["spearman"]:.6f} | {c["kendall_old_rank_corrected_rank"]:.6f} | {c["architectures_changing_rank"]} | {c["maximum_rank_displacement"]:g} | {c["pair_directions_flipped"]} | {c["max_absolute_score_delta"]:.9g} | {c["max_relative_score_delta"]:.9g} |')
    lines+=['','## Per-architecture scores','',
        'Each cell is legacy → corrected (signed delta; relative delta). Units: M3 fF-transitions; M5 um-transitions. Local scores retain frozen cycle/window peak definitions. Absolute deltas and changed FF identities are in metric_deltas.json.','',
        '| Design / architecture | M3 total | M3 local | M5 total | M5 local | Changed FF count | Moved pin fF | Old owner → new owner |',
        '|---|---:|---:|---:|---:|---:|---:|---|']
    for row in deltas:
        cells=[]
        for m in ('M3_load','M3_load_local','M5_hpwl','M5_hpwl_local'):
            v=row['scores'][m];cells.append(f'{v["old"]:.10g} → {v["corrected"]:.10g} ({v["delta"]:+.8g}; {v["relative_delta"]:+.6%})')
        lines.append(f'| {row["design"]} / {row["label"]} | '+' | '.join(cells)+f' | {row["changed_FF_count"]} | {row["transferred_branch_pin_ff"]:.6f} | {row["original_SO_owner"]} → {row["selected_chain0_tail"]} |')
    lines+=['','## Original qualification cells','', '| Design | Family | Legacy | Corrected |','|---|---|---|---|']
    for c in q['cells']:lines.append(f'| {c["design"]} | {c["family"]} | {"PASS" if c["legacy_pass"] else "FAIL"} | {"PASS" if c["corrected_pass"] else "FAIL"} |')
    lines+=['','## Provenance and boundary','',
        f'All {len(freeze["inputs"])} frozen input hashes and the preregistered contract were verified before/after continuation. '
        'Existing activity, targets, OpenRCX/SPEF, route evidence and historical weights were reused without modification. Targets are labels only, never predictor inputs. '
        'commands.json and tests.json include runtime/environment/logs. result_provenance.json hashes the final outputs, attempt-1 snapshot and continuation sources. '
        'No ATPG, routing, placement, new physical implementation, optimizer/search, ML, event-engine integration, extra seeds, Phase-2D or GitHub push was performed. '
        'Phase-2C remains STOPPED_LEGACY_DEFINITION_BUG.']
    (REPORT/'FINAL_REPORT.md').write_text('\n'.join(lines)+'\n')
    write(REPORT/'continuation_integrity.json',dict(status='PASS',frozen_input_count=len(freeze['inputs']),
        contract_sha256=freeze['contract_sha256'],predictor_source_unchanged=True,focused_tests_source_unchanged=True,
        original_witness_log_unchanged=True,attempt1_manifest_sha256=sha(REPORT/'attempt1/snapshot_manifest.json'),verified_utc=now()))
    print(q['final_classification'],q['multiseed_decision'],flush=True)


def verify():
    freeze=integrity()
    provenance=read(REPORT/'result_provenance.json')
    for path,digest in provenance['files'].items(): check(REPORT/path,digest)
    for path,digest in provenance['sources'].items(): check(path,digest)
    preserve()
    expected={(r['design'],r['label']) for r in freeze['architectures']}
    for name in ('topology_equivalence.json','weight_change_audit.json','corrected_weights_manifest.json',
                 'corrected_metrics.json','metric_deltas.json'):
        rows=read(REPORT/name)['rows']
        assert len(rows)==21 and {(r['design'],r['label']) for r in rows}==expected
    q=read(REPORT/'qualification.json')
    assert q['final_classification']==q['scientific_seed11_classification']
    assert read(REPORT/'tests.json')['continuation']['regression_isolated']['status']=='COMPLETE_REGRESSION_PASS'
    assert read(REPORT/'float_reduction_audit.json')['corrected_audit_witness_status']=='PACT_PHASE2CR_REPRESENTATIVE_WITNESS_PASS'
    assert read(REPORT/'numerical_equivalence.json')['status']=='PASS'
    required=['FLOAT_REDUCTION_AUDIT.md','float_reduction_audit.json','REPRESENTATIVE_WITNESS.md',
        'representative_witness.json','topology_equivalence.json','corrected_weights_manifest.json',
        'weight_change_audit.json','metric_deltas.json','corrected_correlations.json','corrected_rankings.json',
        'corrected_pairwise_comparisons.json','qualification.json','tests.json','commands.json','result_provenance.json','FINAL_REPORT.md']
    assert all((REPORT/name).is_file() for name in required)
    print('FINAL_ARTIFACT_VERIFICATION_PASS',len(provenance['files']),'output hashes;',len(freeze['inputs']),'frozen input hashes;',len(expected),'architectures',flush=True)


def preserve():
    dest = REPORT / 'attempt1'
    if dest.exists():
        for name, digest in read(dest / 'snapshot_manifest.json').items():
            check(dest / name, digest)
        return
    dest.mkdir()
    files = [p for p in REPORT.iterdir() if p.is_file()]
    for p in files:
        shutil.copy2(p, dest / p.name)
    shutil.copy2(ROOT / 'scripts/phase2cr_run.py', dest / 'phase2cr_run.py')
    write(dest / 'snapshot_manifest.json', {p.name: sha(p) for p in dest.iterdir()})


def audit_reduction():
    preserve()
    freeze = integrity()
    row = next(r for r in freeze['architectures'] if (r['design'], r['label']) == ('s5378', 'P'))
    a, g, names, old, new, audit = load_case(row, pin_loads(LIB.read_text()))
    n = 'U_n2121gat'
    records = audit['FFs'][n]
    sequence = [hpwl(r['points']) for r in records]
    assert sequence == [r['hpwl_um'] for r in records]
    running = 0.0
    partial = []
    for value in sequence:
        running += value
        partial.append(running)
    lhs, rhs = sum(sequence), float(new['M5_hpwl'][names.index(n)])
    assert running == rhs and lhs != rhs
    np.testing.assert_allclose(lhs, rhs, rtol=1e-12, atol=1e-10)
    diag = read(REPORT / 'attempt1/witness_failure_diagnostic.json')
    record = dict(initial_witness_status='FAIL', failure_reason='FLOAT_REDUCTION_ORDER',
        corrected_audit_witness_status='PENDING', solely_float_reduction=True,
        assertion="sum(r['hpwl_um'] for r in audit['FFs'][n]) == new['M5_hpwl'][i]",
        source='scripts/phase2cr_run.py:148 (attempt1 snapshot)',
        lhs=lhs, rhs=rhs, absolute_difference=abs(lhs-rhs), relative_difference=abs(lhs-rhs)/abs(rhs),
        operand_sequence_predictor=sequence, operand_sequence_audit=sequence,
        net_sequence=[r['net'] for r in records], point_sets=records,
        accumulation_method_predictor='0.0 followed by ordered sequential wire += hpwl(points)',
        accumulation_method_audit='CPython 3.12 built-in sum(generator): compensated float summation',
        distinction='Traversal/operand order is identical; reduction algorithm/association differs.',
        sequential_partial_sums=partial, sequential_audit_value=running,
        data_types=dict(operands=[type(v).__name__ for v in sequence], accumulator='Python float (binary64)',
                        predictor_array=str(new['M5_hpwl'].dtype), predictor_scalar=type(new['M5_hpwl'][names.index(n)]).__name__),
        operand_hex=[v.hex() for v in sequence], lhs_hex=lhs.hex(), rhs_hex=rhs.hex(),
        environment=dict(python=sys.version, executable=sys.executable, platform=platform.platform()),
        original_failure_log_sha256=sha(REPORT/'witness.log'), historical_diagnostic=diag,
        predictor_source_sha256=sha(ROOT/'src/pact/analysis/phase2cr_loads.py'),
        tests_source_sha256=sha(ROOT/'tests/unit/test_phase2cr_loads.py'))
    write(REPORT / 'float_reduction_audit.json', record)
    (REPORT/'FLOAT_REDUCTION_AUDIT.md').write_text(
        '# Floating reduction audit\n\nAttempt 1 remains PACT_PHASE2CR_TOPOLOGY_FAIL; scientific results were not evaluated. '
        'It stopped correctly under the preregistered rule. Original files and source are preserved under attempt1/; witness.log is unchanged.\n\n'
        f'The exact assertion at attempt1/phase2cr_run.py:148 compared lhs `{lhs!r}` (built-in sum) with rhs `{rhs!r}` (predictor). '
        f'Absolute difference: {abs(lhs-rhs)!r} um; relative difference: {abs(lhs-rhs)/abs(rhs)!r}.\n\n'
        f'Both paths use the same net order: {[r["net"] for r in records]!r}, and the same operands: {sequence!r}. '
        'Every operand was independently recomputed from its emitted point set. Operands and sequential accumulator are Python binary64 floats; '
        'the stored predictor is NumPy float64. CPython 3.12 built-in sum uses compensated float summation; the predictor uses ordered sequential += from 0.0. '
        f'The sequential partial sums are {partial!r}, reproducing the predictor exactly.\n\n'
        'Thus only the floating reduction algorithm/association differs, not traversal order, topology, point sets, or predictor definition. '
        'The authorized fix is ordered sequential witness addition. Independent numeric reductions use only rtol=1e-12, atol=1e-10; structural checks stay exact. '
        'No scientific/predictor source is changed. See float_reduction_audit.json for operands, types, hex values, source hashes and full points.\n')
    print('FLOAT_REDUCTION_ORDER_CONFIRMED', lhs, rhs, abs(lhs-rhs), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['audit','sanity','weights','statistics','finalize','verify'])
    args = parser.parse_args()
    {'audit':audit_reduction,'sanity':sanity,'weights':weights,'statistics':statistics,'finalize':finalize,'verify':verify}[args.stage]()
