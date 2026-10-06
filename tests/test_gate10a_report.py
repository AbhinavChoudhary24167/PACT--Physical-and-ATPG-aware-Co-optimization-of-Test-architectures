"""Synthetic receipt/parser controls; no architecture outcomes are consumed."""
import copy
import csv
import gzip
import importlib.util
import json
from pathlib import Path
import struct

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/gate10a_report.py"
SPEC = importlib.util.spec_from_file_location("gate10a_report", SCRIPT)
report = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(report)


def primitives():
    powers, voltages, activity = [], [], []
    for index, (x, drop) in enumerate(((1, 0.02), (15, 0.04), (25, 0.08)), 1):
        internal, switching, leakage = index * 0.001, index * 0.0002, 0.00001
        powers.append(dict(instance=f"u{index}", x_um=str(x), y_um="1", physical_only="0", powered="1",
                           liberty_modelled="1", internal_w=str(internal), switching_w=str(switching),
                           leakage_w=str(leakage), total_w=str(internal + switching + leakage)))
        voltages.append({"Instance": f"u{index}", "Terminal": "VDD", "Layer": "metal1",
                         "X location": str(x + 1), "Y location": "2", "Voltage": str(1.1 - drop)})
        activity.append(dict(net=f"n{index}", source=f"u{index}/Q", x_um=str(x), y_um="1",
                             transitions=str(index * 2), ground_pin_ff="2"))
    powers.append(dict(instance="tap", x_um="35", y_um="35", physical_only="1", powered="1",
                       liberty_modelled="0", internal_w="0", switching_w="0", leakage_w="0", total_w="0"))
    voltages += [{"Instance": "u1", "Terminal": "VDD2", "Layer": "metal1", "X location": "2",
                  "Y location": "3", "Voltage": "1.09"},
                 {"Instance": "tap", "Terminal": "VDD", "Layer": "metal1", "X location": "35",
                  "Y location": "35", "Voltage": "0.6"}]
    segments = [{"Node0 X location": "0", "Node0 Y location": "0", "Node1 X location": "10",
                 "Node1 Y location": "0", "Node0 Layer": "metal1", "Node1 Layer": "metal1", "Current": "-0.001"},
                {"Node0 X location": "20", "Node0 Y location": "0", "Node1 X location": "30",
                 "Node1 Y location": "0", "Node0 Layer": "metal1", "Node1 Layer": "metal1", "Current": "0.003"}]
    export = dict(bounds_um=[0, 0, 40, 40], scan_cycles=2)
    protocol = dict(voltage_v=1.1, percentiles=[50, 95, 99], spatial_resolutions=[4, 8],
                    drop_threshold_fraction=[0.01, 0.03, 0.05])
    result = dict(power=dict(internal_w=0.006, switching_w=0.0012, leakage_w=0.00003, total_w=0.00723, dynamic_w=0.0072),
                  ir=dict(worst_drop_v=0.08, mean_drop_v=0.14 / 3, p50_drop_v=0.04, p95_drop_v=0.076,
                          p99_drop_v=0.0792, powered_instances=3, voltage_rows=5),
                  current=dict(peak_segment_current_a=0.003, p50_segment_current_a=0.002,
                               p95_segment_current_a=0.0029, p99_segment_current_a=0.00298, segments=2))
    return powers, voltages, segments, activity, export, protocol, result


def test_raw_population_collapses_supply_terminals_excludes_physical_only_and_keeps_locations():
    summary = report.summarize_raw(*primitives())
    assert summary["ir"]["powered_instances"] == 3
    assert summary["ir"]["voltage_rows"] == 5
    assert summary["ir"]["worst_drop_v"] == pytest.approx(0.08)
    assert summary["ir"]["p50_drop_v"] == pytest.approx(0.04)
    assert summary["ir"]["worst_drop_instances"] == [dict(instance="u3", x_um=25, y_um=1)]
    assert summary["current"]["peak_segments"][0]["x_um"] == 25
    assert summary["current"]["current_density_status"].startswith("NOT_EVALUATED")
    assert [summary["ir"][f"count_over_{p}pct_supply"] for p in (1, 3, 5)] == [3, 2, 1]
    assert summary["ir"]["grid4_coarse_area_um2_over_3pct_supply"] == 200
    assert len(summary["grids"]["4"]["activity"]["values"]) == 16
    assert len(summary["grids"]["8"]["static_vdd_drop"]["values"]) == 64
    assert summary["grids"]["4"]["domain"]["bin_ids"] == [0, 1, 2]
    assert len(summary["correlations"]) == 6
    assert all(row["spearman_rho"] == pytest.approx(1) for row in summary["correlations"] if row["comparison"].startswith("mean_activity_"))
    diagnostics = [row for row in summary["correlations"] if row["comparison"].startswith("diagnostic_")]
    assert all(row["status"] == "UNAVAILABLE" for row in diagnostics)  # missing branch midpoint observation stays missing


