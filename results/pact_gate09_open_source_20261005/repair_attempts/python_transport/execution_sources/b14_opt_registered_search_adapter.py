def search(design, *, state_type=sf.State, reference_evaluator=sf.reference):
    folder=OUT/'searches'/design
    manifest=OUT/f'inputs/{design}/cold_start_input.json'
    contract_data=read(manifest)
    seconds=900
    configs=[solver.Config(epsilon=e,seconds=seconds,max_evaluations=20000,stagnation_attempts=2000) for e in (.02,.05,.10)]
    write(folder/'search_configuration.json',dict(design=design,created_utc=now(),seed=11,K=2,
        input=binding(manifest),configurations=[asdict(c) for c in configs],
        sources={p:binding(ROOT/p) for p in SOURCE_NAMES},initialization='external reference only',
        runtime_policy='Preregistered Gate-09 900 seconds per unchanged mutation loop'),immutable=True)
    start=time.perf_counter();usage_start=resource.getrusage(resource.RUSAGE_SELF)
    model,starts,contract=load(manifest)
    setup=time.perf_counter()-start
    write(folder/'initialization.json',dict(status='PASS',created_utc=now(),seconds=setup,
        initial_architecture_hash=contract.initial_architecture.sha256(),start_count=len(starts),
        labels=[label for label,_ in starts],historical_state_accesses=0,model=model.metadata),immutable=True)
    original_archive=solver.Archive
    lanes=[]
    for config in configs:
        out=folder/f'budget_{config.epsilon:.2f}'
        counts=dict(state_constructions=0,state_score_calls=0,state_score_seconds=0.,independent_replays=0,independent_replay_seconds=0.)
        archives=[];discoveries={};profile_before=model.profile.copy()
        class CountArchive(original_archive):
            def __init__(self,*args,**kwargs):
                super().__init__(*args,**kwargs);archives.append(self)
            def insert(self,score,orders,label):
                admitted=super().insert(score,orders,label)
                frame=inspect.currentframe().f_back
                row=frame.f_locals.get('row')
                champions=frame.f_locals.get('champions')
                if row is not None and champions is not None:
                    values=frame.f_locals['values']
                    if any(old is None or value<values(old['score'])[i]-1e-10*max(1.,abs(value))
                           for i,(value,old) in enumerate(zip(values(row['score']),champions))):
                        parent=frame.f_back.f_locals
                        oid=model.canonical_id(orders)
                        discoveries.setdefault(oid,dict(discovered_evaluation=parent.get('evaluations',0),
                            discovered_attempt=parent.get('attempts',0),discovered_utc=now(),
                            discovered_loop_seconds=time.perf_counter()-parent['search_began'] if 'search_began' in parent else 0.))
                return admitted
        class CountState(state_type):
            def __init__(self,*args,**kwargs):
                counts['state_constructions']+=1;super().__init__(*args,**kwargs)
            def score(self):
                tick=time.perf_counter();value=super().score()
                counts['state_score_calls']+=1;counts['state_score_seconds']+=time.perf_counter()-tick
                return value
        def replay(m,o):
            tick=time.perf_counter();value=reference_evaluator(m,o)
            counts['independent_replays']+=1;counts['independent_replay_seconds']+=time.perf_counter()-tick
            return value
        last_progress={}
        def progress(row):
            frame=inspect.currentframe().f_back.f_back
            augmented=dict(row,stagnation_attempts=frame.f_locals.get('stagnation'),
                lane=frame.f_locals.get('lane'))
            last_progress.update(augmented)
            write(out/'progress.json',augmented)
            print(design,config.epsilon,'PROGRESS',round(row['seconds'],1),row['evaluations'],row['accepted'],flush=True)
        solver.Archive=CountArchive
        try:
            result=solver.optimize(model,starts,contract.data['reference_method'],config,
                state_type=CountState,reference_evaluator=replay,checkpoint=progress)
        finally:
            solver.Archive=original_archive
        def package(row):
            arch=model.architecture_from(row['orders'])
            path=out/'architectures'/f'{arch.sha256()}.json'
            arch.to_json(path)
            return {k:v for k,v in row.items() if k not in ('orders','score')}|dict(
                architecture=external_binding(path),architecture_sha256=arch.sha256(),
                parent_architecture_sha256=contract.data['reference_architecture_hash'],
                chain_sizes=list(map(len,row['orders'])),metrics=dict(zip(METRICS,map(float,row['score']))),
                **discoveries.get(arch.sha256(),{}))
        result['selected']=[package(r) for r in result['selected']]
        result['baselines']=[package(r) for r in result['baselines']]
        result['reference_score']=result['reference_score'].tolist()
        result.update(config=asdict(config),instrumentation=counts,
            rejected_exact_moves=result['evaluations']-result['accepted'],
            archive_insertions=archives[0].admissions,initial_reference_archive_insertions=1,
            restarts=counts['state_constructions']-len(starts)-1,
            final_stagnation_attempts=last_progress.get('stagnation_attempts'),
            stagnation_termination_events=int(result['termination']=='stagnation'),
            model_profile={k:model.profile[k]-profile_before.get(k,0.) for k in model.profile})
        write(out/'search.json',result,immutable=True)
        lanes.append(dict(epsilon=config.epsilon,receipt=binding(out/'search.json')))
        print('COLD_START_SEARCH_LANE_COMPLETE',design,config.epsilon,result['evaluations'],result['termination'],flush=True)
    usage=resource.getrusage(resource.RUSAGE_SELF)
    write(folder/'search_results.json',dict(design=design,status='SEARCH_COMPLETE',created_utc=now(),
        lanes=lanes,input=binding(manifest),configuration=binding(folder/'search_configuration.json'),
        initialization=binding(folder/'initialization.json'),model_setup_seconds=setup,
        wall_seconds=time.perf_counter()-start,CPU_seconds=usage.ru_utime+usage.ru_stime-usage_start.ru_utime-usage_start.ru_stime,
        peak_RSS_KiB=usage.ru_maxrss,total_exact_mutation_evaluations=sum(read(ROOT/r['receipt']['path'].removeprefix('repo://'))['evaluations'] for r in lanes)),immutable=True)
    select(design)
