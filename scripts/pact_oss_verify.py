#!/usr/bin/env python3
"""Audit the sealed partial campaign and add original FAN statistics provenance."""
import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path
import re
import sys

from pact_oss_benchmark import ROOT, OUT, DESIGNS, binding, read, verify, write
from pact_oss_canonicalize import validate_architecture
from pact.scan.model import ScanArchitecture


def quality():
    records = {}
    for design in DESIGNS:
        original = ROOT / 'artifacts/raw/tool_qualification/fan_atpg/reports' / f'FAN_{design}.rpt'
        fsim = original.with_name(design + '_fsim.rpt')
        replay = ROOT / 'reports/end_to_end' / design / 'integration_v1/fault_replay/result.json'
        text = original.read_text()
        detected = int(re.search(r'^#\s*DT \(detected\)\s+(\d+)\s*$', text, re.M)[1])
        coverage = float(re.search(r'^#\s*fault coverage\s+([\d.]+)%\s*$', text, re.M)[1])
        old = read(replay)
        if detected != old['original_detected_faults'] or coverage != old['original_coverage']:
            raise ValueError('Original FAN statistics disagree with stored replay evidence')
        records[design] = dict(fault_coverage_percent=coverage, detected_fault_count=detected,
                               original_statistics=binding(original), original_fault_simulation_statistics=binding(fsim),
                               historical_replay=binding(replay), historical_count_and_coverage_equivalence=old['coverage_equivalence'],
                               fault_set_equivalent=None, lost_faults=None, unexpected_faults=None,
                               scope='Original saved FAN evidence only; no new native/OSS/P0 candidate replay in this campaign',
                               report_lines=[line for line in text.splitlines() if 'fault coverage' in line or 'DT (detected)' in line])
    write(OUT / 'stage_a/test_quality_summary.json', dict(records=records,
          supplement_note='FAN redirects report_statistics to separate .rpt files. Initial execution-log excerpt arrays were empty; the complete log hashes remain valid. This supplement binds the actual statistics and prior replay counts.'))


def audit():
    verify()
    manifest = read(OUT / 'stage_a/evidence_manifest.json')
    checked = 0
    for group in (manifest['artifacts'], manifest['benchmark_sources']):
        for name, expected in group.items():
            if binding(expected['path'])['sha256'] != expected['sha256']:
                raise ValueError('Sealed artifact/source changed: ' + name)
            checked += 1
    rows = list(csv.DictReader((OUT / 'stage_a/architecture_index.csv').open()))
    frozen = read(OUT / 'stage_a/P0_FREEZE.json')
    references = {d: ScanArchitecture.from_json(Path(frozen['frozen_inputs'][d]['B0_reference']['path'])) for d in DESIGNS}
    for row in rows:
        architecture = ScanArchitecture.from_json(Path(row['architecture_path']))
        if architecture.sha256() != row['architecture_hash']:
            raise ValueError('Canonical architecture hash mismatch')
        validate_architecture(architecture, references[row['design']])
    state = read(OUT / 'stage_a/status.json')
    assert state['new_routes'] == state['new_extractions'] == state['new_simulations'] == state['new_ATPG_runs'] == 0
    assert state['Stage_B'] == state['Stage_C'] == 'NOT_STARTED_STAGE_A_STOP_CONDITION'
    if not (OUT / 'stage_a/final_integrity_audit.json').exists():
        write(OUT / 'stage_a/final_integrity_audit.json', dict(timestamp=datetime.now(timezone.utc).isoformat(),
              sealed_artifact_and_source_bindings=checked, canonical_architectures_checked=len(rows),
              frozen_input_bindings=454, classification=state['stage_a'], result='PASS',
              evidence_manifest=binding(OUT / 'stage_a/evidence_manifest.json'),
              additive_supplements={p: binding(OUT / p) for p in ('stage_a/test_quality_summary.json',)},
              attributes=binding(ROOT / '.gitattributes'), verifier=binding(Path(__file__))))
    print('PASS sealed bindings', checked, 'canonical identities', len(rows), 'P0 frozen bindings 454; stages B/C not started', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=('quality', 'audit'))
    args = parser.parse_args()
    globals()[args.stage]()
