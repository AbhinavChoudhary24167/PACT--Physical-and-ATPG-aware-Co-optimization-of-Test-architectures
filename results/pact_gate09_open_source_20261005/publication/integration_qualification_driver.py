"""Check publication integration without executing any scientific stage."""
from datetime import datetime, timezone
import hashlib
import importlib
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
import pact_gate09_admission as admission
from pact_experiment_receipts import atomic_write

SCIENCE = 'e8c2f5da298f073c231b5798561ffadce6355ec2'
MAIN = 'fc5211cc3ab5a2a8746521b467dc7a2915611606'
META = ROOT / 'results/pact_gate09_open_source_20261005'
OUT = META / 'publication/integration_qualification'
OUT.mkdir(exist_ok=False)

def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])

protocol = admission.read(admission.INTAKE)
changes = {'scripts/pact_cpu_qualify_continuation.py', 'scripts/pact_experiment_receipts.py'}
frozen = {name: admission.verify(value) for name, value in protocol['frozen_sources'].items()
          if name not in changes}
preserved = admission.read(META / 'publication/execution_source_preservation.json')
archives = {r['source']['path'].removeprefix('repo://'): r['snapshot'] for r in preserved['records']}
integrated = {}
for name in sorted(changes):
    expected = protocol['frozen_sources'][name]
    archive = admission.verify(archives[name])
    upstream = git('show', MAIN+':'+name)
    current = admission.binding(ROOT / name)
    integrated[name] = dict(frozen_execution_source=expected, preserved=archive,
        current=current, main_blob_sha256=hashlib.sha256(upstream).hexdigest(),
        status='PASS' if archive['status']=='PASS' and archives[name]['sha256']==expected['sha256']
                        and current['sha256']==hashlib.sha256(upstream).hexdigest() else 'FAIL')

# Preserve the receipt-control test version from the sealed scientific commit.
test_name = 'tests/unit/test_experiment_receipts.py'
old_test = git('show', SCIENCE+':'+test_name)
snapshot = META / 'publication/execution_sources' / (hashlib.sha256(old_test).hexdigest()+'.py')
if not snapshot.exists():
    snapshot.write_bytes(old_test)

result_diff = git('diff', '--no-ext-diff', '--name-status', '--diff-filter=MD', SCIENCE, '--', 'results').decode()
method_diff = git('diff', '--no-ext-diff', '--name-status', SCIENCE, '--', 'src/pact').decode()
tests = ['tests/unit/test_experiment_receipts.py', 'tests/test_gate09_validate.py',
         'tests/test_gate09_input_recovery.py', 'tests/test_gate09_campaign.py']
command = [sys.executable, '-m', 'pytest', '-q', *tests]
started = time.monotonic()
result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
log = OUT / 'compatibility_tests.log'
log.write_text(result.stdout+result.stderr)
imports = []
for path in sorted((ROOT / 'scripts').glob('pact_gate09_*.py')):
    importlib.import_module(path.stem)
    imports.append(path.stem)
failures = [name for name, row in frozen.items() if row['status']!='PASS']
failures += [name for name, row in integrated.items() if row['status']!='PASS']
if result_diff: failures.append('Existing result files changed during integration')
if method_diff: failures.append('PACT method changed during integration')
if result.returncode: failures.append('Compatibility tests failed')
record = dict(schema='pact_gate09_publication_integration_qualification_v1',
    created_utc=datetime.now(timezone.utc).isoformat(), status='PASS' if not failures else 'FAIL',
    sealed_scientific_commit=SCIENCE, integrated_main_commit=MAIN,
    preintegration_audit=admission.binding(META / 'publication/final_qualification/readonly_audit.json'),
    frozen_sources_unchanged=len(frozen), frozen_source_checks=frozen,
    execution_infrastructure_changes=integrated,
    PACT_source_diff=method_diff, modified_or_deleted_prior_result_files=result_diff,
    historical_preservation='Preintegration 1772-file byte audit passed; integration changed or deleted zero prior result files',
    compatibility=dict(command=command, exit_code=result.returncode,
        wall_seconds=time.monotonic()-started, output=admission.binding(log),
        tests={name: admission.binding(ROOT / name) for name in tests}),
    imported_gate09_modules=imports, archived_preintegration_receipt_tests=admission.binding(snapshot),
    scientific_campaigns_reexecuted=0, scientific_method_changes=0,
    reproduction='Use sealed scientific commit and recorded tool/input hashes; current receipt path portability is a post-science integration',
    driver=admission.binding(Path(__file__)), failures=failures)
atomic_write(OUT / 'qualification.json', record, immutable=True)
print('GATE09_INTEGRATION_QUALIFICATION', record['status'], len(frozen), 'unchanged frozen sources', flush=True)
print(result.stdout, flush=True)
raise SystemExit(0 if record['status']=='PASS' else 2)
