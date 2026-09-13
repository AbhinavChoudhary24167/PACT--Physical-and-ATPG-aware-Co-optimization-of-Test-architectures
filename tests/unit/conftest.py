from __future__ import annotations

import pytest

from pact.scan.model import ScanArchitecture, ScanCell, ScanChain


@pytest.fixture
def tiny_arch() -> ScanArchitecture:
    return ScanArchitecture(
        cells=(
            ScanCell("a", 0.0, 0.0, "clk"),
            ScanCell("b", 1.0, 0.0, "clk"),
            ScanCell("c", 1.0, 2.0, "clk"),
            ScanCell("d", 4.0, 2.0, "clk"),
        ),
        chains=(ScanChain("chain0", ("a", "b", "c", "d")),),
    )
