#!/usr/bin/env python3
"""Prospective reference launch without requiring a prior failed preparation."""
import argparse
import inspect
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
import pact_gate09_admission as admission
import pact_gate09_reference as frozen
from pact_experiment_receipts import atomic_write


def registration_adapter():
    source = inspect.getsource(frozen.register_source)
    old = "if dependency_repair else None,\n        harness=admission.binding(Path(__file__))"
    replacement = ("if dependency_repair and (BASE_META / f'physical/{design}/preparation.json').exists() else None,\n"
                   "        harness=admission.binding(Path(__file__))")
    if source.count(old) != 1:
        raise ValueError('Frozen registration adapter no longer matches')
    namespace = dict(frozen.__dict__)
    exec(compile(source.replace(old, replacement, 1), '<Gate09-prospective-metadata-registration>', 'exec'), namespace)
    return namespace['register_source']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare','references'))
    parser.add_argument('--source-admission', type=Path, required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--dependency-repair', type=Path, required=True)
    args = parser.parse_args()
    probe = frozen.BASE_META / 'dependency_probes/runtime_import.json'
    if admission.read(probe)['status'] != 'QUALIFIED_GENERIC_RUNTIME_MODULE_PATH_REPAIR':
        raise ValueError('Explicit runtime module path must already be qualified')
    meta, raw = frozen.repair_namespace(args.attempt, args.dependency_repair)
    design = admission.read(args.source_admission)['design']
    os.environ['PYTHONPATH'] = ':'.join(str(ROOT / p) for p in ('.optimizer-deps','src','scripts'))
    atomic_write(meta / f'workers/{design}/{args.action}_launch_context.json', dict(design=design,
        child_PYTHONPATH=os.environ['PYTHONPATH'], runtime_import_probe=admission.binding(probe),
        source=admission.binding(Path(__file__)), reused_reference_harness=admission.binding(Path(frozen.__file__)),
        registration_change='Bind prior failed preparation only when it exists; a new design has no required predecessor',
        source_ATPG_placement_search_or_measurement_changes=0, scientific_method_changes=0), immutable=True)
    # configure() changes the destination namespace before run() calls registration.
    original_configure = frozen.configure
    def configure(*arguments, **keywords):
        result = original_configure(*arguments, **keywords)
        frozen.register_source = registration_adapter()
        return result
    frozen.configure = configure
    result = frozen.run(args.action, args.source_admission, args.attempt, args.dependency_repair)
    raise SystemExit(0 if result['status'] in ('PLACEMENT_READY_PENDING_REFERENCES','INFRASTRUCTURE_QUALIFIED') else 2)
