#!/usr/bin/env python3
"""Run with OpenROAD Python: placed-only graph export and exact-route RC extraction."""
from phase2b_common import *
import gzip
import shutil
import subprocess
import time
import re
import odb
from pact.analysis.phase2b_loads import pin_loads
from pact.analysis.phase2b_reference import parse_spef


def placed_graph(path, names):
    start = time.perf_counter()
    db = odb.dbDatabase.create()
    odb.read_lef(db, str(PLATFORM/'lef/NangateOpenCellLibrary.tech.lef'))
    odb.read_lef(db, str(PLATFORM/'lef/NangateOpenCellLibrary.macro.mod.lef'))
    odb.read_def(db.getTech(), str(path))
    block = db.getChip().getBlock()
    units = block.getDbUnitsPerMicron()
    def xy(inst): return [v/units for v in inst.getLocation()]
    ff = {n:block.findInst(n) for n in names}
    roots = {n:dict(master=i.getMaster().getName(),roots={p:i.findITerm(p).getNet().getName()
                  for p in ('Q','QN') if i.findITerm(p) and i.findITerm(p).getNet()}) for n,i in ff.items()}
    transparent = {}
    for inst in block.getInsts():
        master = inst.getMaster().getName()
        if master.startswith(('BUF_X','CLKBUF_X','INV_X')):
            a = inst.findITerm('A').getNet()
            z = inst.findITerm('ZN' if master.startswith('INV_X') else 'Z').getNet()
            if a and z: transparent.setdefault(a.getName(),[]).append(z.getName())
    pending = [v for f in roots.values() for v in f['roots'].values()]
    nets = {}
    while pending:
        name = pending.pop()
        if name in nets: continue
        net = block.findNet(name)
        drivers = [t for t in net.getITerms() if str(t.getIoType()) == 'OUTPUT']
        assert len(drivers) == 1, name
        sinks = [dict(xy=xy(t.getInst()),master=t.getInst().getMaster().getName(),pin=t.getMTerm().getName())
                 for t in net.getITerms() if str(t.getIoType()) == 'INPUT'
                 and not (t.getInst().getName() in ff and t.getMTerm().getName()=='SI')]
        ports = []
        for t in net.getBTerms():
            if t.getName().startswith(('test_si','test_so')): continue
            if str(t.getIoType()) != 'OUTPUT': raise ValueError('Unexpected FF-driven port')
            bbox = t.getBBox()
            ports.append([(bbox.xMin()+bbox.xMax())/2/units,(bbox.yMin()+bbox.yMax())/2/units])
        nets[name] = dict(driver_xy=xy(drivers[0].getInst()),sinks=sinks,ports=ports)
        pending.extend(transparent.get(name,[]))
    result = dict(stage='POST-PLACEMENT',FFs=roots,nets=nets,
                  transparent={k:sorted(v) for k,v in transparent.items() if k in nets})
    odb.dbDatabase.destroy(db)
    return result, time.perf_counter()-start


