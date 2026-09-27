#!/usr/bin/env python3
"""Replay and report a frozen validation; never calls the optimizer/objective."""
import argparse
import itertools
import json
from pathlib import Path
import sys
from datetime import datetime, timezone
import numpy as np
from scipy.stats import rankdata, spearmanr, kendalltau, pearsonr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from pact.analysis.phase2a_shift import replay
from pact.scan.model import ScanArchitecture
from pact.scan.phase0d_operators import structural_proof
from pact.test.pattern_parser import parse_fan_pat, map_ppi_patterns
from pact.experiment_storage import configure_experiment_storage, guard_disk_space
from pact.phase0d.campaign import file_sha256, atomic_write_json as write

REPORT=ROOT/'reports/phase2a_shift_activity'
ENDPOINTS=('raw_total','raw_peak','weighted_total','weighted_peak','raw_bin_peak',
           'raw_local_peak','weighted_bin_peak','weighted_local_peak')
PAIRS={'s5378':[('P','75ea663523d9'),('T','75ea663523d9'),('J50','1f1a3a458946'),('A','1f1a3a458946')],
       's9234':[('T','balanced'),('J50','activity_extreme'),('A','activity_extreme')],
       's15850':[('T','balanced'),('J50','balanced'),('A','activity_extreme')]}
def read(p): return json.loads(Path(p).read_text())

def integrity():
    freeze=read(REPORT/'freeze.json')
    for name,sha in freeze['files'].items(): assert file_sha256(REPORT/name)==sha,name
    for name,sha in read(REPORT/'provenance.json').items(): assert file_sha256(Path(name))==sha,name

def measure():
    integrity()
    paths=configure_experiment_storage()
    guard_disk_space(paths,estimated_bytes=200*1024**2)
    work=paths.results/'phase2a_shift_activity'
    quality=read(REPORT/'test_quality.json')
    patterns={d:map_ppi_patterns(parse_fan_pat(Path(q['pattern_path'])),read(q['identity_path'])['records']) for d,q in quality.items()}
    physical=read(REPORT/'physical_weighting.json')
    assert all(r['cap_nodes']==0 and r['rsegs']==0 and r['cap_api_available'] for r in physical['rows'])
    records={(r['design'],r['label']):r for r in physical['rows']}
    metrics=[]; proofs=[]; output_hashes={}
    for row in read(REPORT/'architecture_set.json'):
        d,label,sha=row['design'],row['label'],row['architecture_sha256']
        rec=records[d,label]
        assert file_sha256(Path(rec['physical_path']))==rec['physical_sha256']
        phy=read(rec['physical_path'])
        assert phy['odb_sha256']==row['odb_sha256'] and phy['architecture_sha256']==sha
        arch=ScanArchitecture.from_json(Path(row['architecture_path']))
        assert arch.sha256()==sha
        base=ScanArchitecture.from_json(ROOT/f'artifacts/derived/phase0c/{d}/s11/k2/P.architecture.json')
        structural=structural_proof(base,arch)  # every pattern checked with carry-state verifier in replay
        assert len(patterns[d])==quality[d]['pattern_count']
        trace=work/(sha+'.trace.npz')
        m,p=replay(arch,patterns[d],{n:r['wire_length_um'] for n,r in phy['FFs'].items()},
            {n:(r['x_um'],r['y_um']) for n,r in phy['FFs'].items()},quality[d]['die_bounds_um'],trace)
        # Check correspondence to archived raw logical evidence, never use it to compute metrics.
        old=read(row['proxy_path'])['activity']
        assert m['raw_total']==old['total_shift_toggles']
        assert m['raw_peak']==old['peak_simultaneous_toggles']
        p.update(design=d,label=label,architecture_sha256=sha,structural_proof=structural,
            archived_raw_totals_and_peaks_match=True,trace_path=str(trace),trace_sha256=file_sha256(trace))
        m.update(design=d,label=label,architecture_sha256=sha,H_eff8=row['H_eff8'],
                 physical_unit='micrometre-transitions',group=row['group'])
        metrics.append(m);proofs.append(p)
        output_hashes[str(trace)]=file_sha256(trace)
        output_hashes[rec['physical_path']]=rec['physical_sha256']
        print('REPLAY PASS',d,label,p['cycles_replayed'],flush=True)
    write(REPORT/'activity_metrics.json',dict(rows=metrics,physical_energy='INCOMPLETE'))
    write(REPORT/'shift_reconstruction.json',dict(status='PASS',rows=proofs))
    for rel in ('scripts/phase2a_validate.py','scripts/phase2a_extract_odb.py','src/pact/analysis/phase2a_shift.py'):
        output_hashes[str(ROOT/rel)]=file_sha256(ROOT/rel)
    write(REPORT/'measurement_provenance.json',dict(completed_utc=datetime.now(timezone.utc).isoformat(),files=output_hashes))
    integrity()

