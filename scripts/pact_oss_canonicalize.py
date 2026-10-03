#!/usr/bin/env python3
"""Freeze generated/native and saved P0 identities using predicted-only selection."""
import csv
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import sys

from pact_oss_benchmark import ROOT, OUT, DESIGNS, binding, read, write
sys.path.insert(0, str(ROOT / 'src'))
from pact.scan.model import ScanArchitecture, ScanChain
from pact.scan.validate import validate_scan
from pact.physical.phase0c_port_policy import frozen_def_ports


def select(archive):
    keys = ('wire_um', 'E_stateful_ff', 'H8_stateful_ff')
    bounds = [(min(r['metrics'][k] for r in archive), max(r['metrics'][k] for r in archive)) for k in keys]
    def regret(row):
        return max((row['metrics'][k] - low) / (high - low) if high > low else 0.
                   for k, (low, high) in zip(keys, bounds))
    chosen = {}
    for role, row in (
        ('physical_extreme', min(archive, key=lambda r: (r['metrics']['wire_um'], r['architecture_sha256']))),
        ('H8_extreme', min(archive, key=lambda r: (r['metrics']['H8_stateful_ff'], r['architecture_sha256']))),
        ('balanced', min(archive, key=lambda r: (regret(r), r['architecture_sha256'])))):
        chosen.setdefault(row['architecture_sha256'], []).append(role)
    return chosen


