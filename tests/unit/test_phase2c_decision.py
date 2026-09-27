from pact.analysis.phase2c_decision import classify,endpoint_pass

def test_original_thresholds_are_inclusive_and_both_required():
    assert endpoint_pass(dict(spearman=.7,pairwise_non_tied_agreement=.75))
    assert not endpoint_pass(dict(spearman=.699999,pairwise_non_tied_agreement=1))
    assert not endpoint_pass(dict(spearman=1,pairwise_non_tied_agreement=.74999))
    assert not endpoint_pass(dict(spearman=None,pairwise_non_tied_agreement=1))

def test_missing_data_and_equivalence_cannot_confirm():
    families={'M3':[True]*15,'M5':[True]*15}
    assert classify(families,True,'PASS')=='PACT_PHASE2C_GENERALIZATION_CONFIRMED'
    assert classify(families,False,'PASS')=='PACT_PHASE2C_INFRASTRUCTURE_BLOCKED'
    assert classify(families,True,'EVENT_EVALUATOR_EQUIVALENCE_FAIL')=='PACT_PHASE2C_EVENT_EVALUATOR_FAIL'
    families['M3'][3]=False
    assert classify(families,True,'PASS')=='PACT_PHASE2C_GENERALIZATION_PARTIAL'
    assert classify({'M3':[False]*15,'M5':[False]*15},True,'PASS')=='PACT_PHASE2C_GENERALIZATION_FAIL'
