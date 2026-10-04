"""Focused before/after exporter regression using an existing new-design ODB."""
import os
from pathlib import Path
import shutil
from pact_generalization import ROOT,OUT,binding,read,write
from pact_generalization_infrastructure import RUN,execute,external_binding

design='s1196'
existing=RUN/'reference_measurement'/design
manifest=read(existing/'manifest.json')
role=manifest['rows'][0]['role']
root=RUN/'repair_verification/buffer_traversal'
results={}
for label,script in [('before','physical_effect_export.py'),('after','pact_generalization_export.py')]:
    base=root/label
    folder=base/design/role
    folder.mkdir(parents=True,exist_ok=True)
    write(base/'manifest.json',manifest,immutable=True)
    shutil.copy2(existing/design/role/'routed.odb',folder/'routed.odb')
    execute(['/usr/bin/openroad','-python','-no_init','-exit',ROOT/'scripts'/script,folder],
        base/'execution',env=dict(os.environ,PACT_PHYSICAL_EFFECT_OUT=str(base)))
    results[label]={name:read(folder/name) for name in ('topology_verification.json',
        'functional_verification.json','net_mapping.json')}
assert results['before']==results['after'],'Repair changed gates or capacitance/attribution export'
write(OUT/'repair_attempts/buffer_traversal_repaired/export_regression.json',dict(status='PASS',
    classification='IMPLEMENTATION_REPAIR',scientific_method_change=False,
    exact_output_equality=list(results['before']),additional_route_executions=0,
    source_database=external_binding(existing/design/role/'routed.odb'),
    before_execution=external_binding(root/'before/execution/execution.json'),
    after_execution=external_binding(root/'after/execution/execution.json'),
    adapter_sources={n:binding(ROOT/'scripts'/n) for n in ('pact_generalization_routed.py',
        'pact_generalization_export.py','pact_generalization_measure_driver.py')}),immutable=True)
print('EXPORT_REGRESSION PASS EXACT_GATE_FUNCTIONAL_MAPPING_EQUALITY',flush=True)
