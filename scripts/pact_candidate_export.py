"""Read-only topology export from the already qualified baseline ODB (OpenROAD)."""
import sys
from pathlib import Path
import odb
from physical_effect import ROOT, LIB, read, write, bind
from pact.analysis.phase2b_loads import pin_loads, liberty_groups
import re


def export(design, output):
    role = {'s5378': 'P', 's9234': 'T', 's15850': 'P'}[design]
    folder = ROOT/'reports/physical_effect'/design/role
    mapping = read(folder/'net_mapping.json')
    db = odb.dbDatabase.create()
    odb.read_db(db, str(folder/'routed.odb'))
    block = db.getChip().getBlock()
    unit = block.getDbUnitsPerMicron()
    loads = pin_loads(LIB.read_text())
    functions = {}
    for master, body in liberty_groups(LIB.read_text(), 'cell'):
        if re.search(r'\b(ff|latch)\s*\(', body):
            continue
        for pin, data in liberty_groups(body, 'pin'):
            match = re.search(r'\bfunction\s*:\s*"([^"]+)"', data)
            if match:
                functions[master+'/'+pin] = match[1]
    cells, nets = {}, {}
    for inst in block.getInsts():
        master = inst.getMaster().getName()
        cells[inst.getName()] = dict(master=master, xy=[v/unit for v in inst.getLocation()],
            transparent=master.startswith(('BUF_X', 'CLKBUF_X', 'INV_X')),
            inputs={t.getMTerm().getName(): t.getNet().getName() for t in inst.getITerms()
                    if t.getNet() and str(t.getIoType()) == 'INPUT' and str(t.getSigType()) not in ('POWER', 'GROUND')},
            outputs={t.getMTerm().getName(): t.getNet().getName() for t in inst.getITerms()
                     if t.getNet() and str(t.getIoType()) == 'OUTPUT'})
    for name, info in mapping['nets'].items():
        net = block.findNet(name)
        sinks = []
        for t in net.getITerms():
            if str(t.getIoType()) != 'INPUT':
                continue
            inst, pin = t.getInst(), t.getMTerm().getName()
            sinks.append(dict(cell=inst.getName(), pin=pin, cap=loads[inst.getMaster().getName(), pin],
                              xy=cells[inst.getName()]['xy']))
        ports = []
        for t in net.getBTerms():
            if str(t.getIoType()) == 'OUTPUT':
                box = t.getBBox()
                ports.append(dict(name=t.getName(), xy=[(box.xMin()+box.xMax())/2/unit,
                                                       (box.yMin()+box.yMax())/2/unit]))
        nets[name] = dict(source=info['source'], xy=info['xy_um'], sinks=sinks, ports=ports)
    write(output, dict(cells=cells, nets=nets, functions=functions, bounds=mapping['bounds_um'],
        inputs={k: bind(p) for k, p in dict(odb=folder/'routed.odb', liberty=LIB,
                mapping=folder/'net_mapping.json', caps=folder/'net_activity_capacitance.csv').items()}))


if __name__ == '__main__':
    export(sys.argv[-2], Path(sys.argv[-1]))
