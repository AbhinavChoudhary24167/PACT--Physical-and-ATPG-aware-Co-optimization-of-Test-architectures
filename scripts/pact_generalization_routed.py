#!/usr/bin/env python3
"""Generalization-only repairs of buffer depth and scan-drive-size recognition.

The frozen module and all gate/measurement expressions remain byte-identical.
Its visited-net set already bounds traversal. Replace only the eight-hop guard
with the number of buffer-source nets, which bounds any simple buffer path.
Recognize SDFF_X2 only after proving its frozen-library sequential/pin logic
identical to SDFF_X1. Exact FF identities and every remaining gate stay fixed.
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
OLD_FF='inst.getMaster().getName() == "SDFF_X1"'
NEW_FF='inst.getMaster().getName() in ("SDFF_X1", "SDFF_X2")'


def repaired_source(source,recognize_sized=False):
    if source.count(OLD)!=1 or source.count(OLD_FF)!=1:
        raise ValueError('Unexpected frozen traversal implementation')
    result=source.replace(OLD,NEW)
    return result.replace(OLD_FF,NEW_FF) if recognize_sized else result


def make_verifier(recognize_sized=False):
    path=Path(frozen.__file__)
    expected=next(b for b in read(OUT/'manifests/pact_v1_frozen_manifest.json')['files']
                  if b['path']=='repo://src/pact/physical/phase0d_routed.py')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=expected['sha256']:
        raise ValueError('Frozen routed verifier source changed')
    if recognize_sized:
        from pact_generalization_scan_masters import logic_contract
        library=Path('/root/pact-deps/OpenROAD-flow-scripts/flow/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib')
        proof=logic_contract(library)
        if proof['library_sha256']!=read(ROOT/'reports/physical_effect/manifest.json')['library']['sha256']:
            raise ValueError('Frozen Nangate scan-cell library changed')
    namespace=dict(frozen.__dict__)
    exec(compile(repaired_source(inspect.getsource(FROZEN_VERIFY),recognize_sized),
                 str(ROOT/'scripts/pact_generalization_routed.py'),'exec'),namespace)
    return namespace['verify_routed']


def verify_routed(routed,architecture,frozen_def,recognize_sized=False):
    return make_verifier(recognize_sized)(routed,architecture,frozen_def)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('routed','architecture','frozen-def','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--compare-frozen',type=Path)
    p.add_argument('--recognize-sized-scan',action='store_true')
    a=p.parse_args()
    result=verify_routed(a.routed,a.architecture,a.frozen_def,a.recognize_sized_scan)
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