def correlations(x,y):
    if len(set(x))<2 or len(set(y))<2:
        return dict(spearman=None,kendall_tau_b=None,pearson=None)
    return dict(spearman=float(spearmanr(x,y).statistic),kendall_tau_b=float(kendalltau(x,y).statistic),
                pearson=float(pearsonr(x,y).statistic))

def weighted_corr(x,y,w):
    x,y,w=map(np.asarray,(x,y,w));w=w/w.sum()
    def midrank(a):
        return np.array([sum(w[a<v])+sum(w[a==v])/2 for v in a])
    def corr(a,b):
        a=a-sum(w*a);b=b-sum(w*b)
        denom=np.sqrt(sum(w*a*a)*sum(w*b*b))
        return float(sum(w*a*b)/denom) if denom else None
    num=dx=dy=0.
    for i in range(len(x)):
        for j in range(i):
            sx,sy=np.sign(x[i]-x[j]),np.sign(y[i]-y[j]);wij=w[i]*w[j]
            num+=wij*sx*sy;dx+=wij*(sx!=0);dy+=wij*(sy!=0)
    return dict(spearman=corr(midrank(x),midrank(y)),kendall_tau_b=float(num/np.sqrt(dx*dy)) if dx*dy else None,
                pearson=corr(x,y))

def analyze():
    rows=read(REPORT/'activity_metrics.json')['rows']
    per_design={};pairs=[]
    for d in PAIRS:
        group=[r for r in rows if r['design']==d]
        x=np.array([round(r['H_eff8'],9) for r in group]); n=len(x)
        ranks=rankdata(x);xc=ranks-ranks.mean()
        perm=np.array(list(itertools.permutations(range(n))),dtype=np.int8)
        px=xc[perm]
        endpoints={}
        for key in ENDPOINTS:
            y=[r[key] for r in group];stats=correlations(x,y)
            yc=rankdata(y);yc-=yc.mean()
            denominator=np.linalg.norm(xc)*np.linalg.norm(yc)
            p=None if denominator==0 else float(np.mean(np.abs(px@yc/denominator)>=abs(stats['spearman'])-1e-12))
            endpoints[key]=dict(**stats,exact_spearman_permutation_p_two_sided=p,
                ascending_ranking=[dict(label=r['label'],value=r[key]) for r in sorted(group,key=lambda r:(r[key],r['label']))])
        per_design[d]=dict(n=n,permutations=len(perm),endpoints=endpoints,
            H_eff8_ascending_ranking=[dict(label=r['label'],value=round(r['H_eff8'],9)) for r in sorted(group,key=lambda r:(round(r['H_eff8'],9),r['label']))])
        lookup={r['label']:r for r in group}
        for left,right in PAIRS[d]:
            a,b=lookup[left],lookup[right]
            delta={key:b[key]-a[key] for key in ('H_eff8',*ENDPOINTS)}
            percentage={key:100*delta[key]/a[key] if a[key] else None for key in delta}
            direction={key:('tie' if abs(delta[key])<1e-9 or abs(delta['H_eff8'])<1e-9 else
                       'correct' if delta[key]*delta['H_eff8']>0 else 'incorrect') for key in ENDPOINTS}
            pairs.append(dict(design=d,baseline=left,PACT=right,delta_PACT_minus_baseline=delta,
                              delta_percent=percentage,H_eff8_direction=direction))
    pooled={}
    for key in ENDPOINTS:
        xx=[];yy=[];ww=[];rx=[];ry=[]
        for d in PAIRS:
            g=[r for r in rows if r['design']==d]
            x=np.array([round(r['H_eff8'],9) for r in g]);y=np.array([r[key] for r in g]);n=len(g)
            xx.extend(x/x.mean()); yy.extend(y/y.mean()); ww.extend([1/n]*n)
            rx.extend((rankdata(x)-1)/(n-1));ry.extend((rankdata(y)-1)/(n-1))
        pooled[key]=dict(within_design_mean_normalized=weighted_corr(xx,yy,ww),
                        within_design_fractional_ranks=weighted_corr(rx,ry,ww))
    strong=all(per_design[d]['endpoints'][k]['spearman']>=.7 for d in PAIRS for k in ('weighted_total','weighted_local_peak'))
    strong &= all(p['H_eff8_direction'][k]=='correct' for p in pairs for k in ('weighted_total','weighted_local_peak'))
    fail=all(per_design[d]['endpoints'][k]['spearman']<=0 for d in PAIRS for k in ('weighted_total','weighted_local_peak'))
    classification=('PACT_PHASE2A_H_EFF8_PHYSICAL_ACTIVITY_VALIDATED' if strong else
                    'PACT_PHASE2A_H_EFF8_ACTIVITY_VALIDATION_FAIL' if fail else
                    'PACT_PHASE2A_H_EFF8_ACTIVITY_VALIDATION_PARTIAL')
    result=dict(classification=classification,per_design=per_design,pooled=pooled,pairwise=pairs,
        inference='Descriptive selected finite architecture set; exact permutation p-values are not confirmatory significance; no multiplicity adjustment or random-sample assumption.',
        pooling='Each design total weight 1, each row 1/n_design. Weighted midranks and weighted pairwise tau-b. No pooled p-value.',
        energy_portion='INCOMPLETE')
    write(REPORT/'correlation.json',result)
    return rows,result

