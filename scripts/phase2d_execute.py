"""Bounded Phase-2D execution; no retries, optimization or upstream mutations."""
from phase2d_common import *
import shutil
import tempfile
import xml.etree.ElementTree as ET
import inspect

def gp():
    verify_contract()
    for d in DESIGNS:
        ex=run('initialize_'+d,['openroad','-python','-no_init','-exit',ROOT/'scripts/phase2d_initialize.py',d],120)
        if ex['exit_code']!=0:raise RuntimeError('INITIALIZATION_STOP '+d)
        dest=placement(d)
        shutil.copyfile(source(d)/'2_floorplan.sdc',dest/'2_floorplan.sdc')
        # Mark only verified pre-GP inputs old. All global-placement stages execute.
        cmd=['make','-o',str(dest/'2_floorplan.odb'),'-o',str(dest/'2_floorplan.sdc'),
             'DESIGN_CONFIG='+str(config(d)),'FLOW_VARIANT=phase2d_gp29','WORK_HOME='+str(OUT/'orfs'),
             'OPENROAD_EXE=/usr/bin/openroad','YOSYS_EXE=/usr/bin/yosys','NUM_CORES=2',
             'GLOBAL_PLACEMENT_ARGS=-skip_initial_place',
             'PRE_GLOBAL_PLACE_SKIP_IO_TCL='+str(ROOT/'scripts/phase2d_gp_hook.tcl'),
             'PRE_GLOBAL_PLACE_TCL='+str(ROOT/'scripts/phase2d_gp_hook.tcl'),'place']
        ex=run('gp_'+d,cmd,600,FLOW)
        if ex['exit_code']!=0 or not (dest/'3_place.odb').is_file():raise RuntimeError('GLOBAL_PLACEMENT_STOP '+d)
    verify_contract()

def tests(stage):
    temp=tempfile.mkdtemp(prefix='pact-phase2d-tests-')
    env=dict(ENV,TMPDIR=temp,MPLCONFIGDIR=temp+'/mpl')
    cmd=[sys.executable,'-m','pytest','-q','--capture=sys','-p','no:cacheprovider',
         '--basetemp='+temp+'/tests','--junitxml='+str(OUT/(stage+'.xml'))]
    if stage.startswith('focused'):
        cmd+=['tests/unit/test_phase2cr_loads.py','tests/unit/test_phase2crm_validation.py']
        if stage!='focused':cmd+=['tests/unit/test_phase2d_decision.py']
    ex=run(stage,cmd,600,env=env)
    if (OUT/(stage+'.xml')).exists():
        root=ET.parse(OUT/(stage+'.xml')).getroot()
        suites=[root] if root.tag=='testsuite' else list(root)
        counts={k:sum(int(s.get(k,0)) for s in suites) for k in ('tests','failures','errors','skipped')}
        ex.update(counts,passed=counts['tests']-counts['failures']-counts['errors']-counts['skipped'])
    path=OUT/'tests.json';record=read(path) if path.exists() else {}
    record[stage]=ex;write(path,record)
    print(ex,flush=True)

def physical():
    verify_contract()
    assert read(OUT/'independent_placement_proof.json')['status']=='PASS'
    import phase2c_run as frozen
    original=inspect.getsource(frozen.run_one)
    adapted=original.replace("ROOT/'scripts/phase2c_physical.py'", "ROOT/'scripts/phase2d_physical.py'")
    assert adapted!=original and adapted.replace('phase2d_physical.py','phase2c_physical.py')==original
    ns=dict(frozen.__dict__)
    ns.update(REPORT=OUT,WORK=OUT/'raw',base=lambda d,s:placement(d),placed_def=lambda d,s:placement(d)/'placed.def')
    exec(compile(adapted,'<phase2d-source-only-route-adapter>','exec'),ns)
    write(OUT/'route_adapter.json',dict(sole_source_substitution=['phase2c_physical.py','phase2d_physical.py'],
          other_adaptations='Output roots, source placement and DEF paths only',original_source=original,adapted_source=adapted))
    jobs=[j for d in DESIGNS for j in read(OUT/'raw'/d/'s29'/'prepared.json')['jobs']]
    assert len(jobs)==21
    rows=[]
    for j in jobs:
        assert not (Path(j['architecture_path']).parent/'attempt.json').exists()
        result=ns['run_one'](j);rows.append(result)
        write(OUT/'physical_results.json',dict(rows=rows,new_exact_order_implementations=sum('route_execution' in r for r in rows)))
        if result['status']!='QUALIFIED':raise RuntimeError('PHYSICAL_STOP '+str(result))
    verify_contract()

if __name__=='__main__':
    if sys.argv[1]=='gp':gp()
    elif sys.argv[1]=='prepare':
        ex=run('prepare',['openroad','-python','-no_init','-exit',ROOT/'scripts/phase2d_physical.py','prepare'],180)
        if ex['exit_code']!=0:raise RuntimeError('PREPARE_STOP')
    elif sys.argv[1]=='physical':physical()
    elif sys.argv[1] in ('topology','measure','report'):
        stage=sys.argv[1]
        cmd=[sys.executable,ROOT/('scripts/phase2d_report.py' if stage=='report' else 'scripts/phase2d_validate.py')]
        if stage!='report':cmd.append(stage)
        ex=run(stage,cmd,900)
        if ex['exit_code']!=0:raise RuntimeError(stage.upper()+'_STOP')
    else:tests(sys.argv[1])
