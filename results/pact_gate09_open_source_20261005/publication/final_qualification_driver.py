"""Terminal qualification only: focused tests and a read-only evidence audit."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
import pact_gate09_admission as admission
from pact_experiment_receipts import atomic_write

META = ROOT / 'results/pact_gate09_open_source_20261005'
OUT = META / 'publication/final_qualification'
OUT.mkdir(exist_ok=False)
tests = sorted(ROOT.glob('tests/test_gate09*.py'))
commands = [
    [sys.executable, '-m', 'pytest', '-q', *map(str, tests)],
    [sys.executable, str(ROOT / 'scripts/pact_gate09_validate.py'),
     '--directory', str(META), '--output', str(OUT / 'readonly_audit.json')],
]
records = []
for index, command in enumerate(commands):
    started = time.monotonic()
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    log = OUT / ('focused_tests.log' if index == 0 else 'readonly_audit.log')
    log.write_text(result.stdout + result.stderr)
    records.append(dict(command=command, exit_code=result.returncode,
                        wall_seconds=time.monotonic()-started, output=admission.binding(log)))
    print('GATE09_FINAL_QUALIFICATION_STAGE', index, result.returncode, flush=True)
    if result.returncode:
        break
record = dict(schema='pact_gate09_terminal_qualification_v1',
    created_utc=datetime.now(timezone.utc).isoformat(),
    status='PASS' if len(records)==2 and all(r['exit_code']==0 for r in records) else 'FAIL',
    scientific_campaigns_reexecuted=0, stages=records,
    tests={str(path.relative_to(ROOT)): admission.binding(path) for path in tests},
    sources={name: admission.binding(ROOT / 'scripts' / name) for name in
             ('pact_gate09_report.py', 'pact_gate09_campaign_report.py', 'pact_gate09_validate.py')},
    driver=admission.binding(Path(__file__)))
atomic_write(OUT / 'qualification.json', record, immutable=True)
print(json.dumps(record, indent=2), flush=True)
raise SystemExit(0 if record['status']=='PASS' else 2)
