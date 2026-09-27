"""Fail-closed all-endpoint gate: no missing/duplicated/undefined endpoint rescue."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from phase2d_report import classify, DESIGNS, ENDPOINTS

def endpoints():
    return [dict(design=d,predictor=m,target=t,spearman=.7,accuracy=.75)
            for d in DESIGNS for m,t in ENDPOINTS]

def test_all_original_boundaries_pass():
    assert classify(endpoints(),True)=='PACT_PHASE2D_INDEPENDENT_GP_GENERALIZATION_CONFIRMED'

def test_one_failed_local_endpoint_cannot_be_averaged_away():
    rows=endpoints();rows[1]['accuracy']=.749999
    assert classify(rows,True)=='PACT_PHASE2D_INDEPENDENT_GP_GENERALIZATION_NOT_CONFIRMED'

def test_undefined_rho_fails_qualification():
    rows=endpoints();rows[-1]['spearman']=None
    assert classify(rows,True)=='PACT_PHASE2D_INDEPENDENT_GP_GENERALIZATION_NOT_CONFIRMED'

def test_missing_or_duplicate_endpoint_is_engineering_block():
    rows=endpoints()
    assert classify(rows[:-1],True)=='PACT_PHASE2D_ENGINEERING_BLOCKED'
    assert classify(rows[:-1]+[rows[0]],True)=='PACT_PHASE2D_ENGINEERING_BLOCKED'

def test_engineering_failure_cannot_be_rescued_by_correlations():
    assert classify(endpoints(),False)=='PACT_PHASE2D_ENGINEERING_BLOCKED'
