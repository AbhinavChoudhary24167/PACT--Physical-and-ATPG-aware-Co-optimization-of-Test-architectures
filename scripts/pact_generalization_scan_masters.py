"""Prove that the two permitted Nangate scan-drive strengths share FF logic."""
import hashlib
import re
from pathlib import Path
from pact_generalization_identity import liberty_groups

MASTERS=('SDFF_X1','SDFF_X2')


def master_allowed(name):
    return name in MASTERS


def logic_contract(liberty):
    cells=dict(liberty_groups(Path(liberty).read_text(),'cell'))
    contracts={}
    for name in MASTERS:
        body=cells[name]
        # The frozen one-name group reader does not parse separately quoted
        # two-variable ff headers. Normalize headers only, not expressions.
        def header(match):
            arguments=match[1]
            parsed=re.fullmatch(r'\s*"?(\w+)"?\s*,\s*"?(\w+)"?\s*',arguments)
            if not parsed:
                raise ValueError('Unexpected FF state variable header')
            return 'ff('+parsed[1]+','+parsed[2]+')'
        normalized=re.sub(r'\bff\s*\(([^()]*)\)',header,body)
        sequential=list(liberty_groups(normalized,'ff'))
        if not sequential:
            raise ValueError('Missing FF state function: '+name)
        states_contract=[]
        for states,definition in sequential:
            fields={k:re.sub(r'\s+','',v) for k,v in re.findall(r'\b(next_state|clocked_on|clear|preset)\s*:\s*"([^"]*)"',definition)}
            if set(fields)!= {'next_state','clocked_on'}:
                raise ValueError('Unexpected sequential behavior: '+name)
            states_contract.append(dict(state_variables=re.sub(r'\s+','',states),sequential=fields))
        pins={}
        for pin,data in liberty_groups(body,'pin'):
            direction=re.search(r'\bdirection\s*:\s*(\w+)',data)
            function=re.search(r'\bfunction\s*:\s*"([^"]*)"',data)
            if direction:
                pins.setdefault(pin,[]).append(dict(direction=direction[1],function=re.sub(r'\s+','',function[1]) if function else None))
        if set(pins)!={'D','CK','SI','SE','Q','QN'}:
            raise ValueError('Unexpected scan FF pins: '+name)
        contracts[name]=dict(state_functions_including_test_cell=states_contract,pins_including_test_cell=pins)
    if contracts[MASTERS[0]]!=contracts[MASTERS[1]]:
        raise ValueError('Resized scan FF truth/pin contract differs')
    return dict(status='PASS',permitted_masters=list(MASTERS),identical_logic=contracts[MASTERS[0]],
        library_sha256=hashlib.sha256(Path(liberty).read_bytes()).hexdigest(),
        rule='Only drive strength may differ; exact pins, state variables, clock expression and next-state/output functions must match')


if __name__=='__main__':
    import argparse
    from pact_generalization import read,write,binding,ROOT
    from pact_generalization_infrastructure import external_binding
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--liberty',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--routed-proof',type=Path)
    p.add_argument('--diagnosis',type=Path)
    p.add_argument('--before-execution',type=Path)
    a=p.parse_args()
    proof=logic_contract(a.liberty)
    receipt=dict(proof,classification='IMPLEMENTATION_REPAIR',scientific_method_change=False)
    if a.routed_proof:
        diagnosis=read(a.diagnosis)
        after=read(a.routed_proof)
        assert not diagnosis['missing'] and not diagnosis['extra']
        assert after['status']=='PASS' and after['scan_ff_count']==diagnosis['expected_FF_count']
        assert read(a.before_execution)['exit_code']!=0
        receipt.update(before=binding(a.diagnosis),before_execution=external_binding(a.before_execution),
            after=external_binding(a.routed_proof),repaired_scan_ff_count=after['scan_ff_count'],
            routed_scan_wirelength_um=after['routed_full_scan_path_net_length_upper_bound_um'],
            frozen_verifier_source=binding(ROOT/'src/pact/physical/phase0d_routed.py'),
            interpretation='Retain exact FF identities and functions; include both proven-identical scan drive strengths',
            additional_route_executions=0)
    write(a.output,receipt,immutable=True)
    print('SCAN_MASTER_LOGIC_CONTRACT PASS',proof['library_sha256'],flush=True)
