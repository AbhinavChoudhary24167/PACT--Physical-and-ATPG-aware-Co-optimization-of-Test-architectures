"""Artifact-driven cold start of the unchanged constrained PACT evaluator.

The only starting order is the independently qualified external reference.
No historical search, archive, or P0 is read by this module.
"""
from dataclasses import dataclass
import csv
import hashlib
import json
from pathlib import Path
import numpy as np

from pact.scan.model import ScanArchitecture
from pact.scan.validate import validate_scan
from pact.integration.patterns import fan_workload
from pact.physical.phase0c_port_policy import frozen_def_ports
from . import implementation_v2 as v2
from . import candidate_sensitive as cs
from .candidate_physical import construct
from .stage_b_inputs import Model


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class ColdStartPACTInput:
    manifest_path: Path
    data: dict

    @classmethod
    def from_manifest(cls,path):
        path=Path(path).resolve()
        data=json.loads(path.read_text(encoding='utf-8'))
        if data.get('schema')!='pact_cold_start_input_v1':
            raise ValueError('Unsupported cold-start input schema')
        if not isinstance(data.get('design'),str) or not data['design']:
            raise ValueError('Missing design identity')
        if data.get('reference_method') not in ('B0','B1','B2','B3T'):
            raise ValueError('Unqualified external reference method')
        if set(data).intersection(('historical_p0','P0','historical_archive','previous_PACT_architecture')):
            raise ValueError('Historical search state is not a cold-start input')
        obj=cls(path,data)
        for name in ('architecture','patterns','identity_map','placement','mapping','caps','topology'):
            obj.artifact(name)
        obj.initial_architecture
        return obj

    @property
    def design(self):
        return self.data['design']

    def artifact(self,name):
        value=self.data['artifacts'][name]
        raw=value['path']
        if raw.startswith('repo://'):
            path=Path(__file__).resolve().parents[3]/raw.removeprefix('repo://')
        else:
            path=Path(raw)
            if not path.is_absolute():
                path=self.manifest_path.parent/path
        if not path.is_file() or digest(path)!=value['sha256']:
            raise ValueError('Cold-start artifact hash mismatch: '+name)
        return path

    @property
    def initial_architecture(self):
        arch=ScanArchitecture.from_json(self.artifact('architecture'))
        validate_scan(arch)
        if arch.sha256()!=self.data['reference_architecture_hash']:
            raise ValueError('Initial architecture differs from frozen external reference')
        if len(arch.chains)!=2 or any(len(c.cells)<8 for c in arch.chains):
            raise ValueError('Frozen K=2 requires at least eight FFs per chain')
        for i,chain in enumerate(arch.chains):
            # Preserve the qualified backend's canonical endpoint aliases.
            suffix='' if i==0 else '_'+str(i)
            if chain.scan_in not in ('test_si'+suffix,'test_si_0' if i==0 else 'test_si'+suffix):
                raise ValueError('Unsupported scan input endpoint contract')
            if chain.scan_out not in ('test_so'+suffix,'test_so_0' if i==0 else 'test_so'+suffix):
                raise ValueError('Unsupported scan output endpoint contract')
        return arch


def load(path):
    """Build exactly the existing v2 -> sensitive -> stateful model layers."""
    contract=ColdStartPACTInput.from_manifest(path)
    arch=contract.initial_architecture
    identity=json.loads(contract.artifact('identity_map').read_text())['records']
    fan,states=fan_workload(contract.artifact('patterns'),identity,arch)
    names=[c.name for c in arch.cells]
    loads=[[s['load_state'][n] for n in names] for s in states]
    responses=[[s['response_state'][n] for n in names] for s in states]
    if any(bit not in ('0','1') for array in (loads,responses) for row in array for bit in row):
        raise ValueError('Unknown ATPG bits cannot be silently filled')
    with contract.artifact('caps').open() as stream:
        caprows=list(csv.DictReader(stream))
    by_source={}
    for row in caprows:
        by_source.setdefault(row['source'],[]).append(row)
    weights=[]
    for name in names:
        if name+'/Q' not in by_source:
            raise ValueError('Missing physical FF Q capacitance: '+name)
        values=[]
        for row in by_source[name+'/Q']+by_source.get(name+'/QN',[]):
            pin=float(row['pin_ff'])
            ground=float(row['ground_ff']) if row['ground_ff'] else None
            if not np.isfinite(pin) or pin<0 or (ground is not None and (not np.isfinite(ground) or ground<0)):
                raise ValueError('Invalid extracted load')
            values.append(pin+(ground if ground is not None else 0))
        weights.append(sum(values))
    mapping=json.loads(contract.artifact('mapping').read_text())
    graph=json.loads(contract.artifact('topology').read_text())
    if mapping['bounds_um']!=graph['bounds']:
        raise ValueError('Topology and mapping bounds differ')
    ports,unit=frozen_def_ports(contract.artifact('placement'),len(arch.chains))
    inputs=[np.array(ports['test_si'+('_'+str(i) if i else '')])/unit for i in range(len(arch.chains))]
    outputs=[np.array(ports['test_so'+('_'+str(i) if i else '')])/unit for i in range(len(arch.chains))]
    frozen=v2.Model(arch,np.asarray(loads,np.uint8),np.asarray(responses,np.uint8),weights,
        mapping['bounds_um'],inputs,outputs)
    physical=construct(frozen,graph,caprows)
    sensitive=cs.Model(frozen,physical,graph['bounds'])
    primary={pin:np.array([int(s['source_fields']['pi1'][i]) for s in states],np.uint8)
        for i,pin in enumerate(fan.primary_inputs)}
    model=Model(sensitive,graph,caprows,primary,depth=3)
    starts=[(contract.data['reference_method'],model.orders(arch))]
    return model,starts,contract
