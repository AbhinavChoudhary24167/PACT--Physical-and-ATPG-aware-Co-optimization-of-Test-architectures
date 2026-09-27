"""Read-only OpenROAD reproducer for the inherited scan-output ownership bug.

This does not construct a corrected metric or rerun any physical stage.
"""
from phase2c_common import *
import odb
from datetime import datetime,timezone
from pact.scan.model import ScanArchitecture
from pact.analysis.phase2b_loads import pin_loads

def main():
    records=[];loads=pin_loads(LIB.read_text())
    architectures=read(OLD/'architecture_set.json')
    physical=read(A/'physical_weighting.json')['rows']
    for d in DESIGNS:
        db=odb.dbDatabase.create();source=base(d,11)/'3_place.odb';odb.read_db(db,str(source))
        block=db.getChip().getBlock();port=block.findBTerm('test_so')
        driver=[t for t in port.getNet().getITerms() if str(t.getIoType())=='OUTPUT']
        assert len(driver)==1
        buffer=driver[0].getInst();net=buffer.findITerm('A').getNet()
        source_driver=[t for t in net.getITerms() if str(t.getIoType())=='OUTPUT']
        assert len(source_driver)==1
        old_owner=source_driver[0].getInst().getName()
        graph_path=Path('/mnt/d/PACT_EXPERIMENTS/results/phase2b_activity_model')/(d+'.placed_graph.json')
        graph=read(graph_path);buffer_xy=[v/block.getDbUnitsPerMicron() for v in buffer.getLocation()]
        sink=dict(master=buffer.getMaster().getName(),pin='A',xy=buffer_xy)
        assert sink in graph['nets'][net.getName()]['sinks']
        assert port.getNet().getName() in graph['transparent'][net.getName()]
        affected=[]
        for row in architectures:
            if row['design']!=d:continue
            arch=ScanArchitecture.from_json(Path(row['architecture_path']))
            tail=arch.chains[0].cells[-1]
            phyrec=next(r for r in physical if r['design']==d and r['label']==row['label'])
            phy=read(phyrec['physical_path'])
            owners=[n for n,f in phy['FFs'].items() if any(x['instance']==buffer.getName() for x in f['transparent_branches'])]
            assert owners==[tail]
            affected.append(dict(label=row['label'],architecture_sha256=row['architecture_sha256'],
                frozen_predictor_buffer_owner=old_owner,selected_chain0_tail=tail,routed_buffer_owner=owners[0],
                ownership_mismatch=old_owner!=tail,
                routed_physical_path=phyrec['physical_path'],routed_physical_sha256=file_sha256(Path(phyrec['physical_path']))))
        records.append(dict(design=d,source_odb=str(source),source_sha256=file_sha256(source),
            frozen_graph_path=str(graph_path),frozen_graph_sha256=file_sha256(graph_path),
            output_buffer=buffer.getName(),buffer_master=buffer.getMaster().getName(),buffer_xy_um=buffer_xy,
            buffer_input_pin_cap_ff=loads[buffer.getMaster().getName(),'A'],
            original_source_net=net.getName(),original_source_FF=old_owner,
            retained_graph_sink=sink,retained_transparent_child=port.getNet().getName(),
            selected_architectures=affected))
        odb.dbDatabase.destroy(db)
    write(REPORT/'legacy_bug_audit.json',dict(status='CONFIRMED_LEGACY_DEFINITION_BUG',
        observed_utc=datetime.now(timezone.utc).isoformat(),rows=records,
        mismatching_architectures=sum(r['ownership_mismatch'] for d in records for r in d['selected_architectures']),
        checked_architectures=21,
        cause='placed_graph omits test_so BTerms but retains the original output BUF input sink and transparent branch. construct_weights adds a direct tail-to-SO geometry endpoint without moving that BUF input load/branch to chain0 tail. Actual frozen rewire moves the buffer A connection.',
        scientific_consequence='M3 pin load and M5 owned-tree geometry are not the declared selected-architecture SI/SO graph. Numerical reproduction and event/packed equivalence can still pass because both evaluators use the same frozen erroneous weights.',
        stop_rule='User section 1 and Phase-2C contract K: stop and document an inherited definition bug before changing the experiment.',
        changes_to_frozen_definitions=False,corrected_metrics_computed=False,
        source_hashes={str(ROOT/p):file_sha256(ROOT/p) for p in ['scripts/phase2b_extract.py','src/pact/analysis/phase2b_loads.py','scripts/phase0c_rewire_odb.py']}))
    print('CONFIRMED',sum(r['ownership_mismatch'] for d in records for r in d['selected_architectures']),'of 21 frozen architectures')

if __name__=='__main__':main()
