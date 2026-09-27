"""Document the mandatory witness-assertion stop; do not continue the campaign."""
from phase2cr_common import *
import platform
import xml.etree.ElementTree as ET


def main():
    # Read-only integrity audit remains permitted after stopping scientific work.
    f=integrity()
    diagnostic=read(REPORT/'witness_failure_diagnostic.json')
    failure=dict(status='FAIL_AUDIT_ASSERTION',stop_condition='representative witness assertion failed',
        scientific_failure=False,physical_semantic_mismatch_demonstrated=False,
        assertion="sum(r['hpwl_um'] for r in audit['FFs'][n]) == new['M5_hpwl'][i]",
        source='scripts/phase2cr_run.py:witness',diagnostic=diagnostic,
        explanation='Sequential float accumulation gives 66.94999999999999; Python 3.12 built-in sum gives 66.95. The exact-equality audit uses different reduction arithmetic.',
        disposition='Stop retained per user section 23. Do not change the checker and resume implicitly.',
        next_step='Repair the audit to use the same ordered sequential addition, without changing predictor weights or the frozen scientific definition; rerun witness before all-21 topology and measurements.')
    write(REPORT/'representative_witness.json',failure)
    (REPORT/'REPRESENTATIVE_WITNESS.md').write_text('''# Representative witness: stopped at audit assertion

The witness did not finish. No accepted representative witness is claimed.
The s5378/P topology-only diagnostic passed: output38/BUF_X1/A moves from
U_n1588gat to U_n2121gat, the pin load transfers once, the unrelated graph
is preserved, and the physical endpoint proof matches.

The numerical audit then compared sequentially accumulated HPWL
66.94999999999999 with Python 3.12 built-in sum 66.95 (difference about
1.42e-14 um). This is a mismatch in the audit reduction arithmetic, not
evidence of a topology inconsistency. The old-owner HPWL audit agrees exactly
at 5.910000000000003 um. See witness_failure_diagnostic.json for the three
selected-tail net contributions and witness.log for the retained traceback.

User section 23 requires stopping on a representative witness failure. The
checker has therefore not been changed and scientific work has not continued.
No corrected correlations or requalification result are validly available.
Fix the audit reduction in a follow-up, then rerun this gate first.
''')
    write(REPORT/'topology_equivalence.json',dict(status='PACT_PHASE2CR_TOPOLOGY_FAIL',
        gate_satisfied=False,reason='Representative witness gate incomplete; all-21 audit not started',
        checked=0,passed=0,required=21,rows=[],physical_topology_mismatch_demonstrated=False,
        diagnostic_representative_topology='PASS, not a substitute for the all-21 gate'))
    blocked=dict(status='NOT_RUN_STOP_CONDITION',reason='Representative witness audit assertion; no valid scientific result',rows=[])
    for n in ('corrected_weights_manifest.json','metric_deltas.json','corrected_correlations.json',
              'corrected_rankings.json','corrected_pairwise_comparisons.json'):
        write(REPORT/n,blocked)
    write(REPORT/'qualification.json',dict(execution_classification='PACT_PHASE2CR_TOPOLOGY_FAIL',
        classification_scope='Required topology qualification gate incomplete; no demonstrated topology mismatch',
        scientific_classification=None,scientific_status='NOT_EVALUATED',
        engineering_recommendation='MULTISEED_REPAIR_RERUN_BLOCKED',
        phase2c_status='STOPPED_LEGACY_DEFINITION_BUG',remaining_seeds_started=False))
    suites=ET.parse(REPORT/'focused_tests.xml').getroot()
    suite=suites.find('testsuite')
    counts={k:int(suite.get(k,'0')) for k in ('tests','failures','errors','skipped')}
    tests=dict(environment=dict(platform=platform.platform(),python=platform.python_version(),
        executable='/root/pact-deps/pact-venv/bin/python',numpy='2.5.3',scipy='1.18.1',pytest='9.1.1'),
        focused=dict(passed=counts['tests']-counts['failures']-counts['errors']-counts['skipped'],
            failed=counts['failures'],errors=counts['errors'],skipped=counts['skipped'],
            runtime_seconds=float(suite.get('time')),log='focused_tests.log',log_sha256=sha(REPORT/'focused_tests.log'),
            command='PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 /root/pact-deps/pact-venv/bin/python -m pytest -q --capture=sys -p no:cacheprovider tests/unit/test_phase2cr_loads.py --junitxml=results/phase2c_repair/focused_tests.xml',
            scope_note='Initial test run before witness. The integration test originally also exercised corrected construction for all 21 while checking historical reproduction; that premature call was removed afterward. No architecture-level scores/correlations were produced. The final edited test file has not been rerun because of the stop.'),
        full_regression=dict(status='NOT_RUN_STOP_CONDITION',passed=None,failed=None,skipped=None,runtime_seconds=None),
        initial_environmental_failures=[
            'Sandbox WSL enumeration initially returned E_ACCESSDENIED; authorized elevated WSL access succeeded.',
            'System Python with phase2a cache lacked scipy.',
            'Repository .venv NumPy import failed on missing libscipy_openblas64 shared library.',
            'Original /root/pact-deps/pact-venv runtime successfully imported dependencies.'],
        witness_validation=failure)
    write(REPORT/'tests.json',tests)
    commands=dict(environment='Windows PowerShell host; Ubuntu-24.04 WSL scientific runtime',
        completed=[
            'git status --short; git rev-parse HEAD (nested PACT repository; initial snapshot preserved)',
            'Read pasted request, required source files and Phase-2C reports; locate frozen evidence in D:/PACT_EXPERIMENTS',
            'wsl --list --quiet (initial access denial, successful elevated retry)',
            'Dependency probes: system Python, repository .venv, original /root/pact-deps/pact-venv',
            'PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/mnt/d/PACT_EXPERIMENTS/cache/phase2a_python openroad -python -no_init -exit scripts/phase2cr_extract.py',
            'PYTHONDONTWRITEBYTECODE=1 /root/pact-deps/pact-venv/bin/python scripts/phase2cr_freeze.py',
            tests['focused']['command'],
            'PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 /root/pact-deps/pact-venv/bin/python scripts/phase2cr_run.py witness (assertion failure; witness.log)',
            'Read-only representative diagnostic using phase2cr_run.load_case and topology; write witness_failure_diagnostic.json',
            'PYTHONDONTWRITEBYTECODE=1 /root/pact-deps/pact-venv/bin/python scripts/phase2cr_stop_report.py'],
        not_run=['phase2cr_run.py topology','phase2cr_run.py measure','corrected correlations',
            'full regression','routing','RC extraction','ATPG','optimizer','multi-seed execution','git push'])
    write(REPORT/'commands.json',commands)
    (REPORT/'TOPOLOGY_REPAIR.md').write_text('''# Versioned topology repair (not fully qualified)

`phase2cr_loads` leaves the historical builder unchanged. The placed graph has
explicit scan_endpoints and scan_ports, exported read-only from the frozen DEF.
Architecture construction removes the unique inherited buffer sink and child
edge from the old Q net, appends them to the selected chain-0 tail Q net, and
places the SO port on the buffer output net. The same-owner case avoids a
remove/reinsert operation. Direct chain-1 semantics are preserved.

Unique transparent-net traversal recomputes HPWL from driver/sink/port points.
No M5 scalar subtraction is used. The fixed coefficient is 0.103981 fF/um.
Strict nested schema checks reject unknown/routed fields. The predictor accepts
only an architecture, placed graph and parsed Liberty loads. Routed evidence is
only read by the separate validation boundary. It is never passed to the builder.

Fourteen initial focused tests passed, including synthetic same-owner, changed
owner, functional fanout preservation, descendant branch transfer, direct chain-1,
nonlinear geometry and feature-leakage rejection. Historical archived weights
reproduced exactly for all 21. The representative topology diagnostic also passed.
The representative numerical audit assertion subsequently failed due to unequal
floating-point reductions. Full topology qualification and regression are not
complete; the implementation must not yet be treated as scientifically qualified.

Execution ordering note: the first focused integration test exercised corrected
per-FF construction for all 21 earlier than the requested witness ordering. That
call was removed. It produced no corrected architecture scores or correlations,
but this deviation is retained in tests.json; it is not presented as a gate pass.
''')
    (REPORT/'FINAL_REPORT.md').write_text('''# Phase-2C-R stop report

**Execution: PACT_PHASE2CR_TOPOLOGY_FAIL — required validation incomplete.**
**Scientific classification: not evaluated.**
**Engineering recommendation: MULTISEED_REPAIR_RERUN_BLOCKED.**

This is an audit-check failure, not demonstrated physical topology disagreement
or scientific invalidation. The representative witness asserted exact equality
between two floating-point reductions: 66.94999999999999 and 66.95. The difference
is approximately 1.42e-14 um. The user-required witness stop was retained rather
than changing the assertion and continuing. No corrected correlations, rankings,
architecture-level metric deltas or qualification claims were generated.

## Direct answers

1. **Mismatch reproduced?** Yes: PACT_PHASE2CR_BUG_REPRODUCED. All three historical
   placed graphs regenerated exactly; the s5378/P frozen witness matches.
2. **Legacy topology?** U_n1588gat/Q -> n1588gat -> output38/A -> output38/Z ->
   test_so remains under the old owner, plus synthetic selected-tail-to-SO geometry.
3. **Physical topology?** U_n2121gat/Q -> output38/A -> output38/Z -> test_so.
4. **Correction implemented?** New explicit placed endpoints, complete branch
   ownership transfer, real buffer-output port geometry, unique traversal and
   point-set HPWL; no change to historical functions.
5. **Historical preservation?** Yes. Final integrity checks verify all 534 frozen
   inputs/preserved files. Phase-2B/C results and user modifications are unchanged.
6. **All 21 topology checks pass?** Not established: the mandatory all-21 audit was
   not started after the representative numerical assertion. The representative
   topology-only diagnostic passes. This is not a 21/21 qualification.
7. **Representative transfer correct?** The topology diagnostic confirms
   output38 moves from U_n1588gat to U_n2121gat; the complete witness is unaccepted.
8. **BUF cap transferred once?** The representative topology diagnostic verifies
   exactly one 0.974659 fF transfer and preserved unrelated pin load.
9. **M5 recomputed from points?** Yes in the implementation and focused tests.
   The failed assertion concerns summation arithmetic in the audit only.
10. **Changed FF weights per architecture?** Not reported as qualified results;
    all-architecture diagnostic and score analysis was not completed.
11. **How much did M3 change?** Architecture scores not computed.
12. **How much did M5 change?** Architecture scores not computed. Diagnostic
    old-owner per-FF corrected HPWL is 5.910000000000003 um; selected-tail net
    terms are 34.699999999999996, 15.750000000000002 and 16.5 um. These are audit
    operands, not a qualified scientific measurement.
13. **Architecture rankings changed?** Not evaluated.
14. **Pair directions changed?** Not evaluated.
15. **M3 original gates on all designs?** Not evaluated.
16. **M5 original gates on all designs?** Not evaluated.
17. **Any original pass/fail conclusion changed?** No new conclusion issued;
    historical conclusions are preserved, not reaffirmed by this incomplete run.
18. **Minor, rank-significant or qualification-changing bug?** Undetermined.
    The small audit rounding difference says nothing about the legacy bug's impact.
19. **Multi-seed rerun justified?** Blocked pending witness, 21/21 topology,
    full regression and corrected seed-11 scientific evidence.
20. **Unvalidated?** Complete numerical witness, all-21 topology, corrected
    correlations and qualification, full regression; also all generalization,
    optimization, causal, power/energy and large-design claims.
21. **Exact classification?** PACT_PHASE2CR_TOPOLOGY_FAIL as an unsatisfied
    execution gate. No SEED11_REQUALIFIED/PARTIAL/INVALIDATED status is assigned.

## Tests and protocol accounting

Initial focused run: 14 passed, 0 failed, 0 skipped (6.53 s pytest summary).
No full regression was run after the stop. The initial integration test also
exercised corrected construction on the 21 inputs before the representative
witness; this was an ordering deviation. That call was removed, no architecture
scores/correlations were produced, and the edited test file has not been rerun.
See tests.json for environment, exact runtime, commands and setup failures.
The source implementation remains a candidate repair, not fully qualified code.

## Exact next experiment

First correct only the audit reduction to match the predictor's ordered
sequential addition, retaining this failed log. Re-run focused tests and the same
frozen s5378/P witness. Only after it passes, run all 21 topology gates, then
score the unchanged archived activity against corrected predictor weights and
reuse exact physical targets. Reuse Phase-2B statistics and the preregistered
gates, run isolated full regression and issue a seed-11 classification. Do not
launch any additional seed, route, ATPG, optimizer or Phase-2D work.

Phase-2C remains STOPPED_LEGACY_DEFINITION_BUG. No historical artifact was
overwritten, no routed quantity was used as a predictor feature, and no push occurred.
''')
    sources=[p for folder,pattern in ((ROOT/'scripts','phase2cr*.py'),(ROOT/'src/pact/analysis','phase2cr*.py'),
        (ROOT/'tests/unit','test_phase2cr*.py')) for p in folder.glob(pattern)]
    write(REPORT/'source_provenance.json',dict(files={str(p):sha(p) for p in sources},
        git_commit=read(REPORT/'initial_repository_state.json')['commit'],
        historical_inputs_unchanged=True,preserved_file_count=len(f['inputs'])))
    # Native Windows Git supplies this read-only snapshot; WSL status can stall on OneDrive.
    assert read(REPORT/'final_repository_state.json')['commit']==read(REPORT/'initial_repository_state.json')['commit']
    write(REPORT/'result_provenance.json',dict(observed_utc=now(),
        files={str(p.relative_to(REPORT)):sha(p) for p in REPORT.rglob('*') if p.is_file() and p.name!='result_provenance.json'},
        frozen_integrity_verified=True,new_routes=0,new_ATPG=0,new_optimizer_runs=0,pushed=False))
    print('STOP documented; historical integrity verified;',len(f['inputs']),'files')

if __name__=='__main__': main()
