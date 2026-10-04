"""Independent Phase-2C paths, identity and immutable input gates."""
from pact.environment import dependency_path
from pact.experiment_storage import experiment_root
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from pact.phase0d.campaign import file_sha256, atomic_write_json as write

REPORT = ROOT / 'reports/phase2c'
OLD = ROOT / 'reports/phase2b_activity_model'
A = ROOT / 'reports/phase2a_shift_activity'
WORK = Path(f'{experiment_root()}/results/phase2c')
FLOW = Path(f'{dependency_path("OpenROAD-flow-scripts")}/flow')
PLATFORM = FLOW / 'platforms/nangate45'
LIB = PLATFORM / 'lib/NangateOpenCellLibrary_typical.lib'
RULES = PLATFORM / 'rcx_patterns.rules'
DESIGNS = ('s5378', 's9234', 's15850')
SEEDS = (11, 13, 17, 19, 23)
BLOCK = dict(s5378='s5378', s9234='s9234f', s15850='s15850')
ENDPOINTS = (('M3_load', 'cap_total'), ('M3_load_local', 'cap_local_peak'),
             ('M5_hpwl', 'wire_total'), ('M5_hpwl_local', 'wire_local_peak'))

def read(path):
    return json.loads(Path(path).read_text())

def order_hash(arch):
    obj = [dict(chain_id=c.chain_id, cells=list(c.cells), scan_in=c.scan_in,
                scan_out=c.scan_out) for c in arch.chains]
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def placed_def(d, s):
    return ROOT / f'artifacts/raw/phase0b/placements/{d}/s{s}/placed.def'

def base(d, s):
    return FLOW / f'results/nangate45/{BLOCK[d]}/phase0b_s{s}_B0'

def integrity():
    for path, sha in read(REPORT/'provenance.json')['inputs'].items():
        if file_sha256(Path(path)) != sha:
            raise ValueError('Changed frozen input: '+path)
    for name, sha in read(REPORT/'freeze.json')['files'].items():
        if file_sha256(REPORT/name) != sha:
            raise ValueError('Changed Phase-2C contract: '+name)

def require_open_experiment():
    """A documented legacy bug cannot be silently bypassed on resume."""
    if (REPORT/'legacy_bug_audit.json').exists():
        raise RuntimeError('Phase-2C stopped by the preregistered legacy-bug rule; see reports/phase2c/BUG_REPORT.md. A corrected experiment requires a new registration, not deletion of this guard.')
