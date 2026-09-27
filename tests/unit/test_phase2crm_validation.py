"""Scientific failure modes: seed-11 rescue, endpoint loss, ties and boundaries."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from phase2crm_validate import classify,endpoint_pass,effect,topology_function

def test_seed11_cannot_rescue_new_seed_failure():
    assert classify([dict(seed=11,passed=True),dict(seed=13,passed=False)]).endswith('GENERALIZATION_FAIL')

def test_missing_physical_evidence_cannot_confirm():
    assert classify([dict(seed=13,passed=True)],complete=False).endswith('VALIDATION_INCOMPLETE')

def test_only_seed11_is_incomplete():
    assert classify([dict(seed=11,passed=True)]).endswith('VALIDATION_INCOMPLETE')

def test_partial_preserves_failure():
    assert classify([dict(seed=13,passed=True),dict(seed=17,passed=False)]).endswith('GENERALIZATION_PARTIAL')

def test_original_endpoint_gates_and_undefined():
    assert endpoint_pass(.7,.75)
    assert not endpoint_pass(.699999,.99)
    assert not endpoint_pass(.99,.749999)
    assert not endpoint_pass(None,1)
    assert not endpoint_pass(1,None)

def test_effect_sign_ties_and_one_percent_boundary():
    assert effect(2,.99,100)[1]=='directionally_correct_physically_negligible'
    assert effect(2,1,100)[1]=='directionally_correct_materially_different'
    assert effect(2,-1,100)[1]=='directionally_incorrect'
    assert effect(0,1,100)[1]=='tied'
    assert effect(1,1,0)[0] is None

def test_topology_reuses_all_assertions():
    _,original,adapted=topology_function()
    assert adapted.replace("r['seed']==row['seed']","r['seed']==11")==original
    assert adapted.count('assert ')==original.count('assert ')
