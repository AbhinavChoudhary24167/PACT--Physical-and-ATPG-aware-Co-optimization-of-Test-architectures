from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'scripts'))
from pact_gate09_input_recovery import allocate_input, require_unstarted_primary, adapted_input, adapted_admission, check_bases


def test_existing_preparation_is_preserved_and_prospective_input_is_separate(tmp_path):
    preparation = tmp_path / 'inputs/example'
    preparation.mkdir(parents=True)
    config = preparation / 'config.mk'
    config.write_bytes(b'qualified source preparation\n')
    result = allocate_input(tmp_path,'example')
    assert result == preparation / 'PACT_primary'
    assert config.read_bytes() == b'qualified source preparation\n'
    sentinel = result / 'net_mapping.json'
    sentinel.write_bytes(b'preserved prospective input')
    with pytest.raises(ValueError,match='Preserve'):
        allocate_input(tmp_path,'example')
    assert sentinel.read_bytes() == b'preserved prospective input'


def test_primary_started_or_legacy_artifacts_cannot_be_reinterpreted(tmp_path):
    meta,raw = tmp_path / 'meta',tmp_path / 'raw'
    require_unstarted_primary(meta,raw,'example')
    primary = meta / 'searches/example'
    primary.mkdir(parents=True)
    with pytest.raises(ValueError,match='already started'):
        require_unstarted_primary(meta,raw,'example')
    other = raw / 'inputs/other'
    other.mkdir(parents=True)
    (other / 'net_mapping.json').write_text('{}')
    with pytest.raises(ValueError,match='Prior prospective'):
        require_unstarted_primary(meta,raw,'other')


def test_adapter_accepts_only_the_preserved_source_body():
    check_bases()
    assert adapted_input().__name__ == 'prepare_input'
    assert adapted_admission().__name__ == 'admit_and_run'
