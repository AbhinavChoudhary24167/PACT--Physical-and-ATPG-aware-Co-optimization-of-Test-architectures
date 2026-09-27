"""OpenROAD adapter reusing the frozen Phase-2A/B extraction functions."""
from phase2c_common import *
import argparse
import odb
from pact.scan.model import ScanArchitecture
from pact.physical.phase0d_routed import verify_routed
from phase2b_extract import placed_graph
from phase2a_extract_odb import extract
from phase0c_rewire_odb import fingerprint
from pact.analysis.phase2b_loads import pin_loads
from pact.analysis.phase2b_reference import parse_spef

def prepare(d,s):
    folder=WORK/d/f's{s}';folder.mkdir(parents=True,exist_ok=True)
    template=ScanArchitecture.from_json(ROOT/f'artifacts/derived/phase0c/{d}/s{s}/k2/P.architecture.json')
    db=odb.dbDatabase.create();odb.read_db(db,str(base(d,s)/'3_place.odb'))
    block=db.getChip().getBlock();units=block.getDbUnitsPerMicron()
    for c in template.cells:
        assert tuple(v/units for v in block.findInst(c.name).getLocation()) == (c.x_um,c.y_um)
    # Independent source ODB versus frozen DEF check for ALL instances/connectivity.
    other=odb.dbDatabase.create()
    odb.read_lef(other,str(PLATFORM/'lef/NangateOpenCellLibrary.tech.lef'))
    odb.read_lef(other,str(PLATFORM/'lef/NangateOpenCellLibrary.macro.mod.lef'))
    odb.read_def(other.getTech(),str(placed_def(d,s)))
    assert fingerprint(block)==fingerprint(other.getChip().getBlock())
    die=block.getDieArea()
    info=dict(design=d,seed=s,placed_instance_count=len(block.getInsts()),
              bounds=[v/units for v in (die.xMin(),die.yMin(),die.xMax(),die.yMax())],
              source_odb_def_fingerprint_equal=True)
    odb.dbDatabase.destroy(db);odb.dbDatabase.destroy(other)
    graph,elapsed=placed_graph(placed_def(d,s),[c.name for c in template.cells])
    write(folder/'placed_graph.json',graph)
    jobs=[]
    for row in read(REPORT/'architecture_set.json'):
        if row['design']!=d:continue
        old=ScanArchitecture.from_json(Path(row['architecture_path']))
        assert set(c.name for c in old.cells)==set(c.name for c in template.cells)
        arch=ScanArchitecture(template.cells,old.chains)
        assert order_hash(arch)==row['scan_order_sha256']
        names=[n for ch in arch.chains for n in ch.cells]
        assert len(names)==len(set(names))==len(arch.cells)
        out=folder/row['label'];out.mkdir(exist_ok=True)
        arch.to_json(out/'architecture.json')
        jobs.append(dict(design=d,seed=s,label=row['label'],original_architecture_sha256=old.sha256(),
            architecture_sha256=arch.sha256(),scan_order_sha256=order_hash(arch),
            architecture_path=str(out/'architecture.json'),FF_bijection=True,K=len(arch.chains)))
    write(folder/'prepared.json',dict(**info,graph_seconds=elapsed,jobs=jobs,
        inputs={str(p):file_sha256(p) for p in (base(d,s)/'3_place.odb',placed_def(d,s))},
        graph_sha256=file_sha256(folder/'placed_graph.json')))

def reference(jobpath):
    job=read(jobpath);folder=Path(jobpath).parent
    arch=Path(job['architecture_path']);routed=Path(job['routed_path'])
    proof=verify_routed(routed,arch,placed_def(job['design'],job['seed']))
    assert proof['status']=='PASS'
    db=odb.dbDatabase.create();odb.read_db(db,str(routed));block=db.getChip().getBlock()
    phy=extract(block,read(arch));write(folder/'physical.json',phy)
    loads=pin_loads(LIB.read_text());nets=parse_spef((folder/'extracted.spef').read_text())
    assert not set(phy['nets'])-set(nets)
    assert sum(n['resistors'] for n in nets.values())>0 and sum(n['capacitors'] for n in nets.values())>0
    pins={n:sum(loads[t.getInst().getMaster().getName(),t.getMTerm().getName()]
                for t in block.findNet(n).getITerms() if str(t.getIoType())=='INPUT') for n in phy['nets']}
    weights={}
    for n,f in phy['FFs'].items():
        ground=sum(nets[k]['ground_ff'] for k in f['nets'])
        coupling=sum(nets[k]['coupling_ff'] for k in f['nets'])
        pin=sum(pins[k] for k in f['nets']);assert ground+coupling>0
        weights[n]=dict(ground_ff=ground,coupling_ff=coupling,pin_ff=pin,
                       effective_ff=ground+coupling+pin,ground_pin_ff=ground+pin)
    write(folder/'reference_weights.json',weights)
    write(folder/'extraction.json',dict(status='QUALIFIED',proof=proof,routed_nets=len(block.getNets()),
        FF_nets=len(phy['nets']),extracted_nets=len(nets),physical_summary=phy['summary'],
        inputs={str(p):file_sha256(p) for p in (routed,arch,folder/'extracted.spef',LIB,RULES)},
        outputs={str(p):file_sha256(p) for p in (folder/'reference_weights.json',folder/'physical.json')}))
    odb.dbDatabase.destroy(db)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','reference'])
    parser.add_argument('--design');parser.add_argument('--seed',type=int);parser.add_argument('--job',type=Path)
    args=parser.parse_args()
    if args.stage=='prepare':prepare(args.design,args.seed)
    else:reference(args.job)
