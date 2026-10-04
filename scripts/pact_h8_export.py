"""Read-only export of saved routed ODBs; does not route, extract, or simulate."""
import json
import gzip
import sys
from pathlib import Path
import odb

root = Path(__file__).resolve().parents[1]
out = Path(sys.argv[-1]).resolve()
index = json.loads((out/'evidence_index.json').read_text())
def local(value):
    value = str(value).replace('\\','/')
    return str(root/value.split('/PACT/PACT/',1)[1]) if '/PACT/PACT/' in value else value
if '--inspect' in sys.argv:
    db = odb.dbDatabase.create()
    odb.read_db(db, local(index['architectures'][0]['folder'])+'/routed.odb')
    block = db.getChip().getBlock()
    wire = next(n.getWire() for n in block.getNets() if n.getWire())
    print('WIRE_API', [x for x in dir(wire) if any(s in x.lower() for s in ('shape','box','length'))])
    print('SHAPE_API', [x for x in dir(odb) if 'WireShape' in x or x == 'dbShape'])
    decoder=odb.dbWireDecoder()
    print('DECODER_API',dir(decoder))
    decoder.begin(wire)
    for _ in range(10):
        op=decoder.next()
        print('OP',op, type(op))
        if op in (decoder.POINT,decoder.POINT_EXT):
            print('POINT',decoder.getPoint())
    sys.exit(0)

for entry in index['architectures']:
    target = out/entry['design']/entry['architecture_sha256']
    target.mkdir(parents=True, exist_ok=True)
    db = odb.dbDatabase.create()
    odb.read_db(db, local(entry['folder'])+'/routed.odb')
    block = db.getChip().getBlock()
    unit = block.getDbUnitsPerMicron()
    cells = {}
    for inst in block.getInsts():
        cells[inst.getName()] = dict(master=inst.getMaster().getName(),
            xy=[v/unit for v in inst.getLocation()],
            inputs={t.getMTerm().getName(): t.getNet().getName() for t in inst.getITerms()
                    if t.getNet() and str(t.getIoType()) == 'INPUT' and str(t.getSigType()) not in ('POWER','GROUND')},
            outputs={t.getMTerm().getName(): t.getNet().getName() for t in inst.getITerms()
                     if t.getNet() and str(t.getIoType()) == 'OUTPUT'})
    nets = {}
    for net in block.getNets():
        if str(net.getSigType()) in ('POWER','GROUND'):
            continue
        sinks = [dict(id=t.getInst().getName()+'/'+t.getMTerm().getName(),
                      xy=cells[t.getInst().getName()]['xy']) for t in net.getITerms()
                 if str(t.getIoType()) == 'INPUT']
        ports = []
        for term in net.getBTerms():
            if str(term.getIoType()) == 'OUTPUT':
                box = term.getBBox()
                ports.append(dict(id='PORT/'+term.getName(), xy=[(box.xMin()+box.xMax())/2/unit,
                                                                 (box.yMin()+box.yMax())/2/unit]))
        wire = net.getWire()
        points, segments = [], []
        if wire:
            decoder=odb.dbWireDecoder()
            decoder.begin(wire)
            last=None
            junctions={}
            while True:
                op=decoder.next()
                if op==decoder.END_DECODE:
                    break
                if op==decoder.PATH:
                    last=None
                elif op==decoder.JUNCTION:
                    last=junctions.get(decoder.getJunctionValue())
                elif op in (decoder.SHORT,decoder.VWIRE):
                    last=None
                elif op in (decoder.POINT,decoder.POINT_EXT):
                    xy=[v/unit for v in decoder.getPoint()]
                    points.append(xy)
                    if last is not None and xy!=last:
                        segments.append([*last,*xy])
                    last=xy
                    junctions[decoder.getJunctionId()]=xy
        nets[net.getName()] = dict(sinks=sorted(sinks, key=lambda t:t['id']),
            ports=sorted(ports, key=lambda t:t['id']), routed_length_um=wire.getLength()/unit if wire else None,
            route_points_um=sorted(set(tuple(p) for p in points)),route_segments_um=segments,
            decoded_segment_length_um=sum(abs(s[0]-s[2])+abs(s[1]-s[3]) for s in segments))
    result = dict(provenance=entry['provenance'], cells=cells, nets=nets,
        operation='read_db and inspect only; no database writes or physical runs')
    with (target/'routed_topology.json.gz').open('wb') as stream:
        with gzip.GzipFile(fileobj=stream,mode='wb',filename='',mtime=0) as archive:
            archive.write((json.dumps(result,sort_keys=True,indent=2)+'\n').encode())
    print('EXPORTED', entry['design'], entry['architecture'], flush=True)
