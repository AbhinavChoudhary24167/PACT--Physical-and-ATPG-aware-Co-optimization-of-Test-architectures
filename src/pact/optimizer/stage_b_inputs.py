"""Portable inputs for the constrained search, without workstation receipts."""
import gzip
import json
from pathlib import Path
import numpy as np
from pact.scan.model import ScanArchitecture, ScanCell, ScanChain
from . import implementation_v2 as v2
from . import candidate_sensitive as cs
from . import candidate_stateful as sf


class Model(sf.Model):
    """Preserve the capacity multiset, including reversed-capacity starts."""
    def validate(self, orders):
        if sorted(map(len, orders)) != sorted(self.capacities) or not np.array_equal(
                np.sort(np.concatenate(orders)), np.arange(len(self.names))):
            raise ValueError('Changed capacity multiset or FF bijection')
        if any(len(set(self.domains[o])) != 1 for o in orders):
            raise ValueError('Mixed clock domains')


def architecture(payload):
    if payload['schema_version'] != '0.1':
        raise ValueError('Unsupported architecture schema')
    return ScanArchitecture(tuple(ScanCell(**c) for c in payload['cells']), tuple(
        ScanChain(c['chain_id'], tuple(c['cells']), c.get('scan_in'), c.get('scan_out'))
        for c in payload['chains']))


def load_bundle(path):
    """Reconstruct the exact frozen model arrays and labelled starting orders."""
    path = Path(path)
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8') as stream:
        data = json.load(stream)
    if data['schema'] != 'pact_stage_b_inputs_v1':
        raise ValueError('Unsupported Stage-B input bundle')
    frozen = v2.Model(architecture(data['architecture']), data['load'], data['response'],
                      data['caps'], data['bounds'], data['inputs'], data['outputs'])
    sensitive = cs.Model(frozen, data['physical'], data['bounds'])
    primary = {name: np.asarray(bits, np.uint8) for name, bits in data['primary'].items()}
    model = Model(sensitive, data['graph'], data['caprows'], primary, depth=data['depth'])
    starts = [(r['label'], [np.asarray(o, np.int32) for o in r['orders']]) for r in data['starts']]
    for _, orders in starts:
        model.validate(orders)
    return model, starts, data['reference_label']
