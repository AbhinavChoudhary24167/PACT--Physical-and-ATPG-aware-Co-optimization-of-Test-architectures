from __future__ import annotations

import os
from pathlib import Path

import pytest

from pact.experiment_storage import (
    EXPERIMENT_ROOT_ENV,
    LowDiskSpaceError,
    configure_experiment_storage,
    experiment_root,
    guard_disk_space,
    remove_owned_tree,
    worker_scratch,
)


def test_command_line_root_overrides_environment(tmp_path: Path) -> None:
    environment_root = tmp_path / "environment"
    command_line_root = tmp_path / "command-line"
    assert experiment_root(
        command_line_root,
        environ={EXPERIMENT_ROOT_ENV: str(environment_root)},
    ) == command_line_root
    assert experiment_root(
        environ={EXPERIMENT_ROOT_ENV: str(environment_root)}
    ) == environment_root


def test_configuration_creates_all_paths_and_redirects_temp_caches(tmp_path: Path) -> None:
    environment: dict[str, str] = {}
    paths = configure_experiment_storage(tmp_path / "experiments", environ=environment)
    for path in (
        paths.tmp, paths.cache, paths.synthetic, paths.profiles,
        paths.checkpoints, paths.workers, paths.logs, paths.results,
        paths.memmap, paths.pytest_tmp,
    ):
        assert path.is_dir()
        assert paths.root in path.parents
    assert environment[EXPERIMENT_ROOT_ENV] == str(paths.root)
    assert environment["TEMP"] == str(paths.tmp)
    assert environment["TMP"] == str(paths.tmp)
    assert environment["TMPDIR"] == str(paths.tmp)
    assert environment["PYTHONPYCACHEPREFIX"] == str(paths.cache / "pycache")
    assert environment["NUMBA_CACHE_DIR"] == str(paths.cache / "numba")
    assert environment["MPLCONFIGDIR"] == str(paths.cache / "matplotlib")
    assert environment["JOBLIB_TEMP_FOLDER"] == str(paths.tmp / "joblib")


def test_disk_guard_refuses_an_unsafe_reserve(tmp_path: Path) -> None:
    paths = configure_experiment_storage(tmp_path / "experiments", environ={})
    with pytest.raises(LowDiskSpaceError, match="PACT_EXPERIMENT_ABORTED_LOW_DISK_SPACE"):
        guard_disk_space(paths, minimum_free_gib=10**9)


def test_worker_cleanup_is_confined_to_experiment_root(tmp_path: Path) -> None:
    paths = configure_experiment_storage(tmp_path / "experiments", environ={})
    scratch = worker_scratch(paths, "run-1", "L0")
    (scratch / "state.bin").write_bytes(b"state")
    remove_owned_tree(paths, scratch)
    assert not scratch.exists()
    with pytest.raises(ValueError, match="outside experiment root"):
        remove_owned_tree(paths, tmp_path)
    with pytest.raises(ValueError, match="Unsafe run id"):
        worker_scratch(paths, "../escape", "L0")


def test_live_configuration_resets_python_tempfile_cache(tmp_path: Path, monkeypatch) -> None:
    import tempfile

    for name in (
        EXPERIMENT_ROOT_ENV, "TEMP", "TMP", "TMPDIR", "PYTHONPYCACHEPREFIX",
        "NUMBA_CACHE_DIR", "MPLCONFIGDIR", "JOBLIB_TEMP_FOLDER",
    ):
        monkeypatch.setenv(name, "before-test")
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "old"))
    paths = configure_experiment_storage(tmp_path / "experiments")
    assert os.environ["TEMP"] == str(paths.tmp)
    assert tempfile.gettempdir() == str(paths.tmp)
