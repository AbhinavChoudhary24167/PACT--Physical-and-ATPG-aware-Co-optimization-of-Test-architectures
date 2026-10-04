"""Protect prospective scientific interpretation from missing-data shortcuts."""
import json
import pytest
import pact_cold_start_report as report
from pact_cold_start_report import activity_category, profile_summary, relation, scientific_assessment


@pytest.fixture
def reporter_directories(tmp_path, monkeypatch):
    monkeypatch.setattr(report,'OUT',tmp_path/'current')
    monkeypatch.setattr(report,'PREVIOUS',tmp_path/'previous')
    monkeypatch.setattr(report,'binding',lambda p:dict(path=str(p),sha256=report.sha(p)))
    def save(path,data):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(data),encoding='utf-8')
    return save


def test_unavailable_exact_activity_never_becomes_a_benefit():
    category, relations = activity_category(dict(E=80, H4=None, H8=9), dict(E=100, H4=20, H8=10))
    assert category is None
    assert relations == {}


def test_measured_alternative_regression_remains_mixed():
    reference = dict(E=306019.16041981, H4=141.79185422, H8=63.23074092)
    primary = dict(E=243554.84719727, H4=128.57546064, H8=56.09291641)
    alternative = dict(E=293092.9600281, H4=138.56759178, H8=65.30057435)
    assert activity_category(primary, reference)[0] == 'PACT_STRONG_IMPROVEMENT'
    category, relations = activity_category(alternative, reference)
    assert category == 'PACT_MIXED_TRADEOFF'
    assert relations == dict(E='improved', H4='improved', H8='regressed')


def test_fixed_equality_tolerance_and_partial_improvement():
    assert relation(100 - 5e-9, 100) == 'equal'
    assert relation(100 - 2e-8, 100) == 'improved'
    category, relations = activity_category(dict(E=90, H4=20, H8=10), dict(E=100, H4=20, H8=10))
    assert category == 'PACT_MIXED_TRADEOFF'
    assert relations == dict(E='improved', H4='equal', H8='equal')


def test_structural_blocks_do_not_become_negative_scientific_evidence():
    data = dict(design_outcomes=[dict(eligible=False, search_completed=False, failure_class='SCAN_TOPOLOGY_FAIL')],
        counts=dict(designs_with_physically_qualified_candidate=1, designs_with_useful_activity_improvement=1,
            designs_with_mixed_or_no_improvement=0, designs_improving_all_three=1, designs_blocked=2),
        physical_measurement_scalability=[])
    assert scientific_assessment(data) == ('CAMPAIGN_ACTIVE_SNAPSHOT', [])
    assert scientific_assessment(data, sealed=True) == ('PACT_COLD_START_GENERALIZATION_SUPPORTED', [])


def test_epsilon_profiles_sum_only_exclusive_component_increments():
    rows = [dict(design='new', FF_count=20, ATPG_pattern_count=10,
                 model_profile=dict(geometry_seconds=2, scan_waveform_seconds=1)),
            dict(design='new', FF_count=20, ATPG_pattern_count=10,
                 model_profile=dict(geometry_seconds=3, scan_waveform_seconds=4))]
    summary = profile_summary(dict(solver_scalability=rows))[0]
    assert summary['components'] == dict(geometry_seconds=5, scan_waveform_seconds=5)
    assert summary['largest_component_seconds'] == 5


def test_old_timeout_and_input_package_do_not_terminate_or_initialize_new_unit(reporter_directories):
    save=reporter_directories
    save(report.PREVIOUS/'physical/new/reference_measurement/result.json',dict(status='FAILED',failure_class='RESOURCE_LIMIT'))
    save(report.OUT/'inputs/new/cold_start_input.json',dict(historical_state_required=False))
    assert report.terminal_design_stop('new','B2') is None
    assert report.initialization_evidence('new')['initialized'] is False


def test_new_reference_timeout_stops_only_that_design_without_inventing_initialization(reporter_directories):
    save=reporter_directories
    save(report.OUT/'physical/new/REF_B2/activity/result.json',dict(status='FAILED',failure_class='RESOURCE_LIMIT'))
    stop=report.terminal_design_stop('new','B2')
    assert stop['terminal'] is True
    assert stop['failure_domain']=='MEASUREMENT'
    assert stop['blocker_subtype']=='REFERENCE_EXACT_ACTIVITY'
    assert report.initialization_evidence('new')['initialized'] is False
    assert report.terminal_design_stop('other','B2') is None


