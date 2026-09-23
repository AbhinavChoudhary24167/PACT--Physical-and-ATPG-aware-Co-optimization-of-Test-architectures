#!/usr/bin/env python3
"""Frozen primary measurements and separate FF capture/unload sensitivity."""
from phase2b_common import *
import time
import resource
import numpy as np
from pact.scan.model import ScanArchitecture
from pact.physical.phase0c_port_policy import frozen_def_ports
from pact.analysis.phase2b_loads import pin_loads, construct_weights
from pact.analysis.phase2b_scoring import score_packed, fixed_bins

def main():
    integrity()
    quality=read(OLD/'test_quality.json')
    oldrows={(r['design'],r['label']):r for r in read(OLD/'activity_metrics.json')['rows']}
    proofs={(r['design'],r['label']):r for r in read(OLD/'shift_reconstruction.json')['rows']}
    physical={(r['design'],r['label']):r for r in read(OLD/'physical_weighting.json')['rows']}
    extraction=read(REPORT/'extraction_audit.json')
    qualified=extraction['capacitance_qualified']
    erows={(r['design'],r['label']):r for r in extraction['rows']}
    waveform=read(REPORT/'waveform_audit.json')
    wave={(r['design'],r['label']):r for r in waveform['rows']}
    loads=pin_loads(LIB.read_text()); results=[]; timings=[]; supplementary=[]
    construction=read(REPORT/'placement_audit.json')
    graphs={d:read(c['path']) for d,c in construction.items()}
    for d,c in construction.items(): assert file_sha256(Path(c['path']))==c['sha256']
    for row in read(REPORT/'architecture_set.json'):
        d,label,sha=row['design'],row['label'],row['architecture_sha256']; key=d,label
        arch=ScanArchitecture.from_json(Path(row['architecture_path'])); assert arch.sha256()==sha
        names=sorted(c.name for c in arch.cells); n=len(names)
        ports,units=frozen_def_ports(Path(quality[d]['placed_def']),len(arch.chains))
        ports={p:[v/units for v in xy] for p,xy in ports.items()}
        start=time.perf_counter();weights=construct_weights(arch,graphs[d],loads,ports)
        weight_seconds=time.perf_counter()-start
        xy={c.name:(c.x_um,c.y_um) for c in arch.cells}
        bins=fixed_bins([xy[name] for name in names],quality[d]['die_bounds_um'])
        proof=proofs[key]
        assert file_sha256(Path(proof['trace_path']))==proof['trace_sha256']
        trace=np.load(proof['trace_path']); assert trace['names'].tolist()==names
        packed=trace['toggles_packed']
        rec=dict(design=d,label=label,architecture_sha256=sha,predictors={'M1_H_eff8':round(row['H_eff8'],9)},targets={})
        for metric,weight in weights.items():
            start=time.perf_counter();score,counts=score_packed(packed,n,weight,bins)
            rec['predictors'][metric]=score['total'];rec['predictors'][metric+'_local']=score['local_peak']
            assert counts.tolist()==[proof['FF_transition_totals'][name] for name in names]
            timings.append(dict(design=d,label=label,metric=metric,total_and_local_seconds=time.perf_counter()-start,
                shared_weight_construction_seconds=weight_seconds,N_ff=n,N_shift_cycles=len(packed),N_patterns=quality[d]['pattern_count'],weight_bytes=weight.nbytes))
        ph=physical[key]; assert file_sha256(Path(ph['physical_path']))==ph['physical_sha256']
        phy=read(ph['physical_path'])
        reference={'wire':np.array([phy['FFs'][name]['wire_length_um'] for name in names])}
        if qualified:
            ext=erows[key]; assert file_sha256(Path(ext['weights_path']))==ext['weights_sha256']
            cap=read(ext['weights_path'])
            reference.update(cap=np.array([cap[name]['effective_ff'] for name in names]),
                cap_ground=np.array([cap[name]['ground_pin_ff'] for name in names]))
        for target,weight in reference.items():
            score,_=score_packed(packed,n,weight,bins)
            rec['targets'][target+'_total']=score['total'];rec['targets'][target+'_local_peak']=score['local_peak']
        rec['targets']['raw_total']=rec['predictors']['M0']
        assert rec['targets']['raw_total']==oldrows[key]['raw_total']
        assert np.isclose(rec['targets']['wire_total'],oldrows[key]['weighted_total'],rtol=1e-12)
        assert np.isclose(rec['targets']['wire_local_peak'],oldrows[key]['weighted_local_peak'],rtol=1e-12)
        # Explanatory decomposition: shares from scan extension vs functional tree.
        rec['diagnostics']=dict(
            toggle_weighted_wire_um=rec['targets']['wire_total']/rec['targets']['raw_total'],
            routed_wire_weight_sum_um=float(reference['wire'].sum()),
            functional_hpwl_activity=rec['predictors']['M5_functional_hpwl'],
            added_scan_hpwl_activity=rec['predictors']['M5_hpwl']-rec['predictors']['M5_functional_hpwl'],
            estimated_mean_load=rec['predictors']['M3_load']/rec['targets']['raw_total'])
        results.append(rec)
        write(WORK/sha/'predictor_weights.json',{m:dict(zip(names,map(float,w))) for m,w in weights.items()})
        if key in wave:
            wr=wave[key];assert file_sha256(Path(wr['trace_path']))==wr['trace_sha256']
            wt=np.load(wr['trace_path']);assert wt['names'].tolist()==names
            rr=dict(design=d,label=label,architecture_sha256=sha,predictors={},targets={})
            for metric,weight in weights.items():
                score,_=score_packed(wt['toggles_packed'],n,weight,bins)
                rr['predictors'][metric]=score['total'];rr['predictors'][metric+'_local']=score['local_peak']
            for target,weight in reference.items():
                score,_=score_packed(wt['toggles_packed'],n,weight,bins)
                rr['targets'][target+'_total']=score['total'];rr['targets'][target+'_local_peak']=score['local_peak']
            rr['targets']['raw_total']=rr['predictors']['M0']; supplementary.append(rr)
        print('MEASURED',d,label,flush=True)
    write(REPORT/'candidate_metrics.json',dict(rows=results,capacitance_qualified=qualified,
        primary_waveform='Phase-2A carry-loaded/no-capture/no-final-unload',
        formulas={
            'M0':'sum FF toggles; local version sum toggles in fixed window',
            'M1_H_eff8':'unchanged frozen objective, rounded 9 decimals only for ties',
            'M2_scan':'toggle * source-to-next-FF Manhattan length; tail zero',
            'M2_port':'M2_scan plus tail-to-fixed-scan-output length; no SI-driven activity',
            'M3_load':'toggle * (input-pin capacitance fF + 0.103981 fF/um * owned-net HPWL)',
            'M4_fanout':'toggle * connected input terminal count, functional + selected SI',
            'M4_pin':'toggle * sum input pin capacitance fF, functional + selected SI',
            'M4_functional_fanout':'M4 excluding selected scan SI loads',
            'M4_functional_pin':'M4_pin excluding selected scan SI loads',
            'M5_hpwl':'toggle * sum pre-route owned-net HPWL, functional + selected SI/SO',
            'M5_star':'toggle * sum pre-route driver-to-sink Manhattan lengths',
            'M5_functional_hpwl':'toggle * owned-net HPWL without SI/SO',
            '*_local':'M6 peak cycle/window of same per-FF weight; fixed 10x10 bins, 2x2 windows'},
        stage='All physical predictors POST-PLACEMENT at latest; no fitted parameters; route/SPEF labels isolated.'))
    write(REPORT/'waveform_sensitivity.json',dict(rows=supplementary,
        interpretation='Separate FF stable-state load/capture/final-zero-unload protocol. Frozen H_eff8 not redefined for this waveform.'))
    write(REPORT/'complexity.json',dict(rows=timings,placed_graph_construction=construction,
        peak_process_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        construction='Shared graph O(N_instances + N_sinks); weight arrays O(N_ff + reachable N_sinks + N_scan_links). Sparse adjacency; no dense FF-pair matrix.',
        totals='After per-FF counts are cached, each metric total is O(N_ff), or update O(number_of_shift_toggles). Computing counts from packed full trace costs O(N_ff*N_shift_cycles).',
        local='Current chunked evaluator O(N_ff*N_shift_cycles + N_spatial_bins*N_shift_cycles), fixed chunk 1024; O(1024*(N_ff+N_spatial_bins)) transient memory.',
        trace_storage='Packed O(N_ff*N_shift_cycles) plus states. Proof recorder retains trace; unsuitable at million-FF scale without streaming. Scoring weights themselves O(N_ff).',
        future_scale='Sparse per-FF totals scalable; exact exhaustive waveform/local peaks are not demonstrated cheap at 100k-1M gates. Stream/toggle-event accumulation and reuse counts; benchmark larger designs before integration.',
        fitted_coefficients=False,leave_one_design_out='Not applicable: no fitted parameters, physical coefficient fixed before measurement. All three designs are finite-set holdouts for same formula, not independent population validation.'))
    integrity()

if __name__=='__main__': main()
