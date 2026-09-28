"""Keep compact reproducible evidence, hash local intermediates, verify a replay."""
from physical_effect import *
import xml.etree.ElementTree as ET

def replay():
    from pact.physical_effect import analyze
    folder=OUT/'s5378/P'
    names=['activity_summary.json','spatial_bins.json','net_activity_capacitance.csv','per_cycle.csv','FF_transition_crosscheck.json']
    before={p:sha(folder/p) for p in names}
    analyze(folder)
    after={p:sha(folder/p) for p in names}
    assert before==after, 'Nondeterministic analysis replay'
    write(OUT/'deterministic_replay.json',dict(status='PASS',design='s5378',architecture='P',
        source='Same full timestamped VCD independently reread; all displayed/CSV summaries exactly match',before=before,after=after))

def seal():
    manifest=read(OUT/'manifest.json')
    for row in manifest['rows']:
        folder=OUT/row['design']/row['role']
        simulation=read(folder/'simulation_manifest.json')
        for value in simulation['inputs'].values(): check_binding(value)
        summary=read(folder/'activity_summary.json')
        assert sha(folder/'activity.vcd')==summary['VCD']['sha256']
        assert read(folder/'functional_verification.json')['status']=='PASS'
        assert read(folder/'topology_verification.json')['status']=='PASS'
        assert read(folder/'FF_transition_crosscheck.json')['status']=='PASS'
        assert 'PASS patterns=' in (folder/'simulate.log').read_text()
        # Per-cycle data and executable stimulus are supplied compressed, while
        # larger lossless activity arrays remain local with hashes/reproduction.
        for leaf in ('per_cycle.csv','stimulus.v','cycles.json'):
            with (folder/leaf).open('rb') as f, (folder/(leaf+'.gz')).open('wb') as out:
                with gzip.GzipFile(fileobj=out,mode='wb',mtime=0,filename='') as g: shutil.copyfileobj(f,g)
        local=['activity.vcd','extracted.spef','routed.odb','simulation.vvp','transitions.npz']
        write(folder/'analysis_manifest.json',dict(schema='pact_physical_analysis_v1',
            design=row['design'],architecture_role=row['role'],architecture_sha256=row['architecture_sha256'],
            physical_qualification=row['qualification'],routed_archive=row['routed_archive'],SDC=row['SDC'],
            local_intermediates={p:dict(bind(folder/p),bytes=(folder/p).stat().st_size) for p in local},
            retained_compressed={p:bind(folder/(p+'.gz')) for p in ('per_cycle.csv','stimulus.v','cycles.json')},
            provenance=bind(folder/'simulation_manifest.json'),
            generation='python scripts/physical_effect.py run --design '+row['design'],
            analysis_elapsed_upper_bound_seconds=(folder/'transitions.npz').stat().st_mtime-(folder/'simulate.execution.json').stat().st_mtime,
            analysis_timing_method='Artifact timestamp interval from simulation completion record to final count archive; includes any reanalysis and idle gap, not CPU time',
            stage_seconds={n:read(folder/(n+'.execution.json'))['seconds'] for n in ('export','extract','compile','simulate')}))
    suite=ET.parse(OUT/'regression.xml').getroot().find('testsuite')
    assert suite is not None and int(suite.get('failures'))==int(suite.get('errors'))==0
    write(OUT/'validation_summary.json',dict(full_regression=dict(suite.attrib),focused_tests=8,
        deterministic_replay=read(OUT/'deterministic_replay.json')['status'],
        architecture_comparisons=9,patterns=3*(117+156+133),logical_patterns=117+156+133,
        shift_cycles=sum(r['shift_cycles'] for r in manifest['rows']),
        FF_cycle_values_checked=sum(read(OUT/r['design']/r['role']/'FF_transition_crosscheck.json')['FF_cycle_values_checked'] for r in manifest['rows']),
        all_load_capture_unload_checks='PASS',all_topology_placement_connectivity_checks='PASS',
        optimizer_reruns=0,routing_reruns=0,FAN_fault_sets='BLOCKED (prior reporter SIGSEGV); coverage/count PASS preserved'))
    # Index only tracked-size evidence, keeping ignored intermediates in their
    # explicit local manifests. Do not hash this index into itself.
    ignored={'.odb','.vcd','.vvp','.spef','.npz'}
    ignore_names={'stimulus.v','cycles.json','per_cycle.csv','simulation_cells.v','evidence_manifest.json'}
    evidence={str(p.relative_to(ROOT)):sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()
              and p.suffix not in ignored and p.name not in ignore_names}
    sources=['scripts/physical_effect.py','scripts/physical_effect_export.py','scripts/physical_effect_report.py',
             'scripts/physical_effect_finalize.py','scripts/physical_effect_seal.py','src/pact/physical_effect.py','tests/unit/test_physical_effect.py']
    write(OUT/'evidence_manifest.json',dict(artifacts=evidence,measurement_code={p:sha(ROOT/p) for p in sources},
        scope='compact deliverables; raw files hash-indexed in each analysis_manifest.json'))
    print('SEALED',len(evidence),'artifacts')

if __name__=='__main__':
    replay() if '--replay' in sys.argv else seal()
