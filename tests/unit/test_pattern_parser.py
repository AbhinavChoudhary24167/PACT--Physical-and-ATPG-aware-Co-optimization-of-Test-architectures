from __future__ import annotations

from pathlib import Path
import pytest

from pact.test.pattern_parser import map_ppi_patterns, parse_fan_pat


RAW_S27 = Path(__file__).parents[2] / "artifacts/raw/tool_qualification/fan_atpg/patterns/FAN_s27.pat"


def test_pattern_parser() -> None:
    parsed = parse_fan_pat(RAW_S27)
    assert parsed.primary_inputs == ("G0", "G1", "G2", "G3")
    assert parsed.pseudo_primary_inputs == ("U_G5", "U_G6", "U_G7")
    assert len(parsed.patterns) == 5
    assert parsed.patterns[0].ppi == "011"
    assert parsed.patterns[0].ppo == "011"


def test_ppi_order_stable(tmp_path) -> None:
    parsed = parse_fan_pat(RAW_S27)
    ff_map = [
        {"logical_ff": f"ff{i}", "physical_instance": f"p{i}", "atpg_signal": name, "clock_domain": "clk"}
        for i, name in enumerate(parsed.pseudo_primary_inputs)
    ]
    assert map_ppi_patterns(parsed, ff_map)[0] == {"p0": 0, "p1": 1, "p2": 1}
    with pytest.raises(ValueError, match="PPI names"):
        map_ppi_patterns(parsed, ff_map[:-1])


def test_parser_rejects_width_error(tmp_path) -> None:
    path = tmp_path / "bad.pat"
    path.write_text(RAW_S27.read_text(encoding="utf-8").replace("_pattern_1 0000", "_pattern_1 000"), encoding="utf-8")
    with pytest.raises(ValueError, match="PI1 width"):
        parse_fan_pat(path)
