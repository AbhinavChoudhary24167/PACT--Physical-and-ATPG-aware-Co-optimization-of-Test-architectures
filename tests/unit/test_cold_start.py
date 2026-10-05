"""Prospective loader regressions, using synthetic design-owned artifacts only."""
from __future__ import annotations

import builtins
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from pact.optimizer import candidate_physical as cp
from pact.optimizer import candidate_sensitive as cs
from pact.optimizer import candidate_stateful as sf
from pact.optimizer import implementation_v2 as v2
from pact.optimizer import stage_b as sb
from pact.optimizer.stage_b_inputs import Model as FrozenModel, load_bundle
from pact.physical.phase0c_port_policy import frozen_def_ports
from pact.scan.model import ScanArchitecture, ScanCell, ScanChain


def _json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _binding(path, relative_to):
    return {"path": str(path.relative_to(relative_to)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


@pytest.fixture
def unseen_package(tmp_path):
    """A genuine FAN/DEF/capacitance package with K=2 and eight FFs per chain."""
    names = tuple(f"ff{i:02d}" for i in range(16))
    architecture = ScanArchitecture(
        tuple(ScanCell(n, float(3 + i * 2), float(5 + i % 3 * 9), "CK")
              for i, n in enumerate(names)),
        (ScanChain("chain0", names[:8][::-1], "test_si_0", "test_so_0"),
         ScanChain("chain1", names[8:][::-1], "test_si_1", "test_so_1")))
    architecture.to_json(tmp_path / "architecture.json")
    placement = tmp_path / "placement.def"
    placement.write_text(
        "VERSION 5.8 ;\nUNITS DISTANCE MICRONS 2000 ;\n"
        "DIEAREA ( 0 0 ) ( 80000 80000 ) ;\nPINS 2 ;\n"
        "- test_si + NET test_si + DIRECTION INPUT + FIXED ( 0 20000 ) N ;\n"
        "- test_so + NET test_so + DIRECTION OUTPUT + FIXED ( 80000 40000 ) N ;\n"
        "END PINS\nEND DESIGN\n", encoding="utf-8")
    ports, unit = frozen_def_ports(placement, 2)
    inputs = [np.asarray(ports[p], float) / unit for p in ("test_si", "test_si_1")]
    outputs = [np.asarray(ports[p], float) / unit for p in ("test_so", "test_so_1")]

    rng = np.random.default_rng(19)
    load = rng.integers(0, 2, (3, 16), dtype=np.uint8)
    response = rng.integers(0, 2, (3, 16), dtype=np.uint8)
    signal_names = tuple(f"ATPG_{i:02d}" for i in range(16))
    identity = [dict(logical_ff=f"logic_{i}", physical_instance=n,
                     atpg_signal=signal_names[i], clock_domain="CK")
                for i, n in enumerate(names)]
    _json(tmp_path / "identity.json", {"records": identity})
    pattern_lines = ["IN_0 |", " ".join(signal_names) + " |", "OUT_0", "BASIC_SCAN",
                     "_num_of_pattern_3"]
    primary = np.asarray([0, 1, 1], np.uint8)
    for i in range(3):
        ppi = "".join(map(str, load[i]))
        ppo = "".join(map(str, response[i]))
        pattern_lines.append(f"_pattern_{i + 1} {primary[i]}||{ppi}||0||{ppo}")
    (tmp_path / "patterns.pat").write_text("\n".join(pattern_lines) + "\n", encoding="utf-8")

    cells = {c.name: dict(master="SDFF_X1", xy=[c.x_um, c.y_um], inputs={},
                         outputs={"Q": c.name + "q", "QN": c.name + "n"},
                         transparent=False) for c in architecture.cells}
    cells["gate1"] = dict(master="XOR2_X1", xy=[12., 15.],
                          inputs={"A": "ff00q", "B": "ff01n"}, outputs={"Z": "gate1z"},
                          transparent=False)
    cells["gate2"] = dict(master="AND2_X1", xy=[16., 15.],
                          inputs={"A": "gate1z", "B": "primary"}, outputs={"Z": "gate2z"},
                          transparent=False)
    nets = {}
    for n, cell in cells.items():
        for pin, net in cell["outputs"].items():
            nets[net] = dict(source=n + "/" + pin, xy=cell["xy"], sinks=[], ports=[])
    nets["primary"] = dict(source="PORT/IN_0", xy=[0., 15.], sinks=[], ports=[])
    for ci, chain in enumerate(architecture.chains):
        p = "test_si" if ci == 0 else "test_si_1"
        nets[f"si{ci}"] = dict(source="PORT/" + p, xy=inputs[ci].tolist(), sinks=[], ports=[])
        sequence = [f"si{ci}"] + [n + "q" for n in chain.cells[:-1]]
        for source, target in zip(sequence, chain.cells, strict=True):
            nets[source]["sinks"].append(dict(cell=target, pin="SI", xy=cells[target]["xy"], cap=1.))
        p = "test_so" if ci == 0 else "test_so_1"
        nets[chain.cells[-1] + "q"]["ports"].append(dict(name=p, xy=outputs[ci].tolist()))
    for name in ("gate1", "gate2"):
        for pin, net in cells[name]["inputs"].items():
            nets[net]["sinks"].append(dict(cell=name, pin=pin, xy=cells[name]["xy"], cap=1.))
    nets["gate2z"]["ports"].append(dict(name="OUT_0", xy=[40., 15.]))
    graph = dict(cells=cells, nets=nets, bounds=[0., 0., 40., 40.],
                 functions={"XOR2_X1/Z": "A ^ B", "AND2_X1/Z": "A & B"})
    caprows = [dict(net=n, source=net["source"], ground_ff=2.,
                    pin_ff=float(len(net["sinks"]))) for n, net in nets.items()]
    with (tmp_path / "caps.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(caprows[0]))
        writer.writeheader()
        writer.writerows(caprows)
    _json(tmp_path / "topology.json", graph)
    _json(tmp_path / "mapping.json", {"bounds_um": graph["bounds"]})

    paths = dict(architecture=tmp_path / "architecture.json", patterns=tmp_path / "patterns.pat",
                 identity_map=tmp_path / "identity.json", placement=placement,
                 mapping=tmp_path / "mapping.json", caps=tmp_path / "caps.csv",
                 topology=tmp_path / "topology.json")
    manifest = dict(schema="pact_cold_start_input_v1", design="entirely_unseen_design_42",
                    reference_method="B3T", reference_architecture_hash=architecture.sha256(),
                    artifacts={k: _binding(v, tmp_path) for k, v in paths.items()})
    manifest_path = tmp_path / "cold_start_input.json"
    _json(manifest_path, manifest)
    weights = [sum(float(r["ground_ff"]) + float(r["pin_ff"]) for r in caprows
                   if r["source"] in (n + "/Q", n + "/QN")) for n in names]
    frozen = v2.Model(architecture, load, response, weights, graph["bounds"], inputs, outputs)
    physical = cp.construct(frozen, graph, caprows)
    sensitive = cs.Model(frozen, physical, graph["bounds"])
    expected = FrozenModel(sensitive, graph, caprows, {"IN_0": primary}, depth=3)
    return dict(path=manifest_path, manifest=manifest, paths=paths, architecture=architecture,
                expected=expected, load=load, response=response, weights=weights,
                graph=graph, physical=physical, caprows=caprows, primary={"IN_0": primary},
                inputs=[p.tolist() for p in inputs], outputs=[p.tolist() for p in outputs])


def test_arbitrary_design_name_accepts_complete_artifacts(unseen_package):
    from pact.optimizer.cold_start import load
    model, starts, contract = load(unseen_package["path"])
    assert contract.design == "entirely_unseen_design_42"
    assert len(model.names) == 16
    assert model.load.shape == model.response.shape == (3, 16)
    assert [label for label, _ in starts] == ["B3T"]
    np.testing.assert_array_equal(model.load, unseen_package["load"])
    np.testing.assert_array_equal(model.response, unseen_package["response"])


def test_manifest_discovers_renamed_relative_and_absolute_artifacts(unseen_package):
    from pact.optimizer.cold_start import ColdStartPACTInput, load
    manifest = unseen_package["manifest"]
    folder = unseen_package["path"].parent / "arbitrary_artifact_folder"
    folder.mkdir()
    relocated = {}
    for index, (key, path) in enumerate(unseen_package["paths"].items()):
        target = folder / f"artifact_{index}{path.suffix}"
        path.rename(target)
        relocated[key] = target
        manifest["artifacts"][key] = _binding(target, unseen_package["path"].parent)
    manifest["artifacts"]["placement"]["path"] = str(relocated["placement"])
    _json(unseen_package["path"], manifest)
    contract = ColdStartPACTInput.from_manifest(unseen_package["path"])
    for key, path in relocated.items():
        assert contract.artifact(key).resolve() == path.resolve()
    model, starts, _ = load(unseen_package["path"])
    assert model.architecture_from(starts[0][1]).sha256() == unseen_package["architecture"].sha256()


def test_missing_or_changed_manifest_artifact_rejected(unseen_package):
    from pact.optimizer.cold_start import ColdStartPACTInput, load
    unseen_package["paths"]["patterns"].write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="[Hh]ash|SHA256|[Cc]hanged"):
        contract = ColdStartPACTInput.from_manifest(unseen_package["path"])
        contract.artifact("patterns")
        load(unseen_package["path"])


def test_external_reference_is_the_only_initial_architecture(unseen_package):
    from pact.optimizer.cold_start import load
    model, starts, contract = load(unseen_package["path"])
    assert [label for label, _ in starts] == ["B3T"]
    assert contract.initial_architecture.sha256() == unseen_package["architecture"].sha256()
    assert model.architecture_from(starts[0][1]).sha256() == contract.initial_architecture.sha256()
    assert model.canonical_id(starts[0][1]) == contract.initial_architecture.sha256()


def test_no_historical_p0_archive_or_operational_loader_access(unseen_package, monkeypatch):
    """Fail at the actual open/import boundary if any historical dependency returns."""
    historical = ("s5378", "s9234", "s15850", "historical_p0", "pact_candidate_sensitive",
                  "pact_candidate_stateful", "pact_stage_b/inputs", "pact_oss_benchmark",
                  "reports/physical_effect", "pact_v2")
    opened = []
    original_open = builtins.open
    original_path_open = Path.open
    original_import = builtins.__import__

    def check(path):
        resolved = Path(path).resolve()
        # Pytest derives its temp directory from this test's name. Inspect the
        # artifact-relative path there, so the guard does not mistake that
        # directory label for an actual historical P0 file access.
        root = unseen_package["path"].parent.resolve()
        checked = resolved.relative_to(root) if resolved.is_relative_to(root) else resolved
        text = str(checked).replace("\\", "/").lower()
        assert not any(token in text for token in historical), f"Historical state accessed: {path}"
        opened.append(resolved)

    def guard_open(path, *args, **kwargs):
        if isinstance(path, (str, Path)):
            check(path)
        return original_open(path, *args, **kwargs)

    def guard_path_open(path, *args, **kwargs):
        check(path)
        return original_path_open(path, *args, **kwargs)

    def guard_import(name, *args, **kwargs):
        assert name not in {"pact_stage_b", "pact_candidate_sensitive", "pact_v2", "pact_candidate_stateful"}, \
            f"Historical operational loader imported: {name}"
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guard_open)
    monkeypatch.setattr(Path, "open", guard_path_open)
    monkeypatch.setattr(builtins, "__import__", guard_import)
    # Positive controls prove that these guards fail on attempted historical
    # access, before any filesystem lookup or historical import takes place.
    with pytest.raises(AssertionError, match="Historical state accessed"):
        Path(unseen_package["path"].parent / "historical_p0.json").open()
    with pytest.raises(AssertionError, match="Historical operational loader"):
        builtins.__import__("pact_stage_b")
    from pact.optimizer.cold_start import load
    model, starts, _ = load(unseen_package["path"])
    assert starts[0][0] == "B3T"
    assert model.architecture_from(starts[0][1]).sha256() == unseen_package["architecture"].sha256()
    assert set(unseen_package["paths"].values()) <= set(opened)


def test_historical_p0_is_rejected_as_an_input_field(unseen_package):
    from pact.optimizer.cold_start import ColdStartPACTInput
    manifest = unseen_package["manifest"]
    manifest["historical_p0"] = {"path": "unavailable_historical_architecture.json"}
    _json(unseen_package["path"], manifest)
    with pytest.raises(ValueError, match="Historical search state"):
        ColdStartPACTInput.from_manifest(unseen_package["path"])


def test_unknown_atpg_bits_are_never_silently_filled(unseen_package):
    from pact.optimizer.cold_start import load
    path = unseen_package["paths"]["patterns"]
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    fields = lines[5].split("|")
    fields[2] = "X" + fields[2][1:]
    lines[5] = "|".join(fields)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    unseen_package["manifest"]["artifacts"]["patterns"] = _binding(path, path.parent)
    _json(unseen_package["path"], unseen_package["manifest"])
    with pytest.raises(ValueError, match="Unknown ATPG bits"):
        load(unseen_package["path"])


def test_architecture_serialization_is_exact_after_mutation(unseen_package, tmp_path):
    from pact.optimizer.cold_start import load
    model, starts, _ = load(unseen_package["path"])
    orders = [o.copy() for o in starts[0][1]]
    orders[0][[0, 1]] = orders[0][[1, 0]]
    architecture = model.architecture_from(orders)
    path = tmp_path / "mutated_architecture.json"
    architecture.to_json(path)
    restored = ScanArchitecture.from_json(path)
    assert restored.canonical_dict() == architecture.canonical_dict()
    assert restored.sha256() == model.canonical_id(orders)
    for actual, expected in zip(model.orders(restored), orders, strict=True):
        np.testing.assert_array_equal(actual, expected)


def test_candidate_sensitive_state_matches_frozen_full_replay(unseen_package):
    from pact.optimizer.cold_start import load
    model, starts, _ = load(unseen_package["path"])
    state = sf.State(model, starts[0][1])
    original = state.score().copy()
    np.testing.assert_allclose(original, sf.reference(unseen_package["expected"], starts[0][1]),
                               rtol=1e-12, atol=1e-10)
    patch = {0: (np.asarray([0, 1], np.int32), state.orders[0][[1, 0]].copy())}
    undo = state.change(patch)
    np.testing.assert_allclose(state.score(), sf.reference(model, state.orders), rtol=1e-12, atol=1e-10)
    # This is a meaningful changed successor/capacitance test, not only an initial-state comparison.
    assert not np.array_equal(state.score(), original)
    state.change(undo)
    np.testing.assert_allclose(state.score(), original, rtol=1e-12, atol=1e-10)


def test_topology_preserves_inventory_placement_and_endpoints(unseen_package):
    from pact.optimizer.cold_start import load
    model, starts, _ = load(unseen_package["path"])
    orders = [o.copy() for o in starts[0][1]]
    orders[0][[0, 1]] = orders[0][[1, 0]]
    candidate = model.architecture_from(orders)
    assert candidate.cells == unseen_package["architecture"].cells
    assert sorted(n for c in candidate.chains for n in c.cells) == sorted(model.names)
    assert [(c.chain_id, c.scan_in, c.scan_out) for c in candidate.chains] == [
        (c.chain_id, c.scan_in, c.scan_out) for c in unseen_package["architecture"].chains]
    _, audit = model.geometry.capacitances(orders, details=True)
    for net, row in audit.items():
        actual = {t["id"] for t in row["candidate_terminals"]}
        assert {t["id"] for t in model.geometry.fixed[net]} <= actual
    with pytest.raises(ValueError, match="bijection|capacity|capacities"):
        model.architecture_from([np.zeros(8, np.int32), orders[1]])


def test_frozen_portable_input_semantics_remain_compatible(unseen_package, tmp_path):
    """Compare with the unchanged historical API using independent synthetic data."""
    from pact.optimizer.cold_start import load
    initial = unseen_package["architecture"]
    expected = unseen_package["expected"]
    portable = dict(schema="pact_stage_b_inputs_v1", architecture=initial.canonical_dict(),
                    load=unseen_package["load"].tolist(), response=unseen_package["response"].tolist(),
                    caps=unseen_package["weights"], bounds=unseen_package["graph"]["bounds"],
                    inputs=unseen_package["inputs"], outputs=unseen_package["outputs"],
                    physical=unseen_package["physical"], graph=unseen_package["graph"],
                    caprows=unseen_package["caprows"],
                    primary={k: v.tolist() for k, v in unseen_package["primary"].items()}, depth=3,
                    starts=[dict(label="B3T", orders=[o.tolist() for o in expected.orders(initial)])],
                    reference_label="B3T")
    path = tmp_path / "portable_regression_bundle.json"
    _json(path, portable)
    old_model, old_starts, old_label = load_bundle(path)
    new_model, new_starts, _ = load(unseen_package["path"])
    assert isinstance(new_model, FrozenModel)
    assert old_label == new_starts[0][0]
    np.testing.assert_allclose(sf.reference(old_model, old_starts[0][1]),
                               sf.reference(new_model, new_starts[0][1]), rtol=0, atol=0)
    # Run only synthetic short regressions; no historical search is executed.
    config = sb.Config(epsilon=.10, seconds=10, max_evaluations=8, stagnation_attempts=50)
    old_result = sb.optimize(old_model, old_starts, old_label, config)
    new_result = sb.optimize(new_model, new_starts, "B3T", config)
    assert old_result["evaluations"] == new_result["evaluations"] == 8
    assert old_result["attempts"] == new_result["attempts"]
    assert [(old_model.canonical_id(r["orders"]), r["roles"]) for r in old_result["selected"]] == [
        (new_model.canonical_id(r["orders"]), r["roles"]) for r in new_result["selected"]]
