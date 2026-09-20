from pathlib import Path
import importlib.util

from pact.phase0d.pareto import ObjectiveBounds


ROOT = Path(__file__).resolve().parents[2]


def load_pilot_module():
    spec = importlib.util.spec_from_file_location("phase0d_pilot", ROOT / "scripts/phase0d_pilot.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_bounds_serialization_and_route_result_location() -> None:
    pilot = load_pilot_module()
    assert pilot._bounds_dict(ObjectiveBounds((1, 2, 3), (4, 5, 6))) == {
        "ideal": [1, 2, 3], "reference": [4, 5, 6],
    }
    route = pilot._route_result_path({"architecture_sha256": "a" * 64})
    assert route == ROOT / "artifacts/raw/phase0d/pilot/s5378/s11/k2" / ("a" * 64) / "route_result.json"
    assert pilot._route_result_path({"architecture_sha256": None}) is None


def test_source_hashes_cover_frozen_search_components() -> None:
    pilot = load_pilot_module()
    hashes = pilot._source_hashes()
    assert "config/phase0d_pilot_contract.json" in hashes
    assert "src/pact/phase0d/search.py" in hashes
    assert all(len(value) == 64 for value in hashes.values())
    scientific = pilot._scientific_source_hashes()
    assert "scripts/phase0d_pilot.py" not in scientific
    assert pilot._sources_compatible(hashes)
