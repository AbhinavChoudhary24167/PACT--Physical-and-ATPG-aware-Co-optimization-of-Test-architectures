#!/usr/bin/env python3
"""Read-only checks of the sealed blocked-campaign artifacts."""
import csv
import io

from pact_generalization import ROOT, OUT, CORE, binding, now, read, sha, write
from pact_generalization_report import preflight, collect


def main():
    outcomes, refs, measured = collect()
    new_rows = preflight(outcomes, refs, measured)
    original = read(CORE/'canonical_results.json')
    canonical_path = OUT/'canonical/generalization_canonical_results.json'
    canonical = read(canonical_path)
    assert canonical['records'][:12] == original['records']
    assert canonical['records'][12:] == new_rows
    assert len(canonical['records']) == 18 and len(canonical['design_outcomes']) == 8
    old_csv = (CORE/'primary_comparison.csv').read_bytes()
    primary_path = OUT/'canonical/generalization_primary_comparison.csv'
    primary = primary_path.read_bytes()
    assert primary.startswith(old_csv)
    assert len(list(csv.DictReader(io.StringIO(primary.decode())))) == 12
    table_path = OUT/'canonical/generalization_results_table.csv'
    table = list(csv.DictReader(io.StringIO(table_path.read_text())))
    assert len(table) == 18
    for row in table[12:]:
        assert row['PACT_status'] == 'PACT_EXECUTION_BLOCKED'
        assert not row['solver_runtime_seconds'] and not row['exact_evaluation_count']
        if row['design'] in ('s38417', 's38584'):
            assert not any(row[k] for k in ('E', 'H4', 'H8', 'delta_E_percent', 'delta_H4_percent', 'delta_H8_percent'))
    assert read(OUT/'searches/selected_candidate_manifest.json')['records'] == []
    assert read(OUT/'scalability_results.json')['records'] == []
    assert len(list(csv.DictReader(io.StringIO((OUT/'scalability_results.csv').read_text())))) == 0
    assert read(OUT/'manifests/freeze_verification.json')['status'] == 'PACT_V1_CORE_FREEZE_VERIFIED'
    completion = read(OUT/'completion.json')
    assert completion['status'] == 'PACT_V1_GENERALIZATION_BLOCKED_BY_SCALABILITY'
    assert completion['scientific_method_changes'] == 0
    assert completion['physical_metric_resource_blockers'] == ['s38417']
    for item in completion['artifacts'].values():
        assert sha(ROOT/item['path'].removeprefix('repo://')) == item['sha256']
    write(OUT/'logs/final_artifact_audit.json', dict(status='PASS', created_utc=now(),
        frozen_canonical_records_unchanged=12, frozen_primary_CSV_prefix_exact=True,
        selected_designs_retained=8, qualified_new_references=6,
        fully_measured_new_references=4, activity_unavailable_references=2,
        new_PACT_searches_executed=0, solver_scalability_observations=0,
        historical_tool_executions=0, historical_writes=0,
        artifacts=[binding(p) for p in (canonical_path,primary_path,table_path,OUT/'completion.json')]),
        immutable=True)
    print('FINAL_ARTIFACT_AUDIT_PASS: original 12 exact; all 8 retained; 6 references; 4 activity results; 0 PACT searches',flush=True)


if __name__ == '__main__':
    main()
