import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import pact_gate09_reference as reference


def test_repair_cannot_reuse_original_namespace():
    with pytest.raises(ValueError):
        reference.repair_namespace(None, Path('qualified_repair.json'))
    with pytest.raises(ValueError):
        reference.repair_namespace('attempt', None)
    for attempt in ('../old_results', '/absolute', 'a/b', 'a\\b', '..', ''):
        with pytest.raises(ValueError):
            reference.repair_namespace(attempt, Path('qualified_repair.json'))


def test_qualified_repair_is_separate_from_preserved_failure():
    metadata, raw = reference.repair_namespace('compound_circuit', Path('qualified_repair.json'))
    assert metadata != reference.BASE_META and raw != reference.BASE_RAW
    assert metadata.is_relative_to(reference.BASE_META)
    assert raw.is_relative_to(reference.BASE_RAW)


def test_unqualified_or_method_changing_dependency_never_admitted(tmp_path):
    valid_flags = dict(dependency='FAN_ATPG', status='QUALIFIED_GENERIC_INFRASTRUCTURE_REPAIR',
                       PACT_source_changes=0, scientific_parameters_changed=False, benchmark_specific_optimization=False)
    for field, value in (('status', 'PENDING'), ('PACT_source_changes', 1),
                         ('scientific_parameters_changed', True), ('benchmark_specific_optimization', True)):
        path = tmp_path / (field + '.json')
        path.write_text(json.dumps(dict(valid_flags, **{field:value})))
        with pytest.raises(ValueError, match='qualified generic'):
            reference.qualified_dependency(path)


def test_empty_regression_evidence_cannot_qualify_repair(tmp_path):
    path = tmp_path / 'empty.json'
    path.write_text(json.dumps(dict(dependency='FAN_ATPG', status='QUALIFIED_GENERIC_INFRASTRUCTURE_REPAIR',
                                   PACT_source_changes=0, scientific_parameters_changed=False,
                                   benchmark_specific_optimization=False, focused_tests=[])))
    with pytest.raises(ValueError, match='Both circuit and reporter'):
        reference.qualified_dependency(path)


def test_preparation_cannot_be_reused_after_generation_or_fault_model_changes():
    flags = dict(reporting_only_relative_to_predecessor=True, preparation_reuse_permitted=True,
                 ATPG_generation_algorithm_changed=False, fault_universe_changed=False)
    for repair in (None, {}, dict(flags, reporting_only_relative_to_predecessor=False),
                   dict(flags, preparation_reuse_permitted=False),
                   dict(flags, ATPG_generation_algorithm_changed=True), dict(flags, fault_universe_changed=True)):
        with pytest.raises(ValueError):
            reference.reuse_preparation(Path('old_preparation.json'), {}, repair)
