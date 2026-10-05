#!/usr/bin/env python3
"""Launch frozen prospective source preparation/references with qualified paths."""
import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
import pact_gate09_admission as admission
import pact_gate09_reference as frozen
from pact_experiment_receipts import atomic_write


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'references'))
    parser.add_argument('--source-admission', type=Path, required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--dependency-repair', type=Path, required=True)
    args = parser.parse_args()
    probe = frozen.BASE_META / 'dependency_probes/runtime_import.json'
    if admission.read(probe)['status'] != 'QUALIFIED_GENERIC_RUNTIME_MODULE_PATH_REPAIR':
        raise ValueError('Explicit child runtime paths must already be qualified')
    meta, raw = frozen.repair_namespace(args.attempt, args.dependency_repair)
    design = admission.read(args.source_admission)['design']
    os.environ['PYTHONPATH'] = ':'.join(str(ROOT / p) for p in ('.optimizer-deps', 'src', 'scripts'))
    atomic_write(meta / f'workers/{design}/{args.action}_launch_context.json', dict(design=design,
        child_PYTHONPATH=os.environ['PYTHONPATH'], runtime_import_probe=admission.binding(probe),
        source=admission.binding(Path(__file__)), reused_reference_harness=admission.binding(Path(frozen.__file__)),
        scientific_method_changes=0), immutable=True)
    result = frozen.run(args.action, args.source_admission, args.attempt, args.dependency_repair)
    raise SystemExit(0 if result['status'] in ('PLACEMENT_READY_PENDING_REFERENCES', 'INFRASTRUCTURE_QUALIFIED') else 2)
