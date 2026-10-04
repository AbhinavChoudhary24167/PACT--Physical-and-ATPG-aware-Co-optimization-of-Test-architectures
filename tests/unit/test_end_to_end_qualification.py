import pytest
from pact.integration.qualification import parse_export, compare_exports


def report(records):
    sums={s:0 for s in ('UD','DT','PT','AU','TI','RE','AB')}
    for _,s,_,weight in records:
        sums[s]+=weight
    lines=['# FU (full) '+str(sum(sums.values())), '# FU (collapsed) '+str(len(records)),
           '# fault coverage 50.00%', '# #Patterns 1', '# number of faults: '+str(len(records))]
    lines += [f'# {s} ({"detected" if s == "DT" else "state"}) {n}' for s,n in sums.items()]
    lines += [f'# {kind} {state} {site} [equivalent={weight}]' for kind,state,site,weight in records]
    return '\n'.join(lines)


def test_complete_weighted_identity_equivalence():
    value=parse_export(report([('SA0','DT','ff/Q (SDFF_X1)',3),('SA1','UD','ff/D (SDFF_X1)',3)]))
    assert value['statistics']['detected']==3
    assert compare_exports(value,value)['FAULT_IDENTITY']=='FAULT_IDENTITY_PASS'
    # Equal aggregate counts and coverage must not conceal changed identities.
    changed=parse_export(report([('SA0','UD','ff/Q (SDFF_X1)',3),('SA1','DT','ff/D (SDFF_X1)',3)]))
    result=compare_exports(value,changed)
    assert result['FAULT_COVERAGE']=='FAULT_COVERAGE_PASS'
    assert result['status']=='FAIL' and result['lost_faults'] and result['unexpected_faults']


@pytest.mark.parametrize('records,reason',[
    ([('SA0','DT','(SDFF_X1)',1)],'Unresolved'),
    ([('SA0','DT','ff/Q (SDFF_X1)',1)]*2,'Duplicate'),
    ([('SA0','DT','ff/Q (SDFF_X1)',0)],'Nonpositive')])
def test_rejects_invalid_sites(records,reason):
    with pytest.raises(ValueError,match=reason):
        parse_export(report(records))


def test_rejects_truncation_and_wrong_weight():
    text=report([('SA0','DT','ff/Q (SDFF_X1)',2),('SA1','UD','ff/D (SDFF_X1)',1)])
    with pytest.raises(ValueError,match='Partial'):
        parse_export(text.rsplit('\n',1)[0])
    with pytest.raises(ValueError,match='universe weight'):
        parse_export(text.replace('FU (full) 3','FU (full) 4'))
    with pytest.raises(ValueError,match='Detected identity'):
        parse_export(text.replace('DT (detected) 2','DT (detected) 1'))
