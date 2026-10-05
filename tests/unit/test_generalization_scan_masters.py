"""Scan FF resizing is accepted only for identical sequential/pin contracts."""
import pytest
from pact_generalization_scan_masters import master_allowed,logic_contract


def library(tmp_path,second_next='(SE*SI)+(!SE*D)',second_q='IQ',omit_si=False):
    def cell(name,next_state,q,si=True):
        return f'''cell({name}) {{
ff("IQ", "IQN") {{ next_state : "{next_state}"; clocked_on : "CK"; }}
pin(D) {{ direction : input; }} pin(CK) {{ direction : input; }}
pin(SE) {{ direction : input; }}
{('pin(SI) { direction : input; }' if si else '')}
pin(Q) {{ direction : output; function : "{q}"; }}
pin(QN) {{ direction : output; function : "IQN"; }} }}'''
    path=tmp_path/'library.lib'
    path.write_text('library(x) {'+cell('SDFF_X1','(SE*SI)+(!SE*D)','IQ')+
        cell('SDFF_X2',second_next,second_q,not omit_si)+'}')
    return path


def test_drive_strength_with_exact_scan_behavior_is_allowed(tmp_path):
    assert logic_contract(library(tmp_path))['status']=='PASS'
    assert master_allowed('SDFF_X1') and master_allowed('SDFF_X2')
    assert not master_allowed('DFF_X2') and not master_allowed('SDFFR_X1')


def test_changed_next_state_rejected(tmp_path):
    with pytest.raises(ValueError,match='truth/pin contract differs'):
        logic_contract(library(tmp_path,second_next='D'))


def test_changed_output_polarity_rejected(tmp_path):
    with pytest.raises(ValueError,match='truth/pin contract differs'):
        logic_contract(library(tmp_path,second_q='IQN'))


def test_missing_scan_pin_rejected(tmp_path):
    with pytest.raises(ValueError,match='Unexpected scan FF pins'):
        logic_contract(library(tmp_path,omit_si=True))