def test_actual_loader_diagnostic_pass_counts_initialization_only(reporter_directories):
    save=reporter_directories
    path=report.OUT/'scalability/new_initialization_diagnostic.json'
    save(path,dict(status='FAILED'))
    assert report.initialization_evidence('new')['initialized'] is False
    manifest=report.OUT/'inputs/new/cold_start_input.json'
    save(manifest,dict(reference_architecture_hash='reference_hash',reference_method='B2'))
    configuration=report.OUT/'scalability/new_initialization_diagnostic_configuration.json'
    save(configuration,dict(input=report.binding(manifest),sources={}))
    save(path,dict(status='PASS',configuration=report.binding(configuration),optimizer_executions=0,
        candidate_evaluations=0,search_completed=False,start_count=1,exact_roundtrip='PASS',
        initial_architecture_hash='reference_hash',labels=['B2']))
    evidence=report.initialization_evidence('new')
    assert evidence['initialized'] is True
    assert evidence['initialization_scope'].startswith('LOADER_ONLY_DIAGNOSTIC')
    assert 'search_completed' not in evidence


def test_explicit_measurement_stop_is_a_terminal_measurement_event(reporter_directories):
    save=reporter_directories
    save(report.OUT/'failures/new_campaign_stop.json',dict(design='new',status='PACT_EXECUTION_BLOCKED',
        stage='REFERENCE_EXACT_ACTIVITY',failure_class='RESOURCE_LIMIT',reason='Exact deadline reached'))
    stop=report.terminal_design_stop('new','B3T')
    assert stop['terminal'] is True
    assert stop['failure_domain']=='MEASUREMENT'


def test_measurement_resource_failure_does_not_become_solver_failure():
    data=dict(design_outcomes=[dict(eligible=True,search_completed=False,failure_class='RESOURCE_LIMIT',failure_domain='MEASUREMENT')],
        counts=dict(designs_with_physically_qualified_candidate=1,designs_with_useful_activity_improvement=1,
            designs_with_mixed_or_no_improvement=0,designs_improving_all_three=1),
        physical_measurement_scalability=[],measurement_worker_failures=[])
    primary,secondary=scientific_assessment(data,sealed=True)
    assert primary=='PACT_COLD_START_GENERALIZATION_SUPPORTED'
    assert secondary==['PACT_COLD_START_MEASUREMENT_SCALABILITY_BLOCKED']


def test_additive_evaluator_subtotal_excludes_score_overlap_and_loop_subtraction():
    lane=dict(model_profile=dict(zip(report.EVALUATOR_COMPONENTS,(1,2,3,4,5,6))),
        instrumentation=dict(state_score_seconds=1000,independent_replay_seconds=2),
        search_seconds=0.1,runtime_seconds=25)
    accounting=report.evaluator_accounting(lane)
    assert accounting['evaluator_measured_component_seconds']==21
    assert accounting['lane_unattributed_seconds']==2
    assert accounting['solver_overhead_seconds'] is None


def test_computational_bottleneck_observation_keeps_throughput_and_profile_domains():
    small=dict(design='small',FF_count=18,exact_mutation_evaluations_per_second=200)
    large=dict(design='large',FF_count=1728,ATPG_pattern_count=21,epsilon=.02,
        exact_mutation_evaluations=269,search_loop_seconds=901.8,
        exact_mutation_evaluations_per_second=269/901.8,
        model_profile=dict(spatial_seconds=433.7,rollback_seconds=372.7,geometry_seconds=1))
    observation=report.solver_bottleneck_observation(dict(solver_scalability=[small,large]))
    assert observation['evaluations_per_second']==269/901.8
    assert observation['largest_instrumented_evaluator_spans']==[
        dict(component='spatial_seconds',seconds=433.7),dict(component='rollback_seconds',seconds=372.7)]
    assert observation['small_observed_evaluations_per_second_range']==[200,200]
    assert observation['resource_policy_failure'] is False


@pytest.fixture
def physical_start_evidence(reporter_directories):
    save=reporter_directories
    def receipt(folder,name,second,**fields):
        path=report.OUT/folder/name
        save(path,dict(created_utc=f'2026-10-04T00:00:{second:02d}+00:00',**fields))
        return path
    receipt('references/new','reference_frozen.json',1)
    manifest=receipt('inputs/new','cold_start_input.json',2)
    receipt('searches/new','search_configuration.json',3)
    receipt('searches/new','search_results.json',4)
    records=[]
    for candidate in ('CS_C1','CS_C2'):
        path=report.OUT/f'searches/new/{candidate}.json'
        save(path,dict(candidate=candidate))
        records.append(dict(candidate=candidate,architecture_hash=candidate+'_hash',architecture=report.binding(path)))
    selection=receipt('selections/new','preselected_candidates.json',5,records=records)
    snapshot=receipt('physical/new','selection_snapshot.json',6,selection=report.binding(selection),
        input=report.binding(manifest),records=records,executed_sources={},all_candidates_frozen_before_any_candidate_routing=True)
    execution=report.OUT/'physical/new/CS_C1/rewire/execution.json'
    save(execution,dict(command=['openroad','--architecture',records[0]['architecture']['path']],
        timestamp_utc='2026-10-04T00:00:09+00:00',wall_seconds=2,exit_code=0,timed_out=False))
    receipt('physical/new/CS_C1','route_result.json',10,status='PHYSICAL_GATES_PASS')
    receipt('atpg/new/CS_C1','atpg_result.json',11,status='ATPG_GATES_PASS')
    return save,snapshot,execution,manifest,records


