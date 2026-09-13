from __future__ import annotations

import pytest

from pact.scan.model import ScanArchitecture, ScanCell, ScanChain
from pact.scan.validate import ScanConstraints, validate_ff_identity_map, validate_scan
from pact.scan.orderings import activity_only, nearest_neighbor, physical_activity, random_order, serpentine


def test_scan_no_duplicates(tiny_arch: ScanArchitecture) -> None:
    bad = ScanArchitecture(tiny_arch.cells, (ScanChain("x", ("a", "b", "b", "d")),))
    with pytest.raises(ValueError, match="Duplicate"):
        validate_scan(bad)


def test_scan_no_missing_cells(tiny_arch: ScanArchitecture) -> None:
    bad = ScanArchitecture(tiny_arch.cells, (ScanChain("x", ("a", "b", "d")),))
    with pytest.raises(ValueError, match="missing cells"):
        validate_scan(bad)


def test_scan_deterministic_hash(tiny_arch: ScanArchitecture, tmp_path) -> None:
    reordered_cells = ScanArchitecture(tuple(reversed(tiny_arch.cells)), tiny_arch.chains)
    assert reordered_cells.sha256() == tiny_arch.sha256()
    path = tmp_path / "architecture.json"
    tiny_arch.to_json(path)
    assert ScanArchitecture.from_json(path).sha256() == tiny_arch.sha256()


def test_random_order_seed_reproducibility(tiny_arch: ScanArchitecture) -> None:
    assert random_order(tiny_arch, 11).sha256() == random_order(tiny_arch, 11).sha256()
    assert random_order(tiny_arch, 11).sha256() != random_order(tiny_arch, 13).sha256()


def test_nearest_neighbor_determinism(tiny_arch: ScanArchitecture) -> None:
    assert nearest_neighbor(tiny_arch).chains[0].cells == ("a", "b", "c", "d")
    assert nearest_neighbor(tiny_arch).sha256() == nearest_neighbor(tiny_arch).sha256()


def test_serpentine_legal(tiny_arch: ScanArchitecture) -> None:
    validate_scan(serpentine(tiny_arch, 2), ScanConstraints(expected_chain_lengths=(4,)))


def test_clock_domain_constraint(tiny_arch: ScanArchitecture) -> None:
    cells = tiny_arch.cells[:-1] + (ScanCell("d", 4, 2, "other"),)
    with pytest.raises(ValueError, match="Mixed clock"):
        validate_scan(ScanArchitecture(cells, tiny_arch.chains))


def test_ff_identity_map_unique() -> None:
    good = [{"logical_ff": "ff0", "physical_instance": "p0", "atpg_signal": "ppi0", "clock_domain": "clk"}]
    validate_ff_identity_map(good, ["p0"])
    with pytest.raises(ValueError, match="Ambiguous"):
        validate_ff_identity_map(good + [{**good[0], "logical_ff": "ff1"}])


def test_activity_heuristics_deterministic(tiny_arch: ScanArchitecture) -> None:
    patterns = [
        {"a": 0, "b": 0, "c": 1, "d": 1},
        {"a": 1, "b": 1, "c": 0, "d": 0},
        {"a": 0, "b": 1, "c": 0, "d": 1},
    ]
    first = activity_only(tiny_arch, patterns)
    assert first.sha256() == activity_only(tiny_arch, patterns).sha256()
    assert first.sha256() == physical_activity(tiny_arch, patterns, 0.0).sha256()
    assert nearest_neighbor(tiny_arch).sha256() == physical_activity(tiny_arch, patterns, 1.0).sha256()
