"""A ledger written by an older build still reads true.

``Claim.numbers`` is derived data: ``manuscript._claim_from`` builds it by
running ``CANON_PATTERN`` over the quote, and ``model`` documents the invariant
("``claim.numbers`` has always held the quote's numbers").  What changed in
0.22.16 is *how* that pattern reads a grouping space: ``40 688`` used to be two
numbers, and is one now.

So every ledger committed before 0.22.16 holds ``["40", "688"]`` for a quote
that says ``40 688``.  Reading it here compared those two stale tokens against
a page the new build reads as ``40688`` and reported

    [high] number-absent-in-quote ... the quote says 40 and 688 but page 1 of
    the source does not contain those numbers

about a quote that is *verbatim* the page.  That is the one accusation this
tool must never make by mistake, and it landed on every repository that
upgraded, because ``action.yml`` runs ``check --use-recorded``.

The repair is not "be lenient when comparing": a lenient comparison would also
stop catching a genuinely re-typed number.  It is that the field is a
*transcription of the quote*, so on read it is re-derived from the quote - the
load-bearing field, per ``Claim``'s own docstring - and the stored spelling is
only checked for shape.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from citevouch.cli import main
from citevouch.errors import UsageError
from citevouch.model import SUPPORTED_SCHEMA, Ledger

NL = chr(10)

#: What a pre-0.22.16 `scan` wrote for a quote that reads ``40 688``.
OLD_SPELLING = ["40", "688"]
#: What this build writes for the same quote.
NEW_SPELLING = ["40 688"]

PAGE = f"We collected 40 688 examples in total.{NL}"


def _project(tmp_path: Path, quote: str = "We collected 40 688 examples in total.") -> Path:
    (tmp_path / "page.txt").write_text(PAGE, encoding="utf-8")
    (tmp_path / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8"
    )
    body = NL.join(
        [
            "```claim id=c1 source=paper page=1",
            f"quote: {quote}",
            "```",
            "",
        ]
    )
    (tmp_path / "m.md").write_text(body, encoding="utf-8")
    return tmp_path


def _scan(root: Path) -> dict:
    assert main(["scan", str(root / "m.md"), "--root", str(root)]) in (0, 1)
    return json.loads((root / "citevouch.lock.json").read_text(encoding="utf-8"))


def _rewrite(root: Path, numbers: list[str]) -> None:
    path = root / "citevouch.lock.json"
    blob = json.loads(path.read_text(encoding="utf-8"))
    blob["claims"][0]["numbers"] = numbers
    path.write_text(json.dumps(blob), encoding="utf-8", newline=NL)


def _check(root: Path) -> int:
    return main(
        [
            "check",
            "--use-recorded",
            str(root / "m.md"),
            "--root",
            str(root),
            "--fail-on",
            "high",
        ]
    )


class TestTheStoredSpellingIsNotTheVerdict:
    def test_this_build_writes_the_new_spelling(self, tmp_path: Path) -> None:
        blob = _scan(_project(tmp_path))
        assert blob["claims"][0]["numbers"] == NEW_SPELLING

    def test_an_old_ledger_about_a_verbatim_quote_is_green(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _scan(root)
        _rewrite(root, OLD_SPELLING)
        assert _check(root) == 0

    def test_the_stale_spelling_never_survives_the_read(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _scan(root)
        _rewrite(root, OLD_SPELLING)
        blob = json.loads((root / "citevouch.lock.json").read_text(encoding="utf-8"))
        ledger = Ledger.from_json(blob)
        assert ledger.claims[0].numbers == ("40 688",)


class TestWhatIsStillCaught:
    """Re-deriving the field must not turn a real mismatch green."""

    def test_a_retyped_number_is_still_an_accusation(self, tmp_path: Path) -> None:
        root = _project(tmp_path, quote="We collected 80,688 examples in total.")
        _scan(root)
        assert _check(root) == 1

    def test_the_reading_comes_from_the_quote_a_wrong_one_is_still_absent(
        self, tmp_path: Path
    ) -> None:
        root = _project(tmp_path, quote="We collected 80,688 examples in total.")
        _scan(root)
        _rewrite(root, ["80", "688"])
        ledger = Ledger.from_json(
            json.loads((root / "citevouch.lock.json").read_text(encoding="utf-8"))
        )
        # The quote says 80,688: that is what the field becomes, and it is not
        # on the page.  A ledger that stored something else cannot rescue it.
        assert ledger.claims[0].numbers == ("80,688",)
        assert _check(root) == 1


class TestTheFieldIsStillShapeChecked:
    """A value no reader could have produced is damage, not staleness."""

    @pytest.mark.parametrize("value", [5, [1], {"a": 1}, "40,688"])
    def test_a_number_where_a_list_belongs_is_refused(self, tmp_path: Path, value) -> None:
        root = _project(tmp_path)
        blob = _scan(root)
        blob["claims"][0]["numbers"] = value
        with pytest.raises(UsageError):
            Ledger.from_json(blob)

    def test_the_cli_still_exits_two_on_it(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _scan(root)
        _rewrite(root, [])  # a shape the writer produces
        path = root / "citevouch.lock.json"
        blob = json.loads(path.read_text(encoding="utf-8"))
        blob["claims"][0]["numbers"] = 5
        path.write_text(json.dumps(blob), encoding="utf-8", newline=NL)
        assert _check(root) == 2


class TestTheInvariantHoldsEverywhere:
    def test_a_claim_read_back_never_disagrees_with_its_own_quote(self, tmp_path: Path) -> None:
        from citevouch.textnorm import quote_numbers

        for quote in (
            "We collected 40 688 examples.",
            "We collected 40,688 examples.",
            "Accuracy rose 48.4% in 2019.",
            "Nothing numeric here.",
        ):
            root = tmp_path / f"case{len(list(tmp_path.iterdir()))}"
            root.mkdir(parents=True)
            _project(root, quote=quote)
            blob = _scan(root)
            ledger = Ledger.from_json(blob)
            assert ledger.claims[0].numbers == quote_numbers(quote)


def test_the_scanned_ledger_is_schema_one(tmp_path: Path) -> None:
    """The repair must not need a schema bump: old and new ledgers both say 1."""
    blob = _scan(_project(tmp_path))
    assert blob["schema"] == SUPPORTED_SCHEMA == 1
