"""Close the input-integrity audit and hash compact evidence and raw outputs."""
from phase2c_common import *
from datetime import datetime,timezone
import re
import subprocess

def test_summary(path):
    text=path.read_text()
    counts={k:int(v) for v,k in re.findall(r'(\d+) (passed|failed|skipped|errors?)',text)}
    times=re.findall(r'in ([\d.]+)s',text)
    return dict(path=str(path),sha256=file_sha256(path),counts=counts,runtime_seconds=float(times[-1]) if times else None)

def main():
    integrity()
    tests={}
    for name in ('focused','regression','regression_isolated'):
        p=WORK/(name+'.log')
        if p.exists():tests[name]=test_summary(p)
    write(REPORT/'tests.json',dict(runs=tests,
        initial_regression_investigation='The first full run had 200 passes and one existing historical_route_resources filesystem-scandir ENOMEM exception during concurrent routing. Original failure log retained. No test/source weakened; isolated full rerun determines final status.'))
    commands=dict(shell='Ubuntu-24.04 WSL bash',cwd=str(ROOT),
        environment={'PYTHONDONTWRITEBYTECODE':'1','OPENBLAS_NUM_THREADS':'1',
            'PYTHONPATH':'src:/mnt/d/PACT_EXPERIMENTS/cache/phase2a_python','TMPDIR':'/mnt/d/PACT_EXPERIMENTS/tmp',
            'MPLCONFIGDIR':'/mnt/d/PACT_EXPERIMENTS/cache/matplotlib'},
        commands=[
            '/root/pact-deps/pact-venv/bin/python scripts/phase2c_freeze.py',
            '/root/pact-deps/pact-venv/bin/python scripts/phase2c_run.py prepare',
            '/root/pact-deps/pact-venv/bin/python scripts/phase2c_run.py smoke',
            '/root/pact-deps/pact-venv/bin/python scripts/phase2c_run.py run --workers 4',
            '/root/pact-deps/pact-venv/bin/python scripts/phase2c_run.py baseline',
            '/root/pact-deps/pact-venv/bin/python scripts/phase2c_measure.py',
            '/root/pact-deps/pact-venv/bin/python scripts/phase2c_run.py snapshot',
            '/root/pact-deps/pact-venv/bin/python scripts/phase2c_measure.py (incremental; policy-interrupted)',
            'openroad -python -no_init -exit scripts/phase2c_bug_audit.py',
            '/root/pact-deps/pact-venv/bin/python scripts/phase2c_close_stop.py',
            '/root/pact-deps/pact-venv/bin/python scripts/phase2c_benchmark.py --engineering-only',
            '/root/pact-deps/pact-venv/bin/python -m pytest -q --capture=sys --basetemp=/mnt/d/PACT_EXPERIMENTS/pytest_tmp/phase2c_focused tests/unit/test_phase2c_events.py tests/unit/test_phase2c_decision.py tests/unit/test_phase2b_activity.py tests/unit/test_phase2a_shift.py tests/unit/test_phase2a_physical_stats.py',
            '/root/pact-deps/pact-venv/bin/python -m pytest -q --capture=sys --basetemp=/mnt/d/PACT_EXPERIMENTS/pytest_tmp/phase2c_regression_isolated',
            '/root/pact-deps/pact-venv/bin/python scripts/phase2c_engineering_report.py',
            '/root/pact-deps/pact-venv/bin/python scripts/phase2c_finalize.py'],
        normal_physical_report_command_not_executed='/root/pact-deps/pact-venv/bin/python scripts/phase2c_report.py (guarded after bug stop)',
        stop_action='Terminated only the descendants of the Phase-2C campaign and incremental measurement process trees after confirming the inherited bug. Preserved every attempt and partial log.',
        exact_subprocess_commands='All rewire/route/verify/RC/extraction commands, timeouts, input/output/log hashes and timestamps are in raw **/execution.json and per-cell result.json; benchmark commands in benchmark_raw.json.',
        setup_probe='A prepare invocation before freeze completion exited before accessing physical inputs (missing provenance.json). Retried only after freeze completion; no physical attempt consumed.')
    write(REPORT/'commands.json',commands)
    raw={}
    for p in sorted(WORK.rglob('*')):
        if p.is_file() and p.name!='raw_manifest.json':raw[str(p)]=file_sha256(p)
    write(WORK/'raw_manifest.json',raw)
    matrix=read(REPORT/'architecture_matrix.json')['rows']
    counts={s:sum(r['status']==s for r in matrix) for s in sorted({r['status'] for r in matrix})}
    source={str(p):file_sha256(p) for folder in ('scripts','src/pact/analysis','tests/unit') for p in (ROOT/folder).glob('*phase2c*.py')}
    write(REPORT/'source_provenance.json',dict(files=source,git_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        raw_manifest_path=str(WORK/'raw_manifest.json'),raw_manifest_sha256=file_sha256(WORK/'raw_manifest.json'),raw_files=len(raw)))
    native_status=REPORT/'git_status_native.txt'
    status=(native_status.read_text() if native_status.exists() else subprocess.check_output(
        ['git','--no-optional-locks','status','--short'],cwd=ROOT,text=True,timeout=30))
    (REPORT/'git_status_after.txt').write_text(status)
    write(REPORT/'integrity_audit.json',dict(status='PASS',completed_utc=datetime.now(timezone.utc).isoformat(),
        earlier_input_files_unchanged=len(read(REPORT/'provenance.json')['inputs']),
        earlier_evidence_and_dirty_work_unchanged=True,freeze_unchanged=True,matrix_status_counts=counts,
        new_optimizer_runs=0,new_ATPG_runs=0,new_placements=0,
        reused_seed11_evaluations=sum(r['seed']==11 and r['status']=='QUALIFIED' for r in matrix),
        new_route_attempts=len(list(WORK.glob('s*/s*/*/route/stdout.log'))),
        completed_new_routes=sum(r['status']=='QUALIFIED' and r['seed']!=11 and not r.get('reused_route',False) for r in matrix),
        interrupted_attempts=sum(r['status']=='INTERRUPTED_BY_BUG_STOP' for r in matrix),
        reused_non11_routes=sum(r.get('reused_route',False) for r in matrix),
        no_seed_specific_calibration=all(r['wire_cap_per_um']==.103981 for r in read(REPORT/'measurements.json')['rows']),
        raw_manifest_sha256=file_sha256(WORK/'raw_manifest.json')))
    final=REPORT/'FINAL_REPORT.md'
    if final.exists():
        body=final.read_text();marker='\n## Executed regression evidence\n'
        body=body.split(marker)[0]+marker+'\n'
        for name,run in tests.items():body+=f'- {name}: {run["counts"]}, {run["runtime_seconds"]} s.\n'
        body+='\nInitial ENOMEM was an OS/filesystem enumeration exception; the isolated rerun above is the final regression result. Old tests were not modified.\n'
        final.write_text(body)
    outputs={p.name:file_sha256(p) for p in sorted(REPORT.iterdir()) if p.is_file() and p.name!='result_provenance.json'}
    write(REPORT/'result_provenance.json',dict(files=outputs,source_manifest_sha256=file_sha256(REPORT/'source_provenance.json'),
        note='This manifest excludes itself to avoid a circular hash. Raw files are transitively hashed via raw_manifest.json.'))
    print('FINAL INTEGRITY PASS',len(raw),'raw files;',len(outputs),'compact outputs')

if __name__=='__main__':main()
