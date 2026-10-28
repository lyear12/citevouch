"""Shared fixtures.  Everything is built on disk in a temp directory.

The tool's whole job is reading files, so tests build real files rather than
mocking the filesystem — a mock here would let a real bug through.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from citevouch.model import Claim, Finding, Ledger


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A miniature manuscript + one text source + one bib file."""
    (tmp_path / "papers").mkdir()
    (tmp_path / "papers" / "2026_smith_networks.txt").write_text(
        "1. Introduction\n"
        "We train the model on 154,391 sentences drawn from two corpora.\n"
        "The construction inventory totals 40,688 entries.\n",
        encoding="utf-8",
    )
    (tmp_path / "refs.bib").write_text(
        """@article{smith2026cxn,
  author = {Smith, Jane},
  title  = {Construction networks at scale},
  journal = {Journal of Tests},
  year   = {2026},
  doi    = {https://doi.org/10.1000/xyz},
}
""",
        encoding="utf-8",
    )
    (tmp_path / "sources.toml").write_text(
        '[sources]\nsmith2026cxn = "papers/2026_smith_networks.txt"\n', encoding="utf-8"
    )
    return tmp_path


@pytest.fixture
def manuscript_body() -> str:
    return (
        "# Test manuscript\n\n"
        "The grammar is learned from two semantically annotated corpora.\n\n"
        "```claim id=c1 source=smith2026cxn page=1\n"
        "quote: |\n"
        "  We train the model on 154,391 sentences drawn from two corpora.\n"
        "claim: |\n"
        "  The grammar is learned from two semantically annotated corpora.\n"
        "```\n"
    )


@pytest.fixture
def manuscript(project: Path, manuscript_body: str) -> Path:
    path = project / "manuscript.md"
    path.write_text(manuscript_body, encoding="utf-8")
    return path


@pytest.fixture
def make_ledger():
    def _make(claims: list[Claim], **kwargs) -> Ledger:
        ledger = Ledger(**kwargs)
        ledger.claims = claims
        return ledger

    return _make


@pytest.fixture
def write_json(tmp_path: Path):
    def _write(name: str, payload: dict) -> Path:
        path = tmp_path / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    return _write


__all__ = ["Claim", "Finding", "Ledger"]