@pytest.mark.parametrize("case,match", [
    ("aggregate", "aggregate differs"), ("missing_power", "Missing raw instance power"),
    ("missing_terminal", "Incomplete powered-instance"), ("duplicate_terminal", "Duplicate observation"),
    ("duplicate_segment", "Duplicate raw PDN"), ("terminal_outside", "outside die"),
    ("segment_outside", "outside die"), ("wrong_population", "population differs"),
    ("origin", "source-origin mismatch"), ("unpowered", "lacks qualified power model")])
def test_raw_qualification_rejects_corrupted_or_incomplete_evidence(case, match):
    args = primitives()
    if case == "aggregate":
        args[-1]["power"]["switching_w"] = 1.2  # mW misparsed as W
    elif case == "missing_power":
        args[0][0]["internal_w"] = ""
    elif case == "missing_terminal":
        args[1][:] = [row for row in args[1] if row["Instance"] != "u3"]
    elif case == "duplicate_terminal":
        args[1].append(copy.deepcopy(args[1][0]))
    elif case == "duplicate_segment":
        args[2].append(copy.deepcopy(args[2][0]))
    elif case == "terminal_outside":
        args[1][0]["X location"] = "41"
    elif case == "segment_outside":
        args[2][0]["Node0 X location"] = "-1"
    elif case == "wrong_population":
        args[-1]["ir"]["voltage_rows"] = 4
    elif case == "origin":
        args[3][0]["x_um"] = "2"
    elif case == "unpowered":
        args[0][0]["powered"] = "0"
    with pytest.raises(ValueError, match=match):
        report.summarize_raw(*args)


def compact(path, names, rows, footer=b"PACTDONE"):
    with gzip.open(path, "wb") as stream:
        stream.write(b"PACTCN01" + struct.pack("<II", len(names), len(rows)))
        for name in names:
            value = name.encode()
            stream.write(struct.pack("<I", len(value)) + value)
        stream.write(bytes(value for row in rows for value in row))
        stream.write(footer)


def test_secondary_peak_maps_reconstruct_different_peak_cycles_and_do_not_substitute_means(tmp_path):
    path = tmp_path / "counts.gz"
    compact(path, ["a", "b"], [[1, 0], [0, 3], [2, 1]])
    rows = [dict(net="a", x_um=1, y_um=1, ground_pin_ff=2, transitions=3),
            dict(net="b", x_um=15, y_um=1, ground_pin_ff=1, transitions=4)]
    maps = report.frozen_peak_maps(path, rows, [0, 0, 40, 40], 3, [4, 8])
    assert maps["4"]["values"][:2] == [4, 3]
    assert maps["4"]["peak_cycle_index_zero_based"][:2] == [2, 1]
    assert len(maps["8"]["values"]) == 64
    assert maps["8"]["values"][3] == 3
    assert maps["4"]["unit"] == "fF transitions"
    rows[0]["transitions"] = 4
    with pytest.raises(ValueError, match="counts differ"):
        report.frozen_peak_maps(path, rows, [0, 0, 40, 40], 3, [4, 8])


def test_peak_map_complete_footer_net_identity_and_chunk_boundary(tmp_path):
    path = tmp_path / "counts.gz"
    rows = [dict(net="a", x_um=0, y_um=0, ground_pin_ff=2, transitions=513)]
    compact(path, ["a"], [[1]] * 513)
    assert report.frozen_peak_maps(path, rows, [0, 0, 40, 40], 513, [4])["4"]["values"][0] == 2
    compact(path, ["a"], [[1]] * 513, footer=b"PARTDONE")
    with pytest.raises(ValueError, match="completion footer"):
        report.frozen_peak_maps(path, rows, [0, 0, 40, 40], 513, [4])
    compact(path, ["b"], [[1]] * 513)
    with pytest.raises(ValueError, match="net mapping differs"):
        report.frozen_peak_maps(path, rows, [0, 0, 40, 40], 513, [4])


