"""Canonical, deterministic scan architecture records."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ScanCell:
    """One physical scan FF with its fixed placement."""

    name: str
    x_um: float
    y_um: float
    clock_domain: str


@dataclass(frozen=True)
class ScanChain:
    """Cells ordered from scan-in to scan-out."""

    chain_id: str
    cells: tuple[str, ...]
    scan_in: str | None = None
    scan_out: str | None = None


@dataclass(frozen=True)
class ScanArchitecture:
    """Fixed cell inventory and one legal ordering of its chains."""

    cells: tuple[ScanCell, ...]
    chains: tuple[ScanChain, ...]

    def canonical_dict(self) -> dict[str, Any]:
        """Return stable JSON content for storage and hashing."""
        return {
            "schema_version": "0.1",
            "cells": [asdict(c) for c in sorted(self.cells, key=lambda c: c.name)],
            "chains": [asdict(c) for c in sorted(self.chains, key=lambda c: c.chain_id)],
        }

    def sha256(self) -> str:
        """Hash all physical cells and ordered chain membership deterministically."""
        raw = json.dumps(self.canonical_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def to_json(self, path: Path) -> None:
        """Save canonical architecture and its content hash."""
        payload = self.canonical_dict()
        payload["architecture_sha256"] = self.sha256()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    @classmethod
    def from_json(cls, path: Path) -> ScanArchitecture:
        """Load an architecture and reject a mismatched stored hash."""
        obj = json.loads(path.read_text(encoding="utf-8"))
        if obj.get("schema_version") != "0.1":
            raise ValueError("Unsupported architecture schema_version")
        arch = cls(
            cells=tuple(ScanCell(**c) for c in obj["cells"]),
            chains=tuple(ScanChain(chain_id=c["chain_id"], cells=tuple(c["cells"]), scan_in=c.get("scan_in"), scan_out=c.get("scan_out")) for c in obj["chains"]),
        )
        saved = obj.get("architecture_sha256")
        if saved is not None and saved != arch.sha256():
            raise ValueError("Architecture SHA256 mismatch")
        return arch
