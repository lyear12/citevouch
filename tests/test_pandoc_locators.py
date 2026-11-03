"""Pandoc's bracket form holds more than keys, and a draft must read all of it.

Two defects, one dialect apart, both measured before the fix.

The recogniser required the bracket body to be keys separated by semicolons:

    [@a, p. 3]                  -> []
    [see @a]                    -> []
    [@a, p. 3; @b, p. 4]        -> []
    [-@a, ch. 2]                -> []

Pandoc's grammar is `[prefix @key suffix; @key2 suffix2]`, where the prefix is
prose ("see", "cf.") and the suffix is a locator ("p. 3", "ch. 2").  A page
number is how a large share of real Markdown citations are written, and every
reference manager emits it, so `draft` answered "no citations were found" to
manuscripts that cite on every paragraph.

The stripper was missing the plural commands, which the recogniser had only
just learned:

    \\cites{a}{b} in a sentence   ->  `claim: | ... \\cites{a}{b}.`

The unrecognised command survived into the sentence written as the claim text,
so the author was handed a sentence no human wrote - in the one field this
command exists to propose.
"""

from __future__ import annotations

import contextlib
import io
import os
from pathlib import Path

import pytest

from citevouch.cli import main
from citevouch.draft import citation_sites, statement_of

BS = chr(92)

PAGE = "Earlier work notes an interaction between lexis and construction in the corpus.\n"

#: Bracket forms that name exactly one key, and must name it.
ONE_KEY = [
    "[@a]",
    "[@a, p. 3]",
    "[@a, pp. 3-4]",
    "[@a, ch. 2]",
    "[@a, sec. 3.2]",
    "[@a, 3]",
    "[@a, unpaginated]",
    "[see @a]",
    "[see @a, p. 3]",
    "[cf. @a, ch. 2]",
    "[-@a]",
    "[-@a, ch. 2]",
    "[@a p. 3]",
]

#: Bracket forms that name two keys.
TWO_KEYS = [
    "[@a; @b]",
    "[@a, p. 3; @b, p. 4]",
    "[@a, p. 3 and @b, p. 4]",
    "[see @a; cf. @b]",
]

#: Brackets that hold an `@` but are not citations.
NOT_CITATIONS = [
    "[contact me at x@y.com]",
    "[not a citation]",
    "[see the note]",
    "a[1] and an email someone@example.com",
]


class TestABracketHoldingALocatorStillCites:
    @pytest.mark.parametrize("text", ONE_KEY)
    def test_the_key_is_found(self, text: str) -> None:
        assert [site.key for site in citation_sites(text)] == ["a"]

    @pytest.mark.parametrize("text", TWO_KEYS)
    def test_both_keys_are_found(self, text: str) -> None:
        assert [site.key for site in citation_sites(text)] == ["a", "b"]

    def test_the_keys_come_in_reading_order(self) -> None:
        found = citation_sites("First [@a], then [@b, p. 3], and [see @c].")
        assert [site.key for site in found] == ["a", "b", "c"]

    def test_the_line_is_where_the_bracket_is(self) -> None:
        found = citation_sites("one\n\ntwo [@a, p. 3]\n")
        assert [site.line for site in found] == [3]


class TestTheAtSignThatIsNotACitation:
    @pytest.mark.parametrize("text", NOT_CITATIONS)
    def test_it_names_nothing(self, text: str) -> None:
        assert citation_sites(text) == []

    def test_an_address_beside_a_real_citation_is_not_a_key(self) -> None:
        found = citation_sites("[@a; someone@example.com]")
        assert [site.key for site in found] == ["a"]


class TestTheSentenceIsTheAuthors:
    """`claim:` is a sentence the author wrote, so the furniture must be gone."""

    @pytest.mark.parametrize(
        "sentence",
        [
            f"Earlier work notes an interaction {BS}citep{{a}}.",
            f"Earlier work notes an interaction {BS}citep[see][p.~3]{{a}}.",
            f"Earlier work notes an interaction {BS}cites{{a}}{{b}}.",
            f"Earlier work notes an interaction {BS}textcites{{a}}{{b}}{{c}}.",
            f"Earlier work notes an interaction {BS}parencites[1][2]{{a}}[3]{{b}}.",
            "Earlier work notes an interaction [@a].",
            "Earlier work notes an interaction [@a, p. 3].",
            "Earlier work notes an interaction [see @a, pp. 3-4].",
            "Earlier work notes an interaction [@a, p. 3; @b, ch. 2].",
        ],
    )
    def test_no_command_survives_into_the_sentence(self, sentence: str) -> None:
        assert statement_of(sentence) == "Earlier work notes an interaction."


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "p"
    root.mkdir()
    (root / "page.txt").write_text(PAGE, encoding="utf-8", newline="\n")
    (root / "sources.toml").write_text('[sources]\npage = "page.txt"\n', encoding="utf-8")
    return root


def _run(root: Path, argv: list[str]) -> tuple[int, str]:
    out = io.StringIO()
    err = io.StringIO()
    here = os.getcwd()
    os.chdir(root)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = main(argv)
            except SystemExit as exc:  # pragma: no cover - argparse only
                code = int(exc.code or 0)
    finally:
        os.chdir(here)
    return code, out.getvalue()


class TestTheProposalTheAuthorPastes:
    def test_a_locator_citation_produces_a_block(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        (root / "m.md").write_text(
            "# Paper\n\n"
            "Earlier work notes an interaction between lexis and construction "
            "[@page, p. 1].\n",
            encoding="utf-8",
            newline="\n",
        )
        code, _ = _run(root, ["draft", "m.md", "--root", str(root), "-o", "out.md", "--force"])
        written = (root / "out.md").read_text(encoding="utf-8")
        assert code == 0
        assert "```claim" in written
        assert "no citations were found" not in written

    def test_a_plural_command_does_not_reach_the_claim_text(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        (root / "m.md").write_text(
            f"# Paper\n\nEarlier work notes an interaction between lexis and "
            f"construction {BS}cites{{page}}.\n",
            encoding="utf-8",
            newline="\n",
        )
        code, _ = _run(root, ["draft", "m.md", "--root", str(root), "-o", "out.md", "--force"])
        written = (root / "out.md").read_text(encoding="utf-8")
        assert code == 0
        assert "```claim" in written
        body = written.split("```claim", 1)[-1]
        assert BS + "cites" not in body