def csv_write(path, fields, rows):
    if path.exists():
        raise ValueError('Evidence already exists: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def validate_architecture(architecture, reference):
    validate_scan(architecture)
    if len(architecture.chains) != 2:
        raise ValueError('K differs from frozen 2')
    expected = {c.name: asdict(c) for c in reference.cells}
    actual = {c.name: asdict(c) for c in architecture.cells}
    if expected != actual:
        raise ValueError('FF population, coordinates or clock domains differ')
    if sorted(len(c.cells) for c in architecture.chains) != sorted(len(c.cells) for c in reference.chains):
        raise ValueError('Workload chain lengths differ')
    if {(c.scan_in, c.scan_out) for c in architecture.chains} != {(c.scan_in, c.scan_out) for c in reference.chains}:
        raise ValueError('Scan endpoints differ')


def main():
    manifest, index, pre_route, selection = [], [], [], {}
    frozen = read(OUT / 'stage_a/P0_FREEZE.json')
    for design in DESIGNS:
        inputs = frozen['frozen_inputs'][design]
        reference = ScanArchitecture.from_json(Path(inputs['B0_reference']['path']))
        search_path = Path(inputs['P0_search']['path'])
        if binding(search_path)['sha256'] != inputs['P0_search']['sha256']:
            raise ValueError('P0 search changed')
        search = read(search_path)
        chosen = select(search['archive'])
        selection[design] = dict(roles=chosen, input=binding(search_path), full_archive_size=len(search['archive']))
        architectures = [('B0', reference, {}, ['reference'])]
        native_path = OUT / 'baselines/B1_openroad_native' / design / 'architecture.json'
        native = ScanArchitecture.from_json(native_path)
        # PACT's logical chain-0 names are test_si_0/test_so_0; the common
        # implementation adapter maps them to physical test_si/test_so.
        translated = ScanArchitecture(native.cells, tuple(
            ScanChain(c.chain_id, c.cells, reference.chains[i].scan_in, reference.chains[i].scan_out)
            for i, c in enumerate(native.chains)))
        architectures.append(('B1', translated, {}, ['single_solution']))
        translation_path = OUT / 'baselines/B1_openroad_native' / design / 'canonical_translation.json'
        if not translation_path.exists():
            write(translation_path, dict(native_source=binding(native_path), source_architecture_hash=native.sha256(),
                                         canonical_architecture_hash=translated.sha256(),
                                         unchanged='FF identities, positions, membership and order',
                                         mapping={c.scan_in: reference.chains[i].scan_in for i, c in enumerate(native.chains)} |
                                                 {c.scan_out: reference.chains[i].scan_out for i, c in enumerate(native.chains)},
                                         physical_chain0_alias='test_si_0/test_so_0 refer to existing test_si/test_so ports in the common adapter'))
        for row in search['archive']:
            arch = ScanArchitecture.from_json(Path(row['architecture']))
            if arch.sha256() != row['architecture_sha256']:
                raise ValueError('Saved P0 architecture changed')
            architectures.append(('P0', arch, row['metrics'], chosen.get(arch.sha256(), [])))
        ports, unit = frozen_def_ports(Path(inputs['placement']['path']), 2)
        for method, arch, predicted, roles in architectures:
            validate_architecture(arch, reference)
            sha = arch.sha256()
            path = OUT / 'stage_a/canonical' / design / method / (sha + '.json')
            if path.exists():
                if ScanArchitecture.from_json(path).sha256() != sha:
                    raise ValueError('Existing partial canonical output changed')
            else:
                arch.to_json(path)
            selected = bool(roles)
            representative = method != 'P0' or 'balanced' in roles
            index.append(dict(design=design, method=method, architecture_hash=sha, architecture_path=str(path),
                              roles=';'.join(roles), selected=selected, representative=representative,
                              status='CANONICAL_QUALIFIED', FF_count=len(arch.cells), K=2,
                              predicted_E=predicted.get('E_stateful_ff', ''), predicted_H8=predicted.get('H8_stateful_ff', ''),
                              predicted_H4=predicted.get('H4_stateful_ff', '')))
            xy = {c.name: (c.x_um, c.y_um) for c in arch.cells}
            wire, endpoint_wire = 0., 0.
            for chain in arch.chains:
                chain_wire = sum(abs(xy[a][0] - xy[b][0]) + abs(xy[a][1] - xy[b][1]) for a, b in zip(chain.cells, chain.cells[1:]))
                wire += chain_wire
                si = 'test_si' if chain.scan_in == 'test_si_0' else chain.scan_in
                so = 'test_so' if chain.scan_out == 'test_so_0' else chain.scan_out
                p, q = ports[si], ports[so]
                endpoint_wire += sum(abs(xy[chain.cells[0]][i] - p[i] / unit) + abs(xy[chain.cells[-1]][i] - q[i] / unit) for i in (0, 1))
                for position, name in enumerate(chain.cells):
                    manifest.append(dict(design=design, method=method, chain_id=chain.chain_id, chain_index=position,
                                         ordered_ff_identity=name, scan_in=chain.scan_in, scan_out=chain.scan_out,
                                         chain_length=len(chain.cells), architecture_hash=sha, architecture_path=str(path),
                                         roles=';'.join(roles), selected=selected, representative=representative))
            if selected:
                lengths = [len(c.cells) for c in arch.chains]
                pre_route.append(dict(design=design, method=method, architecture_hash=sha, roles=';'.join(roles),
                                      representative=representative, scan_hpwl_um=wire, port_inclusive_scan_hpwl_um=wire + endpoint_wire,
                                      maximum_chain_length=max(lengths), minimum_chain_length=min(lengths), chain_imbalance=max(lengths) - min(lengths),
                                      estimated_scan_path_length_um=wire + endpoint_wire,
                                      predicted_E=predicted.get('E_stateful_ff', ''), predicted_H4=predicted.get('H4_stateful_ff', ''),
                                      predicted_H8=predicted.get('H8_stateful_ff', ''),
                                      predictor_status='saved frozen P0 score' if predicted else 'not scored: PR baseline qualification gate pending',
                                      geometry_semantics='sum of FF-origin L1 scan edges; common fixed ports for inclusive metric'))
    csv_write(OUT / 'stage_a/architecture_manifest.csv', list(manifest[0]), manifest)
    csv_write(OUT / 'architecture_manifest.csv', list(manifest[0]), manifest)
    csv_write(OUT / 'stage_a/architecture_index.csv', list(index[0]), index)
    csv_write(OUT / 'stage_a/pre_route_metrics.csv', list(pre_route[0]), pre_route)
    write(OUT / 'stage_a/P0_SELECTION.json', dict(timestamp=datetime.now(timezone.utc).isoformat(),
                                                policy=binding(OUT / 'protocol/architecture_policy.md'), selection=selection,
                                                measured_results_read=False, new_routes_before_selection=0))
    print('Canonical architectures', len(index), 'selected P0', sum(r['method'] == 'P0' and r['selected'] for r in index),
          'FF manifest rows', len(manifest), flush=True)


if __name__ == '__main__':
    main()
