"""Central storage policy for PACT experiments.

Repository source and compact, version-controlled reports deliberately remain
outside this module.  Every transient or potentially large experiment path is
derived here so an individual experiment cannot quietly fall back to the host
OS temporary directory (C: on the qualification workstation).
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import platform
import re
import shutil
import tempfile
from typing import Any, Mapping, MutableMapping


EXPERIMENT_ROOT_ENV = "PACT_EXPERIMENT_ROOT"
DEFAULT_WINDOWS_EXPERIMENT_ROOT = Path(r"D:\PACT_EXPERIMENTS")
DEFAULT_WSL_EXPERIMENT_ROOT = Path("/mnt/d/PACT_EXPERIMENTS")
DEFAULT_MIN_FREE_GIB = 20.0
LOW_DISK_STATUS = "PACT_EXPERIMENT_ABORTED_LOW_DISK_SPACE"

_DIRECTORIES = (
    "tmp",
    "cache",
    "synthetic",
    "profiles",
    "checkpoints",
    "workers",
    "logs",
    "results",
    "memmap",
    "pytest_tmp",
)
_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9_.-]+$")


def _running_under_wsl() -> bool:
    if os.name == "nt":
        return False
    release = platform.release().lower()
    return "microsoft" in release or "wsl" in release


def experiment_root(
    command_line: str | os.PathLike[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Resolve the one experiment root; command line overrides environment.

    The native-Windows default is D:, and WSL uses the same physical volume via
    ``/mnt/d``.  There is intentionally no repository, home, or system-temp
    fallback.
    """
    environment = os.environ if environ is None else environ
    selected = command_line or environment.get(EXPERIMENT_ROOT_ENV)
    if selected:
        return Path(selected).expanduser()
    if os.name == "nt":
        return DEFAULT_WINDOWS_EXPERIMENT_ROOT
    return DEFAULT_WSL_EXPERIMENT_ROOT


@dataclass(frozen=True)
class ExperimentPaths:
    root: Path
    tmp: Path
    cache: Path
    synthetic: Path
    profiles: Path
    checkpoints: Path
    workers: Path
    logs: Path
    results: Path
    memmap: Path
    pytest_tmp: Path

    @classmethod
    def derive(cls, root: Path) -> "ExperimentPaths":
        root = Path(root)
        return cls(root, *(root / name for name in _DIRECTORIES))

    def create(self) -> "ExperimentPaths":
        self.root.mkdir(parents=True, exist_ok=True)
        for name in _DIRECTORIES:
            getattr(self, name).mkdir(parents=True, exist_ok=True)
        (self.cache / "pycache").mkdir(parents=True, exist_ok=True)
        (self.cache / "numba").mkdir(parents=True, exist_ok=True)
        (self.cache / "matplotlib").mkdir(parents=True, exist_ok=True)
        (self.tmp / "joblib").mkdir(parents=True, exist_ok=True)
        return self

    def as_dict(self) -> dict[str, str]:
        return {
            "experiment_root": str(self.root),
            **{f"{name}_dir": str(getattr(self, name)) for name in _DIRECTORIES},
        }


