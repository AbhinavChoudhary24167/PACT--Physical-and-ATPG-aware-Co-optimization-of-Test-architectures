"""Independently measure the campaign's already frozen unseen reference."""
import argparse
from pathlib import Path

from pact_generalization import ROOT, now, read, sha, write, binding
from pact_generalization_infrastructure import external_binding
from pact_cold_start_measure import OUT, RUN, run_row, validate_row


def resolve(item):
    path = item['path']
    return ROOT / path.removeprefix('repo://') if path.startswith('repo://') else Path(path)


def reference_row(design):
    protocol_path = OUT / 'manifests/campaign_preregistration.json'
    protocol = read(protocol_path)
    entry = next(r for r in protocol['designs'] if r['design'] == design)
    reference = entry['reference']
    if reference is None or reference['status'] != 'QUALIFIED':
        raise ValueError('No qualified frozen campaign reference')
    method = reference['method']
    prior_manifest = Path('/mnt/d/PACT_EXPERIMENTS/results/pact_generalization_20261004/reference_measurement') / design / 'manifest.json'
    package_path = OUT / 'inputs' / design / 'cold_start_input.json'
    if prior_manifest.exists():
        prior = read(prior_manifest)
        row = dict(next(r for r in prior['rows'] if r['design'] == design and r['role'] == method))
        input_source = external_binding(prior_manifest)
    elif package_path.exists():
        package = read(package_path)
        artifacts = package['artifacts']
        route = read(reference['provenance']['path'])
        row = dict(design=design, architecture=artifacts['architecture'], routed_archive=route['archive'],
            source_placed_database=artifacts['source_placed_database'], source_netlist=artifacts['source_netlist'],
            SDC=artifacts['SDC'], qualification=artifacts['qualification'], prior_integration=artifacts['reference_serial'],
            inputs={name: artifacts[name] for name in ('patterns', 'identity_map', 'placement')})
        input_source = binding(package_path)
    else:
        raise ValueError('Qualified unseen reference artifacts not yet packaged; no design-specific fallback')
    arch = validate_row(dict(row, role='REF_' + method))
    if arch.sha256() != reference['architecture_hash']:
        raise ValueError('Measurement would use a different frozen external architecture')
    if sha(row['architecture']['path']) != reference['architecture']['sha256']:
        raise ValueError('Frozen reference architecture byte binding differs')
    row.update(role='REF_' + method, architecture_sha256=arch.sha256(), reference_method=method,
        reference_architecture_hash=reference['architecture_hash'], created_utc=now(),
        campaign_preregistration=binding(protocol_path), qualified_unseen_input_source=input_source,
        initial_reference_frozen_before_search=True, additional_PACT_searches=0)
    frozen_path = OUT / 'references' / design / 'reference_frozen.json'
    row['reference_frozen'] = binding(frozen_path) if frozen_path.exists() else dict(
        preregistration=binding(protocol_path), reference_entry=reference,
        note='Exact minimum-qualified reference identity was frozen in campaign preregistration before any cold-start search')
    path = OUT / 'references' / design / 'measurement_row.json'
    write(path, row, immutable=True)
    return row


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--design', required=True)
    args = parser.parse_args()
    row = reference_row(args.design)
    run_row(row)
