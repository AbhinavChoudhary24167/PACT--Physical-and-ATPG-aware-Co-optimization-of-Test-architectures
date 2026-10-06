"""Focused integrity controls for the bounded compact-count export reader."""
import gzip
from pathlib import Path
import struct
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from gate10a_export_activity import stream_totals


def fixture(path, names=("a", "b"), cycles=3, payload=b"\x01\x00\x02\x01\x00\x03", footer=b"PACTDONE"):
    with gzip.open(path, "wb") as stream:
        stream.write(b"PACTCN01" + struct.pack("<II", len(names), cycles))
        for name in names:
            encoded = name.encode("utf-8")
            stream.write(struct.pack("<I", len(encoded)) + encoded)
        stream.write(payload + footer)


def test_bounded_stream_totals_and_complete_footer(tmp_path):
    path = tmp_path / "counts.gz"
    fixture(path)
    totals, structure = stream_totals(path, ["a", "b"], 3, chunk_cycles=2)
    np.testing.assert_array_equal(totals, [3, 4])
    assert structure["complete"] and structure["gzip_crc"] == "PASS"
    assert structure["maximum_count_rows_in_memory"] == 2


@pytest.mark.parametrize("names,cycles,match", [(["b", "a"], 3, "names/order"), (["a", "b"], 4, "dimensions")])
def test_mapping_or_workload_mismatch_rejected(tmp_path, names, cycles, match):
    path = tmp_path / "counts.gz"
    fixture(path)
    with pytest.raises(ValueError, match=match):
        stream_totals(path, names, cycles)


def test_incomplete_and_trailing_data_rejected(tmp_path):
    path = tmp_path / "counts.gz"
    fixture(path, footer=b"")
    with pytest.raises(ValueError, match="Incomplete"):
        stream_totals(path, ["a", "b"], 3)
    fixture(path, footer=b"PACTDONE\x00")
    with pytest.raises(ValueError, match="footer/trailing"):
        stream_totals(path, ["a", "b"], 3)


def test_excessive_count_chunk_rejected(tmp_path):
    with pytest.raises(ValueError, match="between 1 and 512"):
        stream_totals(tmp_path / "absent", [], 0, chunk_cycles=513)
