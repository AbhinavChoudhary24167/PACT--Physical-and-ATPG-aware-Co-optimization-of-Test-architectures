"""Run the frozen exporter with only the qualified traversal-guard repair."""
import runpy
from functools import partial
from pact.physical import phase0d_routed
from pact_generalization_routed import verify_routed
from pact_generalization import ROOT

phase0d_routed.verify_routed=partial(verify_routed,recognize_sized=True)
runpy.run_path(str(ROOT/'scripts/physical_effect_export.py'),run_name='__main__')
