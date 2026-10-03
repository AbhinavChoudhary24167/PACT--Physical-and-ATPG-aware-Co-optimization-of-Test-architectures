#!/usr/bin/env python3
"""Record before/after execution of the small generic serializer witness."""
import argparse
import shutil

import pact_oss_serialization as s
import pact_oss_topology as r
from pact_oss_benchmark import binding, read, write


def main(mode):
    r.ensure()
    s.activate()
    parent = read(s.REPAIR / 'parent.json')
    executable = '/scratch/topology_recovery_20261004/immutable_binaries/'+parent['parent_revision']+'/openroad' if mode=='before' else '/build_storage/'+s.NAME+'/build/bin/openroad'
    attempt=1
    while (s.SERIAL/(mode+('' if attempt==1 else '_attempt'+str(attempt))+'.execution.json')).exists():
        attempt+=1
    label=mode+('' if attempt==1 else '_attempt'+str(attempt))
    output = r.DATA / 'verilog_input_alias' / label
    output.mkdir(parents=True,exist_ok=True)
    args=[executable,'-python','-no_init','-exit','/workspace/scripts/pact_verilog_alias_witness.py',
        '--library','/build_storage/'+s.NAME+'/source/test/Nangate45',
        '--output','/scratch/topology_recovery_20261004/verilog_input_alias/'+label]
    code=r.run(r.container(args),s.SERIAL,label)
    expected=2 if mode=='before' else 0
    if code!=expected:
        raise ValueError('Small serializer witness did not return expected status: '+str(code))
    for filename in ('proof.json','output.v'):
        shutil.copy2(output/filename,s.SERIAL/(mode+'.'+filename))
    write(s.SERIAL/(mode+'.json'),dict(status='EXPECTED_FAILURE_REPRODUCED' if mode=='before' else 'PASS',
        execution=binding(s.SERIAL/(label+'.execution.json')),proof=binding(s.SERIAL/(mode+'.proof.json')),
        input_ODB=binding(output/'input.odb'),Verilog=binding(s.SERIAL/(mode+'.output.v'))))
    print('GENERIC_SERIALIZATION_WITNESS',mode,'PASS',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=('before','after'))
    main(parser.parse_args().mode)
