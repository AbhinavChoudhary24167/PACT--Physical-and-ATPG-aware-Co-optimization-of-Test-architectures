#!/usr/bin/env python3
"""Prospective campaign receipts; never write to frozen historical evidence."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/pact_generalization_20261004'
CORE = ROOT / 'results/pact_end_to_end_20261004'
sys.path.insert(0, str(ROOT / 'src'))
from pact.scan.model import ScanArchitecture
from pact.scan.validate import validate_scan


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, data, immutable=False):
    path = Path(path)
    if immutable and path.exists():
        raise ValueError('Immutable receipt already exists: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def binding(path):
    path = Path(path)
    return dict(path='repo://' + path.relative_to(ROOT).as_posix(),
                sha256=sha(path), bytes=path.stat().st_size)


def now():
    return datetime.now(timezone.utc).isoformat()


def freeze():
    for name in ('manifests', 'baselines', 'searches', 'physical', 'atpg', 'canonical', 'logs', 'failures'):
        (OUT / name).mkdir(parents=True, exist_ok=True)
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    # Bind all existing scientific receipts and the complete executable source,
    # not just the final table. No tool execution or historical writes occur.
    paths = sorted(p for p in tracked if p and p.startswith(
        ('results/', 'reports/', 'artifacts/', 'src/', 'scripts/', 'config/', 'experiments/'))
        and not p.startswith('results/pact_generalization_20261004/'))
    inventory = [binding(ROOT / p) for p in paths]
    directories = {}
    for prefix in ('results/pact_end_to_end_20261004/', 'results/pact_stage_b/',
                   'results/pact_oss_benchmark/topology_recovery_20261004/'):
        members = [b for b in inventory if b['path'].startswith('repo://' + prefix)]
        canonical = json.dumps([(b['path'], b['sha256'], b['bytes']) for b in members], separators=(',', ':'))
        directories[prefix] = dict(files=len(members), sha256=hashlib.sha256(canonical.encode()).hexdigest(),
                                  algorithm='SHA256 of sorted JSON [repo URI, byte SHA256, byte size] tuples')
    manifest = dict(schema='pact_v1_frozen_manifest_v1', classification='PACT_V1_CORE_FROZEN',
        created_utc=now(), repository_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        tag='pact-v1-core-frozen-20261004', frozen_designs=['s5378','s9234','s15850'],
        optimizer_sources=[b for b in inventory if b['path'].startswith('repo://src/pact/optimizer/')],
        canonical_result=binding(CORE/'canonical_results.json'),
        candidate_manifest=binding(CORE/'selected_candidates.json'), baseline_manifest=binding(CORE/'frozen_baselines.json'),
        FAN_repair=read(CORE/'upstream_repair/qualification.json'),
        backend=read(ROOT/'results/pact_oss_benchmark/protocol/tool_versions.json'),
        ATPG_workloads=[binding(ROOT/f'artifacts/raw/tool_qualification/fan_atpg/patterns/FAN_{d}.pat')
                       for d in ('s5378','s9234','s15850')],
        result_directory_hashes=directories, files=inventory,
        byte_hash_note='Working-checkout bytes are frozen, including Git checkout line endings; repository SHA also binds original Git blobs.',
        forbidden_execution='No historical search, routing, extraction, ATPG generation, or scientific requalification')
    write(OUT/'manifests/pact_v1_frozen_manifest.json', manifest, immutable=True)
    return verify()


def verify():
    manifest = read(OUT/'manifests/pact_v1_frozen_manifest.json')
    for b in manifest['files']:
        path = ROOT / b['path'].removeprefix('repo://')
        if not path.is_file() or path.stat().st_size != b['bytes'] or sha(path) != b['sha256']:
            raise ValueError('Frozen byte binding failed: ' + str(path))
    data = read(CORE/'canonical_results.json')
    baseline = read(CORE/'frozen_baselines.json')['baselines']
    selected = read(CORE/'selected_candidates.json')
    assert data['status'] == 'PACT_END_TO_END_SOLUTION_QUALIFIED' and not data['remaining_blockers']
    assert len(data['records']) == len({(r['design'],r['candidate']) for r in data['records']}) == 12
    for row in data['records']:
        required = ('design','candidate','architecture_hash','qualification_status','E','H4','H8',
                    'routed_scan_wirelength_um','WNS','DRC_count','fault_coverage','gates','provenance')
        assert all(k in row for k in required), 'Invalid frozen canonical schema'
        assert row['qualification_status'] == 'QUALIFIED' and set(row['gates'].values()) == {'PASS'}
        arch = ScanArchitecture.from_json(CORE/f"architectures/{row['design']}_{row['candidate']}.json")
        validate_scan(arch)
        assert arch.sha256() == row['architecture_hash']
        assert (len(arch.cells), len(arch.chains)) == (row['FF_count'], row['chain_count'])
        if row['method'] == 'PACT':
            item = next(r for r in selected[row['design']] if r['candidate'] == row['candidate'])
            assert item['architecture_sha256'] == row['architecture_hash']
            assert row['reference_architecture_hash'] == baseline[row['design']]['architecture_hash']
        else:
            assert row['architecture_hash'] == baseline[row['design']]['architecture_hash']
        for key, b in row['provenance'].items():
            folder = CORE/'correctness'/row['design']/row['candidate']
            names = dict(complete_fault_export='fan/export.json', faults='test_correctness.json',
                physical='physical_proof.json', recovered_patterns='patterns_recovered.pat', serial='serial_replay.json')
            path = CORE/f"architectures/{row['design']}_{row['candidate']}.json" if key == 'architecture' else folder/names[key]
            assert sha(path) == b['sha256'], 'Historical provenance hash mismatch'
    result = dict(status='PACT_V1_CORE_FREEZE_VERIFIED', verified_utc=now(),
        manifest=binding(OUT/'manifests/pact_v1_frozen_manifest.json'), files_checked=len(manifest['files']),
        canonical_records_checked=12, historical_executions=0, historical_writes=0)
    write(OUT/'manifests/freeze_verification.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('freeze','verify'))
    args = parser.parse_args()
    print(json.dumps(globals()[args.action](), indent=2))
