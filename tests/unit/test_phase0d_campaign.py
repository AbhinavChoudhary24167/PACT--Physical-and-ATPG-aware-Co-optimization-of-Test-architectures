from pathlib import Path

import pytest

from pact.phase0d.campaign import (
    ManifestStore,
    canonical_sha256,
    deterministic_run_id,
    valid_cached_artifact,
    write_status,
)


def test_deterministic_run_id_is_stable_and_scoped() -> None:
    first = deterministic_run_id("s5378", 11, 2, "beam", "abc")
    assert first == deterministic_run_id("s5378", 11, 2, "beam", "abc")
    assert first != deterministic_run_id("s5378", 11, 2, "anneal", "abc")
    assert len(first) == 20


def test_manifest_resume_and_provenance(tmp_path: Path) -> None:
    store = ManifestStore(tmp_path / "manifest.json", "pilot", "a" * 40, "b" * 64)
    run_id = deterministic_run_id("pilot")
    store.upsert({"run_id": run_id, "design": "s5378", "physical_seed": 11, "K": 2,
                  "optimizer": "beam", "status": "PLANNED"})
    assert store.first_unfinished()["run_id"] == run_id
    store.upsert({"run_id": run_id, "status": "QUALIFIED", "proxy_evaluations": 16})
    assert store.first_unfinished() is None
    wrong = ManifestStore(store.path, "different", "a" * 40, "b" * 64)
    with pytest.raises(ValueError, match="provenance"):
        wrong.load()


def test_manifest_rejects_bad_status(tmp_path: Path) -> None:
    store = ManifestStore(tmp_path / "manifest.json", "pilot", "a" * 40, "b" * 64)
    with pytest.raises(ValueError, match="status"):
        store.upsert({"run_id": "0" * 20, "status": "MADE_UP"})


def test_cache_and_status_files(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.json"
    artifact.write_text("evidence\n", encoding="utf-8")
    assert valid_cached_artifact(artifact, canonical_sha256("wrong")) is False
    import hashlib
    expected = hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert valid_cached_artifact(artifact, expected)
    write_status(tmp_path / "status.json", tmp_path / "STATUS.md", {
        "campaign_id": "pilot", "current_phase": "PILOT", "completed_contexts": 0,
    })
    assert '"campaign_id": "pilot"' in (tmp_path / "status.json").read_text(encoding="utf-8")
    assert "# PACT Phase-0D Status" in (tmp_path / "STATUS.md").read_text(encoding="utf-8")
