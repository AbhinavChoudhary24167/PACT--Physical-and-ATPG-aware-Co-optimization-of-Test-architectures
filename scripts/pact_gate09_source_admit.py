#!/usr/bin/env python3
"""Prospective cohort intake with the already qualified library-model loading.

Do not repeat the known unused-library frontend failure on each new design.
All BENCH/BLIF and mapped all-state equivalence checks are unchanged.
"""
import argparse
import inspect
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
import pact_gate09_admission as admission
import pact_gate09_source_probe as frozen
from pact_experiment_receipts import atomic_write


def qualified_probe(design, audit):
    prior = frozen.META / 'source_admission/b14_opt__mapped_library_models.json'
    evidence = admission.read(prior)
    if evidence['status'] != 'SOURCE_MAPPED_EQUIVALENCE_QUALIFIED_PENDING_PHYSICAL_ATPG_REFERENCE':
        raise ValueError('Generic unused-library loading must already be qualified')
    for value in (evidence['Liberty'], evidence['Yosys'], evidence['stages']['mapped_equivalence']):
        if admission.verify(value)['status'] != 'PASS':
            raise ValueError('Qualified library frontend evidence changed')
    source = inspect.getsource(frozen.probe)
    old = "f'read_liberty {LIB}\\nread_verilog {folder}/bench_comb.v"
    check = "'miter -equiv -flatten -make_outputs gold gate miter\\nhierarchy -top miter\\nflatten\\nopt_clean\\n'"
    if source.count(old) != 1 or source.count(check) != 1:
        raise ValueError('Generic prospective library-model adapter no longer matches')
    adapted = source.replace(old, "f'read_liberty -ignore_miss_func {LIB}\\nread_verilog {folder}/bench_comb.v", 1)
    adapted = adapted.replace(check, "'miter -equiv -flatten -make_outputs gold gate miter\\nhierarchy -check -top miter\\nflatten\\nopt_clean\\n'", 1)
    namespace = dict(frozen.__dict__, __file__=__file__)
    receipt = frozen.META / f'source_admission/{design}_frontend_adapter.json'
    atomic_write(receipt, dict(design=design, generic_library_model_evidence=admission.binding(prior),
        source=admission.binding(Path(__file__)), original_probe=admission.binding(Path(frozen.__file__)),
        changes=['read_liberty -ignore_miss_func skips only unused unmodeled library cells',
                 'hierarchy -check verifies all actual used cells resolve'],
        source_or_mapping_changes=0, scientific_method_changes=0), immutable=True)
    exec(compile(adapted, '<Gate09-qualified-library-model-adapter>', 'exec'), namespace)
    return namespace['probe'](design, audit)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--design', required=True)
    parser.add_argument('--audit', type=Path, required=True)
    args = parser.parse_args()
    result = qualified_probe(args.design, args.audit)
    raise SystemExit(0 if result['status'].startswith('SOURCE_MAPPED') else 2)
