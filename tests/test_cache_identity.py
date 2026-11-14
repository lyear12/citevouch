"""A cache entry has to describe the bytes it is filed under.

`.citevouch/cache/<sha>.json` is named after a digest of the source, and until
this file existed nothing inside it was ever compared against that name.  The
filename was the only claim of association, and a filename is a claim the
reader never checked: a cache directory copied between checkouts, a merge that
took one side's cache and the other side's source, or a hand-edited file all
arrive looking exactly like an honest one.

Measured on the released behaviour, with the page text replaced and the rest of
the entry left alone:

    two pages numbered 1        the first answered for both, so a quote the
                                second page held was reported missing
    one page numbered 7         `check` said `quote-moved` - a finding against
                                the author - about a quote that was on the only
                                page there was, because the claim said 1 and the
                                record said 7
    one page with no number     the loader invented 1 from the list position
                                and answered anyway
    another file's sha256       nothing looked at it; the entry was used

The last one is the largest: the embedded hash was *written* by `_store_cache`
and never *read*, so the one field that could tie an entry to its filename was
pure decoration.

What this fix is not is authentication.  Anyone who can rewrite the pages can
rewrite the hash beside them; measured, a doctored entry whose pages were
replaced with a sentence the source does not contain turned `quote-missing` into
`quote-found`, and rewriting the hash as well changed nothing.  A self-reported
hash catches an accident, and accident is the whole of what a scratch directory
inside the author's own checkout is exposed to.  `TestTheHashIsNotAuthentication`
below pins that limit so it cannot be quietly upgraded into a security claim.

The rule for page numbers is 1..N, and it is knowable rather than guessed:
`extract_pages` is the only writer of this file, and it re-labels whatever
strings the reader returned with `enumerate(raw, start=1)`.  That is what lets
a record starting at 7 be refused instead of trusted; if a future reader is ever
given its own numbering, `tests/test_damaged_cache.py`'s
`test_the_writer_always_numbers_from_one` goes red first.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import ClassVar

import pytest

from citevouch import sources

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"

QUOTE = "We collected 40,688 examples from the corpus."
CLAIM = "We collected 40,688 examples from the corpus."
SOURCE_TEXT = "A header line.\n\n" + QUOTE + "\n\nA footer line.\n"
MANUSCRIPT = f"```claim\nid: c1\nsource: paper\npage: 1\nquote: |\n  {QUOTE}\n```\n"


def _project(tmp_path: Path, page_text: str = SOURCE_TEXT) -> Path:
    (tmp_path / "page.txt").write_text(page_text, encoding="utf-8", newline="\n")
    (tmp_path / "sources.toml").write_text(
        '[sources]\npaper = "page.txt"\n', encoding="utf-8", newline="\n"
    )
    (tmp_path / "m.md").write_text(MANUSCRIPT, encoding="utf-8", newline="\n")
    return tmp_path


def _warm(root: Path) -> Path:
    """Extract once so a real entry exists, then return its path."""
    sources.extract_pages(root / "page.txt", root)
    files = sorted(sources.cache_root(root).glob("*.json"))
    assert len(files) == 1, files
    return files[0]


def _rewrite(cache: Path, **changes) -> None:
    blob = json.loads(cache.read_text(encoding="utf-8"))
    blob.update(changes)
    cache.write_text(json.dumps(blob), encoding="utf-8", newline="\n")


def _run(root: Path, *argv: str) -> tuple[int, dict]:
    env = {
        **os.environ,
        "PYTHONPATH": str(SRC),
        "PYTHONIOENCODING": "utf-8",
    }
    proc = subprocess.run(
        [sys.executable, "-m", "citevouch", *argv, "--root", str(root), "--format", "json"],
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return proc.returncode, json.loads(proc.stdout)


def _verdict(root: Path, *extra: str) -> tuple[int, dict]:
    code, payload = _run(root, "check", "m.md", *extra)
    return code, payload["summary"]


class TestACacheThatDoesNotDescribeTheseBytesIsNotRead:
    """Every one of these was accepted by the released behaviour."""

    def test_another_files_hash_is_not_our_entry(self, tmp_path: Path):
        root = _project(tmp_path)
        cache = _warm(root)
        _rewrite(cache, sha256="0" * 64)
        assert sources._load_cache(root, cache.stem, ("plain",)) is None

    def test_a_repeated_page_number_is_not_our_entry(self, tmp_path: Path):
        root = _project(tmp_path)
        cache = _warm(root)
        _rewrite(
            cache,
            pages=[
                {"number": 1, "text": "the first page says something else"},
                {"number": 1, "text": SOURCE_TEXT},
            ],
        )
        assert sources._load_cache(root, cache.stem, ("plain",)) is None

    def test_a_gap_in_the_page_numbers_is_not_our_entry(self, tmp_path: Path):
        root = _project(tmp_path)
        cache = _warm(root)
        _rewrite(
            cache,
            pages=[
                {"number": 1, "text": SOURCE_TEXT},
                {"number": 3, "text": "the third page says something else"},
            ],
        )
        assert sources._load_cache(root, cache.stem, ("plain",)) is None

    def test_page_numbers_that_do_not_start_at_one_are_not_ours(self, tmp_path: Path):
        root = _project(tmp_path)
        cache = _warm(root)
        _rewrite(cache, pages=[{"number": 7, "text": SOURCE_TEXT}])
        assert sources._load_cache(root, cache.stem, ("plain",)) is None

    def test_a_page_with_no_number_is_not_ours(self, tmp_path: Path):
        """`PageText.to_json` writes both keys, so a page without one was not
        written here.  The old loader defaulted it to the list position."""
        root = _project(tmp_path)
        cache = _warm(root)
        _rewrite(cache, pages=[{"text": SOURCE_TEXT}])
        assert sources._load_cache(root, cache.stem, ("plain",)) is None


class TestTheVerdictIsTheSameEitherWay:
    """The point is not "the loader returns None" but "the answer is right".

    Each fixture below is doctored, and the answer afterwards must be the answer
    the honest source gives - the bytes are still on disk, so re-extracting is
    always available and always correct.
    """

    DOCTORED: ClassVar[dict[str, dict]] = {
        "another file's hash": {"sha256": "0" * 64},
        "a repeated page number": {
            "pages": [
                {"number": 1, "text": "the first page says something else"},
                {"number": 1, "text": SOURCE_TEXT},
            ]
        },
        "a page numbered seven": {"pages": [{"number": 7, "text": SOURCE_TEXT}]},
        "a page with no number": {"pages": [{"text": SOURCE_TEXT}]},
    }

    @pytest.mark.parametrize("name", sorted(DOCTORED))
    def test_a_doctored_entry_does_not_change_the_answer(self, tmp_path: Path, name: str):
        root = _project(tmp_path)
        honest_code, honest_summary = _verdict(root)
        assert (honest_code, honest_summary["verified"]) == (0, 1)

        cache = _warm(root)
        _rewrite(cache, **self.DOCTORED[name])

        again_code, again_summary = _verdict(root)
        assert again_code == honest_code
        assert again_summary["verified"] == honest_summary["verified"]
        assert again_summary["missing"] == honest_summary["missing"]

    @pytest.mark.parametrize(
        "name",
        [
            "a page numbered seven",
            "a repeated page number",
            "a gap in the page numbers",
            "a wrong hash beside pages that contradict the source",
            "no page number beside pages that contradict the source",
        ],
    )
    def test_a_doctored_entry_cannot_invent_a_quote(self, tmp_path: Path, name: str):
        """The strongest reading: a source that does not contain the quote.

        Re-extracting is then the only way to reach the honest answer
        (``quote-missing``), so any doctored entry that is read instead shows up
        as a ``quote-found`` that no evidence supports.  Cases whose doctored
        text matches the real source cannot distinguish anything here - both
        paths produce the same verdict - which is why these fixtures contradict
        the source rather than merely replacing its bytes.

        One doctored entry is *not* in this list on purpose: pages numbered
        correctly, hashed correctly, holding text the source does not contain.
        Nothing distinguishes it from an honest entry, because the hash is
        self-reported; that is the limitation
        ``TestTheHashIsNotAuthentication`` pins, and putting it here would
        assert a catch that does not exist.
        """
        root = _project(
            tmp_path,
            "The intervention did not improve accuracy in the controlled study.\n",
        )
        assert _verdict(root)[0] == 1

        cache = _warm(root)
        doctored = {
            "a page numbered seven": {"pages": [{"number": 7, "text": QUOTE}]},
            "a repeated page number": {
                "pages": [
                    {"number": 1, "text": QUOTE},
                    {"number": 1, "text": SOURCE_TEXT},
                ]
            },
            "a gap in the page numbers": {
                "pages": [
                    {"number": 1, "text": QUOTE},
                    {"number": 3, "text": SOURCE_TEXT},
                ]
            },
            "a wrong hash beside pages that contradict the source": {
                "sha256": "0" * 64,
                "pages": [{"number": 1, "text": QUOTE}],
            },
            "no page number beside pages that contradict the source": {
                "pages": [{"text": QUOTE}],
            },
        }[name]
        _rewrite(cache, **doctored)

        code, payload = _run(root, "check", "m.md")
        codes = {finding["code"] for finding in payload["findings"]}
        assert payload["summary"]["verified"] == 0, codes
        assert code == 1

    def test_a_page_numbered_seven_does_not_become_quote_moved(self, tmp_path: Path):
        """The measured finding: `quote-moved` is a finding against the author,
        and this one was produced by the cache rather than by the evidence."""
        root = _project(tmp_path)
        cache = _warm(root)
        _rewrite(cache, pages=[{"number": 7, "text": SOURCE_TEXT}])
        code, payload = _run(root, "check", "m.md")
        codes = {finding["code"] for finding in payload["findings"]}
        assert "quote-moved" not in codes
        assert code == 0


class TestColdWarmAndNoCacheAgree:
    """Three ways to reach the same pages must reach the same verdict."""

    def test_the_three_readings_of_one_project_agree(self, tmp_path: Path):
        root = _project(tmp_path)
        cold_code, cold = _verdict(root, "--no-cache")
        warm_code, warm = _verdict(root)
        again_code, again = _verdict(root)
        assert cold_code == warm_code == again_code == 0
        assert cold == warm == again

    def test_a_cache_hit_still_reads_no_source(self, tmp_path: Path, monkeypatch):
        root = _project(tmp_path)
        _warm(root)

        def refuse(_path):
            raise AssertionError("a cache hit must not extract the file again")

        monkeypatch.setattr(sources, "_plain_text_pages", refuse)
        pages, problem = sources.extract_pages(root / "page.txt", root)
        assert problem is None
        assert pages is not None and [page.number for page in pages] == [1]
        assert QUOTE in pages[0].text


class TestTheHashIsNotAuthentication:
    """A limit, pinned so it cannot be advertised as a boundary.

    If real authentication is ever added, this test goes red - and that is the
    correct signal: the docstring above, `docs/`, and the CHANGELOG entry all
    say the same narrow thing, and narrowing the hole means rewriting all three.
    """

    def test_a_careful_forger_is_not_caught(self, tmp_path: Path):
        """The source says the opposite.  The entry says the quote is there."""
        root = _project(
            tmp_path,
            "The intervention did not improve accuracy in the controlled study.\n",
        )
        honest_code, honest_summary = _verdict(root)
        assert honest_code == 1
        assert honest_summary["missing"] == 1
        cache = _warm(root)
        # The quote is not in this source at all; the entry is made to claim it
        # is, and the hash is rewritten to agree with the filename so the new
        # check has nothing to complain about.
        _rewrite(
            cache,
            sha256=cache.stem,
            pages=[{"number": 1, "text": QUOTE}],
        )
        code, payload = _run(root, "check", "m.md")
        assert code == 0
        assert payload["summary"]["verified"] == 1

    def test_the_limitation_is_written_where_a_reader_will_meet_it(self):
        """A hole nobody wrote down becomes a promise by omission.

        The module docstring, the `_load_cache` docstring and the CHANGELOG all
        have to say the same narrow thing - what a self-reported hash catches
        (an accident) and what it does not (a forger) - because `README.md` says
        the tool checks where a quote is, and a cache that can be taught any
        answer is exactly the kind of claim that sentence must not carry.
        """
        load_cache_doc = sources._load_cache.__doc__ or ""
        assert "not" in load_cache_doc and "authentication" in load_cache_doc
        assert "accident" in load_cache_doc
        module_doc = Path(__file__).read_text(encoding="utf-8")
        assert "not authentication" in module_doc
