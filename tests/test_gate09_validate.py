from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import pact_gate09_admission as admission
from pact_gate09_validate import verify_with_snapshot


def test_preserved_source_requires_matching_contents_even_with_hash_filename(tmp_path):
    source = tmp_path / 'source.py'
    source.write_bytes(b'original scientific execution source\n')
    expected = admission.binding(source)
    archive = tmp_path / (expected['sha256'] + '.py')
    archive.write_bytes(source.read_bytes())
    source.write_bytes(b'later publication compatibility source\n')
    snapshots = {archive.stem: archive}
    result = verify_with_snapshot(expected, snapshots)
    assert result['status'] == 'PASS'
    assert result['preserved_execution_source']['sha256'] == expected['sha256']
    archive.write_bytes(b'corrupted preserved source\n')
    assert verify_with_snapshot(expected, snapshots)['status'] != 'PASS'


def test_matching_current_source_needs_no_archive(tmp_path):
    source = tmp_path / 'source.py'
    source.write_bytes(b'unchanged source\n')
    assert verify_with_snapshot(admission.binding(source), {})['status'] == 'PASS'
