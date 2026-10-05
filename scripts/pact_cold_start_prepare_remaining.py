"""Prepare remaining preregistered artifacts independently, without shell loops."""
from pact_cold_start import OUT,prepare,read,write,now
import traceback

campaign=read(OUT/'manifests/campaign_preregistration.json')
order=campaign['execution_order']+[r['design'] for r in campaign['designs'] if not r['eligible']]
for design in order:
    if (OUT/f'inputs/{design}/cold_start_input.json').exists() or (OUT/f'failures/{design}_structural.json').exists():
        continue
    try:
        prepare(design)
    except Exception as error:
        target=OUT/f'failures/{design}_input_preparation.json'
        if not target.exists():write(target,dict(design=design,status='PACT_EXECUTION_BLOCKED',
            error=str(error),traceback=traceback.format_exc(),created_utc=now()),immutable=True)
        print('INDEPENDENT_INPUT_BLOCK',design,str(error),flush=True)
