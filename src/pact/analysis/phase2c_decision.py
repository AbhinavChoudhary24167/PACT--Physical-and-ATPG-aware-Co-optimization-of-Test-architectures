"""Frozen endpoint gates; incomplete evidence cannot support confirmation."""

def endpoint_pass(stat):
    return (stat.get('spearman') is not None and stat['spearman']>=.7 and
            stat.get('pairwise_non_tied_agreement') is not None and stat['pairwise_non_tied_agreement']>=.75)


def classify(families,complete,equivalence):
    if equivalence=='EVENT_EVALUATOR_EQUIVALENCE_FAIL':return 'PACT_PHASE2C_EVENT_EVALUATOR_FAIL'
    if not complete or equivalence!='PASS':return 'PACT_PHASE2C_INFRASTRUCTURE_BLOCKED'
    if all(all(v) for v in families.values()):return 'PACT_PHASE2C_GENERALIZATION_CONFIRMED'
    if any(any(v) for v in families.values()):return 'PACT_PHASE2C_GENERALIZATION_PARTIAL'
    return 'PACT_PHASE2C_GENERALIZATION_FAIL'
