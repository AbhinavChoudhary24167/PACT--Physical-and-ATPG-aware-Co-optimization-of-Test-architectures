"""Exact functional source/parity checks across transparent placement repairs."""
from functools import lru_cache
from pathlib import Path
import re
from pact.scan.identity import scan_ff_instances
from pact.scan.validate import validate_ff_identity_map
from pact.analysis.phase2b_loads import liberty_groups


def circuit(path):
    text=Path(path).read_text()
    header=re.search(r'\bmodule\s+\S+\s*\((.*?)\)\s*;',text,re.S)
    if header and re.search(r'\b(input|output|inout)\b',header[1]):
        raise ValueError('Mapped-source adapter requires explicit non-ANSI port declarations')
    cells={}
    for master,name,body in re.findall(r'\b(\w+_X\d+)\s+(\S+)\s*\((.*?)\)\s*;',text,re.S):
        pins=dict(re.findall(r'\.(\w+)\s*\(\s*([^()\s]+)\s*\)',body))
        if name in cells:
            raise ValueError('Duplicate instance')
        cells[name]=(master,pins)
    aliases=dict(re.findall(r'\bassign\s+(\S+)\s*=\s*([^\s;]+)\s*;',text))
    inputs=set()
    outputs=set()
    for direction,body in re.findall(r'\b(input|output)\s+([^;]+);',text):
        target=inputs if direction=='input' else outputs
        target.update(re.findall(r'[A-Za-z_$][\w$]*',body))
    return dict(cells=cells,aliases=aliases,inputs=inputs,outputs=outputs)


def functional_identity(source,placed,liberty):
    definitions={}
    for master,body in liberty_groups(Path(liberty).read_text(),'cell'):
        definitions[master]={}
        for pin,data in liberty_groups(body,'pin'):
            direction=re.search(r'\bdirection\s*:\s*(\w+)',data)
            function=re.search(r'\bfunction\s*:\s*"([^"]+)"',data)
            if direction:
                definitions[master][pin]=(direction[1],function[1] if function else None)
    old,new=circuit(source),circuit(placed)
    if old['inputs']!=new['inputs'] or old['outputs']!=new['outputs']:
        raise ValueError('Primary interface changed')
    def resolver(graph):
        drivers={}
        for name,(master,pins) in graph['cells'].items():
            for pin,net in pins.items():
                if definitions[master][pin][0]=='output':
                    drivers.setdefault(net,[]).append((name,pin))
        active=set()
        @lru_cache(None)
        def origin(net):
            if net in active:
                raise ValueError('Transparent/alias cycle')
            active.add(net)
            try:
                if net in graph['aliases']:
                    return origin(graph['aliases'][net])
                if net in graph['inputs']:
                    return ('PORT',net,0)
                if net in ("1'b0","1'b1"):
                    return ('CONST',net[-1],0)
                matches=drivers.get(net,[])
                if len(matches)!=1:
                    raise ValueError('Missing or ambiguous signal driver: '+net)
                name,pin=matches[0]
                master,pins=graph['cells'][name]
                function=definitions[master][pin][1]
                if function in ('0','1'):
                    return ('CONST',function,0)
                if master.startswith(('BUF_X','CLKBUF_X','INV_X')):
                    value=origin(pins['A'])
                    return (*value[:2],value[2]^int(master.startswith('INV_X')))
                return (name,pin,0)
            finally:
                active.remove(net)
        return origin
    a,b=resolver(old),resolver(new)
    checked=0
    for name,(master,pins) in old['cells'].items():
        if master.startswith(('BUF_X','CLKBUF_X','INV_X','TAPCELL')):
            continue
        if name not in new['cells']:
            raise ValueError('Missing functional instance: '+name)
        actual,actual_pins=new['cells'][name]
        if master.split('_X')[0]!=actual.split('_X')[0]:
            raise ValueError('Changed function family: '+name)
        for pin,net in pins.items():
            if definitions[master][pin][0]!='input':
                continue
            if pin not in actual_pins or a(net)!=b(actual_pins[pin]):
                raise ValueError('Changed functional source/parity: '+name+'/'+pin)
            checked+=1
    for port in old['outputs']:
        if a(port)!=b(port):
            raise ValueError('Changed primary output source/parity: '+port)
        checked+=1
    return dict(status='PASS',functional_sinks_and_outputs=checked,
        rule='Exact source identity and inversion parity through buffers/inverters; identical nontransparent function families',
        source=str(source),placed=str(placed))


def identity_map(source,placed,patterns,liberty):
    proof=functional_identity(source,placed,liberty)
    old={r.name:r for r in scan_ff_instances(Path(source))}
    new={r.name:r for r in scan_ff_instances(Path(placed))}
    if set(old)!=set(new) or set(old)!=set(patterns.pseudo_primary_inputs):
        raise ValueError('Source, physical and ATPG FF inventories differ')
    if any(old[n].clock_net!=new[n].clock_net for n in old):
        raise ValueError('Clock domain changed')
    records=[dict(logical_ff=old[n].q_net,physical_instance=n,atpg_signal=n,clock_domain=old[n].clock_net)
             for n in patterns.pseudo_primary_inputs]
    validate_ff_identity_map(records,new.keys())
    proof['Q_net_renames']={n:dict(source=old[n].q_net,placed=new[n].q_net) for n in old if old[n].q_net!=new[n].q_net}
    return records,proof


if __name__=='__main__':
    import argparse
    from pact_generalization import binding,now,write
    from pact.test.pattern_parser import parse_fan_pat
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','placed','patterns','liberty','output'):
        p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args()
    records,proof=identity_map(args.source,args.placed,parse_fan_pat(args.patterns),args.liberty)
    write(args.output,dict(classification='IMPLEMENTATION_REPAIR',scientific_method_change=False,
        created_utc=now(),FF_count=len(records),proof=proof,
        frozen_gate='Retain source/physical/ATPG FF identities and functional source/parity',
        before='Q-net label change beyond a single BUF_X1 alias rejected',
        after='All functional sources proven before resolving FFs by exact instance identity'),immutable=True)
    print('FUNCTIONAL_IDENTITY',proof['status'],len(records),proof['functional_sinks_and_outputs'],
        len(proof['Q_net_renames']),flush=True)
