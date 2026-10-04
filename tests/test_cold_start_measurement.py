"""Exact parser semantics survive additive cold-start resource instrumentation."""
import importlib.util
import os
import sys
import time
from pathlib import Path
import tempfile
import unittest
import numpy as np

from pact_cold_start_measure_analyze import AnalysisTimers, FROZEN, instrumented_namespace


class MeasurementInstrumentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('frozen_physical_effect_for_test', FROZEN)
        cls.frozen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.frozen)

    def test_original_executable_operations_retained(self):
        # Loader strips its own insertions and asserts complete AST equality.
        instrumented_namespace(AnalysisTimers())

    def test_exact_timestamp_final_marker_and_alias_counts(self):
        value = '''$scope module tb $end
$var integer 32 c cycle_id [31:0] $end
$scope module dut $end
$var wire 1 a net_a $end
$var wire 1 a net_alias $end
$upscope $end
$upscope $end
$enddefinitions $end
#0
b11111111111111111111111111111111 c
0a
#10
1a
b0 c
#20
0a
b1 c
#30
b11111111111111111111111111111111 c
1a
'''
        timers = AnalysisTimers()
        instrumented = instrumented_namespace(timers)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'synthetic.vcd'
            path.write_text(value)
            actual, actual_info = instrumented['vcd_transitions'](path, ['net_a', 'net_alias'], 2)
            expected, expected_info = self.frozen.vcd_transitions(path, ['net_a', 'net_alias'], 2)
        np.testing.assert_array_equal(actual, expected)
        np.testing.assert_array_equal(actual, np.ones((2, 2), dtype=np.uint8))
        self.assertEqual(actual_info, expected_info)
        self.assertGreater(timers.stages['transition_extraction']['calls'], 0)

    def test_unknown_active_transition_still_rejected(self):
        value = '''$scope module tb $end
$var integer 32 c cycle_id $end
$scope module dut $end
$var wire 1 a net_a $end
$upscope $end
$upscope $end
$enddefinitions $end
#0
b11111111111111111111111111111111 c
0a
#10
b0 c
xa
'''
        instrumented = instrumented_namespace(AnalysisTimers())
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'unknown.vcd'
            path.write_text(value)
            with self.assertRaisesRegex(ValueError, 'Unknown active net'):
                instrumented['vcd_transitions'](path, ['net_a'], 1)
            with self.assertRaisesRegex(ValueError, 'Unknown active net'):
                self.frozen.vcd_transitions(path, ['net_a'], 1)

    @unittest.skipUnless(hasattr(os, 'wait4'), 'Linux stage-resource collection')
    def test_timeout_preserves_simulator_cpu_rss_and_partial_stage_receipt(self):
        import json
        from pact_cold_start_measure import execute_stage
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            with self.assertRaisesRegex(RuntimeError, 'Measurement stage failed'):
                execute_stage([sys.executable, '-c', 'import time; time.sleep(5)'], folder, 'simulate', time.perf_counter() + .1)
            record = json.loads((folder / 'simulate.execution.json').read_text())
            self.assertTrue(record['timed_out'])
            self.assertLess(record['returncode'], 0)
            self.assertGreater(record['peak_RSS_KiB'], 0)
            self.assertGreaterEqual(record['CPU_seconds'], 0)
            self.assertLess(record['wall_seconds'], 2)


if __name__ == '__main__':
    unittest.main()
