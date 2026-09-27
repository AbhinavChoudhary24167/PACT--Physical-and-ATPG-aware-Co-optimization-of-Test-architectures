"""Gated seed-11 repair: witness -> 21 topology proofs -> predictor scores.

Physical evidence is read only by the validation boundary, never passed to the
predictor. Targets are copied verbatim from frozen Phase-2B measurements.
"""
from phase2cr_common import *
import argparse
from copy import deepcopy
import numpy as np
from pact.scan.model import ScanArchitecture
from pact.analysis.phase2b_loads import construct_weights as legacy, pin_loads, hpwl
from pact.analysis.phase2cr_loads import construct_with_audit
from pact.analysis.phase2b_scoring import score_packed, fixed_bins


def old_graph(g):
    return {k:deepcopy(g[k]) for k in ('stage','FFs','nets','transparent')}


def load_case(row, loads):
    a = ScanArchitecture.from_json(Path(row['architecture_path']))
    assert a.sha256() == row['architecture_sha256'] and order_hash(a) == row['scan_order_sha256']
    g = read(REPORT / (row['design'] + '.placed_graph.json'))
    old = legacy(a, old_graph(g), loads, g['scan_ports'])
    archived = read(WORK / a.sha256() / 'predictor_weights.json')
    names = sorted(c.name for c in a.cells)
    for m in old:
        np.testing.assert_array_equal(old[m], [archived[m][n] for n in names])
    new, audit = construct_with_audit(a, g, loads)
    return a, g, names, old, new, audit


def legacy_points(arch, graph, name):
    xy = {c.name:[c.x_um,c.y_um] for c in arch.cells}
    additions = []
    for ci, c in enumerate(arch.chains):
        if name in c.cells:
            i = c.cells.index(name)
            additions = [xy[c.cells[i+1]]] if i < len(c.cells)-1 else [graph['scan_ports']['test_so' if ci==0 else f'test_so_{ci}']]
    roots=graph['FFs'][name]['roots']; pending=list(roots.values()); seen=set(); result=[]
    while pending:
        n=pending.pop()
        if n in seen: continue
        seen.add(n); net=graph['nets'][n]
        points=[net['driver_xy']]+[s['xy'] for s in net['sinks']]+net['ports']
        if n==roots['Q']: points+=additions
        result.append(dict(net=n,points=points,hpwl_um=hpwl(points)))
        pending.extend(graph['transparent'].get(n,[]))
    return result


