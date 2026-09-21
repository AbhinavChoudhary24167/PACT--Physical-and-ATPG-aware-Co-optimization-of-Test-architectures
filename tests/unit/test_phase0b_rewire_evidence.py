"""Regression check on one frozen OpenDB scan-only rewire output."""
from __future__ import annotations

import json
from pathlib import Path
import sys

from pact.scan.identity import scan_ff_instances
from pact.scan.model import ScanArchitecture


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from verify_rewire_s5378 import def_placements, normalize_scan_connectivity


def test_s5378_seed11_open_db_rewire_preserves_placement_and_functional_netlist():
    folder = ROOT / "artifacts/derived/phase0b/s5378/s11"
    before = ROOT / "artifacts/raw/phase0b/placements/s5378/s11"
    after = ROOT / "artifacts/raw/phase0b/rewire/s5378/s11/P"
    endpoints = json.loads((folder / "P.rewire_endpoints.json").read_text())
    architecture = ScanArchitecture.from_json(folder / "P.architecture.json")
    original = (before / "placed.v").read_text()
    rewired = (after / "rewired.v").read_text()
    assert def_placements(before / "placed.def") == def_placements(after / "rewired.def")
    assert (normalize_scan_connectivity(original, endpoints["scan_out_buffer"])
            == normalize_scan_connectivity(rewired, endpoints["scan_out_buffer"]))
    ff = {record.name: record for record in scan_ff_instances(after / "rewired.v")}
    order = architecture.chains[0].cells
    assert len(order) == len(ff) == len(set(order))
    assert ff[order[0]].si_net == endpoints["scan_root_net"]
    assert all(ff[left].q_net == ff[right].si_net for left, right in zip(order, order[1:]))
    assert ff[order[-1]].q_net == endpoints["new_terminal_q"]