def test_preselection_start_proof_binds_snapshot_all_candidates_and_execution(physical_start_evidence):
    _,snapshot,execution,_,_=physical_start_evidence
    audit=report.audit_order('new','CS_C1')
    assert audit['status']=='PASS'
    assert audit['preselection_before_physical_implementation'] is True
    proof=audit['physical_execution_start_proof']
    assert proof['selection_snapshot']==report.binding(snapshot)
    assert proof['rewire_execution']==report.binding(execution)
    assert proof['execution_start_derived_utc']=='2026-10-04T00:00:07+00:00'
    assert 'not a separately recorded' in proof['start_time_basis']


def test_completion_after_selection_cannot_hide_execution_before_selection(physical_start_evidence):
    save,_,execution,_,_=physical_start_evidence
    value=report.read(execution);value['wall_seconds']=5;save(execution,value)
    # Completion remains after selection, but implementation began beforehand.
    with pytest.raises(ValueError,match='chronology'):
        report.audit_order('new','CS_C1')


def test_successful_physical_completion_alone_is_not_start_proof(physical_start_evidence):
    _,_,execution,_,_=physical_start_evidence
    execution.unlink()
    with pytest.raises(ValueError,match='actual preselection-before-execution proof'):
        report.audit_order('new','CS_C1')


def test_selection_snapshot_cannot_drop_a_retained_alternative(physical_start_evidence):
    save,snapshot,_,_,_=physical_start_evidence
    value=report.read(snapshot);value['records']=value['records'][:1];save(snapshot,value)
    with pytest.raises(ValueError,match='frozen candidate list'):
        report.audit_order('new','CS_C1')


def test_selection_snapshot_input_binding_is_validated(physical_start_evidence):
    save,_,_,manifest,_=physical_start_evidence
    save(manifest,dict(changed=True))
    with pytest.raises(ValueError,match='Evidence binding changed'):
        report.audit_order('new','CS_C1')


def test_rewire_command_cannot_use_another_preselected_architecture(physical_start_evidence):
    save,_,execution,_,records=physical_start_evidence
    value=report.read(execution);value['command'][-1]=records[1]['architecture']['path'];save(execution,value)
    with pytest.raises(ValueError,match='architecture differs'):
        report.audit_order('new','CS_C1')


def test_both_new_independent_reference_timeouts_have_explicit_separate_prose():
    rows=[]
    for design,method,wall,rss in (('s38417','B2',1800.314,1302900),('s38584','B3T',1800.277,1446208)):
        rows.append(dict(design=design,candidate='REF_'+method,status='FAILED',failure_class='RESOURCE_LIMIT',
            fixed_deadline_seconds=1800,total_wall_seconds=wall,CPU_seconds=1400,peak_RSS_KiB=rss,
            simulation=dict(timed_out=True,wall_seconds=1720,CPU_seconds=1350,peak_RSS_KiB=290000),
            VCD=dict(complete=False,bytes=2000000000),terminal_diagnosis=dict(parser_transition_and_E_H_stages_executed=False),
            result=dict(path=design+'/result.json'),terminal_diagnosis_receipt=dict(path=design+'/new_diagnosis.json')))
    prose=report.reference_failure_prose(dict(physical_measurement_scalability=rows))
    assert len(prose)==3
    assert prose[0].startswith('Earlier campaign measurement evidence (separate from new attempts)')
    assert 'do not terminate a new campaign unit' in prose[0]
    for row,line in zip(rows,prose[1:]):
        assert 'New independent '+row['design']+' '+row['candidate'] in line
        assert '1800-second deadline' in line
        assert f'Workflow wall {row["total_wall_seconds"]:.3f} s' in line
        assert str(row['peak_RSS_KiB'])+' KiB' in line
        assert 'exact E/H4/H8 stages were not executed' in line
        assert 'Only this design stops' in line
