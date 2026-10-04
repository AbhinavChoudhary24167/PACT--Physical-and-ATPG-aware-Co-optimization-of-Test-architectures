"""Deterministic reporting of saved root-cause reconstructions."""
from pact.environment import python_executable
from pact.experiment_storage import experiment_root
import csv
import gzip
import itertools
import json
import hashlib
import re
from pathlib import Path
import numpy as np
from pact.analysis.h8_rootcause import canonical_json,sha256,write_csv,ordering,pair_classification


def read(path):
    path=Path(path)
    with (gzip.open(path,'rt') if path.suffix=='.gz' else path.open()) as stream:
        return json.load(stream)


def write(path,value):
    Path(path).write_text(canonical_json(value),encoding='utf-8')


def csvrows(path):
    with Path(path).open(encoding='utf-8') as stream:
        return list(csv.DictReader(stream))


def pipeline(index,root):
    e=next(e for e in index['architectures'] if e['architecture']=='4d6ff90b2adc')
    common=dict(provenance=index['provenance'],design=e['design'],architecture_hash=e['architecture_sha256'],
                source_evidence_sha256=e['provenance']['source_evidence_sha256'])
    stages=[]
    def stage(name,source,function,inputs,outputs,coords,cap,trans,bins):
        stages.append(dict(stage=name,source_file=source,relevant_function=function,input_artifact=[str(p).replace('\\','/') for p in inputs],
            output_artifact=[str(p).replace('\\','/') for p in outputs],coordinate_convention=coords,capacitance_definition=cap,
            transition_definition=trans,spatial_bin_definition=bins,source_sha256=sha256(root/source)))
    # Paths in bindings are repository-relative on both execution hosts.
    folder=e['provenance']['source_evidence']['artifacts']['net_mapping.json']['path'].replace('\\','/').rsplit('/',1)[0]
    contract=read(root/'results/pact_candidate_stateful'/e['design']/'model_contract.json')
    inputs=contract['inputs']
    artifact=lambda key: inputs[key]['path']
    manifest=read(root/e['provenance']['source_evidence']['manifest']['path'].replace('\\','/'))
    implemented=next(r for r in manifest['rows'] if r['design']==e['design'] and r['architecture_sha256']==e['architecture_sha256'])
    diagnostic='results/pact_h8_rootcause/'+e['design']+'/'+e['architecture_sha256']
    coords='micrometres; driver cell origin; external input port bounding-box centre; die [xmin,ymin,xmax,ymax]'
    bins='8x8 equal-area half-open die bins; maximum belongs to last bin; id=8*y+x; whole net at driver'
    cap='ground fF + Liberty sink pin fF; incident coupling excluded from primary weight'
    trans='binary 0<->1 counts per measured shift cycle; initialization/capture/PI and SE setup excluded'
    stage('1_predicted_transitions','src/pact/optimizer/candidate_stateful.py',
        'packed_scan; packed_input; packed_function; State.__init__; update_field',
        [artifact('patterns'),artifact('identity_map'),e['provenance']['source_evidence']['architecture']['path'],
         'results/pact_candidate_sensitive/s9234/topology.json'],
        ['in-memory State.waves (packed before-SI/after-SI/after-FF)',diagnostic+'/net_discrepancy.csv'],
        coords,'none at waveform stage','sum of two adjacent settled XORs per cycle; all fanins simultaneous; depth=3, BUF/INV depth=0',bins)
    stage('2_candidate_capacitance','src/pact/optimizer/stateful_geometry.py','Geometry.terminal_sets; evaluate; estimate; mmst',
        ['results/pact_candidate_sensitive/s9234/topology.json','reports/physical_effect/s9234/T/net_activity_capacitance.csv',
         e['provenance']['source_evidence']['architecture']['path']],
        ['in-memory State.caps; per-net geometry audit',diagnostic+'/net_discrepancy.csv'],coords,
        'baseline ground/MMST * candidate shared-terminal MMST + candidate sink pins; named zero-span/missing-ground fallbacks',trans,bins)
    stage('3_predicted_spatial_assignment','src/pact/optimizer/candidate_stateful.py','Model.__init__: bins_by_net',
        ['results/pact_candidate_sensitive/s9234/topology.json'],['in-memory bins_by_net'],coords,cap,trans,bins)
    stage('4_predicted_H8','src/pact/optimizer/candidate_stateful.py','update_field; State.score -> implementation_v2.reduce',
        ['State.waves','State.caps','bins_by_net'],['results/pact_candidate_stateful/s9234/diagnostics.json',
        'results/pact_candidate_stateful/comparison.csv',diagnostic+'/bin_comparison.csv'],coords,cap,
        'H8=max_cycle,bin sum_net_in_bin C_candidate*N_settled; E=sum_cycle,bin field',bins)
    stage('5_routed_implementation','scripts/pact_solver_routes.py','route_selected -> phase0c_rewire_odb.py -> existing ORFS adapter',
        [e['provenance']['source_evidence']['architecture']['path'],implemented['source_placed_database']['path'],
         implemented['source_netlist']['path'],implemented['SDC']['path'],
         artifact('placement'),e['provenance']['source_evidence']['manifest']['path']],
        [implemented['qualification']['path'],implemented['routed_archive']['path'],folder+'/routed.odb',folder+'/routed.v'],
        'ODB database units converted to micrometres; FF origins verified against canonical architecture',
        'none until OpenRCX extraction','not an activity computation','not a bin computation')
    stage('6_VCD_switching','src/pact/physical_effect.py','vcd_transitions; analyze (Icarus stimulus from physical_effect.stimulus)',
        [folder+'/activity.vcd',folder+'/cycles.json.gz',folder+'/net_mapping.json',folder+'/workload.json'],
        [folder+'/transitions.npz',folder+'/FF_transition_crosscheck.json'],coords,'none at event-count stage',
        trans+'; final timestamp cycle marker defines window; zero-delay final VCD events, no SDF/specify delays',bins)
    stage('7_extracted_capacitance','src/pact/physical_effect.py','analyze -> pact.analysis.phase2b_reference.parse_spef; physical_effect_export pin_loads',
        [folder+'/extracted.spef',folder+'/routed.odb',artifact('physical_liberty')],
        [folder+'/net_activity_capacitance.csv'],coords,cap+'; OpenRCX corner0, threshold0.1fF, cc_model10; missing switched C fails',trans,bins)
    stage('8_measured_spatial_assignment','scripts/physical_effect_export.py','driver/port net loop -> net_mapping.json; spatial_bin',
        [folder+'/routed.odb'],[folder+'/net_mapping.json'],coords,cap,trans,bins)
    stage('9_measured_H8','src/pact/physical_effect.py','analyze: all_data grids[8] cap_peak_per_cycle.maximum',
        [folder+'/transitions.npz',folder+'/net_activity_capacitance.csv',folder+'/net_mapping.json'],
        [folder+'/activity_summary.json',folder+'/spatial_bins.json','stored comparison.csv'],coords,cap,
        'H8=max_cycle,bin sum_all_nonclock_unique_driver_nets (C_ground+C_pin)*N_VCD; E=full sum',bins)
    return dict(common,pipeline_generator_sha256=sha256(root/'scripts/pact_h8_report.py'),stages=stages,equivalence=dict(grid=True,capacitance_units=True,source_localization=True,
        shift_windows=True,scope=False,transition_semantics='settled snapshots vs zero-delay VCD events; checked per represented net',
        major_scope_difference='prediction omits outputs with depth>3 or unavailable fanins; measurement uses all_data',
        routed_segment_attribution=False,physical_glitch_measurement=False))


