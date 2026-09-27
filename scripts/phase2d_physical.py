"""Physical source adapter; frozen exporters and routed assertions remain unchanged."""
from phase2d_common import *
import odb
import math
from dataclasses import replace
from pact.scan.model import ScanArchitecture
from phase2cr_common import order_hash
from phase2b_extract import placed_graph
from phase2cr_extract import endpoint_from_def
from phase0c_rewire_odb import fingerprint

def defpath(d):return placement(d)/'placed.def'

def coordinates(block,names):
    u=block.getDbUnitsPerMicron()
    return {n:tuple(v/u for v in block.findInst(n).getLocation()) for n in names}

def hpwl(block):
    total=0
    for n in block.getNets():
        pts=[]
        for t in n.getITerms():
            xy=t.getAvgXY()
            if xy[0]:pts.append(xy[1:])
        for t in n.getBTerms():
            r=t.getBBox();pts.append(((r.xMin()+r.xMax())/2,(r.yMin()+r.yMax())/2))
        if pts:total+=max(p[0] for p in pts)-min(p[0] for p in pts)+max(p[1] for p in pts)-min(p[1] for p in pts)
    return total/block.getDbUnitsPerMicron()

def prepare():
    contract=read(OUT/'contract.json');comparisons=[];proofs=[]
    for d in DESIGNS:
        folder=placement(d);assert not defpath(d).exists()
        db=odb.dbDatabase.create();odb.read_db(db,str(folder/'3_place.odb'));b=db.getChip().getBlock()
        odb.write_def(b,str(defpath(d)))
        old=ScanArchitecture.from_json(Path(next(c['architecture_path'] for c in contract['cells'] if c['design']==d)))
        names=sorted(c.name for c in old.cells)
        observed=sorted(i.getName() for i in b.getInsts() if i.getMaster().getName().startswith('SDFF'))
        assert observed==names,'Frozen FF membership changed'
        xy=coordinates(b,names)
        graph,_=placed_graph(defpath(d),names);ep,ports=endpoint_from_def(defpath(d),graph,2)
        write(OUT/'graphs'/f'{d}.s29.json',dict(graph,scan_endpoints={'chain0_so':ep},scan_ports=ports))
        other=odb.dbDatabase.create()
        for leaf in ('NangateOpenCellLibrary.tech.lef','NangateOpenCellLibrary.macro.mod.lef'):
            odb.read_lef(other,str(PLATFORM/'lef'/leaf))
        odb.read_def(other.getTech(),str(defpath(d)))
        assert fingerprint(b)==fingerprint(other.getChip().getBlock())
        # Reference database used solely AFTER independent GP, for descriptive comparison.
        olddef=ROOT/f'artifacts/raw/phase0b/placements/{d}/s11/placed.def'
        ref=odb.dbDatabase.create()
        for leaf in ('NangateOpenCellLibrary.tech.lef','NangateOpenCellLibrary.macro.mod.lef'):
            odb.read_lef(ref,str(PLATFORM/'lef'/leaf))
        odb.read_def(ref.getTech(),str(olddef));rb=ref.getChip().getBlock();oldxy=coordinates(rb,names)
        distances=sorted(math.dist(xy[n],oldxy[n]) for n in names)
        assert any(v>0 for v in distances),'Independent placement coordinates identical'
        core=b.getCoreArea();corearea=core.dx()*core.dy()
        comparisons.append(dict(design=d,ff_count=len(names),identical_ff_coordinates=sum(xy[n]==oldxy[n] for n in names),
            coordinate_identity=False,min_displacement_um=min(distances),mean_displacement_um=sum(distances)/len(names),
            median_displacement_um=(distances[(len(names)-1)//2]+distances[len(names)//2])/2,max_displacement_um=max(distances),
            p95_displacement_um=distances[math.ceil(.95*len(names))-1],phase2c_seed11_hpwl_um=hpwl(rb),independent_hpwl_um=hpwl(b),
            cell_area_over_core=sum(i.getMaster().getWidth()*i.getMaster().getHeight() for i in b.getInsts())/corearea,
            congestion='See retained ORFS global-placement metrics/logs; no qualification gate applied'))
        jobs=[]
        for c in contract['cells']:
            if c['design']!=d:continue
            a=ScanArchitecture.from_json(Path(c['architecture_path']))
            arch=ScanArchitecture(tuple(replace(cell,x_um=xy[cell.name][0],y_um=xy[cell.name][1]) for cell in a.cells),a.chains)
            assert order_hash(arch)==c['scan_order_sha256']
            ap=OUT/'raw'/d/'s29'/c['label']/'architecture.json';assert not ap.exists();arch.to_json(ap)
            jobs.append(dict(design=d,seed=29,label=c['label'],frozen_architecture_id=c['frozen_architecture_id'],
                original_architecture_sha256=c['frozen_architecture_id'],architecture_sha256=arch.sha256(),
                scan_order_sha256=order_hash(arch),architecture_path=str(ap),FF_bijection=True,K=2))
        u=b.getDbUnitsPerMicron();die=b.getDieArea()
        write(OUT/'raw'/d/'s29'/'prepared.json',dict(jobs=jobs,bounds=[v/u for v in (die.xMin(),die.yMin(),die.xMax(),die.yMax())]))
        proofs.append(dict(design=d,independent=True,initialization=read(OUT/'initialization'/f'{d}.json'),
            gp_execution=read(OUT/'execution'/('gp_'+d)/'result.json'),source_placed_database_used=False,
            placed_odb=str(folder/'3_place.odb'),placed_odb_sha256=sha(folder/'3_place.odb'),placed_def=str(defpath(d)),placed_def_sha256=sha(defpath(d)),
            frozen_ff_membership=True,odb_def_fingerprint_equal=True,comparison_reference=str(olddef),
            comparison_reference_sha256=sha(olddef),reference_read_only_after_gp=True,
            changed_ff_coordinates=sum(xy[n]!=oldxy[n] for n in names)))
        write(OUT/'independent_placement_proof.json',dict(status='PASS' if len(proofs)==3 else 'IN_PROGRESS',rows=proofs))
        for item in (db,other,ref):odb.dbDatabase.destroy(item)
        print('PREPARED_INDEPENDENT',d,len(jobs),flush=True)
    import csv
    with (OUT/'placement_comparison.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(comparisons[0]));w.writeheader();w.writerows(comparisons)

def reference(path):
    import phase2c_physical as frozen
    frozen.placed_def=lambda d,s:defpath(d)
    frozen.reference(Path(path))

if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='reference':reference(sys.argv[sys.argv.index('--job')+1])
