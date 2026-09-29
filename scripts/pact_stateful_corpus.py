"""Reconstruct canonical hashes from historical mutation logs, without scoring."""
import csv
import gzip
from types import SimpleNamespace
import numpy as np
from scipy.spatial import cKDTree
from pact.optimizer.implementation_v2 import order_id
from pact.optimizer.search import Archive, locate, proposal, update_locations
from pact.scan.model import ScanArchitecture
from pact_v2 import read, binding
from pathlib import Path


def reconstruct(model, folder, namespace):
    result = read(folder/'search.json')
    starts = [(r['label'], model.orders(ScanArchitecture.from_json(Path(r['architecture'])))) for r in result['baselines']]
    cfg = result['config']
    archive = Archive(cfg['archive_size'])
    columns = ('wire_um', 'activity_ff_transitions', 'spatial_peak_8_ff') if namespace == 'pact_v2' else (
        'wire_um', 'candidate_E_ff', 'propagated_H8_ff')
    for row, (_, orders) in zip(result['baselines'], starts):
        metric = row['metrics']
        if metric['wire_um'] <= result['wire_ceiling_um']+1e-8 and metric['timing_max_edge_um'] <= result['timing_ceiling_um']+1e-8:
            archive.insert(np.array([metric[k] for k in columns]), orders, row['label'])
    state = SimpleNamespace(costs=model, orders=[o.copy() for o in starts[0][1]])
    locate(state)
    neighbors = np.asarray(cKDTree(model.xy).query(model.xy, k=min(len(model.names), cfg['neighbors']+1))[1], np.int32)
    rng = np.random.default_rng(cfg['seed'])
    mappings = {order_id(o): model.canonical_id(o) for _, o in starts}
    with gzip.open(folder/'evaluations.csv.gz', 'rt') as f:
        rows = list(csv.DictReader(f))
    evaluations = attempts = 0
    while evaluations < len(rows):
        if evaluations and evaluations % cfg['restart_interval'] == 0:
            epoch = evaluations//cfg['restart_interval']
            if epoch % 4 == 0: label, orders = starts[(epoch//4) % len(starts)]
            else:
                r = archive.rows[int(rng.integers(len(archive.rows)))]; label, orders = r['label'], r['orders']
            state.orders = [o.copy() for o in orders]; locate(state)
        parent = order_id(state.orders)
        patch, kind = proposal(state, neighbors, rng, attempts, cfg['segment']); attempts += 1
        if patch is None: continue
        undo = {ci: (positions, state.orders[ci][positions].copy()) for ci, (positions, _) in patch.items()}
        for ci, (positions, nodes) in patch.items(): state.orders[ci][positions] = nodes
        try: model.validate(state.orders)
        except ValueError:
            for ci, (positions, nodes) in undo.items(): state.orders[ci][positions] = nodes
            continue
        row = rows[evaluations]
        oid = order_id(state.orders)
        if parent != row['parent_order_id'] or oid != row['order_id'] or kind != row['operator']:
            raise ValueError(f'Historical trace identity mismatch: {namespace} evaluation {evaluations+1}')
        mappings[oid] = model.canonical_id(state.orders)
        if row['feasible'] == 'True':
            archive.insert(np.array([float(row[k]) for k in columns]), state.orders, row['provenance']+':'+kind)
        if row['accepted'] == 'True': update_locations(state, patch)
        else:
            for ci, (positions, nodes) in undo.items(): state.orders[ci][positions] = nodes
        evaluations += 1
    for r in result['archive']+result['baselines']:
        if mappings[r['order_id']] != r['architecture_sha256']: raise ValueError('Historical canonical hash mismatch')
    return mappings, dict(namespace=namespace, evaluations=evaluations, unique_orders=len(mappings),
        log=binding(folder/'evaluations.csv.gz'), search=binding(folder/'search.json'),
        verification='Every reconstructed order and parent matched historical SHA256; retained canonical hashes matched; no objective or physical experiment rerun')