def experiment_paths(
    command_line: str | os.PathLike[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> ExperimentPaths:
    return ExperimentPaths.derive(experiment_root(command_line, environ=environ))


def configure_experiment_storage(
    command_line: str | os.PathLike[str] | None = None,
    *,
    environ: MutableMapping[str, str] | None = None,
    create: bool = True,
) -> ExperimentPaths:
    """Create the central layout and redirect process-local temp/cache paths."""
    environment = os.environ if environ is None else environ
    paths = experiment_paths(command_line, environ=environment)
    if create:
        paths.create()
    values = {
        EXPERIMENT_ROOT_ENV: paths.root,
        "TEMP": paths.tmp,
        "TMP": paths.tmp,
        "TMPDIR": paths.tmp,
        "PYTHONPYCACHEPREFIX": paths.cache / "pycache",
        "NUMBA_CACHE_DIR": paths.cache / "numba",
        "MPLCONFIGDIR": paths.cache / "matplotlib",
        "JOBLIB_TEMP_FOLDER": paths.tmp / "joblib",
    }
    for name, value in values.items():
        environment[name] = str(value)
    # ``tempfile`` caches the selected directory after its first use.  Reset it
    # explicitly so late-but-valid experiment initialization cannot retain C:.
    if environment is os.environ:
        tempfile.tempdir = str(paths.tmp)
    return paths


def add_experiment_root_argument(parser: Any) -> None:
    parser.add_argument(
        "--experiment-root",
        type=Path,
        default=None,
        help=(
            f"large/scratch experiment root (overrides {EXPERIMENT_ROOT_ENV}; "
            f"default {DEFAULT_WINDOWS_EXPERIMENT_ROOT})"
        ),
    )


class LowDiskSpaceError(RuntimeError):
    status = LOW_DISK_STATUS


def guard_disk_space(
    paths: ExperimentPaths,
    *,
    estimated_bytes: int = 0,
    minimum_free_gib: float = DEFAULT_MIN_FREE_GIB,
) -> dict[str, int | float | str]:
    """Refuse work that would breach the configured free-space reserve."""
    if estimated_bytes < 0 or minimum_free_gib < 0:
        raise ValueError("Disk estimate and reserve must be nonnegative")
    usage = shutil.disk_usage(paths.root)
    reserve = int(minimum_free_gib * (1024 ** 3))
    free_after_estimate = usage.free - int(estimated_bytes)
    result: dict[str, int | float | str] = {
        "status": "OK",
        "free_bytes": usage.free,
        "estimated_bytes": int(estimated_bytes),
        "minimum_free_gib": float(minimum_free_gib),
        "free_after_estimate_bytes": free_after_estimate,
    }
    if free_after_estimate < reserve:
        result["status"] = LOW_DISK_STATUS
        raise LowDiskSpaceError(
            f"{LOW_DISK_STATUS}: {paths.root} has {usage.free / 1024**3:.2f} GiB "
            f"free; estimate={estimated_bytes / 1024**3:.2f} GiB and "
            f"reserve={minimum_free_gib:.2f} GiB"
        )
    return result


def directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def host_filesystem() -> str:
    if os.name == "nt":
        return "native_windows"
    if _running_under_wsl():
        return "wsl_mnt_d"
    return "posix_mnt_d"


def _drive_free(path: Path) -> int | None:
    try:
        return int(shutil.disk_usage(path).free)
    except OSError:
        return None


def free_space_snapshot(paths: ExperimentPaths) -> dict[str, int | None]:
    if os.name == "nt":
        return {
            "free_C": _drive_free(Path("C:/")),
            "free_D": _drive_free(Path("D:/")),
        }
    return {
        "free_C": None,
        "free_D": _drive_free(paths.root),
    }


@dataclass
class StorageRunTracker:
    paths: ExperimentPaths
    free_before: dict[str, int | None]
    bytes_before: int
    peak_bytes: int

    @classmethod
    def start(cls, paths: ExperimentPaths) -> "StorageRunTracker":
        current = directory_size(paths.root)
        return cls(paths, free_space_snapshot(paths), current, current)

    def sample(self) -> int:
        current = directory_size(self.paths.root)
        self.peak_bytes = max(self.peak_bytes, current)
        return current

    def finish(self, *, cleanup_status: str) -> dict[str, Any]:
        retained = self.sample()
        free_after = free_space_snapshot(self.paths)
        bytes_created = max(0, self.peak_bytes - self.bytes_before)
        return {
            "experiment_root": str(self.paths.root),
            "scratch_root": str(self.paths.workers),
            "host_filesystem": host_filesystem(),
            "free_D_before": self.free_before["free_D"],
            "free_D_after": free_after["free_D"],
            "free_C_before": self.free_before["free_C"],
            "free_C_after": free_after["free_C"],
            "temporary_bytes_created": bytes_created,
            "total_bytes_written": bytes_created,
            "peak_experiment_directory_size": self.peak_bytes,
            "retained_bytes": retained,
            "residual_scratch_bytes": directory_size(self.paths.workers),
            "cleanup_status": cleanup_status,
        }


def c_drive_safety_warning(
    paths: ExperimentPaths, *, threshold_gib: float = 10.0,
) -> str | None:
    snapshot = free_space_snapshot(paths)
    free = snapshot["free_C"]
    threshold = int(threshold_gib * 1024**3)
    if free is not None and free < threshold:
        return (
            f"WARNING: C: has only {free / 1024**3:.2f} GiB free; all "
            f"PACT experiment data remains redirected to {paths.root}"
        )
    return None


def _safe_component(value: str, label: str) -> str:
    if not _SAFE_COMPONENT.fullmatch(value):
        raise ValueError(f"Unsafe {label}: {value!r}")
    return value


def worker_scratch(paths: ExperimentPaths, run_id: str, worker_id: str | int) -> Path:
    run = _safe_component(str(run_id), "run id")
    worker = _safe_component(str(worker_id), "worker id")
    target = paths.workers / run / worker
    target.mkdir(parents=True, exist_ok=True)
    return target


def remove_owned_tree(paths: ExperimentPaths, target: Path) -> None:
    """Remove one PACT-owned subtree, never the root or anything outside it."""
    root = paths.root.resolve()
    resolved = Path(target).resolve()
    if resolved == root or root not in resolved.parents:
        raise ValueError(f"Refusing cleanup outside experiment root: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)
