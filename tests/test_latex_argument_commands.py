"""A command whose first argument is not prose must not leave it in the prose.

`\\textcolor{red}{small}` has two arguments: a colour, then the text.  The
colour is not a word, but until `_SKIP_FIRST_ARGUMENT` existed it was left glued
in front of the text - `redsmall` - because the command was in neither
`_KEEP_ARGUMENT` nor `_DROP_ARGUMENT` and fell through to "keep whatever it
wraps, drop the name".  The same held for `\\href{https://x}{this paper}`
(`https://xthis paper`), `\\scalebox{2}{big}` (`2big`), `\\parbox{3cm}{boxed}`
(`3cmboxed`) and `\\hyperlink{target}{linked}` (`targetlinked`).

That sentence is what `draft` proposes as the claim text, so an author reading
the proposal was being handed a sentence the paper does not contain.
"""

from __future__ import annotations

import pytest

from citevouch import latex


def _one(line: str) -> str:
    out = latex.to_text(line)
    return " ".join(out.split())


class TestTheFirstArgumentIsNotProse:
    @pytest.mark.parametrize(
        ("source", "expected"),
        [
            (r"A \textcolor{blue}{blue} word.", "A blue word."),
            (r"A \colorbox{yellow}{highlighted} word.", "A highlighted word."),
            (r"A \scalebox{2}{big} word.", "A big word."),
            (r"A \parbox{3cm}{boxed} word.", "A boxed word."),
            (r"A \hyperlink{target}{linked} word.", "A linked word."),
            (r"A \href{https://example.com/x}{this paper} word.", "A this paper word."),
        ],
    )
    def test_the_argument_does_not_survive(self, source: str, expected: str) -> None:
        assert _one(source) == expected

    def test_the_wrapped_text_is_kept(self) -> None:
        assert _one(r"A \textcolor{blue}{blue} word.") == "A blue word."


class TestTheCommandsWithTwoArguments:
    def test_resizebox_skips_both(self) -> None:
        assert _one(r"A \resizebox{1cm}{!}{resized} word.") == "A resized word."

    def test_fcolorbox_skips_both(self) -> None:
        assert _one(r"A \fcolorbox{red}{white}{two} word.") == "A two word."

    def test_the_last_argument_still_gets_converted(self) -> None:
        assert _one(r"A \textcolor{blue}{\textbf{bold blue}} word.") == "A bold blue word."


class TestTheOptionalArgumentIsNotProseEither:
    @pytest.mark.parametrize(
        ("source", "expected"),
        [
            (r"A \makebox[2cm]{framed} word.", "A framed word."),
            (r"A \framebox[2cm]{framed too} word.", "A framed too word."),
            # An optional argument *before* a skipped one: `\parbox[t]{3cm}{}`
            # and `\textcolor[RGB]{255,0,0}{}` both exist, so the skip has to
            # pass over `[...]` as well as `{}` before it reaches the prose.
            (r"A \parbox[t]{3cm}{boxed} word.", "A boxed word."),
            (r"A \textcolor[RGB]{255,0,0}{red} word.", "A red word."),
        ],
    )
    def test_an_optional_argument_is_not_a_word(self, source: str, expected: str) -> None:
        assert _one(source) == expected


class TestTheCommandsThatAlreadyWorkedStillDo:
    def test_raisebox_keeps_only_the_text(self) -> None:
        assert _one(r"A \raisebox{1pt}{lifted} word.") == "A lifted word."

    def test_includegraphics_drops_its_argument_whole(self) -> None:
        assert _one(r"A \includegraphics[width=1in]{f.pdf} word.") == "A word."

    def test_a_command_with_no_argument_does_not_eat_the_next_word(self) -> None:
        assert _one(r"A \textcolor{blue} word.") == "A word."

    def test_the_text_argument_is_still_ordinary_prose(self) -> None:
        assert _one(r"A \textbf{bold} word.") == "A bold word."


class TestTheProposalIsBuiltOnTheRealSentence:
    def test_draft_does_not_put_a_colour_in_the_claim(self, tmp_path) -> None:
        """The end-to-end consequence: the colour must not reach the proposal."""
        import contextlib
        import io

        from citevouch.cli import main

        (tmp_path / "paper.tex").write_text(
            "The method was shown to work on the corpus by previous studies "
            "\\textcolor{red}{and} then some more words follow here.\n",
            encoding="utf-8",
            newline="\n",
        )
        (tmp_path / "page.txt").write_text(
            "The method was shown to work on the corpus by previous studies "
            "and then some more words follow here.\n",
            encoding="utf-8",
            newline="\n",
        )
        out = tmp_path / "claims.md"
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            code = main(
                [
                    "draft",
                    "paper.tex",
                    "--root",
                    str(tmp_path),
                    "--source",
                    str(tmp_path / "page.txt"),
                    "-o",
                    str(out),
                    "--force",
                ]
            )
        assert code == 0
        written = out.read_text(encoding="utf-8")
        assert "red" not in written.split("claim:", 1)[-1]
