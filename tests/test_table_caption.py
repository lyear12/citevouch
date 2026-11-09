"""A caption inside a long table is a sentence a reader sees.

Dropping a table whole is right for the cells: they are data.  A caption is
not data - it is a sentence the author wrote, printed under the table, and it
can carry the citation that the paragraph refers to.  In a ``table`` float the
caption sits *outside* the grid, so dropping ``tabular`` always left it alone::

    \\begin{table}
    \\caption{We collected \\citep{knuth2020} 154,391 examples.}
    \\begin{tabular}{ll}...\\end{tabular}
    \\end{table}

``longtable`` and ``xltabular`` are different: they are designed to break across
pages, so their caption lives *inside* the environment, before ``\\endfirsthead``.
Dropping the body therefore drops the caption, and nothing else in the tool can
see it.  Measured before the fix, ``draft`` said::

    0 claim block(s) proposed: no citations were found to propose them for
    (this command reads `[@key]` and `\\cite{key}`)

about a paper whose longtable caption cites ``knuth2020`` in plain sight.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from citevouch import latex

BS = chr(92)
NL = chr(10)
ROOT = Path(__file__).resolve().parents[1]
ENV = {
    **os.environ,
    "PYTHONPATH": str(ROOT / "src"),
    "PYTHONIOENCODING": "utf-8",
}

CAPTION = "We collected " + BS + "citep{knuth2020} 154,391 examples."
PLAIN = "We collected 154,391 examples."
PAGE = PLAIN + NL

#: Environments that draw a table and take ``\\caption`` *inside* the body.
LONG_TABLES = ("longtable", "xltabular", "longtabu")


def _document(body: str) -> str:
    return BS + "begin{document}" + NL + body + NL + BS + "end{document}" + NL


def _longtable(environment: str, caption: str = CAPTION) -> str:
    return NL.join(
        [
            BS + "begin{" + environment + "}{ll}",
            BS + "caption{" + caption + "}" + BS * 2,
            "Ours & 90.1 " + BS * 2,
            BS + "end{" + environment + "}",
        ]
    )


class TestTheCaptionSurvivesTheDrop:
    @pytest.mark.parametrize("environment", LONG_TABLES)
    def test_the_caption_text_reaches_the_page(self, environment: str) -> None:
        text = latex.to_text(_document(_longtable(environment)))
        assert "We collected" in text
        assert "154,391 examples." in text

    @pytest.mark.parametrize("environment", LONG_TABLES)
    def test_the_citation_in_the_caption_is_recorded(self, environment: str) -> None:
        text = latex.to_text(_document(_longtable(environment)))
        assert "[@knuth2020]" in text

    @pytest.mark.parametrize("environment", LONG_TABLES)
    def test_the_cells_still_do_not(self, environment: str) -> None:
        text = latex.to_text(_document(_longtable(environment)))
        assert "90.1" not in text
        assert "Ours" not in text

    def test_an_optional_short_caption_is_not_the_prose(self) -> None:
        """``\\caption[short]{The sentence}`` prints the long one; keep that."""
        body = _longtable("longtable", "The sentence a reader sees.")
        body = body.replace(
            BS + "caption{The sentence a reader sees.}",
            BS + "caption[A short label]{The sentence a reader sees.}",
        )
        text = latex.to_text(_document(body))
        assert "The sentence a reader sees." in text
        assert "A short label" not in text

    def test_a_caption_star_survives_too(self) -> None:
        body = _longtable("longtable", "Unnumbered caption.")
        body = body.replace(BS + "caption{", BS + "caption*{")
        assert "Unnumbered caption." in latex.to_text(_document(body))

    def test_two_captions_do_not_run_together(self) -> None:
        """``\\caption{A}\\caption{B}`` must not become the word ``AB``."""
        body = NL.join(
            [
                BS + "begin{longtable}{ll}",
                BS + "caption{The first caption.}" + BS * 2,
                "Ours & 90.1 " + BS * 2,
                BS + "endfirsthead",
                BS + "caption{The second caption.}" + BS * 2,
                "Ours & 90.1 " + BS * 2,
                BS + "end{longtable}",
            ]
        )
        text = latex.to_text(_document(body))
        assert "The first caption." in text
        assert "The second caption." in text
        assert "caption.The" not in text
        assert "The first caption.The second caption." not in text

    def test_a_caption_after_the_environment_is_not_lifted_twice(self) -> None:
        """The scan is bounded by ``\\end{longtable}``, not by the file.

        A ``\\caption`` outside the table is kept by the ordinary
        unknown-command path (it belongs to some other float), so the check is
        that the new extractor does not *also* find it.
        """
        body = NL.join(
            [
                BS + "begin{longtable}{ll}",
                "Ours & 90.1 " + BS * 2,
                BS + "end{longtable}",
                "",
                BS + "caption{Outside the table.}",
            ]
        )
        text = latex.to_text(_document(body))
        assert text.count("Outside the table.") == 1

    def test_a_caption_inside_a_listing_nested_in_the_table(self) -> None:
        body = NL.join(
            [
                BS + "begin{longtable}{ll}",
                BS + "begin{verbatim}",
                BS + "caption{This is code, not a caption.}",
                BS + "end{verbatim}",
                BS + "caption{A real caption.}" + BS * 2,
                BS + "end{longtable}",
            ]
        )
        text = latex.to_text(_document(body))
        assert "This is code, not a caption." not in text
        assert "A real caption." in text

    def test_the_float_form_is_unchanged(self) -> None:
        """In a `table` float the caption was always outside the grid."""
        body = NL.join(
            [
                BS + "begin{table}",
                BS + "caption{" + PLAIN + "}",
                BS + "begin{tabular}{ll}",
                "Ours & 90.1 " + BS * 2,
                BS + "end{tabular}",
                BS + "end{table}",
            ]
        )
        text = latex.to_text(_document(body))
        assert PLAIN in text
        assert "90.1" not in text


class TestTheLiteralEnvironmentsAreNotTouched:
    """A ``\\caption`` inside a listing is code, not a caption."""

    @pytest.mark.parametrize(
        "environment", ["verbatim", "lstlisting", "minted", "filecontents"]
    )
    def test_a_caption_in_a_listing_stays_dropped(self, environment: str) -> None:
        opening = BS + "begin{" + environment + "}"
        if environment == "minted":
            opening += "{python}"
        body = NL.join(
            [opening, BS + "caption{Not a caption}", BS + "end{" + environment + "}"]
        )
        text = latex.to_text(_document(body))
        assert "Not a caption" not in text


class TestDraftSeesTheCitation:
    """The whole point: a citation in a longtable caption is a citation."""

    def _project(self, root: Path, caption: str) -> Path:
        root.mkdir(parents=True, exist_ok=True)
        (root / "page.txt").write_text(PAGE, encoding="utf-8", newline=NL)
        (root / "sources.toml").write_text(
            "[sources]" + NL + 'knuth2020 = "page.txt"' + NL,
            encoding="utf-8",
            newline=NL,
        )
        (root / "paper.tex").write_text(
            BS
            + "documentclass{article}"
            + NL
            + BS
            + "begin{document}"
            + NL
            + _longtable("longtable", caption)
            + NL
            + BS
            + "end{document}"
            + NL,
            encoding="utf-8",
            newline=NL,
        )
        return root

    def _run(self, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "citevouch", *args],
            cwd=root,
            env=ENV,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def test_the_citation_is_found_and_matched(self, tmp_path: Path) -> None:
        root = self._project(tmp_path / "case", CAPTION)
        proc = self._run(root, "draft", "paper.tex", "--root", ".")
        out = proc.stdout + proc.stderr
        assert "no citations were found" not in out
        assert "1 claim block(s) proposed" in out

    def test_a_caption_not_on_any_page_is_reported_as_such(self, tmp_path: Path) -> None:
        """The finding names the caption sentence, not a table row."""
        caption = "Nothing in this caption matches the page at all " + BS + "citep{knuth2020}."
        root = self._project(tmp_path / "case", caption)
        proc = self._run(root, "draft", "paper.tex", "--root", ".")
        out = proc.stdout + proc.stderr
        assert "no citations were found" not in out
        assert "left as comments" in out
