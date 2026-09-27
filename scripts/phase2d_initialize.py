"""OpenDB-only fresh initialization: never reads an existing placed database."""
from phase2d_common import *
import odb
import random
from collections import Counter

def main(design):
    verify_contract()
    folder=placement(design);folder.mkdir(parents=True,exist_ok=True)
    assert not (folder/'2_floorplan.odb').exists()
    path=source(design)/'2_floorplan.odb'
    db=odb.dbDatabase.create();odb.read_db(db,str(path));block=db.getChip().getBlock()
    core=block.getCoreArea();rng=random.Random(SEED)
    movable=sorted((i for i in block.getInsts() if not i.isFixed()),key=lambda i:i.getName())
    statuses=Counter(str(i.getPlacementStatus()) for i in movable)
    proof=dict(design=design,utc=now(),source=str(path),source_sha256=sha(path),seed=SEED,
               core=[core.xMin(),core.yMin(),core.xMax(),core.yMax()],movable_status_counts=dict(statuses),
               old_placed_database_read=False,random_engine='Python random.Random',initial_coordinates=[])
    if any(str(i.getPlacementStatus()) not in ('NONE','UNPLACED') for i in movable):
        proof.update(status='STOP',reason='Pre-GP movable instances already have placed status; cannot prove fresh initialization')
        write(OUT/'initialization'/f'{design}.json',proof)
        raise RuntimeError(proof['reason'])
    for i in movable:
        master=i.getMaster()
        x=rng.randrange(core.xMin(),core.xMax()-master.getWidth()+1)
        y=rng.randrange(core.yMin(),core.yMax()-master.getHeight()+1)
        i.setLocation(x,y);i.setPlacementStatus('PLACED')
        proof['initial_coordinates'].append(dict(name=i.getName(),xy=[x,y]))
    odb.write_db(db,str(folder/'2_floorplan.odb'))
    proof.update(status='PASS',initialization_only=True,output=str(folder/'2_floorplan.odb'),output_sha256=sha(folder/'2_floorplan.odb'))
    write(OUT/'initialization'/f'{design}.json',proof)
    print('FRESH_INITIALIZATION',design,len(movable),flush=True)

if __name__=='__main__':main(sys.argv[1])