def topology(row, case, loads):
    a,g,names,old,new,audit=case
    ep=g['scan_endpoints']['chain0_so']; owner=ep['original_owner_ff']; tail=a.chains[0].cells[-1]
    selected=audit['selected_graph']; source=ep['original_source_net']; target=g['FFs'][tail]['roots']['Q']; child=ep['output_net']
    phyrow=next(r for r in read(A/'physical_weighting.json')['rows'] if (r['design'],r['label'])==(row['design'],row['label']))
    check(phyrow['physical_path'],phyrow['physical_sha256']); phy=read(phyrow['physical_path'])
    proof=read(row['proof_path'])
    owners=[n for n,f in phy['FFs'].items() if any(b['instance']==ep['buffer_instance'] for b in f['transparent_branches'])]
    assert owners==[tail] and audit['buffer_owner']==tail
    branch=[b for b in phy['FFs'][tail]['transparent_branches'] if b['instance']==ep['buffer_instance']]
    assert branch==[dict(instance=ep['buffer_instance'],master=ep['buffer_master'],source_net=target,output_net=child)]
    assert [ep['buffer_instance'],ep['input_pin']] in phy['nets'][target]['sinks']
    assert phy['nets'][child]['driver']==[ep['buffer_instance'],ep['output_pin']]
    assert phy['architecture_sha256']==a.sha256() and phy['odb_sha256']==row['odb_sha256']
    assert sorted(phy['FFs'])==names==row['FFs']
    assert len(a.chains)==row['K']==proof['K']==2
    assert proof['status']=='PASS' and proof['all_chain_inputs_outputs_verified'] and proof['fixed_port_positions_verified']
    edges=[(ci,x,y) for ci,c in enumerate(a.chains) for x,y in zip(c.cells,c.cells[1:])]
    assert edges==[(e['chain'],e['source_ff'],e['dest_ff']) for e in proof['edges']]
    assert [dict(chain_id=c.chain_id,cells=list(c.cells)) for c in a.chains]==row['chains']
    assert [dict(name=c.name,x_um=c.x_um,y_um=c.y_um) for c in a.cells]==row['cells']
    assert sorted(n for c in a.chains for n in c.cells)==names
    matrix=next(r for r in read(C/'architecture_matrix.json')['rows'] if r['seed']==11 and r['design']==row['design'] and r['label']==row['label'])
    assert order_hash(a)==row['scan_order_sha256']==matrix['scan_order_sha256']
    # Independent expected graph edit: restores exactly the original after undoing only SO changes.
    restored=deepcopy(selected)
    sink=dict(master=ep['buffer_master'],pin=ep['input_pin'],xy=ep['buffer_xy'])
    assert sum(v.count(child) for v in selected['transparent'].values())==1
    assert selected['transparent'][target].count(child)==1
    assert selected['nets'][target]['sinks'].count(sink)==1
    if owner!=tail:
        assert sink not in selected['nets'][source]['sinks'] and child not in selected['transparent'][source]
        restored['nets'][target]['sinks'].remove(sink)
        # Preserve original sink ordering in the equality proof.
        restored['nets'][source]['sinks'].insert(g['nets'][source]['sinks'].index(sink),sink)
        restored['transparent'][target].remove(child)
        if target not in g['transparent']: del restored['transparent'][target]
        restored['transparent'][source].insert(g['transparent'][source].index(child),child)
    assert selected['nets'][child]['ports'].count(ep['port_xy'])==1
    restored['nets'][child]['ports'].remove(ep['port_xy'])
    assert restored==g, 'Unrelated placed graph changed'
    records=[(n,r) for n,rr in audit['FFs'].items() for r in rr]
    buffer_records=[(n,r) for n,r in records if r['net']==target and sink in r['sinks']]
    assert len(buffer_records)==1 and buffer_records[0][0]==tail
    assert sum(r['net']==child for _,r in records)==1
    assert not any(s['master'] is None and s['pin']=='test_so' for _,r in records for s in r['additions'])
    # Direct chain-1 SO remains a single zero-pin-load geometry endpoint.
    direct=[(n,s) for n,r in records for s in r['additions'] if s['pin']=='test_so_1']
    assert direct==[(a.chains[1].cells[-1],dict(xy=g['scan_ports']['test_so_1'],master=None,pin='test_so_1'))]
    assert 'test_so_1' in phy['nets'][g['FFs'][a.chains[1].cells[-1]]['roots']['Q']]['bterms']
    q=read(A/'test_quality.json')[row['design']]
    import re
    units=int(re.search(r'UNITS DISTANCE MICRONS (\d+)',Path(q['placed_def']).read_text())[1])
    for p,xy in g['scan_ports'].items():
        np.testing.assert_allclose(np.array(xy)*units,proof['port_centers_dbu'][p],rtol=0,atol=1e-8)
    changed=[n for i,n in enumerate(names) if any(new[m][i]!=old[m][i] for m in new)]
    assert set(changed)<={owner,tail}, 'Unexplained weight change outside affected owners'
    # Complete branch pin load (not merely the first buffer input) is transferred.
    pending=[child]; seen=set(); branchcap=loads[ep['buffer_master'],ep['input_pin']]
    while pending:
        n=pending.pop()
        if n in seen: continue
        seen.add(n); branchcap+=sum(loads[s['master'],s['pin']] for s in g['nets'][n]['sinks'])
        pending.extend(g['transparent'].get(n,[]))
    expected=np.zeros(len(names))
    if owner!=tail:
        expected[names.index(owner)]-=branchcap; expected[names.index(tail)]+=branchcap
    np.testing.assert_allclose(new['M4_pin']-old['M4_pin'],expected,rtol=0,atol=1e-12)
    np.testing.assert_allclose(new['M4_functional_pin']-old['M4_functional_pin'],expected,rtol=0,atol=1e-12)
    return dict(design=row['design'],label=row['label'],architecture_sha256=a.sha256(),scan_order_sha256=order_hash(a),
        status='PASS',selected_chain0_tail=tail,corrected_predictor_output_buffer_owner=audit['buffer_owner'],
        physical_rewire_output_buffer_owner=owners[0],original_SO_owner=owner,
        buffer_instance=ep['buffer_instance'],buffer_master=ep['buffer_master'],buffer_input_pin=ep['input_pin'],
        buffer_input_pin_ff=loads[ep['buffer_master'],ep['input_pin']],transferred_branch_pin_ff=branchcap if owner!=tail else 0.,
        changed_FFs=changed,changed_FF_count=len(changed),unexpected_changed_FFs=[],
        physical_evidence=dict(path=phyrow['physical_path'],sha256=phyrow['physical_sha256']),
        checks={k:True for k in ('FF_inventory','FF_bijection','K','chain_membership','chain_order','chain_IDs',
            'scan_order_hash','architecture_hash','cell_coordinates','selected_tail','buffer_identity','input_pin_identity',
            'buffer_master','old_owner_branch_removed_when_needed','tail_branch_once','BUF_input_load_once',
            'SO_tree_geometry_once','ordinary_functional_sinks_unchanged','unrelated_transparent_branches_unchanged',
            'chain1_direct_port_unchanged','placed_port_policy_matches_physical_proof','legacy_weights_exact',
            'no_routed_predictor_inputs')})


