"""A misspelt attribute on the *opening* line of a claim block.

`_split_body` refuses to drop a field-shaped line inside the body: it reports
`claim-field-unknown` and names the key.  The opening line had no such guard.
`_attrs` parses every `key=value` token it finds and keeps them all in a dict,
but `_claim_from` reads only the keys it knows - so a misspelt one was kept and
then never read, which is the same silence the body path already refuses.

Measured before this file existed, on a project whose quote is on page 3 and
which also prints the same sentence on page 1:

    ```claim id=c1 source=paper page=3   -> quote-found page 3
    ```claim id=c1 source=paper pgae=3   -> quote-found page 1, exit 0, no finding

The author asked for page 3, got page 1, and nothing said so.
"""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path

import pytest

from citevouch.cli import main
from citevouch.manuscript import parse_manuscript

B3 = "`" * 3
NL = chr(10)
# The same sentence on page 1 and page 3, so "which page did the hint pick?"
# is visible in the output rather than inferred.
SENTENCE = "It was the second year of the project."
PAGES = [SENTENCE, "We collected 154,391 examples from the corpus.", SENTENCE]


def _project(root: Path, manuscript: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "page.txt").write_text(chr(12).join(PAGES) + chr(12), encoding="utf-8")
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8"
    )
    (root / "manuscript.md").write_text(manuscript, encoding="utf-8", newline="\n")
    return root


def _fenced(attrs: str, body: str = "") -> str:
    return (
        "# T"
        + NL
        + NL
        + f"{B3}claim {attrs}"
        + NL
        + (body or "quote: |" + NL + "  " + SENTENCE)
        + NL
        + B3
        + NL
    )


def _commented_inline(attrs: str) -> str:
    return "# T" + NL + NL + f"<!-- claim {attrs} -->" + NL + ">> " + SENTENCE + NL


def _commented_block(attrs: str) -> str:
    return (
        "# T"
        + NL
        + NL
        + f"<!-- claim {attrs}"
        + NL
        + "quote: |"
        + NL
        + "  "
        + SENTENCE
        + NL
        + "-->"
        + NL
    )


