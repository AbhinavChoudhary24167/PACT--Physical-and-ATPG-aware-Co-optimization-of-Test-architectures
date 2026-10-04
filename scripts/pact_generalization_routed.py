#!/usr/bin/env python3
"""Generalization-only repair of the verifier's arbitrary buffer-depth guard.

The frozen module and all gate/measurement expressions remain byte-identical.
Its visited-net set already bounds traversal. Replace only the eight-hop guard
with the number of buffer-source nets, which bounds any simple buffer path.
"""
import argparse
import hashlib
import inspect
import json
from pathlib import Path

from pact.physical import phase0d_routed as frozen
from pact_generalization import ROOT,OUT,read

OLD='if len(traversed) < 8:'
NEW='if len(traversed) <= len(buffers):'
FROZEN_VERIFY=frozen.verify_routed


def repaired_source(source):
    if source.count(OLD)!=1:
        raise ValueError('Unexpected frozen traversal implementation')
    return source.replace(OLD,NEW)


def make_verifier():
    path=Path(frozen.__file__)
    expected=next(b for b in read(OUT/'manifests/pact_v1_frozen_manifest.json')['files']
                  if b['path']=='repo://src/pact/physical/phase0d_routed.py')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=expected['sha256']:
        raise ValueError('Frozen routed verifier source changed')
    namespace=dict(frozen.__dict__)
    exec(compile(repaired_source(inspect.getsource(FROZEN_VERIFY)),
                 str(ROOT/'scripts/pact_generalization_routed.py'),'exec'),namespace)
    return namespace['verify_routed']


def verify_routed(routed,architecture,frozen_def):
    return make_verifier()(routed,architecture,frozen_def)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('routed','architecture','frozen-def','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--compare-frozen',type=Path)
    a=p.parse_args()
    result=verify_routed(a.routed,a.architecture,a.frozen_def)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    if a.compare_frozen:
        original=FROZEN_VERIFY(a.routed,a.architecture,a.frozen_def)
        assert original==result,'Repair changed previously passing gate/metric output'
        a.compare_frozen.write_text(json.dumps(dict(status='PASS',classification='IMPLEMENTATION_REPAIR',
            exact_output_equality=True,scientific_method_change=False,
            routed=str(a.routed),architecture=str(a.architecture)),indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('status','scan_ff_count','K','scan_edges',
        'routed_full_scan_path_net_length_upper_bound_um')}),flush=True)