def fmt(v): return 'NA' if v is None else f'{v:.3f}'

def report():
    paths=configure_experiment_storage()
    rows,corr=analyze()
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(3,3,figsize=(12,10),layout='constrained')
    keys=('raw_total','weighted_total','weighted_local_peak')
    for i,d in enumerate(PAIRS):
        g=[r for r in rows if r['design']==d]
        for j,key in enumerate(keys):
            ax=axes[i,j]; mean=np.mean([r[key] for r in g])
            for r in g:
                ax.scatter(r['H_eff8'],r[key]/mean,color='#147d92' if r['group']=='baseline' else '#c45035')
                ax.annotate(r['label'][:5] if len(r['label'])==12 else r['label'].replace('activity_extreme','activity'),
                    (r['H_eff8'],r[key]/mean),fontsize=6,xytext=(3,3),textcoords='offset points')
            rho=corr['per_design'][d]['endpoints'][key]['spearman']
            ax.set_title(f'{d}: {key}\nSpearman rho = {rho:.3f}',fontsize=10)
            ax.set_xlabel('Frozen H_eff8');ax.set_ylabel('Metric / design mean');ax.grid(alpha=.2)
    fig.savefig(REPORT/'activity_comparison.png',dpi=170);plt.close(fig)
    quality=read(REPORT/'test_quality.json');proofs=read(REPORT/'shift_reconstruction.json')['rows']
    physical=read(REPORT/'physical_weighting.json')['rows']
    lines=['# PACT Phase-2A independent post-route shift-activity validation','',
        f'**Classification: `{corr["classification"]}`**','',
        '**Answer: H_eff8 does not reliably rank the independent physical switching metrics across all three designs.** '
        'The association is design- and endpoint-dependent. Lower H_eff8 is not sufficient evidence of '
        'lower total routed-wirelength-weighted switching or lower local peak switching. '
        'Electrical energy and dynamic power remain unvalidated.','',
        '## Validation question and frozen evidence','',
        '> Across the frozen s5378, s9234 and s15850 architectures, does H_eff8 correctly rank or track independently '
        'reconstructed and physically weighted post-route scan-shift switching behavior?','',
        'The [contract](reports/phase2a_shift_activity/EXPERIMENT_CONTRACT.md) was hash-frozen before measurement. '
        '[Architecture set](reports/phase2a_shift_activity/architecture_set.json), '
        '[freeze](reports/phase2a_shift_activity/freeze.json) and '
        '[input provenance](reports/phase2a_shift_activity/provenance.json) identify all inputs. '
        'Seed 11 and K=2 are fixed. No optimization, new candidates, ATPG generation, placement or routing was run. '
        'All four requested baselines and Phase-1 balanced/activity extrema are retained on s9234/s15850. '
        's5378 uses every one of the five previously routed Phase-0D candidates, including dominated candidates, '
        'with their original hashes; these are older optimizer evidence, not v2.3 role selections.','',
        '| Design | FFs | Patterns | Frozen stuck-at coverage | Clocks / architecture |',
        '|---|---:|---:|---:|---:|']
    for d,q in quality.items():
        cycles=next(p['cycles_replayed'] for p in proofs if p['design']==d)
        lines.append(f'| {d} | {q["FF_count"]} | {q["pattern_count"]} | {q["stuck_at_coverage_percent"]:.2f}% | {cycles} |')
    lines += ['', '## Independent reconstruction and correctness','',
        f'All {len(proofs)} architectures pass canonical hash, FF inventory/coordinate, chain legality, SI/SO identity '
        'and fresh routed scan-connectivity checks. Every pattern is replayed with the established FAN parser, '
        'PPI bijection and parallel_schedule. A separate cycle recorder is checked against verify_parallel_schedule '
        'for final PPI state and every scan-out sample, including pad tails. Archived raw transition totals and '
        'peaks also match exactly; those archived scores are used only as a post-computation integrity check.','',
        'Initial state is zero. Short chains receive leading zero pad bits while every FF still clocks. Loaded state '
        'carries across pattern boundaries. There is no modeled capture and no extra final unload. Thus these are '
        'exact stable-state transitions for the frozen **carry-loaded/no-capture** sequence, not a simulated tester '
        'load/capture/unload waveform. Scan-link transitions are source-Q changes through verified transparent paths; '
        'glitches and timing are not inferred.','',
        '[Reconstruction results](reports/phase2a_shift_activity/shift_reconstruction.json) record per-pattern '
        'transitions, boundaries, lengths, padding, FF transition totals, state-trace hashes and D: trace locations. '
        'Compressed traces retain every cycle’s FF state, FF toggle mask, SI inputs and raw/weighted counts. '
        'Coverage is inherited from the frozen full-scan qualification, not new post-route fault simulation.','',
        '## Physical weighting and actual functional fanout','',
        'No SPEF was found under the existing Phase-1 or ORFS Nangate45 result trees. All selected ODBs expose '
        'the parasitic APIs but contain zero CapNodes and zero RSegs on the traced nets. Therefore qualified '
        'capacitance is unavailable. Metric B is **routed-wirelength-weighted stable-state switching**, in '
        '**µm-transitions**, computed as sum over cycles and FFs of toggle × actual driven wire length.','',
        'For each Q/QN source, the extractor follows actual BUF/CLKBUF/INV connectivity, includes complete routed '
        'nets with their functional and scan sinks, and counts each unique net once. It stops at other logic. '
        'All selected FF outputs are Q; no connected QN output occurs. Shared routed branches are included '
        'once, not multiplied by sink count. Inverters preserve stable transition counts. This differs from '
        'summing Q-to-SI distances or the existing per-link path bound.','',
        '| Design | Internal scan SI sinks | Nets with scan + other sinks | Other sink terminals | Transparent branches |',
        '|---|---:|---:|---:|---:|']
    for d in PAIRS:
        r=next(p for p in physical if p['design']==d)
        lines.append(f'| {d} | {r["scan_si_terminals"]} | {r["nets_with_scan_and_other_sinks"]} | {r["other_sink_terminals"]} | {r["transparent_branches"]} |')
    lines += ['', 'Counts above are constant within each design in this set. “Other sinks” include functional inputs '
        'and transparent-gate inputs. All internal scan nets share non-scan sinks. '
        '[Physical audit](reports/phase2a_shift_activity/physical_weighting.json) links hashed per-net inventories. '
        'Pin capacitance, layer-dependent capacitance, via capacitance, coupling, cell internal energy, '
        'clock/SE/PI/input-port switching and nontransparent combinational switching are excluded. '
        'Wirelength is a geometric load surrogate, not measured capacitance, energy, or power.','',
        '## Architecture measurements and spatial peaks','',
        'Spatial measurement uses fixed 10×10 bins over the frozen die outline, with routed FF origins. '
        'Per-cycle bin sums use raw toggles or independently extracted wire weights. Local peak is the largest '
        'equal-weight sum in any wholly contained 2×2-bin window over all shift cycles. No H_eff8 kernel, '
        'direct-sink weights or objective score enters measurement. Load is assigned to the driver bin; '
        'this is not a map of distributed wire dissipation. No occupancy normalization is applied.','']
    for d in PAIRS:
        lines += [f'### {d}','', '| Architecture | H_eff8 | Raw total | Raw peak | Weighted total (µm-transitions) | Weighted cycle peak | Raw local peak | Weighted local peak |',
                  '|---|---:|---:|---:|---:|---:|---:|---:|']
        for r in [r for r in rows if r['design']==d]:
            lines.append(f'| {r["label"]} | {r["H_eff8"]:.3f} | {r["raw_total"]:,} | {r["raw_peak"]} | {r["weighted_total"]:,.3f} | {r["weighted_peak"]:,.3f} | {r["raw_local_peak"]:.0f} | {r["weighted_local_peak"]:,.3f} |')
    lines += ['', 'Mean/p95 cycle activity, single-bin peaks, cumulative spatial maps and exact peak cycle/window '
        'locations are in [activity_metrics.json](reports/phase2a_shift_activity/activity_metrics.json).','',
        '![Independent activity comparisons](reports/phase2a_shift_activity/activity_comparison.png)','',
        '## Correlations and exact rankings','',
        'Positive correlation means lower H_eff8 tracks lower measured activity. Rank ties use average ranks '
        'and Kendall tau-b; H_eff8 is rounded to nine decimals only for roundoff ties. Pearson is secondary. '
        'Spearman p-values enumerate all architecture-label permutations, two-sided, and are descriptive: '
        'these selected architectures are not random independent samples, and multiple endpoints are inspected. '
        'No statistical significance or generalization claim is made.','',
        '| Design | Endpoint | Spearman ρ | Kendall τ-b | Pearson r | Exact descriptive p |',
        '|---|---|---:|---:|---:|---:|']
    for d,entry in corr['per_design'].items():
        for key,s in entry['endpoints'].items():
            lines.append(f'| {d} (n={entry["n"]}) | {key} | {fmt(s["spearman"])} | {fmt(s["kendall_tau_b"])} | {fmt(s["pearson"])} | {fmt(s["exact_spearman_permutation_p_two_sided"])} |')
    lines += ['', 'Exact ascending rankings (values retained to identify ties):','']
    for d,entry in corr['per_design'].items():
        lines.append(f'- **{d} H_eff8:** '+ ' → '.join(f'{r["label"]} ({r["value"]:.3f})' for r in entry['H_eff8_ascending_ranking']))
        for key,s in entry['endpoints'].items():
            lines.append(f'- **{d} {key}:** '+' → '.join(f'{r["label"]} ({r["value"]:.3f})' for r in s['ascending_ranking']))
    lines += ['', 'Pooled results divide each metric and H_eff8 by its own design mean before pooling. '
        'Each design has total weight one (each architecture weight 1/n_design); weighted midranks and '
        'weighted pair counts preserve equal design weight. Fractional within-design ranks are a second '
        'scale-free descriptive analysis. No raw quantities or pooled p-values are used.','',
        '| Endpoint | Mean-normalized pooled ρ | Pooled τ-b | Pooled Pearson | Within-design rank pooled ρ |',
        '|---|---:|---:|---:|---:|']
    for k,v in corr['pooled'].items():
        s=v['within_design_mean_normalized'];r=v['within_design_fractional_ranks']
        lines.append(f'| {k} | {fmt(s["spearman"])} | {fmt(s["kendall_tau_b"])} | {fmt(s["pearson"])} | {fmt(r["spearman"])} |')
    lines += ['', '## Preregistered PACT/baseline comparisons','',
        'Every delta below is PACT minus baseline; negative means a reduction. Direction columns compare '
        'the sign of each activity delta with the H_eff8 delta, with ties reported explicitly.','',
        '| Design / baseline → PACT | ΔH_eff8 | Δraw total | Δweighted total | Δweighted cycle peak | Δweighted local peak | Direction raw / weighted total / cycle / local |',
        '|---|---:|---:|---:|---:|---:|---|']
    for p in corr['pairwise']:
        dd=p['delta_PACT_minus_baseline'];ds=p['H_eff8_direction']
        lines.append(f'| {p["design"]} {p["baseline"]} → {p["PACT"]} | {dd["H_eff8"]:+.3f} | {dd["raw_total"]:+,} | {dd["weighted_total"]:+,.3f} | {dd["weighted_peak"]:+,.3f} | {dd["weighted_local_peak"]:+,.3f} | '+ ' / '.join(ds[k] for k in ('raw_total','weighted_total','weighted_peak','weighted_local_peak'))+' |')
    lines += ['', '[correlation.json](reports/phase2a_shift_activity/correlation.json) additionally includes '
        'percentage differences and all raw/bin/local endpoints for every pair.','',
        '## Interpretation, limitations and classification','',
        'The preregistered strong-confirmation rule requires ρ≥0.7 for weighted total and weighted local peak '
        'in every design plus correct directions for both endpoints in every specified pair. It is not met. '
        'The failure rule requires nonpositive correlations for both physical endpoints in every design. '
        'Otherwise the contract classifies the result as partial/design-dependent, rather than hiding negative endpoints.','',
        f'Final classification: **`{corr["classification"]}`**. The physical-energy portion is **INCOMPLETE**. '
        'The partial label is not a claim that H_eff8 is physically validated. See endpoint and pairwise signs above.','',
        'These three ISCAS designs, one seed, fixed K and selected existing architectures cannot establish '
        'general behavior. The metrics share frozen patterns and chain semantics with H_eff8 because those define '
        'the experiment; independence concerns the measurement calculation and physical weights. Raw total is '
        'a logical companion metric already present in earlier reports, not new electrical evidence. The new '
        'routed weighting and 10×10/2×2 spatial measurement use neither H_eff8 internals nor a monotonic transform. '
        'Single peak values may be driven by one cycle or boundary; peak witnesses and full traces are retained.','',
        'To establish electrical behavior requires qualified detailed-route RC extraction (or validated SPEF) '
        'for these exact ODB hashes, compatible timing/library and pin-capacitance data, defined coupling treatment '
        'and voltage, and independently validated test-mode activity including capture/unload, clocks and relevant '
        'combinational transitions. A qualified power analysis is required before a post-route dynamic test-power '
        'claim. No signoff flow was built in this task.','',
        '**Next research question:** With these architectures still frozen, does qualified capacitance-weighted '
        'activity under a validated capture/load/unload waveform preserve or reverse the observed endpoint-dependent rankings?','',
        '## Reproduction and validation','',
        'Implementation: `scripts/phase2a_freeze.py` (one-time freeze), '
        '`openroad -python -no_init -exit scripts/phase2a_extract_odb.py`, '
        '`scripts/phase2a_validate.py measure`, and `scripts/phase2a_validate.py report`. '
        'Use the existing WSL `/root/pact-deps/pact-venv/bin/python` and repository `src` on PYTHONPATH. '
        'The freeze command refuses replacement. Raw evidence and traces are under '
        '`D:/PACT_EXPERIMENTS/results/phase2a_shift_activity`; compact reports remain here.','']
    for name in ('focused_tests.log','regression.log'):
        p=REPORT/name
        if p.exists():
            summary=next((l for l in reversed(p.read_text().splitlines()) if 'passed' in l),'See log')
            lines.append(f'- [{name}](reports/phase2a_shift_activity/{name}): {summary}')
    lines += ['','All frozen evidence is rehashed after measurement. Prior optimizer changes remain untouched.']
    (ROOT/'PACT_PHASE2A_SHIFT_ACTIVITY_VALIDATION.md').write_text('\n'.join(lines)+'\n')
    integrity()
    audit=dict(frozen_files_unchanged=len(read(REPORT/'freeze.json')['files']),
        frozen_input_files_unchanged=len(read(REPORT/'provenance.json')),architectures=len(rows),
        all_reconstruction_pass=True,new_routes=0,new_optimizer_runs=0,new_ATPG_runs=0,
        raw_storage_bytes=sum(p.stat().st_size for p in (paths.results/'phase2a_shift_activity').rglob('*') if p.is_file()))
    write(REPORT/'integrity_audit.json',audit)
    print(json.dumps(dict(classification=corr['classification'],correlations={d:{k:fmt(v['spearman']) for k,v in r['endpoints'].items()} for d,r in corr['per_design'].items()},audit=audit),indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=('measure','report'))
    args=parser.parse_args()
    measure() if args.stage=='measure' else report()