def witness(freeze,loads):
    row=next(r for r in freeze['architectures'] if (r['design'],r['label'])==('s5378','P'))
    case=load_case(row,loads); a,g,names,old,new,audit=case
    proof=topology(row,case,loads)
    ep=g['scan_endpoints']['chain0_so']; owner=ep['original_owner_ff']; tail=a.chains[0].cells[-1]
    assert (owner,tail,ep['buffer_instance'])==('U_n1588gat','U_n2121gat','output38')
    assert proof['transferred_branch_pin_ff']==.974659
    affected={}
    for n in (owner,tail):
        i=names.index(n)
        affected[n]=dict(legacy_points=legacy_points(a,g,n),corrected_points=audit['FFs'][n],
            legacy={m:float(old[m][i]) for m in old},corrected={m:float(new[m][i]) for m in new})
        # Match the predictor's ordered binary64 += reduction. Python 3.12
        # sum() uses different floating arithmetic even for identical operands.
        reconstructed = 0.0
        for record in audit['FFs'][n]:
            length = hpwl(record['points'])
            assert length == record['hpwl_um']
            reconstructed += length
        assert reconstructed == new['M5_hpwl'][i]
    np.testing.assert_allclose([old['M3_load'][names.index(owner)],old['M5_hpwl'][names.index(owner)],
        old['M3_load'][names.index(tail)],old['M5_hpwl'][names.index(tail)]],[4.52743773,9.33,9.78143695,66.95],atol=1e-8,rtol=0)
    record=dict(status='PASS',observed_utc=now(),architecture_sha256=a.sha256(),original_owner=owner,selected_tail=tail,
        exact_moved_branch=ep,buffer_input_cap_ff=proof['buffer_input_pin_ff'],
        removed_synthetic_geometry=dict(root=g['FFs'][tail]['roots']['Q'],point=g['scan_ports']['test_so'],master=None),
        affected_FFs=affected,topology=proof,computed_from_points=True)
    write(REPORT/'representative_witness.json',record)
    lines=['# s5378 / seed-11 / P numerical regression witness','',
        'PASS. output38/BUF_X1/A and its complete transparent branch moved from U_n1588gat to U_n2121gat.',
        'Exactly 0.974659 fF transferred once; unrelated capacitance preserved. HPWL was recomputed from points.',
        'The synthetic direct tail-to-test_so point was removed; the actual placed-policy port is on the buffer output net.','',
        '| FF | old pin fF | new pin fF | old HPWL (M5) | new HPWL (M5) | old M3 | new M3 |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for n,v in affected.items():
        x,y=v['legacy'],v['corrected']
        lines.append(f"| {n} | {x['M4_pin']:.9f} | {y['M4_pin']:.9f} | {x['M5_hpwl']:.9f} | {y['M5_hpwl']:.9f} | {x['M3_load']:.9f} | {y['M3_load']:.9f} |")
    lines+=['','All old/new net point sets, sinks, port points and weights are in representative_witness.json.']
    (REPORT/'REPRESENTATIVE_WITNESS.md').write_text('\n'.join(lines)+'\n')
    print('REPRESENTATIVE_WITNESS_PASS',flush=True)


def all_topology(freeze,loads):
    assert read(REPORT/'representative_witness.json')['status']=='PASS'
    rows=[]
    for row in freeze['architectures']:
        case=load_case(row,loads)
        try:
            rows.append(topology(row,case,loads))
        except Exception as e:
            rows.append(dict(design=row['design'],label=row['label'],status='FAIL',error=str(e)))
            write(REPORT/'topology_equivalence.json',dict(status='PACT_PHASE2CR_TOPOLOGY_FAIL',rows=rows))
            raise
    assert len(rows)==21
    write(REPORT/'topology_equivalence.json',dict(status='PACT_PHASE2CR_TOPOLOGY_PASS',checked=21,passed=21,rows=rows))
    print('PACT_PHASE2CR_TOPOLOGY_PASS 21/21',flush=True)


def measure(freeze,loads):
    top=read(REPORT/'topology_equivalence.json')
    assert top['status']=='PACT_PHASE2CR_TOPOLOGY_PASS' and top['passed']==21
    oldrows={(r['design'],r['label']):r for r in read(B/'candidate_metrics.json')['rows']}
    proofs={(r['design'],r['label']):r for r in read(A/'shift_reconstruction.json')['rows']}
    rows=[]; deltas=[]; manifest=[]
    for row in freeze['architectures']:
        a,g,names,old,new,audit=load_case(row,loads); key=row['design'],row['label']
        proof=proofs[key]; check(proof['trace_path'],proof['trace_sha256'])
        trace=np.load(proof['trace_path']); assert trace['names'].tolist()==names
        q=read(A/'test_quality.json')[row['design']]
        xy={c.name:(c.x_um,c.y_um) for c in a.cells}
        bins=fixed_bins([xy[n] for n in names],q['die_bounds_um'])
        oldrow=oldrows[key]
        rec=dict(design=row['design'],label=row['label'],architecture_sha256=a.sha256(),
            predictors={},targets=deepcopy(oldrow['targets']))
        delta=deepcopy(next(r for r in top['rows'] if (r['design'],r['label'])==key)); delta['scores']={}; delta['affected_FF_weights']={}
        for m in ('M3_load','M5_hpwl'):
            # Reproduce historical scores with the unchanged evaluator before comparison.
            os,counts=score_packed(trace['toggles_packed'],len(names),old[m],bins)
            ns,ncounts=score_packed(trace['toggles_packed'],len(names),new[m],bins)
            assert counts.tolist()==[proof['FF_transition_totals'][n] for n in names]
            np.testing.assert_array_equal(counts,ncounts)
            for suffix,k in (('','total'),('_local','local_peak')):
                metric=m+suffix
                assert os[k]==oldrow['predictors'][metric], 'Historical score reproduction differs'
                rec['predictors'][metric]=ns[k]
                delta['scores'][metric]=dict(old=os[k],corrected=ns[k],delta=ns[k]-os[k],
                    absolute_delta=abs(ns[k]-os[k]),relative_delta=(ns[k]-os[k])/os[k] if os[k] else None)
        for n in delta['changed_FFs']:
            i=names.index(n)
            delta['affected_FF_weights'][n]={m:dict(old=float(old[m][i]),corrected=float(new[m][i]),delta=float(new[m][i]-old[m][i])) for m in new}
        path=REPORT/'weights'/f'{a.sha256()}.json'
        write(path,{m:dict(zip(names,map(float,w))) for m,w in new.items()})
        manifest.append(dict(design=row['design'],label=row['label'],architecture_sha256=a.sha256(),
            scan_order_sha256=order_hash(a),path=str(path),sha256=sha(path),
            placed_graph_sha256=sha(REPORT/f"{row['design']}.placed_graph.json"),liberty_sha256=sha(LIB),
            predictor_api='phase2cr_loads.construct_weights(architecture, placed_graph, Liberty_loads)',
            coefficient_ff_per_um=.103981))
        rows.append(rec); deltas.append(delta)
        print('MEASURED',*key,flush=True)
    write(REPORT/'corrected_metrics.json',dict(rows=rows,targets_reused_exactly=True))
    write(REPORT/'metric_deltas.json',dict(rows=deltas))
    write(REPORT/'corrected_weights_manifest.json',dict(rows=manifest))


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('stage',choices=['witness','topology','measure'])
    args=parser.parse_args(); freeze=integrity(); loads=pin_loads(LIB.read_text())
    {'witness':witness,'topology':all_topology,'measure':measure}[args.stage](freeze,loads)
    integrity()

if __name__=='__main__': main()
