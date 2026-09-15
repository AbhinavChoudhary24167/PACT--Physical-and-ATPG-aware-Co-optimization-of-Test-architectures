from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


def route_module():
    scripts = Path(__file__).resolve().parents[2] / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        spec = importlib.util.spec_from_file_location("phase0c_run_route_test",
                                                      scripts / "phase0c_run_route.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(scripts))


def test_superseded_pilot_evidence_is_archived_without_overwrite(tmp_path: Path):
    module = route_module()
    (tmp_path / "route_metrics.json").write_text("pilot metrics", encoding="utf-8")
    (tmp_path / "routed_verification_v2.json").write_text("pilot proof", encoding="utf-8")
    (tmp_path / "route").mkdir()
    previous = {"variant": "phase0c_s11_k2_P_hash"}
    module.archive_superseded_evidence(tmp_path, previous)
    archive = tmp_path / "variants" / previous["variant"]
    assert (archive / "route_metrics.json").read_text() == "pilot metrics"
    assert (archive / "routed_verification_v2.json").read_text() == "pilot proof"
    (tmp_path / "route_metrics.json").write_text("later metrics", encoding="utf-8")
    module.archive_superseded_evidence(tmp_path, previous)
    assert (archive / "route_metrics.json").read_text() == "pilot metrics"
