"""Use the frozen graph exporter with a manifest-driven reference directory."""
import inspect
from pathlib import Path
import sys
import pact_candidate_export as frozen

source=inspect.getsource(frozen.export)
old="    role = {'s5378': 'P', 's9234': 'T', 's15850': 'P'}[design]\n    folder = ROOT/'reports/physical_effect'/design/role\n"
assert source.count(old)==1
source=source.replace('def export(design, output):','def export(reference_folder, output):',1)
source=source.replace(old,'    folder = Path(reference_folder)\n',1)
namespace=dict(frozen.__dict__)
exec(compile(source,'<frozen-graph-export-directory-adapter>','exec'),namespace)
namespace['export'](Path(sys.argv[-2]),Path(sys.argv[-1]))
