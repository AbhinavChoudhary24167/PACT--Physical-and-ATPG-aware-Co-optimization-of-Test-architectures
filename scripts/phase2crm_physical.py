"""Placed-only export: reuse the repaired endpoint exporter without changing it."""
from phase2crm_audit import *
from phase2cr_extract import endpoint_from_def
from phase2b_extract import placed_graph
from pact.scan.model import ScanArchitecture

def main():
    contract=read(OUT/'multiseed_contract.json')
    for d in DESIGNS:
        for s in contract['new_seeds']:
            cell=next(c for c in contract['cells'] if c['design']==d and c['seed']==s)
            a=ScanArchitecture.from_json(Path(cell['architecture_path']))
            dp=ROOT/f'artifacts/raw/phase0b/placements/{d}/s{s}/placed.def'
            graph,_=placed_graph(dp,[c.name for c in a.cells])
            # Exact historical exporter agreement before adding repaired endpoint schema.
            assert graph==read(CW/d/f's{s}'/'placed_graph.json')
            ep,ports=endpoint_from_def(dp,graph,2)
            path=OUT/'graphs'/f'{d}.s{s}.json'; assert not path.exists()
            write(path,dict(graph,scan_endpoints={'chain0_so':ep},scan_ports=ports))
            print('PLACED_GRAPH',d,s,sha(path),flush=True)

if __name__=='__main__':main()