def json_file(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return report.binding(path)


def selection_fixture(tmp_path):
    fingerprint = {"runner_source.py": "runner", "measurement_source.tcl": "tcl"}
    snapshots = []
    for name, content in list(fingerprint.items()):
        path = tmp_path / "sources" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        snapshots.append(report.binding(path))
        fingerprint[name] = snapshots[-1]["sha256"]
    nominal = dict(design="b14_opt", architecture="B3T", status="QUALIFIED", nonclock_density_scale=1,
                   completed_utc="2026-10-06T04:00:00+00:00", execution_source_snapshots=snapshots, outputs=[])
    receipt = json_file(tmp_path / "B3T" / "good" / "receipt.json", nominal)
    controls = [json_file(tmp_path / "smoke_controls" / str(index) / "receipt.json",
                          dict(nominal, nonclock_density_scale=scale, completed_utc="2026-10-06T04:10:00+00:00"))
                for index, scale in enumerate((1, 0, 2))]
    smoke = dict(status="PASS", flow_fingerprint=fingerprint, invalidated_receipts=[],
                 records=[receipt, *controls], nominal_architecture_receipt=receipt)
    smoke_binding = json_file(tmp_path / "smoke.json", smoke)
    manifest = dict(smoke_qualification=smoke_binding, runs=[dict(design="b14_opt", architecture="B3T", receipt=receipt)])
    manifest_path = tmp_path / "manifest.json"
    json_file(manifest_path, manifest)
    return manifest_path, manifest, smoke, nominal


def test_selection_uses_earliest_admissible_nominal_and_ignores_density_controls(tmp_path):
    path, manifest, smoke, nominal = selection_fixture(tmp_path)
    for scale in (0, 2):
        control = dict(nominal, nonclock_density_scale=scale, completed_utc="2026-10-06T03:00:00+00:00")
        json_file(tmp_path / "B3T" / f"control{scale}" / "receipt.json", control)
    records, _, _ = report.selected_runs(path)
    assert records[("b14_opt", "B3T")][0].parent.name == "good"
    json_file(tmp_path / "B3T" / "older" / "receipt.json", dict(nominal, completed_utc="2026-10-06T03:30:00+00:00"))
    with pytest.raises(ValueError, match="earliest completed"):
        report.selected_runs(path)


def test_invalidated_legacy_qualified_and_different_source_attempts_do_not_enter_selection(tmp_path):
    path, manifest, smoke, nominal = selection_fixture(tmp_path)
    legacy = json_file(tmp_path / "B3T" / "legacy" / "receipt.json",
                       dict(nominal, completed_utc="2026-10-06T03:00:00+00:00"))
    wrong = dict(nominal, completed_utc="2026-10-06T03:30:00+00:00", execution_source_snapshots=[])
    json_file(tmp_path / "B3T" / "wrong_source" / "receipt.json", wrong)
    smoke["invalidated_receipts"] = [legacy]
    manifest["smoke_qualification"] = json_file(tmp_path / "smoke.json", smoke)
    json_file(path, manifest)
    assert report.selected_runs(path)[0][("b14_opt", "B3T")][0].parent.name == "good"
    manifest["runs"][0]["receipt"] = legacy
    json_file(path, manifest)
    with pytest.raises(ValueError, match="invalidated"):
        report.selected_runs(path)


@pytest.mark.parametrize("case,match", [("shared_fail", "Shared smoke did not qualify"),
                                       ("control", "Controls or incomplete"),
                                       ("identity", "identity mismatch"),
                                       ("changed", "Bound evidence changed"),
                                       ("duplicate", "Duplicate selected")])
def test_selection_fails_closed_for_invalid_receipts(tmp_path, case, match):
    path, manifest, smoke, nominal = selection_fixture(tmp_path)
    if case == "shared_fail":
        smoke["status"] = "FAIL"
        manifest["smoke_qualification"] = json_file(tmp_path / "smoke.json", smoke)
    elif case in ("control", "identity"):
        nominal["nonclock_density_scale" if case == "control" else "architecture"] = 2 if case == "control" else "CS_C1"
        manifest["runs"][0]["receipt"] = json_file(tmp_path / "alternate/receipt.json", nominal)
    elif case == "changed":
        (tmp_path / "B3T/good/receipt.json").write_text("{}")
    elif case == "duplicate":
        manifest["runs"].append(copy.deepcopy(manifest["runs"][0]))
    json_file(path, manifest)
    with pytest.raises(ValueError, match=match):
        report.selected_runs(path)


def test_machine_csv_keeps_nested_locations_as_valid_json_and_null_values_blank(tmp_path):
    path = tmp_path / "test.csv"
    report.write_csv(path, [dict(status="UNAVAILABLE", metric=None, locations=[dict(x_um=1)])],
                     ["status", "metric", "locations"])
    with path.open(newline="") as stream:
        row = next(csv.DictReader(stream))
    assert row["metric"] == ""
    assert json.loads(row["locations"]) == [dict(x_um=1)]


def test_zero_denominator_is_unavailable_not_imputed():
    assert report.relative_delta(0, 0) is None
    assert report.relative_delta(None, 1) is None
    assert report.relative_delta(0.9, 1) == pytest.approx(-0.1)


def test_immutable_derived_records_allow_identical_replay_and_reject_changed_bytes(tmp_path):
    path = tmp_path / "evidence.json"
    report.write_json(path, dict(status="PASS"), immutable=True)
    report.write_json(path, dict(status="PASS"), immutable=True)
    with pytest.raises(ValueError, match="Preserve immutable"):
        report.write_json(path, dict(status="FAIL"), immutable=True)
