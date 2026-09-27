"""Canonical old position <-> FF identity <-> new position transformation."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from pact.scan.model import ScanArchitecture
from pact.scan.validate import validate_scan


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False)
                          + '\n', encoding='utf-8')


@dataclass(frozen=True)
class ScanPermutation:
    before: ScanArchitecture
    after: ScanArchitecture

    def __post_init__(self):
        for arch in (self.before, self.after):
            validate_scan(arch)
            if any(not c.scan_in or not c.scan_out for c in arch.chains):
                raise ValueError('Explicit SI/SO endpoints required')
            if len({c.clock_domain for c in arch.cells}) != 1:
                raise ValueError('Multiple clock domains are not supported')
        old = {c.name: c for c in self.before.cells}
        new = {c.name: c for c in self.after.cells}
        if old != new:
            raise ValueError('FF bijection, placement or clock domain changed')
        def boundaries(arch):
            return {c.chain_id: (c.scan_in, c.scan_out, len(c.cells)) for c in arch.chains}
        if boundaries(self.before) != boundaries(self.after):
            raise ValueError('Chain identities, SI/SO association or fixed capacities changed')

    def payload(self):
        def chains(arch):
            return [dict(chain_id=c.chain_id, cells=list(c.cells), head=c.cells[0],
                         tail=c.cells[-1], scan_in=c.scan_in, scan_out=c.scan_out,
                         length=len(c.cells)) for c in sorted(arch.chains, key=lambda c: c.chain_id)]
        def positions(arch):
            return {n: dict(chain_id=c.chain_id, position=i)
                    for c in arch.chains for i, n in enumerate(c.cells)}
        old, new = positions(self.before), positions(self.after)
        mapping = [dict(ff=n, old=old[n], new=new[n]) for n in sorted(old)]
        return dict(schema='pact_scan_permutation_v1', orientation='SI_to_SO',
                    input_topology_sha256=self.before.sha256(),
                    selected_architecture_sha256=self.after.sha256(),
                    K=len(self.before.chains), FF_count=len(old),
                    old_order=chains(self.before), new_order=chains(self.after),
                    old_to_new=sorted(mapping, key=lambda r: (r['old']['chain_id'], r['old']['position'])),
                    new_to_old=sorted(mapping, key=lambda r: (r['new']['chain_id'], r['new']['position'])))

    def to_json(self, path):
        payload = self.payload()
        write(path, dict(payload, permutation_sha256=digest(payload)))

    @classmethod
    def verify_json(cls, path, before, after):
        saved = read(path)
        sha = saved.pop('permutation_sha256')
        permutation = cls(before, after)
        if digest(saved) != sha or saved != permutation.payload():
            raise ValueError('Permutation hash/provenance mismatch')
        return permutation
