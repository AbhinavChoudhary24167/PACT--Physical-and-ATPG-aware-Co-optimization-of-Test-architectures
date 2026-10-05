"""OpenROAD-only, read-only proof for absent switched-net SPEF records."""
import argparse
import json
from pathlib import Path
import re
import sys
import odb

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from pact.activity.spef_evidence import binding,checked,name_map
from pact.analysis.phase2b_reference import parse_spef
from pact.analysis.phase2b_loads import pin_loads
from pact.scan.model import ScanArchitecture


def collect(source,inspection_db,reproduced_spef,output):
    source=Path(source)
    manifest=json.loads((source.parents[1]/'manifest.json').read_text())
    row=next(r for r in manifest['rows'] if r['design']==source.parent.name and r['role']==source.name)
    simulation=json.loads((source/'simulation_manifest.json').read_text())
    for item in simulation['inputs'].values():checked(item)
    checked(manifest['library'])
    checked(row['architecture'])
    mapping=json.loads((source/'net_mapping.json').read_text())
    spef=parse_spef((source/'extracted.spef').read_text())
    reproduced=parse_spef(Path(reproduced_spef).read_text())
    if spef.keys()!=reproduced.keys() or any(spef[n]!=reproduced[n] for n in spef):
        raise ValueError('Frozen extraction reproducer changed extracted net capacitances')
    loads=pin_loads(Path(manifest['library']['path']).read_text())
    logical=(source/'routed.v').read_text()
    db=odb.dbDatabase.create(); odb.read_db(db,str(inspection_db)); block=db.getChip().getBlock()
    original_db=odb.dbDatabase.create(); odb.read_db(original_db,str(source/'routed.odb'))
    original=original_db.getChip().getBlock()
    unit=block.getDbUnitsPerMicron()
    names=name_map((source/'extracted.spef').read_text())
    def term(t):
        inst=t.getInst(); pin=t.getMTerm().getName()
        return dict(id=inst.getName()+'/'+pin,instance=inst.getName(),master=inst.getMaster().getName(),
            pin=pin,direction=str(t.getIoType()),signal=str(t.getSigType()),
            location_um=[v/unit for v in inst.getLocation()],placement=str(inst.getPlacementStatus()),
            scan_pin_relevance=pin if pin in ('Q','QN','SI','SO') else None)
    def logical_connection(t,net):
        token=lambda s:r'\\?'+re.escape(s)+r'\s*'
        pattern=token(t['master'])+token(t['instance'])+r'\((.*?)\)\s*;'
        matches=re.findall(pattern,logical,re.S)
        return len(matches)==1 and len(re.findall(r'\.'+token(t['pin'])+r'\(\s*'+token(net)+r'\)',matches[0]))==1
    records={}
    for n in sorted(set(mapping['nets'])-set(spef)):
        net=block.findNet(n); old=original.findNet(n)
        e=dict(odb_net_present=net is not None,net_mapping_matches=False,
            logical_net_present=bool(re.search(r'\b(?:wire|input|output)\s+\\?'+re.escape(n)+r'\s*;',logical)))
        if not net or not old:records[n]=e;continue
        iterms=[term(t) for t in net.getITerms()]
        ports=[dict(id='PORT/'+t.getName(),direction=str(t.getIoType()),signal=str(t.getSigType())) for t in net.getBTerms()]
        drivers=[t for t in iterms if t['direction']=='OUTPUT']+[t for t in ports if t['direction']=='INPUT']
        sinks=[t for t in iterms if t['direction']=='INPUT']+[t for t in ports if t['direction']=='OUTPUT']
        known=all((t['master'],t['pin']) in loads for t in sinks if 'master' in t)
        pin=sum(loads[t['master'],t['pin']] for t in sinks if 'master' in t) if known else None
        old_terms=sorted(t.getInst().getName()+'/'+t.getMTerm().getName() for t in old.getITerms())
        old_ports=sorted(t.getName() for t in old.getBTerms())
        preserved=(old_terms==sorted(t['id'] for t in iterms) and old_ports==sorted(t.getName() for t in net.getBTerms())
            and (old.getWire() is None)==(net.getWire() is None)
            and (old.getWire().getLength() if old.getWire() else 0)==(net.getWire().getLength() if net.getWire() else 0))
        wire=net.getWire()
        capnodes=net.getCapNodeCount(); rsegs=net.getRSegCount(); coupling=net.getCcCount()
        geometry=wire is not None or bool(net.getSWires()) or net.getGlobalWire() is not None
        logical_ok=all(logical_connection(t,n) for t in iterms) and not ports
        # This conservative patch proves dangling, one-terminal nets only.
        # Connected sinks lacking geometry remain unresolved.
        e.update(driver=drivers[0] if len(drivers)==1 else None,driver_count=len(drivers),sinks=sinks,
            sink_count=len(sinks),terminal_count=len(iterms)+len(ports),iterms=iterms,ports=ports,
            pin_cap_known=known,pin_cap_ff=pin,logical_connection_matches=logical_ok,
            net_mapping_matches=preserved and len(drivers)==1 and drivers[0]['id']==mapping['nets'][n]['source'],
            topology_valid=preserved and all(t['direction'] in ('INPUT','OUTPUT') and t['signal']=='SIGNAL' for t in iterms+ports),
            routing_status='NO_INTERCONNECT_ONE_TERMINAL' if not geometry and len(iterms)+len(ports)==1 else 'GEOMETRY_PRESENT_OR_CONNECTIVITY_UNRESOLVED',
            wire_present=wire is not None,wire_geometry_present=geometry,
            wire_length_um=wire.getLength()/unit if wire else 0.,wire_segments=0 if not wire else 'PRESENT',
            special_wire_count=len(net.getSWires()),global_wire_present=net.getGlobalWire() is not None,
            special_net=net.isSpecial(),cap_node_count=capnodes,rseg_count=rsegs,coupling_segment_count=coupling,
            odb_parasitic_available=bool(capnodes or rsegs or coupling),
            extractor_expected_omission=n not in reproduced and capnodes==rsegs==coupling==0,
            preserved_geometry_and_terminals=preserved,spef_name_map_present=n in names.values())
        if drivers and 'instance' in drivers[0]:
            driver=next(iter(net.getITerms())) if len(net.getITerms())==1 else None
            trace=[]; seen=set()
            current=driver
            while current and current.getInst().getName() not in seen:
                inst=current.getInst(); seen.add(inst.getName()); trace.append(term(current))
                if not inst.getMaster().getName().startswith(('BUF_X','CLKBUF_X','INV_X')):break
                inp=inst.findITerm('A')
                upstream=[t for t in inp.getNet().getITerms() if str(t.getIoType())=='OUTPUT'] if inp and inp.getNet() else []
                current=upstream[0] if len(upstream)==1 else None
            e['upstream_scan_relationship']=trace
        records[n]=e
    report=dict(schema='pact_missing_spef_implementation_evidence_v1',design=row['design'],
        architecture=ScanArchitecture.from_json(Path(row['architecture']['path'])).sha256(),nets=records,
        bindings=dict(mapping=binding(source/'net_mapping.json'),SPEF=binding(source/'extracted.spef'),
            original_ODB=binding(source/'routed.odb'),inspection_ODB=binding(inspection_db),
            reproduced_SPEF=binding(reproduced_spef),logical_netlist=binding(source/'routed.v'),
            library=binding(manifest['library']['path']),architecture=binding(row['architecture']['path']),
            exporter=binding(__file__),OpenROAD=binding('/usr/bin/openroad')),
        all_existing_extracted_capacitances_reproduced_exactly=True,
        static_or_switched_omission_population=len(records),operation='Read only two ODBs; original inputs unchanged')
    output=Path(output); output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as f:json.dump(report,f,indent=2,sort_keys=True)
    print('MISSING_SPEF_IMPLEMENTATION_EVIDENCE',row['design'],len(records))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--inspection-db',type=Path,required=True)
    p.add_argument('--reproduced-spef',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();collect(a.source,a.inspection_db,a.reproduced_spef,a.output)
