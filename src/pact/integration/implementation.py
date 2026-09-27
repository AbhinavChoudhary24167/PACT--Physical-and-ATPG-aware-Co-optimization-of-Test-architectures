"""Deterministic scan-only connectivity patch and executable OpenROAD handoff."""
from pathlib import Path
import runpy

from .permutation import read, file_hash, write
from pact.scan.model import ScanArchitecture


def port_bindings(architecture, adapter):
    bindings = {}
    for i, c in enumerate(architecture.chains):
        if adapter == 'qualified':
            if (c.scan_in, c.scan_out) != (f'test_si_{i}', f'test_so_{i}'):
                raise ValueError('Qualified adapter requires indexed logical test_si_i/test_so_i endpoints')
            suffix = f'_{i}' if i else ''
            bindings[c.scan_in] = 'test_si'+suffix
            bindings[c.scan_out] = 'test_so'+suffix
        else:
            bindings[c.scan_in], bindings[c.scan_out] = c.scan_in, c.scan_out
    return bindings


def emit(output, permutation, root, adapter):
    bindings = port_bindings(permutation.after, adapter)
    chains = []
    for c in permutation.after.chains:
        links = [dict(source=dict(port=bindings[c.scan_in]), destination=dict(instance=c.cells[0], pin='SI'))]
        links.extend(dict(source=dict(instance=a, pin='Q'), destination=dict(instance=b, pin='SI'))
                     for a, b in zip(c.cells, c.cells[1:]))
        links.append(dict(source=dict(instance=c.cells[-1], pin='Q'), destination=dict(port=bindings[c.scan_out])))
        chains.append(dict(chain_id=c.chain_id, links=links))
    script = root/'scripts/phase0c_rewire_odb.py'
    patch = dict(schema='pact_scan_connectivity_patch_v1', adapter=adapter,
                 architecture_sha256=permutation.after.sha256(),
                 before_sha256=permutation.before.sha256(), chains=chains, logical_to_physical_ports=bindings,
                 scan_pins=dict(input='SI', output='Q'), functional_D='untouched',
                 source_contract='original frozen single-chain ODB' if adapter == 'qualified' else 'old topology ODB, direct SI/SO only',
                 endpoint_policy='inherited transparent chain-0 SI/SO buffers; other ports direct' if adapter == 'qualified' else 'direct',
                 adapter_sha256=file_hash(script) if adapter == 'qualified' else file_hash(Path(__file__)))
    write(output/'implementation_patch.json', patch)
    # Repository explicitly supplied at execution: portable across Windows/WSL.
    (output/'implementation_patch.py').write_text(
        '"""Run with openroad -python -exit; changes scan connectivity only."""\n'
        'import argparse\nfrom pathlib import Path\nimport sys\n'
        'p = argparse.ArgumentParser()\n'
        'p.add_argument("--repository", type=Path, required=True)\n'
        'p.add_argument("--source", type=Path, required=True)\n'
        'p.add_argument("--output", type=Path, required=True)\n'
        'a = p.parse_args()\nsys.path.insert(0, str(a.repository / "src"))\n'
        'from pact.integration.implementation import apply\n'
        'apply(Path(__file__).resolve().parent, a.repository, a.source, a.output)\n', encoding='utf-8')
    return patch


def apply(folder, root, source, output):
    patch = read(folder/'implementation_patch.json')
    after = ScanArchitecture.from_json(folder/'scan_topology_after.json')
    before = ScanArchitecture.from_json(folder/'scan_topology_before.json')
    from .permutation import ScanPermutation
    permutation = ScanPermutation.verify_json(folder/'scan_permutation.json', before, after)
    if after.sha256() != patch['architecture_sha256'] or before.sha256() != patch['before_sha256']:
        raise ValueError('Implementation patch topology hash mismatch')
    # Verify the emitted graph itself, not just the architecture it references.
    expected = []
    bindings = port_bindings(after, patch['adapter'])
    if bindings != patch['logical_to_physical_ports']:
        raise ValueError('Endpoint binding changed')
    for c in after.chains:
        links = [dict(source=dict(port=bindings[c.scan_in]), destination=dict(instance=c.cells[0], pin='SI'))]
        links += [dict(source=dict(instance=a, pin='Q'), destination=dict(instance=b, pin='SI')) for a,b in zip(c.cells,c.cells[1:])]
        links += [dict(source=dict(instance=c.cells[-1], pin='Q'), destination=dict(port=bindings[c.scan_out]))]
        expected.append(dict(chain_id=c.chain_id, links=links))
    if patch['chains'] != expected:
        raise ValueError('Implementation patch edges differ from selected topology')
    if output.exists():
        raise ValueError('Refusing to overwrite implementation ODB')
    source_hash = file_hash(source)
    source_check = check_source_placement(source, before)
    if patch['adapter'] == 'qualified':
        script = root/'scripts/phase0c_rewire_odb.py'
        if file_hash(script) != patch['adapter_sha256']:
            raise ValueError('Qualified rewire adapter changed')
        proof = runpy.run_path(str(script))['rewire'](source, folder/'scan_topology_after.json', output)
    elif patch['adapter'] == 'direct':
        if file_hash(Path(__file__)) != patch['adapter_sha256']:
            raise ValueError('Direct rewire adapter changed')
        proof = apply_direct(source, permutation, output)
    else:
        raise ValueError('Unsupported implementation adapter')
    if file_hash(source) != source_hash:
        raise ValueError('Source ODB changed during implementation')
    write(folder/'implementation_applied.json', dict(proof, source_check=source_check, source_sha256=source_hash,
          output_sha256=file_hash(output), architecture_sha256=after.sha256(),
          patch_sha256=file_hash(folder/'implementation_patch.json')))


