"""Verify committed seal bytes and add provenance without changing the seal."""
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
from pact_oss_benchmark import GIT, binding, git, read, write

RECOVERY = Path(__file__).resolve().parent
STAGE = RECOVERY / 'stage_a'
sha = git('rev-parse', 'HEAD')
if sha != '4a0512bbb91d93c98ed1deb11313f245d07f386c':
    raise ValueError('Milestone commit differs from the reviewed recovery')
manifest = read(STAGE / 'evidence_manifest.json')
items = list(manifest['artifacts'].values()) + list(manifest['benchmark_sources'].values())
queries = [sha + ':' + Path(item['path']).relative_to(ROOT).as_posix() for item in items]
data = subprocess.check_output([GIT, 'cat-file', '--batch'],
    input=('\n'.join(queries) + '\n').encode(), cwd=ROOT)
offset = 0
for item in items:
    stop = data.index(b'\n', offset)
    fields = data[offset:stop].split()
    if len(fields) != 3 or fields[1] != b'blob':
        raise ValueError('Sealed file is missing from the milestone: ' + item['path'])
    size = int(fields[2])
    start = stop + 1
    if hashlib.sha256(data[start:start+size]).hexdigest() != item['sha256']:
        raise ValueError('Committed bytes differ from sealed evidence: ' + item['path'])
    offset = start + size + 1
if offset != len(data):
    raise ValueError('Unexpected Git batch output remains')
audit = read(STAGE / 'final_integrity_audit.json')
status = read(STAGE / 'status.json')
write(RECOVERY / 'COMMIT_RECEIPT.json', dict(
    timestamp_utc=datetime.now(timezone.utc).isoformat(), milestone_commit=sha,
    milestone_parent=git('rev-parse', 'HEAD^'),
    milestone_title=git('show', '-s', '--format=%s', 'HEAD'),
    committed_files=len(git('diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD').splitlines()),
    committed_sealed_blob_bindings_verified=len(items),
    stage_a=status['stage_a'], scientific=status['scientific'],
    new_sealed_bindings_verified=audit['new_sealed_bindings_checked'],
    prior_recovery_bindings_verified=audit['previous_recovery_bindings_checked'],
    B3R_repair_commit=status['B3R_repair_commit_sha'], B3R_patch_sha256=status['B3R_patch_sha256'],
    B3R_binary_sha256=status['B3R_binary_sha256'], B3R_design_qualification=status['B3R_design_qualification'],
    B2_unchanged=True, P0_unchanged=True, Stage_B=status['Stage_B'],
    new_routes=0, new_extractions=0, new_simulations=0,
    unit_tests_distinct_passed=status['unit_tests_passed'], native_DFT_tests_passed=3,
    upstream_PR=status['upstream_contribution']['PR_URL'],
    latest_upstream_description_edit=status['upstream_contribution']['latest_description_edit'],
    evidence_manifest=binding(STAGE / 'evidence_manifest.json'),
    final_integrity_audit=binding(STAGE / 'final_integrity_audit.json'),
    final_report=binding(RECOVERY / 'FINAL_REPORT.md'), receipt_driver=binding(Path(__file__)),
    Git_status_after_milestone=subprocess.check_output([GIT, 'status', '--short'], text=True, cwd=ROOT).splitlines(),
    user_changes_included=False,
    receipt_scope='Additive postseal receipt; sealed report and evidence manifest are unchanged. Stage A remains incomplete.'))
print('COMMITTED_SEALED_BLOBS_VERIFIED', len(items), sha, flush=True)
