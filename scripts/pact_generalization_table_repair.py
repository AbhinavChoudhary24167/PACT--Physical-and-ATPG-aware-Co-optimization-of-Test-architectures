#!/usr/bin/env python3
"""Remove only the duplicated CSV qualification heading; preserve all values."""
import csv
import io
import shutil

from pact_generalization import OUT, CORE, binding, now, sha, write
from pact_generalization_report import csv_text, table_fields


def main():
    folder=OUT/'repair_attempts/table_schema_repaired'
    folder.mkdir(parents=True,exist_ok=True)
    target=OUT/'canonical/generalization_results_table.csv'
    before=folder/'previous_results_table.csv'
    assert not before.exists()
    shutil.copy2(target,before)
    text=before.read_text()
    matrix=list(csv.reader(io.StringIO(text)))
    fields=matrix[0]
    duplicates={name for name in fields if fields.count(name)>1}
    assert duplicates=={'qualification_status'}
    positions=[i for i,name in enumerate(fields) if name=='qualification_status']
    assert all(row[positions[0]]==row[positions[1]] for row in matrix[1:])
    rows=list(csv.DictReader(io.StringIO(text)))
    protected=(CORE/'canonical_results.json',CORE/'primary_comparison.csv',
        OUT/'canonical/generalization_canonical_results.json',
        OUT/'canonical/generalization_primary_comparison.csv',OUT/'completion.json')
    hashes={str(p):sha(p) for p in protected}
    old_fields=next(csv.reader(io.StringIO((CORE/'primary_comparison.csv').read_text())))
    corrected_fields=table_fields(old_fields)
    assert len(corrected_fields)==len(set(corrected_fields))
    assert set(corrected_fields)==set(fields)
    target.write_text(csv_text(corrected_fields,rows),encoding='utf-8',newline='')
    assert list(csv.DictReader(io.StringIO(target.read_text())))==rows
    assert {str(p):sha(p) for p in protected}==hashes
    previous_audit=OUT/'logs/final_artifact_audit.json'
    shutil.copy2(previous_audit,folder/'previous_artifact_audit.json')
    # Keep the previous receipt above; the improved audit will create a new one.
    previous_audit.unlink()
    write(folder/'qualification.json',dict(status='PASS',classification='IMPLEMENTATION_REPAIR',
        created_utc=now(),repair='Remove duplicate qualification_status heading only',
        before=binding(before),after=binding(target),row_dictionaries_exactly_unchanged=len(rows),
        frozen_and_canonical_protected_hashes=hashes,scientific_method_changes=0,
        additional_EDA_executions=0,additional_PACT_searches=0),immutable=True)
    print('TABLE_SCHEMA_REPAIR_PASS',len(rows),'row dictionaries unchanged',flush=True)


if __name__=='__main__':
    main()