def check_source_placement(source, architecture):
    """Bind the actual implementation database to the canonical physical FFs."""
    import odb
    db = odb.dbDatabase.create()
    odb.read_db(db, str(source))
    block = db.getChip().getBlock()
    units = block.getDbUnitsPerMicron()
    scanned = {i.getName():i for i in block.getInsts() if i.findITerm('SI') is not None}
    if set(scanned) != {c.name for c in architecture.cells}:
        raise ValueError('Source ODB scan FF inventory differs')
    for c in architecture.cells:
        xy = scanned[c.name].getLocation()
        if abs(xy[0]/units-c.x_um) > .5/units or abs(xy[1]/units-c.y_um) > .5/units:
            raise ValueError(f'Source ODB placement differs for {c.name}')
    return dict(status='PASS', FF_count=len(scanned), placement_matches_input=True)


def apply_direct(source, permutation, output):
    import odb
    db = odb.dbDatabase.create()
    odb.read_db(db, str(source))
    block = db.getChip().getBlock()
    instances = {c.name: block.findInst(c.name) for c in permutation.before.cells}
    if any(i is None or i.findITerm('SI') is None or i.findITerm('Q') is None for i in instances.values()):
        raise ValueError('Direct adapter requires SI/Q scan cells')
    actual_scan = {i.getName() for i in block.getInsts() if i.findITerm('SI') is not None}
    if actual_scan != set(instances):
        raise ValueError('ODB scan inventory differs')
    def fingerprint():
        return {i.getName(): (i.getMaster().getName(), i.getLocation(), i.getOrient(),
                 {t.getMTerm().getName(): t.getNet().getName() if t.getNet() else None
                  for t in i.getITerms() if not (i.getName() in instances and t.getMTerm().getName() == 'SI')})
                for i in block.getInsts()}
    fixed = fingerprint()
    def check(arch):
        for c in arch.chains:
            si, so = block.findBTerm(c.scan_in), block.findBTerm(c.scan_out)
            if si is None or so is None or str(si.getIoType()) != 'INPUT' or str(so.getIoType()) != 'OUTPUT':
                raise ValueError('Missing or incorrectly directed SI/SO')
            net = si.getNet()
            for ff in c.cells:
                if instances[ff].findITerm('SI').getNet() != net:
                    raise ValueError('Direct chain topology mismatch; buffered/inverted links unsupported')
                net = instances[ff].findITerm('Q').getNet()
                if net is None:
                    raise ValueError('Disconnected Q')
            if so.getNet() != net:
                raise ValueError('Direct SO topology mismatch')
    check(permutation.before)
    for c in permutation.after.chains:
        net = block.findBTerm(c.scan_in).getNet()
        for ff in c.cells:
            pin = instances[ff].findITerm('SI')
            pin.disconnect(); pin.connect(net)
            net = instances[ff].findITerm('Q').getNet()
        so = block.findBTerm(c.scan_out)
        so.disconnect(); so.connect(net)
    check(permutation.after)
    if fingerprint() != fixed:
        raise ValueError('Functional nets or placement changed')
    output.parent.mkdir(parents=True, exist_ok=True)
    odb.write_db(db, str(output))
    return dict(status='PASS', functional_connections_placement_unchanged=True, SI_SO_topology_verified=True)
