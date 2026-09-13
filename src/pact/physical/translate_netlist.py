"""Explicit fixed physical-cell translation, never an upstream edit."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re


@dataclass(frozen=True)
class Translation:
    """Auditable cell-master-only physical netlist translation."""

    source_sha256: str
    output_sha256: str
    from_master: str
    to_master: str
    replacement_count: int


def translate_buf_x3_to_x4(source: Path, output: Path, expected_count: int) -> Translation:
    """Replace only named BUF_X3 instance masters with Boolean-equivalent BUF_X4.

    This changes drive strength and physical cost, so the translated netlist
    must be fixed for every compared ordering. It does not change any nets,
    ports, scan pins, or FF names.
    """
    raw = source.read_bytes()
    text = raw.decode("utf-8")
    pattern = r"(?m)^(\s*)BUF_X3(\s+[A-Za-z_][\w$]*\s*\()"
    result, count = re.subn(pattern, r"\g<1>BUF_X4\g<2>", text)
    if count != expected_count:
        raise ValueError(f"Expected {expected_count} BUF_X3 instances, found {count}")
    if result.replace("BUF_X4", "BUF_X3") != text.replace("BUF_X4", "BUF_X3"):
        raise AssertionError("Translation changed more than the declared master")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(result, encoding="utf-8", newline="\n")
    return Translation(
        hashlib.sha256(raw).hexdigest(), hashlib.sha256(output.read_bytes()).hexdigest(),
        "BUF_X3", "BUF_X4", count,
    )
