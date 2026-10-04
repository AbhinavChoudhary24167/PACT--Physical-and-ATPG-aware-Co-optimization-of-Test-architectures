"""Phase-2C-R only: immutable evidence helpers, no physical execution."""
from pact.environment import dependency_path
from pact.experiment_storage import experiment_root
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
REPORT = ROOT / 'results/phase2c_repair'
B = ROOT / 'reports/phase2b_activity_model'
A = ROOT / 'reports/phase2a_shift_activity'
C = ROOT / 'reports/phase2c'
WORK = Path(f'{experiment_root()}/results/phase2b_activity_model')
PLATFORM = Path(f'{dependency_path("OpenROAD-flow-scripts")}/flow/platforms/nangate45')
LIB = PLATFORM / 'lib/NangateOpenCellLibrary_typical.lib'
DESIGNS = ('s5378', 's9234', 's15850')

def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def write(p, obj):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + '\n')

def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def check(p, expected):
    actual = sha(p)
    if actual != expected:
        raise ValueError(f'Frozen hash mismatch: {p}: expected {expected}, observed {actual}')
    return actual

def now():
    return datetime.now(timezone.utc).isoformat()

def order_hash(arch):
    obj = [dict(chain_id=c.chain_id, cells=list(c.cells), scan_in=c.scan_in,
                scan_out=c.scan_out) for c in arch.chains]
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def integrity():
    freeze = read(REPORT / 'freeze.json')
    for p, expected in freeze['inputs'].items():
        check(p, expected)
    check(REPORT / 'EXPERIMENT_CONTRACT.md', freeze['contract_sha256'])
    return freeze
