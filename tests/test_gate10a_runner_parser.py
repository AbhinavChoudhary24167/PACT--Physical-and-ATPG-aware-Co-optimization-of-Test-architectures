"""Focused admission tests for SI, population, geometry, and solver integrity."""
import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gate10a_run", ROOT / "scripts/gate10a_run.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class RunnerParserTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.protocol = json.loads((ROOT / "reports/gate10a/protocol.json").read_text())
        self.row = {"bounds_um": [0, 0, 10, 10], "ff_count": 1}
        self.write("instance_power.csv", [{"instance": "cell", "x_um": 5, "y_um": 5, "master": "DFF_X1",
            "physical_only": 0, "powered": 1, "liberty_modelled": 1,
            "internal_w": .0001, "switching_w": .0002, "leakage_w": .00003, "total_w": .00033}])
        self.write("instance_voltage.csv", [{"Instance": "cell", "Terminal": "VDD", "Layer": "metal1",
            "X location": 5, "Y location": 5, "Voltage": 1.099}])
        self.write("segment_current.csv", [{"Node0 Layer": "metal1", "Node0 X location": 4, "Node0 Y location": 5,
            "Node1 Layer": "metal1", "Node1 X location": 6, "Node1 Y location": 5, "Current": .0003}])
        (self.folder / "sources.csv").write_text("1,1,1,1.1\n")
        (self.folder / "pdn_geometry.tsv").write_text("net\ttype\tlayer\txmin_dbu\tymin_dbu\txmax_dbu\tymax_dbu\tvia\nVDD\tPOWER\tmetal1\t0\t0\t100\t100\t\n")
        (self.folder / "unannotated_nets.tsv").write_text("net\ttype\titerms\tbterms\tfallback_density_per_ns\n")
        (self.folder / "openroad.log").write_text("All shapes on net VDD are connected.\nAll shapes on net VDD are connected.\nIR report\nEM analysis\nGATE10A_POWER_SI 0.0001 0.0002 0.00003\nGATE10A_FF_POPULATION 1\nGATE10A_MEASURE_COMPLETE\n")
        self.report = {k: dict(internal=0.0, switching=0.0, leakage=0.0, total=0.0)
            for k in ("Sequential", "Combinational", "Clock", "Macro", "Pad", "Total")}
        self.report["Sequential"] = dict(internal=.0001, switching=.0002, leakage=.00003, total=.00033)
        self.report["Total"] = dict(self.report["Sequential"])
        self.native()
        (self.folder / "native_power_units.json").write_text(json.dumps({"watts_per_UI_unit": 1e-9, "UI_units_per_watt": 1e9}))

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, rows):
        with (self.folder / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def native(self):
        (self.folder / "power_report.json").write_text(json.dumps(self.report))

    def parse(self):
        return runner.parse_outputs(self.folder, self.row, self.protocol)

    def test_complete_si_record_is_admitted(self):
        result = self.parse()
        self.assertEqual(result["native_power_integrity"]["status"], "PASS")
        self.assertEqual(result["ir"]["powered_instances"], 1)

    def test_duplicate_power_is_rejected(self):
        path = self.folder / "instance_power.csv"
        path.write_text(path.read_text() + path.read_text().splitlines()[1] + "\n")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.parse()

    def test_native_unit_error_is_rejected(self):
        for group in self.report.values():
            for key in group:
                group[key] *= 1000
        self.native()
        with self.assertRaisesRegex(ValueError, "Native SI"):
            self.parse()

    def test_missing_supply_terminal_is_rejected(self):
        path = self.folder / "instance_voltage.csv"
        path.write_text(path.read_text().splitlines()[0] + "\n")
        with self.assertRaisesRegex(ValueError, "Incomplete powered-instance"):
            self.parse()

    def test_out_of_die_coordinate_is_rejected(self):
        path = self.folder / "instance_power.csv"
        path.write_text(path.read_text().replace("cell,5,5", "cell,11,5"))
        with self.assertRaisesRegex(ValueError, "out-of-die"):
            self.parse()

    def test_nonfinite_segment_coordinate_is_rejected(self):
        path = self.folder / "segment_current.csv"
        path.write_text(path.read_text().replace("metal1,4,5", "metal1,nan,5"))
        with self.assertRaisesRegex(ValueError, "coordinate"):
            self.parse()

    def test_solver_error_is_rejected(self):
        (self.folder / "solve_errors.txt").write_text("unconnected load\n")
        with self.assertRaisesRegex(ValueError, "error file"):
            self.parse()


if __name__ == "__main__":
    unittest.main()
