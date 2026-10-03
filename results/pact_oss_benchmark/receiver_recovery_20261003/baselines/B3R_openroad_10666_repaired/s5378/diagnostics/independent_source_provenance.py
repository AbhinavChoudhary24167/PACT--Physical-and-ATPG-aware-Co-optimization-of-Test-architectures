"""Bind inherited restitch source without modifying or executing it."""
import hashlib
import json
from pathlib import Path
import subprocess

SOURCE=Path('/mnt/pact-oss-recovery/B3R_openroad_10666_repaired/source')
BASE='746c748b19cd2b9d7fb6aa3afe53fe4c31ce3656'
RELATIVE='src/dft/src/Dft.cpp'
current=SOURCE/RELATIVE
original=subprocess.run(['git','-C',str(SOURCE),'show',BASE+':'+RELATIVE],check=True,capture_output=True).stdout
assert current.read_bytes()==original, 'Restitch source differs from inherited upstream base'
commit=subprocess.run(['git','-C',str(SOURCE),'rev-parse','HEAD'],check=True,capture_output=True,text=True).stdout.strip()
result=dict(status='PASS',operation='Read-only local file/Git-object comparison; no DFT commands',
    upstream_base_sha=BASE,repair_commit_sha=commit,
    inherited_source=dict(path=str(current),sha256=hashlib.sha256(original).hexdigest()),
    byte_identical_to_upstream_base=True,
    source_statements=dict(RestitchChain_definition=[79,128],output_metadata_only=[123,127],
        inherited_output_comment=[76,78],final_optimizer_restitch_call=568))
target=Path(__file__).with_name('inherited_restitch_source.json')
if target.exists():
    raise ValueError('Source provenance receipt already exists')
target.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps(result,indent=2))
