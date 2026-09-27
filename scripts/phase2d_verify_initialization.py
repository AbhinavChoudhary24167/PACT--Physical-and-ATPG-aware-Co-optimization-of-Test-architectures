"""Independent read-only witness that scratch initialization changes only movable placement."""
from phase2d_common import *
import odb
import random

def rect(r):return [r.xMin(),r.yMin(),r.xMax(),r.yMax()]

def topology(block):
    return dict(instances=sorted((i.getName(),i.getMaster().getName(),str(i.getOrient()),i.isFixed()) for i in block.getInsts()),
        nets=sorted((n.getName(),str(n.getSigType()),
            sorted((t.getInst().getName(),t.getMTerm().getName()) for t in n.getITerms()),
            sorted(t.getName() for t in n.getBTerms())) for n in block.getNets()),
        ports=sorted((t.getName(),str(t.getIoType()),str(t.getSigType()),rect(t.getBBox())) for t in block.getBTerms()),
        die=rect(block.getDieArea()),core=rect(block.getCoreArea()),
        rows=sorted((r.getName(),r.getSite().getName(),rect(r.getBBox())) for r in block.getRows()))

def main():
    assert not (OUT/'initialization_equivalence.json').exists()
    rows=[]
    for d in DESIGNS:
        witness=read(OUT/'initialization'/f'{d}.json')
        assert sha(witness['source'])==witness['source_sha256']
        assert sha(witness['output'])==witness['output_sha256']
        before=odb.dbDatabase.create();after=odb.dbDatabase.create()
        odb.read_db(before,witness['source']);odb.read_db(after,witness['output'])
        b=before.getChip().getBlock();a=after.getChip().getBlock()
        assert topology(b)==topology(a),'Initialization changed netlist/floorplan/orientation/IO geometry'
        rng=random.Random(SEED);core=b.getCoreArea();expected=[];fixed=0
        for i in sorted(b.getInsts(),key=lambda i:i.getName()):
            j=a.findInst(i.getName())
            if i.isFixed():
                assert i.getLocation()==j.getLocation() and i.getPlacementStatus()==j.getPlacementStatus()
                fixed+=1;continue
            assert str(i.getPlacementStatus()) in ('NONE','UNPLACED')
            x=rng.randrange(core.xMin(),core.xMax()-i.getMaster().getWidth()+1)
            y=rng.randrange(core.yMin(),core.yMax()-i.getMaster().getHeight()+1)
            assert tuple(j.getLocation())==(x,y) and str(j.getPlacementStatus())=='PLACED'
            expected.append(dict(name=i.getName(),xy=[x,y]))
        assert expected==witness['initial_coordinates']
        rows.append(dict(design=d,status='PASS',scratch_coordinates_reproduced=len(expected),fixed_instances_unchanged=fixed,
            netlist_connectivity_equal=True,instance_master_orientation_equal=True,rows_die_core_equal=True,port_geometry_equal=True,
            all_original_movable_instances_unplaced=True,source_sha256=witness['source_sha256'],initialized_sha256=witness['output_sha256']))
        odb.dbDatabase.destroy(before);odb.dbDatabase.destroy(after)
    write(OUT/'initialization_equivalence.json',dict(status='PASS',utc=now(),rows=rows,script_sha256=sha(__file__),scientific_scores_observed=False))
    print('INITIALIZATION_EQUIVALENCE_PASS',flush=True)

if __name__=='__main__':main()