def main():
    integrity()
    quality = read(OLD/'test_quality.json')
    rows = read(REPORT/'architecture_set.json')
    construction = {}
    for d,q in quality.items():
        arch = read(next(r['architecture_path'] for r in rows if r['design']==d))
        graph, elapsed = placed_graph(Path(q['placed_def']),[c['name'] for c in arch['cells']])
        p = WORK/(d+'.placed_graph.json'); write(p,graph)
        construction[d] = dict(path=str(p),sha256=file_sha256(p),seconds=elapsed,
            placed_def=q['placed_def'],placed_def_sha256=file_sha256(Path(q['placed_def'])),
            FFs=len(graph['FFs']),nets=len(graph['nets']),sinks=sum(len(n['sinks']) for n in graph['nets'].values()))
    write(REPORT/'placement_audit.json',construction)
    loads = pin_loads(LIB.read_text())
    physical = {(r['design'],r['label']):r for r in read(OLD/'physical_weighting.json')['rows']}
    audit = []
    for row in rows:
        sha = row['architecture_sha256']; folder=WORK/sha; folder.mkdir(exist_ok=True)
        copied = folder/'frozen.odb'
        with gzip.open(row['odb_archive'],'rb') as src, copied.open('wb') as dst: shutil.copyfileobj(src,dst)
        assert file_sha256(copied) == row['odb_sha256']
        db = odb.dbDatabase.create(); odb.read_db(db,str(copied)); block=db.getChip().getBlock()
        # Actual routed pin loads belong ONLY to reference; never feed placed graph.
        phy = read(physical[row['design'],row['label']]['physical_path'])
        pin = {}
        for name in phy['nets']:
            net = block.findNet(name)
            pin[name] = sum(loads[t.getInst().getMaster().getName(),t.getMTerm().getName()]
                for t in net.getITerms() if str(t.getIoType())=='INPUT')
        odb.dbDatabase.destroy(db)
        spef = folder/'extracted.spef'; tcl=folder/'extract.tcl'; log=folder/'extract.log'
        if log.exists() and 'invalid command name "set_extraction_rules_file"' in log.read_text():
            shutil.copyfile(log, folder/'extract_api_probe.log')
            shutil.copyfile(tcl, folder/'extract_api_probe.tcl')
        command = f'''read_db {copied}
define_process_corner -ext_model_index 0 X
extract_parasitics -ext_model_file {RULES} -coupling_threshold 0.1 -cc_model 10 -context_depth 5 -version 1.0
write_spef {spef}
exit
'''
        tcl.write_text(command)
        start=time.perf_counter()
        proc=subprocess.run(['openroad','-no_init','-exit',str(tcl)],cwd=folder,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        log.write_text(proc.stdout)
        rec=dict(design=row['design'],label=row['label'],architecture_sha256=sha,
            odb_sha256=row['odb_sha256'],archive_sha256=file_sha256(Path(row['odb_archive'])),
            technology='Nangate45',liberty=str(LIB),liberty_sha256=file_sha256(LIB),
            routing_state='exact frozen 5_2_route detailed-routed ODB; no finish, reroute or repair',
            RC_corner='X: Nangate45 rules model index 0',rules_sha256=file_sha256(RULES),
            tool=read(REPORT/'provenance.json')['openroad'],command=command,
            api_compatibility='Installed binary uses -ext_model_file; newer ORFS source set_extraction_rules_file command is unavailable. Same rules and parameters; failed probe logs retained.',
            elapsed_seconds=time.perf_counter()-start,returncode=proc.returncode,
            log_path=str(log),log_sha256=file_sha256(log),
            warnings_errors=[l for l in proc.stdout.splitlines() if re.search(r'WARN|ERROR|Error|Warning',l)])
        try:
            assert proc.returncode == 0, 'Extraction process failed'
            nets = parse_spef(spef.read_text())
            owned = set(phy['nets'])
            missing = sorted(owned-set(nets))
            assert not missing, f'FF nets missing from SPEF: {missing[:20]}'
            weights = {}
            for name,f in phy['FFs'].items():
                ground=sum(nets[n]['ground_ff'] for n in f['nets'])
                coupling=sum(nets[n]['coupling_ff'] for n in f['nets'])
                pincap=sum(pin[n] for n in f['nets'])
                assert ground+coupling > 0, f'Zero FF wire cap: {name}'
                weights[name]=dict(ground_ff=ground,coupling_ff=coupling,pin_ff=pincap,
                    effective_ff=ground+coupling+pincap,ground_pin_ff=ground+pincap)
            count_res=sum(n['resistors'] for n in nets.values())
            count_cap=sum(n['capacitors'] for n in nets.values())
            assert count_res>0 and count_cap>0
            write(folder/'reference_weights.json',weights)
            rec.update(status='QUALIFIED_LOAD_REFERENCE',spef_path=str(spef),spef_sha256=file_sha256(spef),
                extracted_nets=len(nets),resistor_count=count_res,capacitor_entries=count_cap,
                total_ground_ff=sum(n['ground_ff'] for n in nets.values()),
                total_incident_coupling_ff=sum(n['coupling_ff'] for n in nets.values()),
                total_dnet_capacitance_ff=sum(n['declared_ff'] for n in nets.values()),
                FF_owned_nets=len(owned),FF_nets_covered=len(owned),FF_Q_usable=True,
                weights_path=str(folder/'reference_weights.json'),weights_sha256=file_sha256(folder/'reference_weights.json'))
        except (AssertionError,ValueError,OSError) as error:
            rec.update(status='BLOCKED',blocker=str(error),FF_Q_usable=False)
        assert file_sha256(copied)==row['odb_sha256']
        audit.append(rec)
        write(REPORT/'extraction_audit.json',dict(rows=audit,
            capacitance_qualified=len(audit)==len(rows) and all(r['status']=='QUALIFIED_LOAD_REFERENCE' for r in audit),
            convention='C_eff = ground + 1x incident coupling + input pin caps; coupling endpoints each bear full incident load. NOT coupling energy.',
            scope='Unique FF Q/QN nets through transparent gates. A_cap_total over these relevant nets equals A_ff_cap; all-circuit activity unavailable.',
            exclusions='Internal-cell/glitch switching, clocks, PI/SE-driven nets, nontransparent combinational outputs; no external output load invented.',
            vias='OpenRCX route/via geometry and default via resistance merging; no separately fabricated via capacitance.',
            total_capacitance_note='Sum D_NET includes incident coupling on both endpoint nets; not unique physical capacitor sum.',
            energy_portion='INCOMPLETE even with qualified capacitance load counts'))
        print('EXTRACTION',row['design'],row['label'],rec['status'],rec.get('blocker',''),flush=True)
    integrity()

if __name__=='__main__': main()
