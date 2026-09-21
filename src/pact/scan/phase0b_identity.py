"""Audited FF identity when ORFS inserts a transparent output buffer."""
from __future__ import annotations

from pathlib import Path
import re

from pact.scan.identity import ScanFFInstance, scan_ff_instances
from pact.scan.validate import validate_ff_identity_map
from pact.test.pattern_parser import FanPatternFile


def transparent_q_buffer_aliases(source: Path, placed: Path) -> dict[str, dict[str, str]]:
    originals = {record.name: record for record in scan_ff_instances(source)}
    physical = {record.name: record for record in scan_ff_instances(placed)}
    if set(originals) != set(physical):
        raise ValueError("Source and placed FF instance sets differ")
    text = placed.read_text(encoding="utf-8")
    buffers = []
    for match in re.finditer(r"\bBUF_X1\s+([A-Za-z_][\w$]*)\s*\((.*?)\)\s*;", text, re.DOTALL):
        pins = dict(re.findall(r"\.([A-Za-z_][\w$]*)\s*\(\s*([^()\s]+)\s*\)", match.group(2)))
        if "A" in pins and "Z" in pins:
            buffers.append((match.group(1), pins["A"], pins["Z"]))
    aliases = {}
    for name in originals:
        before, after = originals[name], physical[name]
        if before.clock_net != after.clock_net:
            raise ValueError(f"Clock net changed for {name}")
        if before.q_net == after.q_net:
            continue
        matches = [buffer for buffer in buffers if buffer[1] == after.q_net and buffer[2] == before.q_net]
        if len(matches) != 1:
            raise ValueError(f"Q identity changed without unique transparent BUF_X1 alias for {name}")
        aliases[name] = {"placed_q_net": after.q_net, "source_q_net": before.q_net,
                         "buffer_instance": matches[0][0]}
    return aliases


def phase0b_ff_identity_map(source: Path, placed: Path, patterns: FanPatternFile) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    originals = {record.name: record for record in scan_ff_instances(source)}
    physical = {record.name: record for record in scan_ff_instances(placed)}
    if set(originals) != set(physical) or set(originals) != set(patterns.pseudo_primary_inputs):
        raise ValueError("Source, placed, and ATPG FF sets differ")
    aliases = transparent_q_buffer_aliases(source, placed)
    records = [{"logical_ff": originals[name].q_net, "physical_instance": name,
                "atpg_signal": name, "clock_domain": originals[name].clock_net}
               for name in patterns.pseudo_primary_inputs]
    validate_ff_identity_map(records, physical.keys())
    return records, aliases


def verify_order_with_transparent_buffers(order: tuple[str, ...],
                                          ff: dict[str, ScanFFInstance],
                                          placed_verilog: str,
                                          scan_in: str = "test_si",
                                          scan_out: str = "test_so") -> dict[str, object]:
    """Prove an ordered chain allowing only unique one-hop BUF_X1 scan edges."""
    if len(order) != len(ff) or set(order) != set(ff):
        raise ValueError("Scan order and placed FF inventory differ")
    buffers = []
    for match in re.finditer(r"\bBUF_X1\s+([A-Za-z_][\w$]*)\s*\((.*?)\)\s*;", placed_verilog, re.DOTALL):
        pins = dict(re.findall(r"\.([A-Za-z_][\w$]*)\s*\(\s*([^()\s]+)\s*\)", match.group(2)))
        if "A" in pins and "Z" in pins:
            buffers.append((match.group(1), pins["A"], pins["Z"]))

    def edge(source: str, target: str, label: str) -> str | None:
        if source == target:
            return None
        matches = [name for name, input_net, output_net in buffers
                   if input_net == source and output_net == target]
        if len(matches) != 1:
            raise ValueError(f"{label} lacks one direct or unique transparent-buffer connection")
        return matches[0]

    input_buffer = edge(scan_in, ff[order[0]].si_net, "scan input")
    inter_ff = []
    for index, (left, right) in enumerate(zip(order, order[1:])):
        buffer = edge(ff[left].q_net, ff[right].si_net, f"scan edge {index}")
        if buffer is not None:
            inter_ff.append({"edge_index": index, "from_ff": left, "to_ff": right,
                             "buffer_instance": buffer})
    output_buffer = edge(ff[order[-1]].q_net, scan_out, "scan output")
    return {"scan_input_buffer": input_buffer,
            "inter_ff_buffer_edges": inter_ff,
            "scan_output_buffer": output_buffer}
