"""Clarify an inherited summary flag without changing any topology assertion."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from phase2crm_audit import OUT,read,write,sha
import shutil

path=OUT/'topology_audit.json';raw=OUT/'topology_audit_raw.json'
assert not raw.exists()
shutil.copyfile(path,raw)
audit=read(path)
for row in audit['rows']:
    if row['seed']!=11:
        # The old function's summary flag assumes load_case() checked a legacy
        # archive. New-seed weights have no mandatory legacy archive to reproduce.
        row['checks']['legacy_weights_exact']=None
        row['legacy_weight_archive_status']='NOT_APPLICABLE_NEW_PHYSICAL_SEED'
        row['scope_note']='Every reused topology assertion passed. Legacy comparison weights were computed with the unchanged legacy builder solely for the owner-cone audit; no archived new-seed equality is claimed.'
audit['summary_flag_clarification']=dict(raw_audit_sha256=sha(raw),
    reason='Inherited legacy_weights_exact summary assumed the seed-11 archive caller; marked not applicable for new seeds. No topology assertion, predictor, score, target, gate or threshold changed.')
write(path,audit)
print('TOPOLOGY_SCOPE_CLARIFIED',audit['passed'],'topology cases remain PASS')
