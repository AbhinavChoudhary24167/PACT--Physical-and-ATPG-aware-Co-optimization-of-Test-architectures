#!/usr/bin/env python3
"""Add explicit scan-test semantics to an isolated Nangate45 Liberty copy."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path("/root/pact-deps/OpenROAD-flow-scripts/flow/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib")
OUTPUT = ROOT / "artifacts/derived/phase0b/lib/NangateOpenCellLibrary_typical_dft.lib"
ANNOTATION = '''\n\ttest_cell () {
\t\tff ("IQ", "IQN") {
\t\t\tclocked_on : "CK";
\t\t\tnext_state : "D";
\t\t}
\t\tpin ("CK") { direction : "input"; }
\t\tpin ("D") { direction : "input"; }
\t\tpin ("Q") { direction : "output"; function : "IQ"; signal_type : "test_scan_out"; }
\t\tpin ("QN") { direction : "output"; function : "IQN"; signal_type : "test_scan_out_inverted"; }
\t\tpin ("SI") { direction : "input"; signal_type : "test_scan_in"; }
\t\tpin ("SE") { direction : "input"; signal_type : "test_scan_enable"; }
\t}\n'''


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    start = source.find("  cell (SDFF_X1) {")
    if start < 0 or source.find("  cell (SDFF_X1) {", start + 1) >= 0:
        raise ValueError("Unique SDFF_X1 Liberty cell not found")
    area = source.find("\n\tarea", start)
    next_cell = source.find("\n  cell (", start + 1)
    if area < 0 or (next_cell >= 0 and area >= next_cell):
        raise ValueError("SDFF_X1 area insertion point not found")
    if "test_cell" in source[start:area]:
        raise ValueError("Source already has DFT test-cell semantics")
    result = source[:area] + ANNOTATION + source[area:]
    if result.replace(ANNOTATION, "", 1) != source:
        raise AssertionError("Liberty translation modified unintended bytes")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(result, encoding="utf-8")
    metadata = {
        "source": str(SOURCE), "source_sha256": sha(SOURCE),
        "output": str(OUTPUT.relative_to(ROOT)).replace("\\", "/"),
        "output_sha256": sha(OUTPUT), "modified_cell": "SDFF_X1",
        "modification": "test_cell scan-pin annotation only",
        "timing_tables_and_functional_ff_unchanged": True,
        "application": "OpenROAD-native DFT experiment only; ORFS physical routes retain the original Nangate45 Liberty",
    }
    (OUTPUT.parent / "annotation.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(metadata, sort_keys=True))


if __name__ == "__main__":
    main()
