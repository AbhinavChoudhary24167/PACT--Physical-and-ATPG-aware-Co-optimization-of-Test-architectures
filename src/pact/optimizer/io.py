"""Repository adapters and portable, explicit input bundle (no routed labels)."""
import json
import math
from pathlib import Path
import re
from pact.environment import dependency_path, relocate
import numpy as np
from pact.scan.model import ScanArchitecture,ScanCell,ScanChain
from pact.scan.validate import validate_scan
from pact.test.pattern_parser import parse_fan_pat,map_ppi_patterns
from pact.analysis.phase2b_loads import pin_loads
from .costs import PlacedCosts


def read(path):return relocate(json.loads(Path(path).read_text(encoding='utf-8-sig')))


def orders_for(arch,costs):
    validate_scan(arch)
    if {c.name for c in arch.cells}!=set(costs.names):raise ValueError('Baseline FF set differs')
    return [np.array([costs.index[n] for n in c.cells],np.int32) for c in arch.chains]


def pattern_array(records,names):
    if not records:raise ValueError('At least one complete ATPG pattern is required')
    for record in records:
        if set(record)!=set(names) or any(v not in (0,1) for v in record.values()):raise ValueError('Patterns must be complete binary FF target maps')
    return np.array([[r[n] for n in names] for r in records],np.uint8)


def load_design(root,design,k,liberty=None):
    if k!=2:raise ValueError('Repository repaired placed-graph adapter requires K=2; use --input for arbitrary K with explicit ports/topology')
    folder=root/f'artifacts/derived/phase0c/{design}/s11/k2'
    arch=ScanArchitecture.from_json(folder/'B0.architecture.json')
    graph=read(root/f'results/phase2c_repair/{design}.placed_graph.json')
    if liberty is None:liberty=dependency_path('OpenROAD-flow-scripts/flow/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib')
    loads=pin_loads(Path(liberty).read_text())
    defs=(root/f'artifacts/raw/phase0b/placements/{design}/s11/placed.def').read_text()
    unit=float(re.search(r'UNITS DISTANCE MICRONS\s+(\d+)',defs)[1])
    match=re.search(r'DIEAREA\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)',defs)
    bounds=[float(v)/unit for v in match.groups()]
    costs=PlacedCosts(arch,graph,loads,bounds)
    records=map_ppi_patterns(parse_fan_pat(root/f'artifacts/raw/tool_qualification/fan_atpg/patterns/FAN_{design}.pat'),read(root/f'artifacts/derived/{design}/ff_identity_map.json')['records'])
    patterns=pattern_array(records,costs.names)
    starts=[]
    for label in ('B0','P','A','J50','T'):
        other=ScanArchitecture.from_json(folder/f'{label}.architecture.json')
        if other.cells!=arch.cells:raise ValueError('Baseline placement differs')
        starts.append((label,orders_for(other,costs)))
    return arch,costs,patterns,starts,dict(design=design,synthetic=False,source=str(folder),scope=costs.scope)


def load_bundle(path,k):
    data=read(path);folder=Path(path).resolve().parent
    arch=ScanArchitecture.from_json(folder/data['architecture'])
    if len(arch.chains)!=k:raise ValueError('--chains must match input architecture; ports and topology cannot be invented')
    patterns=pattern_array(data['patterns'],[c.name for c in arch.cells])
    if 'placed_graph' in data:
        costs=PlacedCosts(arch,read(folder/data['placed_graph']),pin_loads((folder/data['liberty']).read_text()),data['bounds'])
    else:
        g=data['compiled_functional_sources']
        costs=PlacedCosts.generic(arch,patterns,data['input_ports'],data['output_ports'],data['bounds'],g['pin_ff'],g['wire_um'],g['si_pin_ff'],g['q_boxes'])
    return arch,costs,patterns,[('supplied',orders_for(arch,costs))],dict(design=Path(path).stem,synthetic=False,scope=costs.scope)


def synthetic(n,k=None,p=4):
    if n<2 or p<1:raise ValueError('Synthetic size >=2, pattern count >=1 required')
    k=k or max(2,math.ceil(n/500))
    if not 1<=k<=n:raise ValueError('K must be in [1,N]')
    rng=np.random.default_rng(11);xy=rng.uniform(1,999,(n,2))
    cells=tuple(ScanCell(f'ff{i:06d}',float(x),float(y),'clk') for i,(x,y) in enumerate(xy))
    groups=np.array_split(np.arange(n),k)
    chains=tuple(ScanChain(f'C{ci}',tuple(cells[j].name for j in g),f'si{ci}',f'so{ci}') for ci,g in enumerate(groups))
    arch=ScanArchitecture(cells,chains);patterns=rng.integers(0,2,(p,n),dtype=np.uint8)
    ports=np.linspace(0,1000,k+2)[1:-1]
    costs=PlacedCosts.generic(arch,patterns,np.column_stack((np.zeros(k),ports)),np.column_stack((np.full(k,1000),ports)),[0,0,1000,1000],np.ones(n)*2,np.ones(n)*4,np.ones(n),np.column_stack((xy-1,xy+1)))
    return arch,costs,patterns,[('supplied',groups)],dict(design=f'synthetic_{n}',synthetic=True,scope='ALGORITHM_SCALING_ONLY',pattern_count=p,full_load=True)


def architecture_from(arch,costs,orders):
    result=ScanArchitecture(arch.cells,tuple(ScanChain(c.chain_id,tuple(costs.names[int(j)] for j in o),c.scan_in,c.scan_out) for c,o in zip(arch.chains,orders)))
    validate_scan(result)
    return result


def write_json(path,value,compact=False):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=None if compact else 2,separators=(',',':') if compact else None,allow_nan=False)+'\n',encoding='utf-8')
    temporary.replace(path)
