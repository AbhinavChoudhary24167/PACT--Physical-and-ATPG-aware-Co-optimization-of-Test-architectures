#!/usr/bin/env python3
"""Generate the safety-first repository cleanup inventories."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/repository_cleanup"
RAW_PHASE0B = ROOT / "artifacts/raw/phase0b"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_bytes(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def repository_files():
    for directory, child_dirs, names in os.walk(ROOT, followlinks=False):
        child_dirs[:] = [name for name in child_dirs if name != ".git"]
        for name in names:
            path = Path(directory) / name
            try:
                if not path.is_symlink() and path.is_file():
                    yield path
            except OSError:
                # Windows cannot stat a few Linux virtualenv symlinks. They are
                # already classified as ignored local machine state.
                continue


def classify(path: str) -> tuple[str, str, str]:
    normalized = path.replace("\\", "/")
    if normalized.startswith("artifacts/raw/phase0b/"):
        return (
            "B_REQUIRED_SCIENTIFIC_EVIDENCE",
            "PRESERVE_EXTERNAL_AND_IGNORE",
            "Inherited raw Phase-0B execution evidence; 568 MB aggregate is retained locally and SHA256-indexed, not staged.",
        )
    if normalized.startswith(("artifacts/derived/phase0b/", "artifacts/derived/s15850/",
                              "artifacts/manifests/phase0b/", "artifacts/derived/phase0d/optimizer_v1/",
                              "artifacts/raw/phase0d/optimizer_v1/", "reports/figures/phase0b/")):
        return (
            "B_REQUIRED_SCIENTIFIC_EVIDENCE", "TRACK_AND_COMMIT",
            "Compact scientific evidence, frozen result, route proof, or source figure.",
        )
    if normalized.startswith(("src/", "scripts/", "tests/", "config/", "experiments/")):
        return (
            "A_REQUIRED_SOURCE", "TRACK_AND_COMMIT",
            "Implementation, frozen configuration, test, or reproducibility script.",
        )
    if normalized == "README.md" or normalized == ".gitignore" or normalized.startswith("reports/"):
        return (
            "C_REQUIRED_DOCUMENTATION", "TRACK_AND_COMMIT",
            "Research status, method/report, patch notes, or cleanup provenance.",
        )
    if any(part in normalized for part in ("/__pycache__/", "/.pytest_cache/")) or normalized.endswith((".pyc", ".pyo", ".tmp")):
        return (
            "D_REPRODUCIBLE_TRANSIENT_OUTPUT", "KEEP_IGNORED",
            "Reproducible interpreter/test transient.",
        )
    if normalized.startswith((".venv/", "external/")):
        return (
            "E_LOCAL_MACHINE_STATE", "KEEP_IGNORED",
            "Local dependency checkout or virtual environment.",
        )
    return "F_UNKNOWN_POTENTIALLY_IMPORTANT", "PRESERVE_AND_REVIEW", "No safe automatic classification rule."


def changed_paths() -> set[str]:
    raw = git_bytes("status", "--porcelain=v1", "-z", "-uall")
    records = [record for record in raw.decode("utf-8", errors="surrogateescape").split("\0") if record]
    paths = set()
    for record in records:
        path = record[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.add(path.replace("\\", "/"))
    if RAW_PHASE0B.is_dir():
        paths.update(path.relative_to(ROOT).as_posix() for path in RAW_PHASE0B.rglob("*") if path.is_file())
    return paths


def write_classification() -> tuple[int, int]:
    paths = sorted(changed_paths())
    lines = ["path\tcategory\tproposed_action\treason"]
    unknown = 0
    for path in paths:
        category, action, reason = classify(path)
        unknown += int(category.startswith("F_"))
        lines.append(f"{path}\t{category}\t{action}\t{reason}")
    (REPORT / "file_classification.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return len(paths), unknown


def write_external_manifest() -> tuple[int, int, str]:
    records = []
    total = 0
    if RAW_PHASE0B.is_dir():
        for path in sorted(item for item in RAW_PHASE0B.rglob("*") if item.is_file()):
            size = path.stat().st_size
            total += size
            records.append((path.relative_to(ROOT).as_posix(), size, sha256(path)))
    root = hashlib.sha256("".join(f"{digest}  {path}\n" for path, _, digest in records).encode()).hexdigest()
    lines = [
        "PACT external scientific artifacts manifest",
        "",
        "Reason not tracked: inherited raw Phase-0B command logs, intermediate physical files, and execution evidence",
        "are preserved locally as a 568 MB external archive. Compact derived evidence, manifests, figures, source, and",
        "tests are tracked. This manifest makes the external archive auditable without committing the raw working tree.",
        "",
        f"file_count\t{len(records)}",
        f"total_bytes\t{total}",
        f"manifest_root_sha256\t{root}",
        "",
        "path\tbytes\tsha256\treason_not_tracked",
    ]
    lines.extend(
        f"{path}\t{size}\t{digest}\traw Phase-0B external scientific evidence"
        for path, size, digest in records
    )
    (REPORT / "external_artifacts_manifest.txt").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )
    return len(records), total, root


def write_large_file_audit() -> tuple[int, int, int]:
    tracked = set(git_bytes("ls-files", "-z").decode().split("\0"))
    rows = []
    counts = {10: 0, 50: 0, 100: 0}
    for path in repository_files():
        size = path.stat().st_size
        if size <= 10 * 1024 * 1024:
            continue
        relative = path.relative_to(ROOT).as_posix()
        for threshold in counts:
            counts[threshold] += int(size > threshold * 1024 * 1024)
        if relative.startswith("external/"):
            classification, action = "E_LOCAL_MACHINE_STATE", "KEEP_IGNORED"
        elif relative.startswith(".venv/"):
            classification, action = "E_LOCAL_MACHINE_STATE", "KEEP_IGNORED"
        elif relative.startswith("artifacts/raw/phase0b/"):
            classification, action = "B_REQUIRED_SCIENTIFIC_EVIDENCE", "PRESERVE_EXTERNAL_AND_IGNORE"
        else:
            classification, action = "F_UNKNOWN_POTENTIALLY_IMPORTANT", "PRESERVE_AND_REVIEW"
        rows.append((relative, size, size > 50 * 1024 * 1024, size > 100 * 1024 * 1024,
                     relative in tracked, classification, action))
    lines = ["path\tbytes\tover_50mb\tover_100mb\ttracked\tcategory\taction"]
    lines.extend("\t".join(map(str, row)) for row in sorted(rows, key=lambda row: (-row[1], row[0])))
    (REPORT / "large_file_audit.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return counts[10], counts[50], counts[100]


def main() -> None:
    REPORT.mkdir(parents=True, exist_ok=True)
    classified, unknown = write_classification()
    external_count, external_bytes, root = write_external_manifest()
    over10, over50, over100 = write_large_file_audit()
    summary = [
        "PACT repository cleanup inventory summary",
        f"classified_changed_or_external_files={classified}",
        f"unknown_files={unknown}",
        f"external_phase0b_files={external_count}",
        f"external_phase0b_bytes={external_bytes}",
        f"external_phase0b_manifest_root_sha256={root}",
        f"repository_files_over_10mb={over10}",
        f"repository_files_over_50mb={over50}",
        f"repository_files_over_100mb={over100}",
        "large_staging_policy=No file over 10 MB is a planned staging candidate; large files are ignored local dependencies.",
        "destructive_actions=NONE",
    ]
    (REPORT / "inventory_summary.txt").write_text("\n".join(summary) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(summary))


if __name__ == "__main__":
    main()
