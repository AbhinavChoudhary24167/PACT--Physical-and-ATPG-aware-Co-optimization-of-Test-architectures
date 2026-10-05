"""Focused prospective handoff tests; no EDA tools or historical state."""
import json
from pathlib import Path
import tempfile
import unittest

from pact.scan.model import ScanArchitecture, ScanCell, ScanChain
from pact_generalization import sha
from pact_cold_start_physical import load_selection


class ProspectivePhysicalHandoffTest(unittest.TestCase):
    def make_package(self, root, architecture=None):
        def artifact(name, data):
            path = root/name
            path.write_text(json.dumps(data), encoding='utf-8')
            return dict(path=str(path), sha256=sha(path), bytes=path.stat().st_size)
        cells = tuple(ScanCell(f'ff{i}', float(i), float(i % 2), 'CK') for i in range(16))
        reference = ScanArchitecture(cells, (
            ScanChain('chain_0', tuple(c.name for c in cells[:8]), 'test_si', 'test_so'),
            ScanChain('chain_1', tuple(c.name for c in cells[8:]), 'test_si_1', 'test_so_1')))
        candidate = architecture or ScanArchitecture(cells, (
            ScanChain('chain_0', tuple(reversed(reference.chains[0].cells)), 'test_si', 'test_so'),
            reference.chains[1]))
        def arch_binding(name, arch):
            path = root/name
            arch.to_json(path)
            return dict(path=str(path), sha256=sha(path), bytes=path.stat().st_size)
        ref = arch_binding('external.json', reference)
        after = arch_binding('candidate.json', candidate)
        prep = {name: artifact(name+'.json', {}) for name in
            ('source', 'patterns', 'source_placed_database', 'SDC', 'placed_def', 'config')}
        prep_binding = artifact('preparation.json', prep)
        artifacts = dict(architecture=ref, qualification=artifact('reference_route.json', {'status':'QUALIFIED'}),
            reference_fault_export=artifact('faults.json', {'records': []}),
            reference_serial=artifact('serial.json', {'status': 'PASS'}),
            identity_map=artifact('identity.json', {'records': []}))
        artifacts.update(patterns=prep['patterns'], source_placed_database=prep['source_placed_database'],
            SDC=prep['SDC'], placement=prep['placed_def'], source_netlist=artifact('compatible.v', {}))
        package = artifact('cold_start_input.json', dict(schema='pact_cold_start_input_v1',
            design='arbitrary_unseen_name', reference_method='B2', reference_architecture_hash=reference.sha256(),
            preparation=prep_binding, reference=artifact('reference_frozen.json', {'status': 'REFERENCE_FROZEN'}),
            artifacts=artifacts))
        selection = artifact('preselected_candidates.json', dict(design='arbitrary_unseen_name',
            cold_start_input=package, records=[dict(candidate='CS_C1', role='primary',
                architecture=after, architecture_hash=candidate.sha256(), parent_reference_hash=reference.sha256())]))
        return Path(selection['path']), reference, candidate

    def test_arbitrary_unseen_name_passes_explicit_artifact_handoff(self):
        with tempfile.TemporaryDirectory() as name:
            selection, reference, candidate = self.make_package(Path(name))
            loaded = load_selection(selection)
            self.assertEqual(loaded['design'], 'arbitrary_unseen_name')
            self.assertEqual(loaded['before'].sha256(), reference.sha256())
            self.assertEqual(loaded['validated'][0][1].sha256(), candidate.sha256())

    def test_functional_inventory_and_topology_capacity_fail_before_routing(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            _, before, _ = self.make_package(root)
            changed = ScanArchitecture(before.cells, (
                ScanChain('chain_0', before.chains[0].cells, 'wrong_si', 'test_so'), before.chains[1]))
            selection, _, _ = self.make_package(root, changed)
            with self.assertRaisesRegex(ValueError, 'Chain identities'):
                load_selection(selection)

    def test_altered_architecture_file_rejected_before_routing(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            selection, _, _ = self.make_package(root)
            with (root/'candidate.json').open('a') as stream:
                stream.write('\n')
            with self.assertRaisesRegex(ValueError, 'Artifact binding mismatch'):
                load_selection(selection)


if __name__ == '__main__':
    unittest.main()
