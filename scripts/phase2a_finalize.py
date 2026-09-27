#!/usr/bin/env python3
"""Finalize presentation and integrity records without repeating measurements."""
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import platform
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from pact.phase0d.campaign import file_sha256, atomic_write_json as write
REPORT=ROOT/'reports/phase2a_shift_activity'
def read(p): return json.loads(Path(p).read_text())

def main():
    regression=(REPORT/'regression.log').read_text()
    assert re.search(r'\b\d+ passed in ',regression) and not re.search(r'\b[1-9]\d* (failed|error)',regression)
    spec=importlib.util.spec_from_file_location('phase2a_validate',ROOT/'scripts/phase2a_validate.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.report()
    provenance=read(REPORT/'measurement_provenance.json')['files']
    for path,expected in provenance.items():
        assert file_sha256(Path(path))==expected, f'Measurement artifact or code changed: {path}'
    corr=read(REPORT/'correlation.json')
    audit=read(REPORT/'integrity_audit.json')
    audit.update(measurement_artifacts_and_code_hashes_rechecked=len(provenance),
        complete_regression_summary=next(l for l in reversed(regression.splitlines()) if ' passed in ' in l),
        focused_tests_summary=next(l for l in reversed((REPORT/'focused_tests.log').read_text().splitlines()) if ' passed in ' in l),
        physical_total_pair_directions_correct=sum(p['H_eff8_direction']['weighted_total']=='correct' for p in corr['pairwise']),
        physical_local_pair_directions_correct=sum(p['H_eff8_direction']['weighted_local_peak']=='correct' for p in corr['pairwise']),
        pair_count=len(corr['pairwise']))
    write(REPORT/'integrity_audit.json',audit)
    env=dict(python=sys.version,platform=platform.platform(),
        openroad=subprocess.check_output(['openroad','-version'],text=True).strip(),
        packages={m:importlib.metadata.version(m) for m in ('numpy','scipy','matplotlib','pytest','threadpoolctl')},
        regression_command='PYTHONPATH=src:/mnt/d/PACT_EXPERIMENTS/cache/phase2a_python PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 TMPDIR=/mnt/d/PACT_EXPERIMENTS/tmp MPLCONFIGDIR=/mnt/d/PACT_EXPERIMENTS/cache/matplotlib /root/pact-deps/pact-venv/bin/python -m pytest -q --capture=sys --basetemp=/mnt/d/PACT_EXPERIMENTS/pytest_tmp/phase2a_regression',
        dependency_recovery='threadpoolctl installed into /mnt/d/PACT_EXPERIMENTS/cache/phase2a_python; no repository dependency/code edits',
        capture_recovery='First full-regression attempt failed before running tests in WSL mounted-drive tempfile fd capture; final run uses in-memory sys capture.')
    write(REPORT/'environment.json',env)
    path=ROOT/'PACT_PHASE2A_SHIFT_ACTIVITY_VALIDATION.md'
    text=path.read_text()
    summary=['Spearman correlations show where the logical proxy stops tracking the physical surrogate:','',
        '| Design | Raw transition total | Routed-weighted total | Routed-weighted local peak |',
        '|---|---:|---:|---:|']
    for d in ('s5378','s9234','s15850'):
        e=corr['per_design'][d]['endpoints']
        summary.append('| '+d+' | '+' | '.join(f'{e[k]["spearman"]:.3f}' for k in ('raw_total','weighted_total','weighted_local_peak'))+' |')
    summary += ['',f'H_eff8 predicts the expected direction in **{audit["physical_total_pair_directions_correct"]}/{audit["pair_count"]}** '
        f'preregistered pairs for weighted total and **{audit["physical_local_pair_directions_correct"]}/{audit["pair_count"]}** for weighted local peak. '
        'For example, s9234 balanced lowers H_eff8 relative to T but raises both weighted total and local peak. '
        'On s15850, activity_extreme lowers H_eff8 relative to A while raw transitions, weighted total, cycle peak '
        'and local peak all rise. These counterexamples remain in the result.','']
    text=text.replace('## Validation question and frozen evidence','\n'.join(summary)+'\n## Validation question and frozen evidence',1)
    text=text.replace('|\n### ','|\n\n### ')
    text += ('\nFinal audit: all 148 frozen input files, four frozen contract files, and '
        f'{len(provenance)} measurement artifact/code hashes were rechecked. Raw net inventories and cycle traces '
        f'occupy {audit["raw_storage_bytes"]/1024**2:.2f} MiB on D:. See '
        '[integrity audit](reports/phase2a_shift_activity/integrity_audit.json).\n\n'
        'Regression setup notes: the initial WSL mounted-drive file-descriptor capture error and subsequent '
        'missing-threadpoolctl collection error occurred before tests ran. Their logs are retained as '
        '[capture error](reports/phase2a_shift_activity/regression_capture_error.log) and '
        '[missing dependency](reports/phase2a_shift_activity/regression_missing_dependency.log). '
        'The successful full run uses in-memory output capture and threadpoolctl from the D: experiment cache. '
        '[Environment and exact command](reports/phase2a_shift_activity/environment.json) record the setup. '
        'Run `scripts/phase2a_finalize.py` after `report` to reproduce this final presentation and audit.\n')
    path.write_text(text)
    sources=[ROOT/'scripts'/name for name in ('phase2a_freeze.py','phase2a_extract_odb.py','phase2a_validate.py','phase2a_finalize.py')]
    sources += [ROOT/'src/pact/analysis/phase2a_shift.py',ROOT/'tests/unit/test_phase2a_shift.py',ROOT/'tests/unit/test_phase2a_physical_stats.py']
    # The redirected console log is still open; hash only finalized artifacts.
    files=[p for p in REPORT.iterdir() if p.is_file() and p.name not in
           ('result_provenance.json','finalization.log')]+[path]+sources
    write(REPORT/'result_provenance.json',{str(p):file_sha256(p) for p in files})
    print(json.dumps(audit,indent=2))

if __name__=='__main__':main()
