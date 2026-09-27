"""Bounded physical jobs in the new directory; inherited route flow unchanged."""
from phase2crm_audit import *
import os
import shutil
import tempfile
import xml.etree.ElementTree as ET

ENV=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',
    PYTHONPATH=str(ROOT/'src')+':/mnt/d/PACT_EXPERIMENTS/cache/phase2a_python')

def verify():
    for p,h in read(OUT/'freeze.json')['files'].items():check(p,h)
    b=read(OUT/'initial_integrity.json')
    for p,h in dict(b['frozen_sources'],**b['seed11_files']).items():check(p,h)

def run(stage,cmd,timeout=600):
    path=OUT/(stage+'.log'); assert not path.exists(),path
    start=time.perf_counter();temp=tempfile.mkdtemp(prefix='pact-multiseed-')
    env=dict(ENV,TMPDIR=temp,MPLCONFIGDIR=temp+'/mpl')
    with path.open('w') as f:
        p=subprocess.run(cmd,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
    record=dict(stage=stage,command=cmd,exit_code=p.returncode,runtime_seconds=time.perf_counter()-start,
        stdout_stderr=str(path),log_sha256=sha(path),environment={k:env[k] for k in ('PYTHONPATH','PYTHONDONTWRITEBYTECODE','OPENBLAS_NUM_THREADS','TMPDIR')},utc=now())
    cp=OUT/'commands.json'; commands=read(cp) if cp.exists() else dict(environment=dict(python=sys.version,platform=platform.platform()),runs=[])
    commands['runs'].append(record);write(cp,commands)
    if stage in ('focused','regression'):
        root=ET.parse(OUT/(stage+'.xml')).getroot()
        ss=[root] if root.tag=='testsuite' else list(root)
        counts={k:sum(int(s.get(k,0)) for s in ss) for k in ('tests','failures','errors','skipped')}
        record.update(counts,passed=counts['tests']-counts['failures']-counts['errors']-counts['skipped'])
        tp=OUT/'tests.json'; tests=read(tp) if tp.exists() else {};tests[stage]=record;write(tp,tests)
    print(json.dumps(record),flush=True)
    if p.returncode:raise RuntimeError(stage+' failed; see '+str(path))

def physical():
    verify(); contract=read(OUT/'multiseed_contract.json'); matrix=read(C/'architecture_matrix.json')['rows']
    import phase2c_run as route
    route.REPORT=OUT;route.WORK=OUT/'raw'
    # Only new output roots change; no change to rewire, verification, route or RC commands.
    results=[];jobs=[]
    for c in contract['cells']:
        old=next(r for r in matrix if (r['design'],r['seed'],r['label'])==(c['design'],c['seed'],c['label']))
        if c['seed']==11 or c['spef_available']:
            results.append(dict(old,multiseed_reused=True));continue
        d,s,label=c['design'],c['seed'],c['label'];folder=OUT/'raw'/d/f's{s}'/label
        folder.mkdir(parents=True,exist_ok=True)
        ap=folder/'architecture.json'; assert not ap.exists();shutil.copyfile(c['architecture_path'],ap)
        job=next(j for j in read(CW/d/f's{s}'/'prepared.json')['jobs'] if j['label']==label)
        jobs.append(dict(job,architecture_path=str(ap)))
    write(OUT/'physical_plan.json',dict(jobs=jobs,reused=len(results),new_routes_max=contract['routing']['new_routes_max']))
    from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
    pending_jobs=iter(jobs)
    with ThreadPoolExecutor(max_workers=2) as pool:
        active={pool.submit(route.run_one,j):j for j in [next(pending_jobs),next(pending_jobs)]}
        while active:
            done,_=wait(active,return_when=FIRST_COMPLETED)
            for future in done:
                active.pop(future);result=future.result();results.append(result)
                write(OUT/'physical_results.json',dict(rows=results))
                if result['status']!='QUALIFIED':raise RuntimeError('PHYSICAL_STOP: '+str(result))
            for _ in done:
                job=next(pending_jobs,None)
                if job is not None:active[pool.submit(route.run_one,job)]=job
    assert sum(not r.get('multiseed_reused') and not r.get('reused_route') for r in results)<=contract['routing']['new_routes_max']
    write(OUT/'physical_results.json',dict(rows=results))
    print('PHYSICAL_COMPLETE',len(results),flush=True)

def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['graphs','physical','campaign','focused','regression']);a=parser.parse_args()
    if a.stage=='physical':physical();return
    if a.stage=='campaign':
        run('physical_campaign',[sys.executable,str(Path(__file__)),'physical'],22000);return
    verify()
    if a.stage=='graphs':cmd=['openroad','-python','-no_init','-exit',str(ROOT/'scripts/phase2crm_physical.py')]
    else:
        cmd=[sys.executable,'-m','pytest','-q','--capture=sys','-p','no:cacheprovider',
             '--basetemp='+tempfile.mkdtemp(prefix='pact-multiseed-pytest-')+'/tests','--junitxml='+str(OUT/(a.stage+'.xml'))]
        if a.stage=='focused':cmd+=['tests/unit/test_phase2cr_loads.py','tests/unit/test_phase2crm_validation.py']
    run(a.stage,cmd,600)

if __name__=='__main__':main()