def _run(root: Path, *args: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main([*args, "manuscript.md", "--root", str(root)])
    return code, out.getvalue()


def _unknown(output: str) -> list[str]:
    return [line for line in output.splitlines() if "claim-field-unknown" in line]


class TestTheDistanceIsReal:
    @pytest.mark.parametrize(
        ("typo", "right"),
        [
            ("pgae", "page"),
            ("paeg", "page"),
            ("soruce", "source"),
            ("surce", "source"),
            ("idd", "id"),
            ("rfe", "ref"),
            ("citee", "cite"),
            ("markr", "marker"),
        ],
    )
    def test_a_near_miss_points_at_the_right_key(self, typo: str, right: str) -> None:
        from citevouch.manuscript import _nearest_attribute

        assert _nearest_attribute(typo) == right

    @pytest.mark.parametrize("word", ["data", "toolkit", "kind", "colour", "note", "mkr"])
    def test_a_word_that_is_not_a_key_is_not_near_one(self, word: str) -> None:
        """`mkr` is an abbreviation, not a slip: three letters are missing."""
        from citevouch.manuscript import _nearest_attribute

        assert _nearest_attribute(word) is None


class TestTheOpeningLineIsReadTheWayTheBodyIs:
    def test_a_misspelt_key_on_the_opening_line_is_reported(self, tmp_path: Path) -> None:
        root = _project(tmp_path, _fenced("id=c1 source=paper pgae=3"))
        code, output = _run(root, "check")
        assert _unknown(output), output
        assert "pgae" in output
        assert code == 0, "medium is below the default --fail-on high"

    def test_the_hint_that_was_spelt_right_is_not_reported(self, tmp_path: Path) -> None:
        root = _project(tmp_path, _fenced("id=c1 source=paper page=3"))
        code, output = _run(root, "check")
        assert not _unknown(output), output
        assert "quote-found at manuscript.md:3 (c1): quote found on page 3" in output
        assert code == 0

    def test_the_output_shows_which_page_the_hint_picked(self, tmp_path: Path) -> None:
        """The misspelt hint is not fatal; the point is that it is visible."""
        root = _project(tmp_path, _fenced("id=c1 source=paper pgae=3"))
        _, output = _run(root, "check")
        assert "quote found on page 1" in output, (
            "the hint was ignored, so the search took the first page it matched"
        )

    def test_the_message_lists_the_keys_that_do_exist(self, tmp_path: Path) -> None:
        root = _project(tmp_path, _fenced("id=c1 source=paper pgae=3"))
        _, output = _run(root, "check")
        line = _unknown(output)[0]
        assert "page" in line and "source" in line, line


class TestEveryDialect:
    def test_the_comment_dialect_reports_it_too(self, tmp_path: Path) -> None:
        root = _project(tmp_path, _commented_block("id=c1 source=paper pgae=3"))
        _, output = _run(root, "check")
        assert _unknown(output), output
        assert "pgae" in output

    def test_the_one_line_comment_reports_it_too(self, tmp_path: Path) -> None:
        root = _project(tmp_path, _commented_inline("id=c1 source=paper pgae=3"))
        _, output = _run(root, "check")
        assert _unknown(output), output
        assert "pgae" in output


class TestWhatMustStayQuiet:
    @pytest.mark.parametrize(
        "attrs",
        [
            "id=c1 source=paper",
            "id=c1 source=paper ref=knuth2020",
            "id=c1 source=paper cite=knuth2020",
            "id=c1 source=paper page=3 marker=x",
        ],
    )
    def test_a_known_key_is_never_unknown(self, tmp_path: Path, attrs: str) -> None:
        root = _project(tmp_path, _fenced(attrs))
        _, output = _run(root, "check")
        assert not _unknown(output), (attrs, output)

    def test_a_missing_source_is_still_the_error_about_the_source(self, tmp_path: Path) -> None:
        root = _project(tmp_path, _fenced("id=c1 page=3"))
        _, output = _run(root, "check")
        assert "claim-uncheckable" in output, output
        assert "names no source=" in output, output
        assert not _unknown(output), output

    def test_the_quoted_value_may_contain_an_equals_sign(self, tmp_path: Path) -> None:
        root = _project(tmp_path, _fenced('id=c1 source=paper ref="a=b"'))
        _, output = _run(root, "check")
        assert not _unknown(output), output

    @pytest.mark.parametrize("token", ["data-x=3", "toolkit=2", "kind=sentence", "colour=red"])
    def test_a_token_that_is_not_near_any_key_is_not_reported(
        self, tmp_path: Path, token: str
    ) -> None:
        """Some other tool's annotation is not a typo for one of our six keys."""
        root = _project(tmp_path, _fenced("id=c1 source=paper " + token))
        _, output = _run(root, "check")
        assert not _unknown(output), (token, output)

    def test_a_near_miss_beside_the_right_spelling_is_not_reported(
        self, tmp_path: Path
    ) -> None:
        """Nothing was lost: the key the author needed is written correctly."""
        root = _project(tmp_path, _fenced("id=c1 source=paper page=3 pgae=1"))
        _, output = _run(root, "check")
        assert not _unknown(output), output
        assert "quote found on page 3" in output


class TestTheTwoLinesAreBothNamed:
    def test_one_typo_in_the_body_and_one_on_the_opening_line(self, tmp_path: Path) -> None:
        body = "pgae: 3" + NL + "quote: |" + NL + "  " + SENTENCE
        root = _project(tmp_path, _fenced("id=c1 source=paper pgge=3", body))
        _, output = _run(root, "check")
        lines = _unknown(output)
        assert len(lines) == 2, lines
        # The opening-line one is line 3 (the fence), the body one line 4.
        assert "manuscript.md:3" in lines[0] or "manuscript.md:3" in lines[1]
        assert "manuscript.md:4" in lines[0] or "manuscript.md:4" in lines[1]


class TestTheSeverityContract:
    def test_fail_on_medium_refuses_the_run(self, tmp_path: Path) -> None:
        root = _project(tmp_path, _fenced("id=c1 source=paper pgae=3"))
        code, _ = _run(root, "check", "--fail-on", "medium")
        assert code == 1

    def test_the_sarif_rule_is_the_one_already_declared(self, tmp_path: Path) -> None:
        root = _project(tmp_path, _fenced("id=c1 source=paper pgae=3"))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            main(["check", "manuscript.md", "--root", str(root), "--format", "sarif"])
        blob = json.loads(out.getvalue())
        ids = [rule["id"] for rule in blob["runs"][0]["tool"]["driver"]["rules"]]
        assert "claim-field-unknown" in ids

    def test_the_parser_reports_it_without_the_cli(self, tmp_path: Path) -> None:
        text = _fenced("id=c1 source=paper pgae=3")
        result = parse_manuscript(text, "manuscript.md")
        assert [f.code for f in result.findings] == ["claim-field-unknown"]
