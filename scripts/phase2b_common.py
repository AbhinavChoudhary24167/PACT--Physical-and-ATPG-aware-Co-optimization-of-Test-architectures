"""Paths and integrity gates shared by the standalone Phase-2B experiment."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from pact.phase0d.campaign import file_sha256, atomic_write_json as write

REPORT = ROOT / 'reports/phase2b_activity_model'
OLD = ROOT / 'reports/phase2a_shift_activity'
WORK = Path('/mnt/d/PACT_EXPERIMENTS/results/phase2b_activity_model')
PLATFORM = Path('/root/pact-deps/OpenROAD-flow-scripts/flow/platforms/nangate45')
LIB = PLATFORM / 'lib/NangateOpenCellLibrary_typical.lib'
RULES = PLATFORM / 'rcx_patterns.rules'

def read(path):
    return json.loads(Path(path).read_text())

def integrity():
    for name, expected in read(REPORT / 'freeze.json')['files'].items():
        if file_sha256(REPORT / name) != expected:
            raise ValueError('Changed contract: ' + name)
    for name, expected in read(REPORT / 'provenance.json')['inputs'].items():
        if file_sha256(Path(name)) != expected:
            raise ValueError('Changed frozen input: ' + name)
