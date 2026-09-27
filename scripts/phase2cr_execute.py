"""Log each authorized continuation stage without replacing attempt-1 logs."""
from phase2cr_common import *
import argparse
import importlib.metadata
import os
import platform
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['focused','witness','sanity','topology','weights','measure','statistics','regression','regression_isolated','finalize'])
    stage = parser.parse_args().stage
    tests_path = REPORT/'tests.json'
    tests = read(tests_path)
    if 'attempt1' not in tests:
        tests = dict(attempt1=tests, continuation={}, initial_environmental_failures=[
            'WSL enumeration E_ACCESSDENIED under sandbox; elevated WSL access succeeded.'])
    tests['environment'] = dict(python=sys.version, executable=sys.executable, platform=platform.platform(),
        packages={p:importlib.metadata.version(p) for p in ('numpy','scipy','pytest')})
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(ROOT/'src'), OPENBLAS_NUM_THREADS='1')
    if stage in ('focused','regression','regression_isolated'):
        if stage.startswith('regression'):
            assert read(REPORT/'qualification.json')['scientific_seed11_classification'].startswith('PACT_PHASE2CR_SEED11_')
        if stage == 'regression_isolated':
            cache=Path('/mnt/d/PACT_EXPERIMENTS/cache/phase2a_python')
            assert (cache/'threadpoolctl.py').is_file()
            env['PYTHONPATH'] += ':'+str(cache)
            tests['dependency_cache']=dict(path=str(cache),threadpoolctl_sha256=sha(cache/'threadpoolctl.py'))
            tests['initial_environmental_failures'].append('Initial continuation regression: 3 collection errors, missing threadpoolctl; restored historical phase2a_python dependency cache on PYTHONPATH without changing tests.')
        temp = tempfile.mkdtemp(prefix='pact-phase2cr-'+stage+'-')
        env.update(TMPDIR=temp, MPLCONFIGDIR=temp+'/matplotlib')
        cmd = [sys.executable,'-m','pytest','-q','--capture=sys','-p','no:cacheprovider',
               '--basetemp='+temp+'/pytest','--junitxml='+str(REPORT/(stage+'_continuation.xml'))]
        if stage == 'focused': cmd += ['tests/unit/test_phase2cr_loads.py']
    else:
        if stage == 'witness': assert tests['continuation']['focused']['status']=='PHASE2CR_FOCUSED_TESTS_PASS'
        if stage == 'topology':
            assert read(REPORT/'representative_witness.json')['status']=='PASS'
            assert read(REPORT/'implementation_sanity.json')['status']=='PASS'
        if stage == 'measure': assert read(REPORT/'weight_change_audit.json')['status']=='PASS'
        if stage == 'statistics': assert (REPORT/'corrected_metrics.json').exists()
        script = 'phase2cr_run.py' if stage in ('witness','topology','measure') else 'phase2cr_continue.py'
        cmd = [sys.executable,str(ROOT/'scripts'/script),stage]
    log = REPORT/(stage+'_continuation.log')
    assert not log.exists(), 'Refuse to overwrite continuation log'
    start = time.perf_counter()
    with log.open('w') as out:
        run = subprocess.run(cmd,cwd=ROOT,env=env,stdout=out,stderr=subprocess.STDOUT)
    rec = dict(command=cmd,environment_overrides={k:env[k] for k in ('PYTHONPATH','PYTHONDONTWRITEBYTECODE','OPENBLAS_NUM_THREADS')},
        exit_code=run.returncode,runtime_seconds=time.perf_counter()-start,log=str(log),log_sha256=sha(log),observed_utc=now())
    if stage in ('focused','regression','regression_isolated'):
        suite = ET.parse(REPORT/(stage+'_continuation.xml')).getroot()
        suites = [suite] if suite.tag=='testsuite' else list(suite)
        counts = {k:sum(int(s.get(k,0)) for s in suites) for k in ('tests','failures','errors','skipped')}
        rec.update(passed=counts['tests']-counts['failures']-counts['errors']-counts['skipped'],
            failed=counts['failures'], errors=counts['errors'], skipped=counts['skipped'], isolated_temp=temp,
            source_sha256=sha(ROOT/'tests/unit/test_phase2cr_loads.py'),
            status=('PHASE2CR_FOCUSED_TESTS_PASS' if stage=='focused' else 'COMPLETE_REGRESSION_PASS') if run.returncode==0 else 'FAIL')
        tests['continuation'][stage] = rec
        write(tests_path,tests)
    commands = read(REPORT/'commands.json')
    if 'attempt1' not in commands: commands = dict(attempt1=commands,continuation=[])
    commands['continuation'].append(dict(stage=stage,**rec))
    write(REPORT/'commands.json',commands)
    if stage == 'finalize' and run.returncode == 0:
        source = {str(p):sha(p) for folder in (ROOT/'scripts',ROOT/'src/pact/analysis',ROOT/'tests/unit')
                  for p in sorted(folder.glob('*phase2cr*')) if p.is_file()}
        write(REPORT/'source_provenance.json',dict(attempt1=read(REPORT/'attempt1/source_provenance.json'),
            continuation_files=source,historical_inputs_unchanged=True,predictor_definition_unchanged=True))
        write(REPORT/'result_provenance.json',dict(completed_utc=now(),
            files={str(p.relative_to(REPORT)):sha(p) for p in sorted(REPORT.rglob('*'))
                   if p.is_file() and p != REPORT/'result_provenance.json'},
            sources=source,original_stop_preserved=True,freeze_sha256=sha(REPORT/'freeze.json'),
            audit_command=[sys.executable,'scripts/phase2cr_continue.py','audit'],
            verification_command=[sys.executable,'scripts/phase2cr_continue.py','verify'],
            note='Manifest excludes itself; includes original attempt1/result_provenance.json. All frozen inputs verified by unchanged integrity().'))
    print(log.read_text(),flush=True)
    print(json.dumps(rec),flush=True)
    if run.returncode: raise SystemExit(run.returncode)


if __name__ == '__main__': main()
