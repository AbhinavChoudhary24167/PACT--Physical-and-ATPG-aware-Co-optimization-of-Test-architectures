"""Read-only OpenROAD placed export and independent legacy-bug reproduction.

No rewire, routing, RC extraction, or physical database writes are performed.
The corrected predictor endpoint is derived exclusively from the frozen DEF.
"""
from phase2cr_common import *
import odb
from phase2b_extract import placed_graph
from pact.analysis.phase2b_loads import pin_loads
from pact.physical.phase0c_port_policy import frozen_def_ports
from pact.scan.model import ScanArchitecture


def endpoint_from_def(path, graph, k):
    db = odb.dbDatabase.create()
    try:
        odb.read_lef(db, str(PLATFORM / 'lef/NangateOpenCellLibrary.tech.lef'))
        odb.read_lef(db, str(PLATFORM / 'lef/NangateOpenCellLibrary.macro.mod.lef'))
        odb.read_def(db.getTech(), str(path))
        block = db.getChip().getBlock()
        port = block.findBTerm('test_so')
        drivers = [t for t in port.getNet().getITerms() if str(t.getIoType()) == 'OUTPUT']
        assert len(drivers) == 1, 'Ambiguous output buffer'
        buffer = drivers[0].getInst()
        assert buffer.getMaster().getName() == 'BUF_X1'
        source = buffer.findITerm('A').getNet()
        sources = [t for t in source.getITerms() if str(t.getIoType()) == 'OUTPUT']
        assert len(sources) == 1
        owner = sources[0].getInst().getName()
        assert graph['FFs'][owner]['roots']['Q'] == source.getName()
        units = block.getDbUnitsPerMicron()
        ports, u = frozen_def_ports(Path(path), k)
        assert units == u
        ports = {n: [v / u for v in xy] for n, xy in ports.items()}
        bbox = port.getBBox()
        endpoint = dict(port='test_so', buffer_instance=buffer.getName(),
            buffer_master=buffer.getMaster().getName(), input_pin='A', output_pin='Z',
            buffer_xy=[v / units for v in buffer.getLocation()],
            output_net=port.getNet().getName(), original_source_net=source.getName(),
            original_owner_ff=owner, port_xy=ports['test_so'],
            inherited_port_xy=[(bbox.xMin()+bbox.xMax())/2/units,
                               (bbox.yMin()+bbox.yMax())/2/units])
        return endpoint, ports
    finally:
        odb.dbDatabase.destroy(db)


def main():
    audit = read(C / 'legacy_bug_audit.json')
    inputs = {}
    def verify(path, expected):
        inputs[str(path)] = check(path, expected)
    for p, expected in audit['source_hashes'].items():
        verify(p, expected)
    for n, expected in read(B / 'freeze.json')['files'].items():
        verify(B / n, expected)
    original_inputs = read(B / 'provenance.json')['inputs']
    verify(LIB, original_inputs[str(LIB)])
    loads = pin_loads(LIB.read_text())
    rows = read(B / 'architecture_set.json')
    records = []
    for d in DESIGNS:
        witness = next(r for r in audit['rows'] if r['design'] == d)
        gp = Path(witness['frozen_graph_path'])
        verify(gp, witness['frozen_graph_sha256'])
        q = read(A / 'test_quality.json')[d]
        dp = q['placed_def']; verify(dp, original_inputs[dp])
        ar = next(r for r in rows if r['design'] == d and r['label'] == 'P')
        verify(ar['architecture_path'], original_inputs[ar['architecture_path']])
        arch = ScanArchitecture.from_json(Path(ar['architecture_path']))
        assert arch.sha256() == ar['architecture_sha256']
        graph = read(gp)
        exported, _ = placed_graph(Path(dp), [c.name for c in arch.cells])
        assert exported == graph, 'Historical exporter reproduction differs'
        ep, ports = endpoint_from_def(dp, graph, 2)
        assert ep['buffer_instance'] == witness['output_buffer']
        assert ep['original_owner_ff'] == witness['original_source_FF']
        sink = dict(master=ep['buffer_master'], pin=ep['input_pin'], xy=ep['buffer_xy'])
        assert graph['nets'][ep['original_source_net']]['sinks'].count(sink) == 1
        assert graph['transparent'][ep['original_source_net']].count(ep['output_net']) == 1
        assert not graph['nets'][ep['output_net']]['ports']
        # Physical inventory is an audit witness only, never an exporter input.
        aw = next(r for r in witness['selected_architectures'] if r['label'] == 'P')
        verify(aw['routed_physical_path'], aw['routed_physical_sha256'])
        phy = read(aw['routed_physical_path'])
        owners = [n for n, f in phy['FFs'].items() if any(
            b['instance'] == ep['buffer_instance'] for b in f['transparent_branches'])]
        assert owners == [arch.chains[0].cells[-1]]
        cap = loads[ep['buffer_master'], ep['input_pin']]
        assert cap == 0.974659
        if d == 's5378':
            assert (ep['original_owner_ff'], ep['original_source_net'], ep['buffer_instance'], owners[0]) == (
                'U_n1588gat', 'n1588gat', 'output38', 'U_n2121gat')
            assert arch.sha256() == 'bf4923662baa3ce72543bd3ad5092fb514808ffe46ce23173d3c9695ff0c9486'
        records.append(dict(design=d, architecture_sha256=arch.sha256(), endpoint=ep,
            legacy_buffer_owner=ep['original_owner_ff'], selected_tail=owners[0], physical_buffer_owner=owners[0],
            liberty_input_cap_ff=cap, legacy_export_exactly_reproduced=True,
            retained_sink=sink, retained_transparent_child=ep['output_net']))
        # Add an explicit placed-only endpoint; retain frozen legacy fields for reproducibility.
        write(REPORT / f'{d}.placed_graph.json', dict(graph,
            scan_endpoints={'chain0_so': ep}, scan_ports=ports))
    write(REPORT / 'bug_reproduction.json', dict(status='PACT_PHASE2CR_BUG_REPRODUCED',
        observed_utc=now(), rows=records, verified_inputs=inputs,
        corrected_metrics_computed=False, predictor_features='Frozen placed DEF and Liberty only'))
    print('PACT_PHASE2CR_BUG_REPRODUCED', flush=True)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        write(REPORT / 'bug_reproduction.json', dict(status='PACT_PHASE2CR_BUG_REPRODUCTION_FAIL',
            error=str(e), observed_utc=now(), corrected_metrics_computed=False))
        raise
