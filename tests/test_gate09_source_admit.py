from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import pact_gate09_source_admit as intake


def test_unused_library_repair_cannot_admit_a_design_using_the_unmodeled_cell():
    mapped = dict(modules=dict(d=dict(cells=dict(macro=dict(type='CLKGATETST_X1')))))
    with pytest.raises(ValueError, match='when its cell is used'):
        intake.mapped_witness(mapped, {}, 'd', {})
