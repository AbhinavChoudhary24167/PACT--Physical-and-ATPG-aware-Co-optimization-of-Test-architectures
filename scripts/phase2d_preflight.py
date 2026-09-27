"""Read-only upstream integrity audit; writes exclusively to the new Phase-2D directory."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/phase2d_independent_gp'

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def read(path):
    return json.loads(Path(path).read_text())

def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + '\n')

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    assert not (OUT / 'initial_integrity.json').exists(), 'Preserve completed preflight'
    prior = ROOT / 'results/phase2c_repair_multiseed'
    seed11 = ROOT / 'results/phase2c_repair'
    expected = {}
    conflicts = []
    for line in (prior / 'manifest.sha256').read_text().splitlines():
        digest, path = line.split('  ', 1)
        if path in expected and expected[path] != digest:
            conflicts.append(path)
        expected[path] = digest
    prov = read(seed11 / 'result_provenance.json')
    for path, digest in prov['files'].items():
        expected[str(seed11 / path)] = digest
    expected.update(prov['sources'])
    checks = []
    for path, digest in expected.items():
        p = Path(path)
        actual = sha(p) if p.is_file() else None
        checks.append(dict(path=path, expected=digest, actual=actual, passed=actual == digest))
    snapshots = {str(p): sha(p) for folder in (prior, seed11)
                 for p in sorted(folder.rglob('*')) if p.is_file()}
    result = dict(utc=datetime.now(timezone.utc).isoformat(), checks=checks,
                  conflicts=conflicts, checked=len(checks),
                  failures=[r for r in checks if not r['passed']],
                  upstream_snapshot=snapshots, python=sys.version,
                  git_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip())
    write(OUT / 'initial_integrity.json', result)
    flow = Path('/root/pact-deps/OpenROAD-flow-scripts/flow')
    inventory = {}
    for design, block in [('s5378','s5378'), ('s9234','s9234f'), ('s15850','s15850')]:
        folders = [flow / 'results/nangate45' / block / 'base', flow / 'results/nangate45' / block / 'phase0b_s11_B0']
        inventory[design] = {str(f): [dict(path=str(p), size=p.stat().st_size, sha256=sha(p))
                           for p in sorted(f.glob('*')) if p.is_file() and (p.name.startswith(('1_', '2_', '3_1_')))] for f in folders}
    write(OUT / 'pregp_inventory.json', inventory)
    print(json.dumps(dict(checked=len(checks), failures=result['failures'], conflicts=conflicts,
                         snapshot_files=len(snapshots), pregp_inventory=inventory), indent=2))

if __name__ == '__main__':
    main()
