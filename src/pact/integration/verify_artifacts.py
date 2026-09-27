"""Read-only verification of a delivered integration bundle."""
import argparse
from pathlib import Path
from .permutation import read, file_hash, ScanPermutation
from pact.scan.model import ScanArchitecture


def verify_manifest(folder):
    folder = Path(folder).resolve()
    manifest = read(folder/'manifest.json')
    for name, expected in manifest['artifacts'].items():
        path = (folder/name).resolve()
        if not path.is_relative_to(folder) or file_hash(path) != expected:
            raise ValueError(f'Artifact hash/path mismatch: {name}')
    before = ScanArchitecture.from_json(folder/'scan_topology_before.json')
    after = ScanArchitecture.from_json(folder/'scan_topology_after.json')
    ScanPermutation.verify_json(folder/'scan_permutation.json',before,after)
    if (before.sha256(),after.sha256()) != (manifest['input_topology_sha256'],manifest['selected_architecture_sha256']):
        raise ValueError('Manifest topology provenance mismatch')
    return dict(status='PASS', artifacts_checked=len(manifest['artifacts']))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('folder', type=Path)
    print(verify_manifest(p.parse_args().folder))
