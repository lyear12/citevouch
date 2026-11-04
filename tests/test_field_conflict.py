"""Two spellings of one attribute, written at once, and neither says so.

`ref=` and `cite=` name the same thing (`_claim_from` reads
`attrs.get("ref", attrs.get("cite", ""))`, and `_attribute_key` lists both).
Measured on a project whose `refs.bib` holds `knuth2020` and `dijkstra1972`,
with a quote that is verbatim on page 1:

    ref=phantom cite=knuth2020   ->  check exit 1
        [high] bib-key-missing: claim c1 cites 'phantom', ...
    cite=phantom ref=knuth2020   ->  check exit 0, no finding at all

One direction accuses the author on the strength of a string they may have
meant to replace; the other throws that string away without a word.  Both are
silent about the fact that two conflicting instructions were written.  This is
the `Page: 1` defect again, one attribute over: a statement in the manuscript
that is neither applied nor reported.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from citevouch.manuscript import parse_manuscript

NL = chr(10)

BIB = (
    "@article{knuth2020,"
    + NL
    + "  title = {Literate Programming},"
    + NL
    + "  author = {Knuth, Donald},"
    + NL
    + "  journal = {The Computer Journal},"
    + NL
    + "  year = {2020}"
    + NL
    + "}"
    + NL
    + "@article{dijkstra1972,"
    + NL
    + "  title = {The Humble Programmer},"
    + NL
    + "  author = {Dijkstra, Edsger},"
    + NL
    + "  journal = {CACM},"
    + NL
    + "  year = {1972}"
    + NL
    + "}"
    + NL
)

PAGE = "We collected 40,688 examples in total." + NL
QUOTE = "quote: |" + NL + "  We collected 40,688 examples in total." + NL


def block(head: str, body_extra: str = "") -> str:
    return "```claim " + head + NL + body_extra + QUOTE + "```" + NL


def codes(text: str) -> list[str]:
    parsed = parse_manuscript(text, "m.md")
    return [finding.code for finding in parsed.findings]


# --------------------------------------------------------------------------
# The parser: a disagreeing pair is named.


class TestDisagreeingSpellings:
    def test_both_on_the_fence_and_different(self):
        parsed = parse_manuscript(
            block("id=c1 source=paper page=1 ref=phantom cite=knuth2020"), "m.md"
        )
        assert [f.code for f in parsed.findings] == ["claim-field-conflict"]
        assert parsed.claims[0].ref == "phantom"

    def test_the_other_order_is_the_same_defect(self):
        parsed = parse_manuscript(
            block("id=c1 source=paper page=1 cite=phantom ref=knuth2020"), "m.md"
        )
        assert [f.code for f in parsed.findings] == ["claim-field-conflict"]

    def test_both_in_the_body(self):
        parsed = parse_manuscript(
            block(
                "id=c1 source=paper page=1",
                "ref: phantom" + NL + "cite: knuth2020" + NL,
            ),
            "m.md",
        )
        assert [f.code for f in parsed.findings] == ["claim-field-conflict"]

    def test_one_on_the_fence_one_in_the_body(self):
        parsed = parse_manuscript(
            block("id=c1 source=paper page=1 ref=knuth2020", "cite: phantom" + NL),
            "m.md",
        )
        assert [f.code for f in parsed.findings] == ["claim-field-conflict"]

    def test_agreement_is_not_a_conflict(self):
        parsed = parse_manuscript(
            block("id=c1 source=paper page=1 ref=knuth2020 cite=knuth2020"), "m.md"
        )
        assert parsed.findings == []

    def test_one_spelling_alone_is_not_a_conflict(self):
        for spelling in ("ref=knuth2020", "cite=knuth2020"):
            parsed = parse_manuscript(block(f"id=c1 source=paper page=1 {spelling}"), "m.md")
            assert parsed.findings == [], spelling
            assert parsed.claims[0].ref == "knuth2020", spelling


class TestWhatTheMessageSays:
    def test_it_names_both_values(self):
        parsed = parse_manuscript(
            block("id=c1 source=paper page=1 ref=phantom cite=knuth2020"), "m.md"
        )
        message = parsed.findings[0].message
        assert "phantom" in message
        assert "knuth2020" in message

    def test_it_names_both_attributes(self):
        parsed = parse_manuscript(
            block("id=c1 source=paper page=1 ref=phantom cite=knuth2020"), "m.md"
        )
        message = parsed.findings[0].message
        assert "ref" in message
        assert "cite" in message

    @pytest.mark.parametrize(
        ("head", "kept", "dropped"),
        [
            ("id=c1 source=paper page=1 ref=phantom cite=knuth2020", "ref", "cite"),
            ("id=c1 source=paper page=1 cite=phantom ref=knuth2020", "ref", "cite"),
        ],
    )
    def test_it_says_which_one_was_used(self, head, kept, dropped):
        """The pair holds two values and the run picks one, so the sentence has
        to say which.  Measured: without this, the message still named both
        values and still read like an explanation, and a mutation that dropped
        the attribution survived every other test in this file."""
        parsed = parse_manuscript(block(head), "m.md")
        message = parsed.findings[0].message
        assert f"{kept} was used" in message
        assert f"{dropped} was dropped" in message

    def test_it_points_at_the_opening_line(self):
        parsed = parse_manuscript(
            "prose" + NL + block("id=c1 source=paper page=1 ref=a cite=b"), "m.md"
        )
        assert parsed.findings[0].line == 2


# --------------------------------------------------------------------------
# The whole command: no direction is silent any more.


def project(root: Path, head: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "page.txt").write_text(PAGE, encoding="utf-8")
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8"
    )
    (root / "refs.bib").write_text(BIB, encoding="utf-8")
    (root / "m.md").write_text(block(head), encoding="utf-8", newline=NL)
    return root


def check(root: Path, capsys) -> tuple[int, str]:
    from citevouch.cli import main

    code = main(
        [
            "check",
            "m.md",
            "--root",
            str(root),
            "--bib",
            "refs.bib",
            "--fail-on",
            "medium",
        ]
    )
    return code, capsys.readouterr().out


class TestTheVerdictOnAProject:
    @pytest.mark.parametrize(
        "head",
        [
            "id=c1 source=paper page=1 ref=phantom cite=knuth2020",
            "id=c1 source=paper page=1 cite=phantom ref=knuth2020",
        ],
    )
    def test_a_conflicting_pair_is_reported(self, tmp_path, capsys, head):
        root = project(tmp_path / "p", head)
        code, out = check(root, capsys)
        assert "claim-field-conflict" in out
        assert code == 1

    def test_the_ledger_records_the_pair_too(self, tmp_path):
        root = project(tmp_path / "p", "id=c1 source=paper page=1 ref=phantom cite=knuth2020")
        from citevouch.cli import main

        main(["scan", "m.md", "--root", str(root), "--bib", "refs.bib"])
        text = (root / "citevouch.lock.json").read_text(encoding="utf-8")
        assert (
            "claim-field-conflict" in text or json.loads(text)["claims"][0]["ref"] == "phantom"
        )

    def test_an_agreeing_pair_stays_quiet(self, tmp_path, capsys):
        root = project(tmp_path / "p", "id=c1 source=paper page=1 ref=knuth2020 cite=knuth2020")
        code, out = check(root, capsys)
        assert "claim-field-conflict" not in out
        assert code == 0