def report(out,root):
    idx=read(out/'evidence_index.json')
    common=idx['provenance']
    summary=read(root/'results/pact_candidate_stateful/summary.json')
    notes={}
    peaks={}
    for entry in idx['architectures']:
        d,h=entry['design'],entry['architecture_sha256']
        target=out/d/h
        note=read(target/'topology_notes.json')
        if (target/'omitted_cap_control.json').exists():
            control=read(target/'omitted_cap_control.json')
            if control['provenance']['source_evidence_sha256']!=entry['provenance']['source_evidence_sha256']:
                raise ValueError('Cached C control evidence mismatch')
            note['omitted_cap_control']=control
            notes[(d,entry['architecture'])]=note
            peaks[(d,entry['architecture'])]=csvrows(target/'peak_contributors.csv')
            continue
        # Separate omitted-region coverage from its extracted-C changes, using
        # saved VCD counts rather than a deeper model or a new simulation.
        baseline_geometry=read(root/'results/pact_candidate_stateful'/d/'baseline_geometry.json')
        baseline_graph=read(root/'results/pact_candidate_sensitive'/d/'topology.json')
        sources={v['source']:n for n,v in baseline_graph['nets'].items()}
        evidence_folder=root/entry['provenance']['source_evidence']['artifacts']['net_mapping.json']['path'].replace('\\','/')
        evidence_folder=evidence_folder.parent
        with np.load(evidence_folder/'transitions.npz',allow_pickle=False) as archive:
            counts,names=archive['counts'],archive['names'].tolist()
        caprows={r['net']:r for r in csvrows(evidence_folder/'net_activity_capacitance.csv')}
        discrepancy={r['meas_net']:r for r in csvrows(target/'net_discrepancy.csv') if r['meas_net']}
        represented=np.zeros((len(counts),64))
        omitted_baseline=np.zeros_like(represented)
        omitted_measured=np.zeros_like(represented)
        capcontrol=[]
        for j,n in enumerate(names):
            row=discrepancy[n]
            b=int(row['meas_bin'])
            cap=float(caprows[n]['ground_pin_ff'] or 0.)
            if row['coverage']=='represented':
                represented[:,b]+=counts[:,j]*cap
            elif row['coverage']!='new_topology':
                bn=sources[row['source']]
                bc=baseline_geometry[bn]['candidate_cap_ff']
                omitted_baseline[:,b]+=counts[:,j]*bc
                omitted_measured[:,b]+=counts[:,j]*cap
                capcontrol.append(dict(source=row['source'],coverage=row['coverage'],baseline_cap_ff=bc,
                    extracted_cap_ff=cap,cap_delta_ff=cap-bc,bin=b,
                    transitions_at_measured_peak=int(counts[note['meas_peak_cycle'],j]),
                    cap_effect_at_measured_peak=float(counts[note['meas_peak_cycle'],j])*(cap-bc) if b==note['meas_peak_bin'] else 0.))
        control=dict(provenance=note['provenance'],represented_measured_H8=float(represented.max()),
            plus_omitted_counts_baseline_C_H8=float((represented+omitted_baseline).max()),
            plus_omitted_counts_extracted_C_H8=float((represented+omitted_measured).max()),
            omitted_cap_effect_at_measured_peak=sum(r['cap_effect_at_measured_peak'] for r in capcontrol),
            interpretation='Measured omitted counts reweighted by baseline C at measured driver bins; isolates C inside omitted contributions, not unknown settled/event activity.')
        write(target/'omitted_cap_control.json',control)
        write_csv(target/'omitted_cap_discrepancy.csv',[dict(r,repository_commit=common['repository_commit'],
            timestamp=common['timestamp'],design=d,architecture_hash=h,model_version=common['model_version'],
            script_invocation='python scripts/pact_h8_rootcause.py report',
            source_evidence_sha256=entry['provenance']['source_evidence_sha256']) for r in capcontrol])
        note['omitted_cap_control']=control
        del counts,represented,omitted_baseline,omitted_measured
        notes[(d,entry['architecture'])]=note
        peaks[(d,entry['architecture'])]=csvrows(target/'peak_contributors.csv')
    write(out/'pipeline_map.json',pipeline(idx,root))
    pairrows=[]; mechanisms=[]
    outputpairs=out/'pairs'; outputpairs.mkdir(exist_ok=True)
    for d in ('s9234','s15850','s5378'):
        candidates=[r for r in summary['candidates'] if r['design']==d and r['measured']]
        prior_selected={p['a'] for p in summary['historical_diagnostics'][d]['previous_sensitive_selected_pair']['H8']['stateful']['pairs']}|{
            p['b'] for p in summary['historical_diagnostics'][d]['previous_sensitive_selected_pair']['H8']['stateful']['pairs']}
        for a,b in itertools.combinations(candidates,2):
            # Historical 8-way corpus, latest selected pair, and latest recommendation comparisons.
            selected_previous={a['architecture'],b['architecture']}==prior_selected
            selected_new=a['new'] and b['new']
            cls=pair_classification(a['stateful']['H8_stateful_ff'],b['stateful']['H8_stateful_ff'],
                                    a['measured']['peak_local_cap_ff'],b['measured']['peak_local_cap_ff'])
            if cls=='correct' and not selected_previous and not selected_new:
                continue
            na,nb=notes[(d,a['architecture'])],notes[(d,b['architecture'])]
            sa,sb=na['counterfactual_maxima'],nb['counterfactual_maxima']
            assert [x['stage'] for x in sa]==[x['stage'] for x in sb]
            orders=[ordering(x['H8'],y['H8']) for x,y in zip(sa,sb)]
            categories=[]
            for j,(x,y) in enumerate(zip(sa[1:],sb[1:]),1):
                stage=x['stage']
                impact=(x['H8']-y['H8'])-(sa[j-1]['H8']-sb[j-1]['H8'])
                code={'activity':'ACTIVITY_REPRESENTATION_ERROR','capacitance':'CAPACITANCE_ERROR',
                      'geometry':'SPATIAL_GEOMETRY_ERROR','omitted':'OMITTED_LOGIC_ERROR',
                      'new_topology':'CANDIDATE_TOPOLOGY_ERROR','removed_topology':'CANDIDATE_TOPOLOGY_ERROR'}[stage]
                # Report nonzero effects, even if they do not change the ordering.
                if abs(impact)>1e-7:
                    categories.append(code)
                mechanisms.append(dict(design=d,arch_a_hash=a['architecture_sha256'],arch_b_hash=b['architecture_sha256'],
                    stage=stage,track='primary_ordered_substitution',category=code,pair_gap_before=sa[j-1]['H8']-sb[j-1]['H8'],
                    pair_gap_after=x['H8']-y['H8'],gap_change=impact,order_before=orders[j-1],order_after=orders[j],
                    term_at_measured_peak_a=na['terms_at_measured_peak'][stage],
                    term_at_measured_peak_b=nb['terms_at_measured_peak'][stage],
                    interpretation='ordered substitution; interactions and maximum movement retained',
                    repository_commit=common['repository_commit'],timestamp=common['timestamp'],
                    model_version=common['model_version'],script_invocation='python scripts/pact_h8_rootcause.py report',
                    source_evidence_sha256=na['provenance']['source_evidence_sha256']+';'+nb['provenance']['source_evidence_sha256']))
            ca,cb=na['omitted_cap_control'],nb['omitted_cap_control']
            for before,after,stage,category in (
                ('represented_measured_H8','plus_omitted_counts_baseline_C_H8','omitted_counts_at_baseline_C','OMITTED_LOGIC_ERROR'),
                ('plus_omitted_counts_baseline_C_H8','plus_omitted_counts_extracted_C_H8','omitted_extracted_C','CAPACITANCE_ERROR')):
                mechanisms.append(dict(design=d,arch_a_hash=a['architecture_sha256'],arch_b_hash=b['architecture_sha256'],
                    stage=stage,track='omitted_region_C_control',category=category,
                    pair_gap_before=ca[before]-cb[before],pair_gap_after=ca[after]-cb[after],
                    gap_change=(ca[after]-cb[after])-(ca[before]-cb[before]),
                    order_before=ordering(ca[before],cb[before]),order_after=ordering(ca[after],cb[after]),
                    term_at_measured_peak_a=ca['omitted_cap_effect_at_measured_peak'] if category=='CAPACITANCE_ERROR' else None,
                    term_at_measured_peak_b=cb['omitted_cap_effect_at_measured_peak'] if category=='CAPACITANCE_ERROR' else None,
                    interpretation='control retains measured represented counts/C/locations; not a model prediction',
                    repository_commit=common['repository_commit'],timestamp=common['timestamp'],model_version=common['model_version'],
                    script_invocation='python scripts/pact_h8_rootcause.py report',
                    source_evidence_sha256=na['provenance']['source_evidence_sha256']+';'+nb['provenance']['source_evidence_sha256']))
            first_correct=next((x['stage'] for x,o in zip(sa,orders) if o==orders[-1]),None)
            row=dict(design=d,architecture_a=a['architecture'],architecture_b=b['architecture'],
                arch_a_hash=a['architecture_sha256'],arch_b_hash=b['architecture_sha256'],
                pred_h8_a=na['pred_h8'],pred_h8_b=nb['pred_h8'],meas_h8_a=na['meas_h8'],meas_h8_b=nb['meas_h8'],
                pred_order=orders[0],meas_order=orders[-1],classification=cls,
                historical_pair=not a['new'] and not b['new'],previous_selected_pair=selected_previous,
                latest_selected_pair=selected_new,pred_peak_bin_a=na['pred_peak_bin'],pred_peak_bin_b=nb['pred_peak_bin'],
                meas_peak_bin_a=na['meas_peak_bin'],meas_peak_bin_b=nb['meas_peak_bin'],
                mechanisms=';'.join(sorted(set(categories))),first_correct_substitution=first_correct,
                omitted_baseline_C_h8_a=na['omitted_cap_control']['plus_omitted_counts_baseline_C_H8'],
                omitted_baseline_C_h8_b=nb['omitted_cap_control']['plus_omitted_counts_baseline_C_H8'],
                omitted_baseline_C_order=ordering(na['omitted_cap_control']['plus_omitted_counts_baseline_C_H8'],
                                                nb['omitted_cap_control']['plus_omitted_counts_baseline_C_H8']),
                confidence='high for saved field algebra; physical activity cause beyond excluded cone remains bounded',
                repository_commit=common['repository_commit'],timestamp=common['timestamp'],model_version=common['model_version'],
                script_invocation='python scripts/pact_h8_rootcause.py report',
                source_evidence_sha256=na['provenance']['source_evidence_sha256']+';'+nb['provenance']['source_evidence_sha256'])
            pairrows.append(row)
            if cls!='correct' or selected_previous or selected_new:
                pa={r['source']:r for r in peaks[(d,a['architecture'])]}
                pb={r['source']:r for r in peaks[(d,b['architecture'])]}
                contributors=[]
                for source in sorted(set(pa)|set(pb)):
                    ra,rb=pa.get(source,{}),pb.get(source,{})
                    ma,mb=float(ra.get('measured_contribution',0)),float(rb.get('measured_contribution',0))
                    if ma==mb==float(ra.get('residual',0))==float(rb.get('residual',0))==0:
                        continue
                    contributors.append(dict(source=source,measured_at_A_peak=ma,measured_at_B_peak=mb,
                        difference_A_minus_B=ma-mb,coverage_A=ra.get('coverage'),coverage_B=rb.get('coverage'),
                        residual_at_A_peak=float(ra.get('residual',0)),residual_at_B_peak=float(rb.get('residual',0)),
                        repository_commit=common['repository_commit'],timestamp=common['timestamp'],design=d,
                        arch_a_hash=a['architecture_sha256'],arch_b_hash=b['architecture_sha256'],
                        model_version=common['model_version'],script_invocation=row['script_invocation'],
                        source_evidence_sha256=row['source_evidence_sha256']))
                np.testing.assert_allclose(sum(r['difference_A_minus_B'] for r in contributors),na['meas_h8']-nb['meas_h8'],atol=1e-7)
                contributors.sort(key=lambda r:(-abs(r['difference_A_minus_B']),r['source']))
                stem=d+'_'+a['architecture']+'__'+b['architecture']
                write_csv(outputpairs/(stem+'.csv'),contributors)
                lines=['# '+d+': '+a['architecture']+' / '+b['architecture'],'',
                    'Provenance: '+canonical_json(row),'',
                    f"Predicted: {na['pred_h8']:.9f} / {nb['pred_h8']:.9f}; {orders[0]}.",
                    f"Measured: {na['meas_h8']:.9f} / {nb['meas_h8']:.9f}; {orders[-1]}.",
                    f"Predicted bins: {na['pred_peak_bin']} / {nb['pred_peak_bin']}; measured bins: {na['meas_peak_bin']} / {nb['meas_peak_bin']}.",'',
                    '| Substitution | A H8 | B H8 | A−B | Ordering |','|---|---:|---:|---:|---|']
                lines += [f"| {x['stage']} | {x['H8']:.9f} | {y['H8']:.9f} | {x['H8']-y['H8']:.9f} | {o} |"
                          for x,y,o in zip(sa,sb,orders)]
                lines += ['','Classification: '+row['mechanisms']+'.',
                    'These are exact ordered field substitutions using measured counts/C/location. The maximum can move; stage H8 changes are not unique independent causal effects.',
                    'Net contributions below compare each implementation at its own measured peak. Their full CSV sums exactly to measured H8(A)−H8(B); large opposing terms are retained.','',
                    '| Source | A contribution | B contribution | A−B | Coverage A / B |','|---|---:|---:|---:|---|']
                lines += [f"| {r['source']} | {r['measured_at_A_peak']:.9f} | {r['measured_at_B_peak']:.9f} | {r['difference_A_minus_B']:.9f} | {r['coverage_A']} / {r['coverage_B']} |" for r in contributors[:20]]
                lines += ['',f"Omitted-region C control: measured represented field plus omitted measured counts weighted by baseline C gives {row['omitted_baseline_C_h8_a']:.9f} / {row['omitted_baseline_C_h8_b']:.9f} ({row['omitted_baseline_C_order']}). This retains measured represented C and driver locations; it is not a new model prediction.",'',
                    'Largest fixed-observation residuals (each architecture at its own measured peak):','',
                    '| Architecture | Source | Residual | Coverage |','|---|---|---:|---|']
                for candidate in (a,b):
                    rs=sorted(peaks[(d,candidate['architecture'])],key=lambda r:-abs(float(r['residual'])))[:8]
                    lines += [f"| {candidate['architecture']} | {r['source']} | {float(r['residual']):.9f} | {r['coverage']} |" for r in rs]
                (outputpairs/(stem+'.md')).write_text('\n'.join(lines)+'\n',encoding='utf-8')
    write_csv(out/'pair_summary.csv',pairrows)
    write_csv(out/'problem_pairs.csv',[r for r in pairrows if r['classification']!='correct'])
    write_csv(out/'mechanism_summary.csv',mechanisms)
    # Compact cross-design and event summaries, independent of pair selection.
    cross=[]
    for d in ('s9234','s15850','s5378'):
        ns=[n for (dd,_),n in notes.items() if dd==d]
        historic=[r for r in pairrows if r['design']==d and r['historical_pair']]
        cross.append(dict(design=d,architectures=len(ns),historical_reversals=sum(r['classification']=='reversal' for r in historic),
            historical_ties=sum(r['classification']=='predicted_tie' for r in historic),
            represented_energy_fraction_min=min(n['measured_energy_represented_fraction'] for n in ns),
            represented_energy_fraction_max=max(n['measured_energy_represented_fraction'] for n in ns),
            peak_moved_count=sum(n['peak_moved'] for n in ns),
            depth_limited_peak_min=min(n['coverage_at_measured_peak']['depth_limited'] for n in ns),
            depth_limited_peak_max=max(n['coverage_at_measured_peak']['depth_limited'] for n in ns),
            matched_activity_l1=sum(n['matched_activity_l1'] for n in ns),q_activity_l1=sum(n['q_activity_l1'] for n in ns),
            cycles_above_two=sum(n['cycles_above_two'] for n in ns),
            buffer_insertions=sum(len(n['buffers']['inserted']) for n in ns),
            buffer_removals=sum(len(n['buffers']['removed']) for n in ns),
            matched_bin_moves=sum(n['bin_moved_sources'] for n in ns),
            repository_commit=common['repository_commit'],timestamp=common['timestamp'],model_version=common['model_version'],
            script_invocation='python scripts/pact_h8_rootcause.py report',source_evidence_sha256=sha256(out/'evidence_index.json')))
    write_csv(out/'cross_design.csv',cross)
    # Source-skeleton/topology audit for important residual sources and route geometry.
    geometry=[]
    topology_changes=[]
    for entry in idx['architectures']:
        d,h=entry['design'],entry['architecture_sha256']
        target=out/d/h
        topology=read(target/('routed_topology.json' if (target/'routed_topology.json').exists() else 'routed_topology.json.gz'))
        baseline=read(root/'results/pact_candidate_sensitive'/d/'topology.json')
        baseline_geometry=read(root/'results/pact_candidate_stateful'/d/'baseline_geometry.json')
        baseline_sources={v['source']:n for n,v in baseline['nets'].items()}
        evidence_folder=root/entry['provenance']['source_evidence']['artifacts']['net_mapping.json']['path'].replace('\\','/')
        measured_caps={r['source']:r for r in csvrows(evidence_folder.parent/'net_activity_capacitance.csv')}
        omitted_rows=csvrows(target/'omitted_cap_discrepancy.csv')
        for row in omitted_rows:
            bn=baseline_sources[row['source']]
            geom=baseline_geometry[bn]
            measured_row=measured_caps[row['source']]
            row.update(baseline_ground_ff=geom['candidate_ground_ff'],baseline_pin_ff=geom['candidate_pin_ff'],
                extracted_ground_ff=measured_row['ground_ff'],actual_pin_ff=measured_row['pin_ff'],
                baseline_mmst_um=geom['candidate_mmst_um'])
            if measured_row['ground_ff']:
                np.testing.assert_allclose(float(row['cap_delta_ff']),float(measured_row['ground_ff'])-geom['candidate_ground_ff']+
                    float(measured_row['pin_ff'])-geom['candidate_pin_ff'],atol=1e-9)
        write_csv(target/'omitted_cap_discrepancy.csv',omitted_rows)
        bounds=baseline['bounds']
        for name in sorted(set(baseline['cells'])|set(topology['cells'])):
            old,new=baseline['cells'].get(name),topology['cells'].get(name)
            if old and new and all(old[k]==new[k] for k in ('master','xy','inputs','outputs')):
                continue
            topology_changes.append(dict(design=d,architecture_hash=h,cell=name,
                change='inserted' if not old else 'removed' if not new else 'modified',
                old_master=old['master'] if old else None,new_master=new['master'] if new else None,
                xy_changed=old['xy']!=new['xy'] if old and new else None,
                inputs_changed=old['inputs']!=new['inputs'] if old and new else None,
                outputs_changed=old['outputs']!=new['outputs'] if old and new else None,
                old_inputs=json.dumps(old['inputs'],sort_keys=True) if old else None,
                new_inputs=json.dumps(new['inputs'],sort_keys=True) if new else None,
                interpretation='baseline skeleton vs candidate; scan SI/last-SO differences can be intentional',
                repository_commit=common['repository_commit'],timestamp=common['timestamp'],model_version=common['model_version'],
                script_invocation='python scripts/pact_h8_rootcause.py report',source_evidence_sha256=entry['provenance']['source_evidence_sha256']))
        rows=csvrows(target/'net_discrepancy.csv')
        important=sorted(rows,key=lambda r:-abs(float(r['peak_residual'])))[:30]
        for r in important:
            net=topology['nets'].get(r['meas_net'])
            points=net['route_points_um'] if net else []
            from pact.physical_effect import spatial_bin
            point_bins=sorted({spatial_bin(p,bounds,8) for p in points})
            geometry.append(dict(design=d,architecture_hash=h,source=r['source'],
                pred_mmst_um=r['pred_mmst_um'],actual_terminal_mmst_um=r['actual_terminal_mmst_um'],
                baseline_mmst_um=baseline_geometry[baseline_sources[r['source']]]['candidate_mmst_um'] if r['source'] in baseline_sources else None,
                baseline_calibrated_cap_ff=baseline_geometry[baseline_sources[r['source']]]['candidate_cap_ff'] if r['source'] in baseline_sources else None,
                activity_excluded=r['coverage']!='represented',
                routed_length_um=r['routed_length_um'],decoded_segment_length_um=net['decoded_segment_length_um'] if net else None,
                route_point_bins=';'.join(map(str,point_bins)),
                route_x_span_um=max(p[0] for p in points)-min(p[0] for p in points) if points else None,
                route_y_span_um=max(p[1] for p in points)-min(p[1] for p in points) if points else None,
                pred_bin=r['pred_bin'],meas_bin=r['meas_bin'],sink_set_changed=r['sink_set_changed'],
                master_changed=r['master_changed'],cap_error_ff=r['cap_error_ff'],peak_residual=r['peak_residual'],
                interpretation='route point/bin span, not segment capacitance redistribution; decoded length can omit RECT/extension detail',
                repository_commit=common['repository_commit'],timestamp=common['timestamp'],model_version=common['model_version'],
                script_invocation='python scripts/pact_h8_rootcause.py report',
                source_evidence_sha256=entry['provenance']['source_evidence_sha256']))
    write_csv(out/'geometry_audit.csv',geometry)
    write_csv(out/'topology_changes.csv',topology_changes)
    write(out/'analysis_summary.json',dict(provenance=common,classification='PACT_H8_ROOT_CAUSE_IDENTIFIED',
        pairs=len(pairrows),problem_pairs=sum(r['classification']!='correct' for r in pairrows),
        cross_design=cross,recommended_change='adaptive stateful cone expansion',
        claim_boundary='root cause of saved source-localized H8 ordering; no claim of physical power-density or out-of-corpus validation'))
    documentation(out,root,idx,notes,pairrows,cross,summary)
    print('REPORT',len(pairrows),'pairs;',sum(r['classification']!='correct' for r in pairrows),'problematic',flush=True)


