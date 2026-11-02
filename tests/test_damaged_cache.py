"""A damaged cache file is a cache miss, not a crash and not a verdict.

`.citevouch/cache/<sha>.json` is scratch: it holds the text some reader produced
for these exact bytes, so it can always be recomputed.  That makes it the
opposite case to the ledger, which is refused out loud when a shape is not
recognised (`tests/test_damaged_ledger.py`) because nothing else can reconstruct
what the author claimed against which source.

Before this file existed, `_load_cache` trusted the shapes it read.  Measured on
a project whose cache file was replaced with each of these:

    {"pages": 5}                  TypeError: 'int' object is not iterable
    {"pages": [null]}             AttributeError: 'NoneType' object has no attribute 'get'
    {"pages": [{"number": "x"}]}  ValueError: invalid literal for int() with base 10: 'x'

Each exited **1** with a traceback - the code that means "findings at or above
--fail-on" - so a scratch file could manufacture the one signal the tool is for.

The fix has three halves and only the third is the obvious one: a shape the
cache does not recognise returns `None` (a miss), `None` re-extracts, and a
*recognised* shape is still trusted - otherwise the fix would be "stop caching",
and the tests below would still all pass.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from citevouch import sources
from citevouch.cli import main

MANUSCRIPT = (
    "```claim id=c1 source=a page=1\n"
    "quote: |\n"
    "  We counted 40,688 examples in the corpus.\n"
    "claim: |\n"
    "  It counted 40,688 examples.\n"
    "```\n"
)
SOURCE_TEXT = "We counted 40,688 examples in the corpus.\n"


def _project(tmp_path: Path) -> Path:
    (tmp_path / "a.txt").write_text(SOURCE_TEXT, encoding="utf-8", newline="\n")
    (tmp_path / "sources.toml").write_text(
        '[sources]\na = "a.txt"\n', encoding="utf-8", newline="\n"
    )
    (tmp_path / "m.md").write_text(MANUSCRIPT, encoding="utf-8", newline="\n")
    return tmp_path


def _scan_then_find_cache(root: Path) -> Path:
    """Run the tool once so it writes a real cache entry, then return the file."""
    assert main(["scan", "m.md", "--root", str(root), "--quiet"]) == 0
    files = sorted(sources.cache_root(root).glob("*.json"))
    assert len(files) == 1, files
    return files[0]


def _shape(**extra) -> dict:
    blob = {
        "schema": 1,
        "tool": __import__("citevouch").__version__,
        "extractor": "plain",
        "pages": [{"number": 1, "text": SOURCE_TEXT}],
    }
    blob.update(extra)
    return blob


DAMAGED: dict[str, object] = {
    "pages is a number": _shape(pages=5),
    "pages is null": _shape(pages=None),
    "pages is a string": _shape(pages="one page"),
    "a page is null": _shape(pages=[None]),
    "a page is a string": _shape(pages=["page one"]),
    "the page number is a string": _shape(pages=[{"number": "x", "text": SOURCE_TEXT}]),
    "the page number is a float": _shape(pages=[{"number": 1.7, "text": SOURCE_TEXT}]),
    "the page number is zero": _shape(pages=[{"number": 0, "text": SOURCE_TEXT}]),
    "the page number is negative": _shape(pages=[{"number": -3, "text": SOURCE_TEXT}]),
    "the page text is a number": _shape(pages=[{"number": 1, "text": 5}]),
    "the page text is null": _shape(pages=[{"number": 1, "text": None}]),
}
ALSO_DAMAGED = ("bool page number",)

#: A cache whose JSON *root* is not an object.  These are the shapes that made
#: `blob.get(...)` raise AttributeError before the first isinstance, and they are
#: kept separate from ``DAMAGED`` because the damaged file is written as raw
#: JSON rather than through ``_shape``.
NOT_AN_OBJECT: dict[str, str] = {
    "a list": "[]",
    "null": "null",
    "a string": '"page one"',
    "a number": "5",
}


class TestTheRootIsNotAnObject:
    @pytest.mark.parametrize("name", sorted(NOT_AN_OBJECT))
    def test_a_cache_root_that_is_not_an_object_is_a_miss(self, tmp_path: Path, name: str):
        root = _project(tmp_path)
        cache = _scan_then_sha(root)
        cache.write_text(NOT_AN_OBJECT[name], encoding="utf-8", newline="\n")
        assert sources._load_cache(root, cache.stem, ("plain",)) is None

    @pytest.mark.parametrize("name", sorted(NOT_AN_OBJECT))
    def test_the_run_still_verifies(self, tmp_path: Path, name: str):
        root = _project(tmp_path)
        cache = _scan_then_find_cache(root)
        cache.write_text(NOT_AN_OBJECT[name], encoding="utf-8", newline="\n")
        assert main(["check", "m.md", "--root", str(root), "--quiet"]) == 0


class TestTheShapeIsRefusedAsAMiss:
    @pytest.mark.parametrize("name", sorted(DAMAGED))
    def test_the_cache_loader_returns_none(self, tmp_path: Path, name: str):
        root = _project(tmp_path)
        cache = _scan_then_sha(root)
        cache.write_text(json.dumps(DAMAGED[name]), encoding="utf-8", newline="\n")
        sha = cache.stem
        assert sources._load_cache(root, sha, ("plain",)) is None

    def test_a_bool_page_number_is_not_a_page_number(self, tmp_path: Path):
        """`isinstance(True, int)` is true and `True` is not a page number."""
        root = _project(tmp_path)
        cache = _scan_then_sha(root)
        cache.write_text(
            json.dumps(_shape(pages=[{"number": True, "text": SOURCE_TEXT}])),
            encoding="utf-8",
            newline="\n",
        )
        assert sources._load_cache(root, cache.stem, ("plain",)) is None


def _scan_then_sha(root: Path) -> Path:
    return _scan_then_find_cache(root)


class TestTheRunStillVerdicts:
    @pytest.mark.parametrize("name", sorted(DAMAGED))
    def test_the_check_re_extracts_and_still_verifies(self, tmp_path: Path, name: str):
        """The point is not "it does not crash" but "the answer is still right":
        the bytes are here, so the text is recoverable and the quote is found."""
        root = _project(tmp_path)
        cache = _scan_then_find_cache(root)
        cache.write_text(json.dumps(DAMAGED[name]), encoding="utf-8", newline="\n")
        assert main(["check", "m.md", "--root", str(root), "--quiet"]) == 0

    def test_a_damaged_cache_does_not_become_a_finding(self, tmp_path: Path, capsys):
        """A scratch file must not appear in the report as a problem with the
        author's evidence.  Silence about the cache is the only honest answer:
        it was re-derived, and there is nothing left to say."""
        root = _project(tmp_path)
        cache = _scan_then_find_cache(root)
        cache.write_text('{"pages": 5}', encoding="utf-8", newline="\n")
        assert main(["check", "m.md", "--root", str(root)]) == 0
        out = capsys.readouterr().out
        assert "cache" not in out.lower()

    def test_a_cache_that_is_not_json_at_all_is_a_miss(self, tmp_path: Path):
        root = _project(tmp_path)
        cache = _scan_then_find_cache(root)
        cache.write_text("{not json", encoding="utf-8", newline="\n")
        assert main(["check", "m.md", "--root", str(root), "--quiet"]) == 0

    def test_a_cache_from_another_tool_version_is_not_used(self, tmp_path: Path):
        root = _project(tmp_path)
        cache = _scan_then_find_cache(root)
        cache.write_text(json.dumps(_shape(tool="0.0.1")), encoding="utf-8", newline="\n")
        assert main(["check", "m.md", "--root", str(root), "--quiet"]) == 0


class TestAGoodCacheIsStillUsed:
    """Without these, the fix could be "stop reading the cache" and pass."""

    def test_the_recorded_pages_are_returned(self, tmp_path: Path):
        root = _project(tmp_path)
        cache = _scan_then_find_cache(root)
        pages = sources._load_cache(root, cache.stem, ("plain",))
        assert pages is not None
        assert [page.number for page in pages] == [1]
        assert pages[0].text == SOURCE_TEXT

    def test_a_hit_does_not_open_the_source(self, tmp_path: Path, monkeypatch):
        root = _project(tmp_path)
        cache = _scan_then_find_cache(root)
        sha = cache.stem

        def refuse(_path):
            raise AssertionError("a cache hit must not extract the file again")

        monkeypatch.setattr(sources, "_plain_text_pages", refuse)
        pages, problem = sources.extract_pages(root / "a.txt", root)
        assert problem is None
        assert pages is not None and pages[0].text == SOURCE_TEXT
        assert sources._load_cache(root, sha, ("plain",)) is not None

    def test_a_page_number_is_taken_from_the_record(self, tmp_path: Path):
        """A cache written by a reader that numbers pages from 7 must keep
        saying 7; renumbering from one would point findings at the wrong page."""
        root = _project(tmp_path)
        cache = _scan_then_find_cache(root)
        cache.write_text(
            json.dumps(_shape(pages=[{"number": 7, "text": SOURCE_TEXT}])),
            encoding="utf-8",
            newline="\n",
        )
        pages = sources._load_cache(root, cache.stem, ("plain",))
        assert pages is not None and [page.number for page in pages] == [7]
