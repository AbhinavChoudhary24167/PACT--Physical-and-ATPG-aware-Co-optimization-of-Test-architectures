"""Register one seeded, from-scratch initialization per design before physical outcomes."""
from phase2d_common import *
from collections import Counter
from pact.scan.model import ScanArchitecture
from phase2cr_common import order_hash
import numpy as np

def main():
    assert not (OUT/'contract.json').exists()
    initial=read(OUT/'initial_integrity.json')
    assert not initial['failures'] and not initial['conflicts']
    old=read(PRIOR/'multiseed_contract.json')
    cells=[dict(c) for c in old['cells'] if c['seed']==11]
    assert Counter(c['design'] for c in cells)==dict(s5378=9,s9234=6,s15850=6)
    frozen={str(PRIOR/'multiseed_contract.json'):sha(PRIOR/'multiseed_contract.json')}
    traces=read(ROOT/'reports/phase2a_shift_activity/shift_reconstruction.json')['rows']
    q=read(ROOT/'reports/phase2a_shift_activity/test_quality.json')
    for c in cells:
        a=ScanArchitecture.from_json(Path(c['architecture_path']))
        assert a.sha256()==c['architecture_sha256'] and order_hash(a)==c['scan_order_sha256']
        names=sorted(x.name for x in a.cells)
        flat=[n for chain in a.chains for n in chain.cells]
        assert sorted(flat)==names and len(set(flat))==len(names) and len(a.chains)==2
        tr=next(r for r in traces if (r['design'],r['label'])==(c['design'],c['label']))
        assert sha(tr['trace_path'])==tr['trace_sha256']
        with np.load(tr['trace_path']) as t:
            assert t['names'].tolist()==names
            assert np.unpackbits(t['toggles_packed'],axis=1)[:,:len(names)].sum(axis=0).tolist()==[tr['FF_transition_totals'][n] for n in names]
        c.update(frozen_architecture_id=a.sha256(),ff_names=names,
                 chains=[dict(chain_id=x.chain_id,cells=list(x.cells),scan_in=x.scan_in,scan_out=x.scan_out) for x in a.chains],
                 trace_path=tr['trace_path'],trace_sha256=tr['trace_sha256'],trace_mapping_verified=True)
        for p in (c['architecture_path'],tr['trace_path'],q[c['design']]['pattern_path'],q[c['design']]['identity_path']):
            frozen[str(p)]=sha(p)
    provenance=read(PRIOR/'result_provenance.json')
    frozen.update(provenance['sources'])
    for p in (ROOT/'src/pact/analysis/phase2b_scoring.py',ROOT/'src/pact/analysis/phase2a_shift.py',ROOT/'scripts/phase2b_report.py',ROOT/'scripts/phase2a_validate.py'):
        frozen[str(p)]=sha(p)
    sources={}
    for d in DESIGNS:
        paths=[source(d)/n for n in ('1_2_yosys.v','2_floorplan.odb','2_floorplan.sdc')]
        paths += [config(d),config(d).parent/'constraint.sdc']
        sources[d]={str(p):sha(p) for p in paths}
        frozen.update(sources[d])
    for p in [PLATFORM/'lib/NangateOpenCellLibrary_typical.lib',PLATFORM/'rcx_patterns.rules',
              PLATFORM/'lef/NangateOpenCellLibrary.tech.lef',PLATFORM/'lef/NangateOpenCellLibrary.macro.mod.lef',
              FLOW/'scripts/global_place.tcl',FLOW/'scripts/global_place_skip_io.tcl',FLOW/'scripts/io_placement.tcl',
              ROOT/'scripts/phase2d_initialize.py',ROOT/'scripts/phase2d_gp_hook.tcl']:
        frozen[str(p)]=sha(p)
    contract=dict(registered_utc=now(),phase='PACT_PHASE2D',cells=cells,counts=dict(Counter(c['design'] for c in cells)),
        independent_gp_per_design=1,seed=SEED,new_exact_order_implementations_max=21,
        gates=old['gates'],endpoint_pairs=old['endpoint_pairs'],materiality=old['materiality'],
        predictor=old['predictor'],statistics=old['statistics'],frozen_files=frozen,pregp_sources=sources,
        initialization=dict(method='Fresh seeded uniform coordinates in the core for movable instances from the retained unplaced 2_floorplan.odb; no old placed database is read. Python random.Random(29), instances sorted by name, x/y sampled independently. This is initialization, not perturbation of any existing placement.',
            evidence='Reject pre-GP input if any movable instance is already placed. Record all original statuses, generated coordinates and hashes. Audit pre-GP against retained source flow commands.',
            global_placement='Same installed OpenROAD and ORFS placement constraints. GLOBAL_PLACEMENT_ARGS=-skip_initial_place; hook removes -force_center_initial_place so the fresh initialization is not discarded. Both skip-IO GP and final GP run normally from the new ancestry. No native random_seed support is claimed.',
            placements_tuned=False,one_attempt_per_design=True,timeout_seconds=600),
        routing=dict(flow='Exact qualified phase2c_run downstream route/extraction and repaired topology assertions; adapt source paths only.',seed=SEED,max_routes=21,one_attempt_per_architecture=True,timeout_seconds=600),
        identity='Retain frozen seed-11 architecture ID and order hash. Physical serialization hash changes with coordinates; never use it as a replacement logical architecture ID.',
        placement_dependent_inputs=['FF, functional sink, transparent-buffer and port coordinates','net HPWL and Manhattan distances','spatial bin membership in the fixed 10x10 grid'],
        placement_independent_inputs=['chain membership and order','packed toggle traces, test patterns and FF mapping','Liberty pin loads','0.103981 fF/um coefficient','10x10 bins and all 81 contained 2x2 windows','correlation, pair direction, tie rules and gates'],
        targets='Unchanged routed wire and extracted ground+coupling+pin capacitance weighted by frozen packed transitions; total and local peak use unchanged score_packed.',
        stop='Any independence, provenance, frozen hash, identity, topology, predictor, target or reproducibility failure stops scientific execution. Preserve attempts. No tuning, optimizer, ATPG, Phase-3 or push.',
        classification=dict(confirmed='Every one of 12 independent GP endpoints satisfies both original gates.',not_confirmed='Complete qualified experiment with at least one endpoint failure.',blocked='Required engineering/provenance/topology evidence unavailable or failed.'),
        scientific_outcomes_observed=False)
    write(OUT/'contract.json',contract)
    write(OUT/'contract_freeze.json',dict(utc=now(),contract_sha256=sha(OUT/'contract.json'),new_placements=0,new_routes=0,new_targets_observed=False))
    (OUT/'EXPERIMENT_CONTRACT.md').write_text('Phase-2D authoritative contract: contract.json; hash: '+sha(OUT/'contract.json')+'\n')
    print('REGISTERED',len(cells),sha(OUT/'contract.json'),flush=True)

if __name__=='__main__':main()