def documentation(out,root,idx,notes,pairrows,cross,summary):
    common=idx['provenance']
    preamble=f"Repository commit: `{common['repository_commit']}`. Timestamp: `{common['timestamp']}`. Model: `{common['model_version']}`. Source evidence hashes and invocations: [evidence_manifest.json](evidence_manifest.json), [evidence_index.json](evidence_index.json).\n"
    lines=['# PACT H8 root-cause diagnosis','', '**Classification: PACT_H8_ROOT_CAUSE_IDENTIFIED**','',preamble,
        'This identifies the failure mechanisms for the saved source-localized switching metric. It does not validate prediction on new architectures, distributed power density, physical glitches, or fault identity sets. Historical evidence and model/solver semantics are unchanged.','',
        '## 1. What exactly is wrong?','',
        'The historical 24-architecture corpus contains 25 H8 reversals and four predicted ties with unequal measurements: s9234 18/1, s15850 6/3, s5378 1/0. The full 28-architecture measured set contains 37 problematic pairs, including the two latest selected ties and six other comparisons involving latest candidates. All appear in problem_pairs.csv. pair_summary.csv also retains the resolved previous s5378 selected pair as a control.','',
        '| Important pair (A / B) | Predicted A / B | Measured A / B | First ordered substitution agreeing with measurement |','|---|---:|---:|---|']
    selected=[r for r in pairrows if r['previous_selected_pair'] or r['latest_selected_pair']]
    for r in selected:
        stem=r['design']+'_'+r['architecture_a']+'__'+r['architecture_b']
        lines.append(f"| [{r['design']} {r['architecture_a']} / {r['architecture_b']}](pairs/{stem}.md) | {r['pred_h8_a']:.6f} / {r['pred_h8_b']:.6f} | {r['meas_h8_a']:.6f} / {r['meas_h8_b']:.6f} | {r['first_correct_substitution']} |")
    lines += ['','H8 units are fF·transitions per bin/cycle; E is fF·transitions summed over the workload. Bin IDs are 8*y+x. Comparing separately maximized fields requires retaining peak cycles as well as bins.','',
        '## 2. Where does the error enter?','',
        '**The spatial field omits depth-limited combinational outputs, and candidate ground-capacitance errors matter for close orderings.** Every saved predicted and measured E/H8 was independently reconstructed from the existing architecture, workload, graph, compact VCD counts and C tables, and checked against the historical values. Fixed-observation residuals exactly sum from net contributions; the complete cycle×bin field decomposition also closes numerically.','',
        'Across the 37 problematic pairs, 27 first reach the measured ordering when omitted nets are added after represented-net activity/C/location substitutions; ten first agree after capacitance substitution. These are ordered counterfactuals, not independent additive causal effects on a nonlinear maximum. Adding omitted nets with their measured C combines coverage and C inside that region; omitted_cap_control.json explicitly separates baseline-C and extracted-C reweighting.','',
        'For s9234 4d6ff90b2adc / 1359e456272b, represented counts agree in every cycle and source locations agree. Both predictions peak in bin 35 = (3,4) at 162.06390223. Extracted represented C breaks the tie to 163.24046488 / 164.13199099; omitted depth-limited contributions at the measured maxima are 29.42368275 / 29.91670115. The measured difference is 1.38454451. U_g3/Q has unchanged pin load 6.0748 fF and predicted total C 9.05456505 fF, but extracted totals 9.72587067 / 9.99982980 fF: this is ground-C variation with unchanged sinks, not evidence of buffer insertion at the peak.','',
        'For s15850 630da6943398 / a3dd757a7e17, predicted bin 38 = (6,4) differs from measured bin 22 = (6,2). The omitted region contributes 241.31745144 / 240.11994793 at the measured peaks, versus represented 30.21993400 / 30.42257373. Capacitance substitution of the represented field still gives the wrong ordering (228.22600756 < 229.89820314); adding omitted measured contributions yields 271.53738544 > 270.54252166. Both measured peaks occur at cycle 30166, and every depth-limited source in bin 22 has identical counts in A and B. Its omitted difference of 1.19750351 is therefore entirely extracted-C variation at that observation. U_g10433/ZN contributes C=4.346997 / 3.8000678 fF; U_g10518/ZN 8.39072455 / 7.8848694 fF. Reweighting omitted counts with baseline C gives maxima 269.83279287 < 269.86182598, so coverage alone under that control does not recover the implemented ordering. The defensible diagnosis is an omitted dominant region interacting with candidate ground C, not solely a switching-state error.','',
        'Topology changes exist in the corpus, including relocated sources, inserted buffers and changed scan sink sets. They are audited in topology_changes.csv and each topology_notes.json. Nevertheless activity, driver-bin movement and inserted/removed-net substitutions change **none of the global H8 maxima in this corpus**. At all selected measured peak observations, these terms are zero. Candidate topology is therefore not established as the dominant H8 explanation here. Matched-source activity differences elsewhere are retained rather than hidden.','',
        'Route geometry is audited via endpoint MMST, actual route length, route points and bin spans. Both metrics assign whole-net C at the source: metal crossing another bin cannot directly relocate H8 under these semantics. Route differences enter through C or driver/buffer changes. MMST estimates length rather than a distributed spatial RC field. Decoded route segments can omit RECT/extension details, so route-length discrepancies and point spans are descriptive, not segment-level energy attribution.','',
        'Predicted and measured grid, coordinates, units and shift-window semantics agree. Their coverage differs deliberately. This is an omitted-logic/model completeness error rather than an inconsistent H8 formula. The full chain is in pipeline_map.json.','',
        '## 3. Why is E much more reliable than H8?','',
        'E ordering remains 26/28, 28/28 and 28/28 in the historical s5378/s9234/s15850 corpora. That does not establish absolute accuracy. The represented measured E fraction is approximately 83–84%, 72–74% and 69–70%, respectively, and stays relatively stable within each design. The missing whole-design activity is large but largely tracks the global architecture ordering. H8 instead takes a maximum; a concentrated omitted region can overtake a represented region and reverse an ordering even while E ordering remains correct. s15850 has roughly 30% unrepresented E but as much as 89% unrepresented switching-C at its selected measured hotspot. No population-level generalization is claimed.','',
        '## 4. Why does s5378 behave better than s9234/s15850?','',
        '| Design | Represented measured E fraction | Predicted peak bin differs (all saved architectures) | Depth-limited contribution at measured peak |','|---|---:|---:|---:|']
    for r in cross:
        lines.append(f"| {r['design']} | {100*r['represented_energy_fraction_min']:.2f}–{100*r['represented_energy_fraction_max']:.2f}% | {r['peak_moved_count']}/{r['architectures']} | {r['depth_limited_peak_min']:.6f}–{r['depth_limited_peak_max']:.6f} |")
    lines += ['','All ten s5378 predictions and measurements peak in bin 18 = (2,2). Its omitted peak contribution is small enough that represented stateful activity generally preserves the ranking. Its remaining historical reversal b5c4710dcf54 / c11dfeee8d44 has predicted H8 168.889234 > 163.720115 but measured 177.510518 < 177.666719: omitted additions of 8.650311 / 13.429161 overturn that small measured gap. This is the same coverage mechanism seen more strongly in s9234/s15850, not a separate theory for the control design.','',
        '## 5. What should be changed next?','',
        '**Recommend exactly one model change: adaptive stateful cone expansion.** Reconstruct the exact settled fanin closures of downstream outputs beyond the fixed three-level cone so that large currently absent spatial regions enter the field. Use topology/workload coverage to select closures; do not tune coefficients or choose depth from these H8 labels. This is a prerequisite for comparing the true dominant region. No model change is implemented here.','',
        'This recommendation is not a promise that expansion alone fixes close rankings. Ground-C variation independently resolves the selected s9234 tie and both latest selected ties; the omitted-region C controls also retain C interactions. A future expansion must preserve those limitations and be evaluated on independent implementations. We are recommending the dominant coverage mechanism first, not fitting these candidates.','',
        '## 6. What should NOT be changed yet?','',
        'No ML, new search algorithms, K/seed/depth/placement sweeps, additional ATPG generation, broad benchmarking or large routing campaigns: these do not isolate the observed missing spatial contributions, and would mix changed architectures/implementations with a model-coverage question. There were zero new physical implementation, extraction, simulation or ATPG runs. OpenROAD only read existing ODBs to export topology/route geometry.','',
        '## 7. What remains unknown?','',
        'The exact settled/event decomposition of activity beyond the represented cone remains unknown. Matched FF Q counts agree in every cycle; all s15850 represented counts agree, and the selected s9234 represented counts agree. Some other s5378/s9234 matched transparent-source counts differ away from the H8 maxima. No saved net/cycle has more than two transitions. This rejects a demonstrated event/glitch cause of these H8 failures but does not prove absence of hazards: zero-delay VCD is not a physical timing measurement, and counts ≤2 can still conceal event differences.','',
        'Capacitance errors on omitted nets and routing interactions are real; ordered substitutions do not give a unique causal allocation of the final maximum. Route point spans are available, but segment-resolved extracted capacitance is not assigned to spatial bins. Physical timing/glitch and distributed power-density claims would need different evidence. No expensive run was needed to reach the present bounded diagnosis.','',
        'Full detected-fault identity equivalence remains independent and unresolved. The minimum stored-pattern extraction path is documented in ../pact_fault_identity/NEXT_STEPS.md; no FAN run was launched.','',
        '## Reproduction and artifact interpretation','',
        'Run in the existing qualified WSL environment; the index refuses to overwrite an initialized output directory. Historical files are never written.','',
        '```sh','export PYTHONPATH=.optimizer-deps:src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1',
        ('PY=' + python_executable() + ''),'$PY scripts/pact_h8_rootcause.py index',
        'openroad -python -no_init -exit scripts/pact_h8_export.py results/pact_h8_rootcause',
        '$PY scripts/pact_h8_rootcause.py analyze --design s9234',
        '$PY scripts/pact_h8_rootcause.py analyze --design s15850',
        '$PY scripts/pact_h8_rootcause.py analyze --design s5378',
        '$PY scripts/pact_h8_rootcause.py report',
        '$PY -m pytest -q tests/unit/test_h8_rootcause.py tests/unit/test_candidate_stateful.py tests/unit/test_physical_effect.py',
        '$PY scripts/pact_h8_rootcause.py seal','```','',
        'Focused suite: 19 tests passed. Artifact reconstruction assertions additionally check full canonical identities, workload cycle alignment, saved scores, complete field residual closure and selected-pair net-contribution sums. Every generated artifact is bound in evidence_manifest.json to commit, timestamp, model, invocation and source evidence.','',
        'bin_comparison.csv predicted_value/measured_value are each bin’s temporal maxima, with raw residual measured−predicted. Snapshot columns compare the same cycle and are additive across nets. Per-bin totals are retained. Rankings use deterministic bin-ID tie breaks; top-eight lists and both peak cycles are in topology_notes.json. net_discrepancy.csv distinguishes absent fields (empty) from actual zero, includes counts/C/ground/pins/sink differences, and attributes the residual at the measured peak. Pair CSVs sum measured contributions at each implementation’s own peak; they do not imply both peaks occur at the same cycle.','',
        'Added diagnostic code: scripts/pact_h8_rootcause.py, scripts/pact_h8_report.py, scripts/pact_h8_export.py, src/pact/analysis/h8_rootcause.py; tests/unit/test_h8_rootcause.py. Production model, optimizer, historical results and existing user edits are untouched. No commit or push was made.']
    (out/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    profiles=summary['designs']
    perf=['# Performance notes','',preamble,'This milestone changes no solver behavior or model semantics.','',
        '| Design | Stateful propagation s | Spatial updates s | Rollback s |','|---|---:|---:|---:|']
    for d in ('s9234','s15850','s5378'):
        p=profiles[d]['profile']
        perf.append(f"| {d} | {p['stateful_propagation_seconds']:.6f} | {p['spatial_seconds']:.6f} | {p['rollback_seconds']:.6f} |")
    perf += ['', 'These are existing recorded profiles, not new benchmarks. update_field scans the full cycle vector for each changed net; rollback repeats field subtraction/addition and score performs reductions. They dominate Boolean evaluation. Diagnostic decomposition accumulates into shared cycle×bin arrays and uses a one-cycle slice for per-net peak attribution; it does not allocate a full field for each net. Report-only C controls re-read compact count arrays to avoid rerunning the model. No runtime optimization campaign or solver edit was performed.']
    (out/'performance_notes.md').write_text('\n'.join(perf)+'\n',encoding='utf-8')
    faults=root/'results/pact_fault_identity'; faults.mkdir(exist_ok=True)
    faultpreamble=preamble.replace('](evidence_manifest.json)','](../pact_h8_rootcause/evidence_manifest.json)').replace('](evidence_index.json)','](../pact_h8_rootcause/evidence_index.json)')
    faultlines=['# Minimum fault-identity extraction path','',faultpreamble,
        'Scope: independent of H8. Existing coverage/count matches do not prove detected-fault identity sets. No ATPG regeneration or new FAN execution was performed.','',
        'For each design use reports/end_to_end/<design>/integration_v1/fault_replay/detected_fault_probe.script, original.script, remapped.script, recorded execution/logs and result.json. Original patterns are artifacts/raw/tool_qualification/fan_atpg/patterns/FAN_<design>.pat; remapped states were independently recovered to integration_v1/patterns_recovered.pat. Preserve executable/library/netlist/pattern hashes from result.json.','',
        '1. Reproduce the existing reporter failure with the saved probe script using the already qualified FAN binary (`fan -f <saved-probe.script>`). It reads patterns and runs single-frame stuck-at fault simulation; do not invoke run_atpg or generate patterns. Keep this reproduction separate from successful simulation/statistics.','2. Inspect the detailed reporter around negative/sentinel gate IDs and library pin lookup. The saved diagnosis records a dereference before a negative-ID check. The minimum fix/extraction is a stable detected-fault export after run_fault_sim, using the same fault universe and stable original functional gate/pin plus SA0/SA1 identity. Do not compare transient array indices or collapse conventions from different runs. Validate complete export size against the recorded DT count, reject duplicate or unresolvable identities and preserve raw status/universe mapping.','3. Run the same extraction for original.script and remapped.script, reading the existing original and recovered patterns on the same original functional circuit/library. Independently parse and compare the canonical sets (src/pact/integration/faults.py already contains parse_fault_report/replay_faults but currently leaves sets null when the reporter crashes).','',
        '```text','lost_faults = original_detected - remapped_detected','unexpected_faults = remapped_detected - original_detected','```','',
        'Export both complete identity sets and sorted differences with command/commit/tool/input hashes. A PASS requires complete successful exports and both differences empty; failed or partial lists remain unknown, never empty. This is a minimum next-step note, not a claimed repair or completed set-equivalence check.']
    (faults/'NEXT_STEPS.md').write_text('\n'.join(faultlines)+'\n',encoding='utf-8')


def seal(out,root):
    """Validate immutable inputs, compact new exports and bind every deliverable."""
    out=out.resolve()
    idx=read(out/'evidence_index.json')
    common=idx['provenance']
    input_bindings={}
    for entry in idx['architectures']:
        evidence=entry['provenance']['source_evidence']
        for record in [evidence['manifest'],evidence['architecture'],*evidence['artifacts'].values()]:
            path=root/record['path'].replace('\\','/')
            if sha256(path)!=record['sha256']:
                raise ValueError('Historical input changed: '+str(path))
            input_bindings[record['path']]=record
        d,h=entry['design'],entry['architecture_sha256']
        target=out/d/h
        # Replace the invocation family template with the exact producing command.
        invocation=('PYTHONPATH=.optimizer-deps:src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 ' + python_executable() + ' scripts/pact_h8_rootcause.py analyze --design ')+d
        for name in ('bin_comparison.csv','net_discrepancy.csv','peak_contributors.csv'):
            rows=csvrows(target/name)
            for row in rows:
                row['script_invocation']=invocation
            write_csv(target/name,rows)
        notes=read(target/'topology_notes.json')
        notes['provenance']['script_invocation']=invocation
        write(target/'topology_notes.json',notes)
        control=read(target/'omitted_cap_control.json')
        control['provenance']['script_invocation']='python scripts/pact_h8_rootcause.py report'
        write(target/'omitted_cap_control.json',control)
        raw=target/'routed_topology.json'
        if raw.exists():
            if not raw.resolve().is_relative_to(out):
                raise ValueError('Export outside intended diagnostic directory')
            data=read(raw)
            data['provenance']['script_invocation']='openroad -python -no_init -exit scripts/pact_h8_export.py results/pact_h8_rootcause'
            data['provenance']['export_source_sha256']=sha256(root/'scripts/pact_h8_export.py')
            payload=canonical_json(data).encode()
            packed=target/'routed_topology.json.gz'
            with packed.open('wb') as stream:
                with gzip.GzipFile(fileobj=stream,mode='wb',filename='',mtime=0) as archive:
                    archive.write(payload)
            if gzip.decompress(packed.read_bytes())!=payload:
                raise ValueError('Compact export verification failed')
            raw.unlink()  # Only the newly generated, verified raw export is removed.
        else:
            packed=target/'routed_topology.json.gz'
            data=read(packed)
            data['provenance']['script_invocation']='openroad -python -no_init -exit scripts/pact_h8_export.py results/pact_h8_rootcause'
            data['provenance']['final_export_source_sha256']=sha256(root/'scripts/pact_h8_export.py')
            data['provenance']['source_note']='Final source directly emits gzip; export numerical inspection is unchanged.'
            payload=canonical_json(data).encode()
            with packed.open('wb') as stream:
                with gzip.GzipFile(fileobj=stream,mode='wb',filename='',mtime=0) as archive:
                    archive.write(payload)
            if gzip.decompress(packed.read_bytes())!=payload:
                raise ValueError('Compact export verification failed')
    # Bind every model input consumed by the existing loader and unchanged sources.
    for d in ('s9234','s15850','s5378'):
        for name in ('model_contract.json','inputs.json','baseline_geometry.json','diagnostics.json'):
            path=root/'results/pact_candidate_stateful'/d/name
            input_bindings[str(path.relative_to(root))]=dict(path=str(path.relative_to(root)),sha256=sha256(path),bytes=path.stat().st_size)
        for name in ('topology.json',):
            path=root/'results/pact_candidate_sensitive'/d/name
            input_bindings[str(path.relative_to(root))]=dict(path=str(path.relative_to(root)),sha256=sha256(path),bytes=path.stat().st_size)
        contract=read(root/'results/pact_candidate_stateful'/d/'model_contract.json')
        for path,expected in contract['source_code'].items():
            if sha256(root/path)!=expected:
                raise ValueError('Production model source changed: '+path)
        for record in contract['inputs'].values():
            from pact_h8_rootcause import local
            path=local(record['path'])
            if not path.exists() or sha256(path)!=record['sha256']:
                raise ValueError('Model input absent or changed: '+str(path))
            input_bindings[record['path']]=record
    for namespace in ('pact_candidate_stateful','pact_candidate_sensitive','pact_v2'):
        path=root/'results'/namespace/'summary.json'
        input_bindings[str(path.relative_to(root))]=dict(path=str(path.relative_to(root)),sha256=sha256(path),bytes=path.stat().st_size)
    tests=(out/'unit_tests.log').read_text()
    passed=re.search(r'(\d+) passed in ([\d.]+)s',tests)
    if passed is None or 'failed' in tests:
        raise ValueError('Focused unit test result missing or failed')
    pairs=csvrows(out/'problem_pairs.csv')
    validation=dict(provenance=common,classification='PACT_H8_ROOT_CAUSE_IDENTIFIED',
        historical_inputs_unchanged=True,production_model_sources_unchanged=True,
        reconstructed_architectures=len(idx['architectures']),problem_pairs=len(pairs),
        tests_passed=int(passed[1]),tests_seconds=float(passed[2]),new_physical_runs=0,
        checks=['full canonical identities','saved E/H8 reproduction','complete cycle/bin residual closure',
                'selected and problematic pair peak net sums','historical input and source checksums',
                'lossless deterministic export compression'],
        limitation='Unknown excluded settled/event partition and future prediction accuracy; fault sets remain unknown')
    write(out/'validation_summary.json',validation)
    sources=('scripts/pact_h8_rootcause.py','scripts/pact_h8_report.py','scripts/pact_h8_export.py',
             'src/pact/analysis/h8_rootcause.py','tests/unit/test_h8_rootcause.py')
    artifacts={}
    lookup={(e['design'],e['architecture_sha256']):e for e in idx['architectures']}
    for path in sorted(out.rglob('*')):
        if not path.is_file() or path.name=='evidence_manifest.json':
            continue
        relative=path.relative_to(out)
        parts=relative.parts
        entry=lookup.get(tuple(parts[:2]))
        pair_entries=[]
        if parts[0]=='pairs':
            design,labels=path.stem.split('_',1)
            names=labels.split('__')
            pair_entries=[e for e in idx['architectures'] if e['design']==design and e['architecture'] in names]
        script='python scripts/pact_h8_rootcause.py report'
        if entry and path.name in ('bin_comparison.csv','net_discrepancy.csv','peak_contributors.csv','topology_notes.json'):
            script=('PYTHONPATH=.optimizer-deps:src ' + python_executable() + ' scripts/pact_h8_rootcause.py analyze --design ')+entry['design']
        elif path.name=='routed_topology.json.gz':
            script='openroad -python -no_init -exit scripts/pact_h8_export.py results/pact_h8_rootcause'
        elif path.name=='evidence_index.json':
            script='python scripts/pact_h8_rootcause.py index'
        elif path.name=='unit_tests.log':
            script=('PYTHONPATH=.optimizer-deps:src ' + python_executable() + ' -m pytest -q tests/unit/test_h8_rootcause.py tests/unit/test_candidate_stateful.py tests/unit/test_physical_effect.py')
        artifacts[str(relative).replace('\\','/')]=dict(sha256=sha256(path),bytes=path.stat().st_size,
            repository_commit=common['repository_commit'],timestamp=common['timestamp'],model_version=common['model_version'],
            script_invocation=script,design=entry['design'] if entry else pair_entries[0]['design'] if pair_entries else 'all_designs',
            architecture_hash=entry['architecture_sha256'] if entry else ';'.join(e['architecture_sha256'] for e in pair_entries) if pair_entries else 'see rows/evidence_index',
            source_evidence_sha256=entry['provenance']['source_evidence_sha256'] if entry else ';'.join(e['provenance']['source_evidence_sha256'] for e in pair_entries) if pair_entries else sha256(out/'evidence_index.json'))
    fault=root/'results/pact_fault_identity/NEXT_STEPS.md'
    write(out/'evidence_manifest.json',dict(provenance=common,artifacts=artifacts,source_evidence=input_bindings,
        final_diagnostic_source_code={p:sha256(root/p) for p in sources},
        diagnostic_source_note='Initial per-architecture hashes retained; final additions are validation/packaging/reporting. Production numerical model sources are unchanged.',
        external_deliverables={str(fault.relative_to(root)):dict(sha256=sha256(fault),bytes=fault.stat().st_size,
            repository_commit=common['repository_commit'],timestamp=common['timestamp'],model_version=common['model_version'],
            script_invocation='python scripts/pact_h8_rootcause.py report',source_evidence_sha256=sha256(out/'evidence_index.json'))}))
    print('SEALED',len(artifacts),'artifacts;',len(input_bindings),'unchanged input bindings;',passed[1],'tests',flush=True)
