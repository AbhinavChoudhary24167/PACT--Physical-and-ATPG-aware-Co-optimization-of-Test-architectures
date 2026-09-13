#!/usr/bin/env python3
"""Freeze SHA256 for compact raw and derived Phase-0 evidence."""
from __future__ import annotations

import hashlib
from pathlib import Path


def main() -> None:
    """Write a repository-relative GNU sha256sum manifest in stable path order."""
    root = Path(__file__).resolve().parents[1]
    sources = (root / "artifacts/raw", root / "artifacts/derived", root / "reports/figures")
    paths = sorted(
        (path for area in sources for path in area.rglob("*")
         if path.is_file() and path.suffix != ".sha256"),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    paths.extend(root / "artifacts/manifests" / name for name in (
        "python-packages.txt", "s5378_translation.json", "s9234_translation.json",
    ))
    paths.sort(key=lambda path: path.relative_to(root).as_posix())
    lines = [f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(root).as_posix()}" for path in paths]
    target = root / "artifacts/manifests/phase0_evidence.sha256"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
