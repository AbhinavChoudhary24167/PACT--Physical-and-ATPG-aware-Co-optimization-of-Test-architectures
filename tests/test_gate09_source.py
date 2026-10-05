"""Import safety: reject incompatible state/ports/feedback without repairing it."""
import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('gate09_source', Path(__file__).parents[1] / 'scripts/pact_gate09_source.py')
source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)
BENCH = 'INPUT(a)\nOUTPUT(y)\nq = DFF(d)\nd = XOR(a, q)\ny = NOT(q)\n'
BLIF = '.model x\n.inputs a\n.outputs y\n.latch d q 0\n.names a q d\n01 1\n10 1\n.names q y\n0 1\n.end\n'


def test_feedback_state_is_cut_at_dff_and_all_ppi_states_are_free():
    model = source.parse_bench(BENCH)
    witness, latches = source.blif_witness(BLIF, model)
    assert model['flops'] == ['q']
    assert latches['q']['initial'] == '0'
    assert '.latch' not in witness
    assert '.inputs a __pact_ppi_0000' in witness
    assert '.names __pact_ppi_0000 q' in witness


@pytest.mark.parametrize('text', [BENCH + 'd = AND(a,q)\n', BENCH.replace('XOR(a, q)', 'XOR(a, missing)'),
                                    BENCH.replace('XOR(a, q)', 'XOR(a, d)'), BENCH.replace('INPUT(a)', 'INPUT(CK)'),
                                    BENCH.replace('NOT(q)', 'MAGIC(q)')])
def test_invalid_bench_is_not_forced_through(text):
    with pytest.raises(ValueError):
        source.parse_bench(text)


@pytest.mark.parametrize('text', [BLIF.replace('.latch d q 0', '.latch d r 0'),
                                    BLIF.replace('.latch d q 0', '.latch a q 0'),
                                    BLIF.replace('.outputs y', '.outputs q'),
                                    BLIF.replace('.latch d q 0', '.latch d q re clock 0')])
def test_incompatible_blif_is_preserved_as_failure(text):
    with pytest.raises(ValueError):
        source.blif_witness(text, source.parse_bench(BENCH))
