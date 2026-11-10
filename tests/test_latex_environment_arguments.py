"""The arguments a `\\begin{...}` line takes are markup, not prose.

`\\begin{minipage}{0.5\\textwidth}` and `\\begin{multicols}{2}` name a width and a
column count.  The converter read the environment name and left everything after
it in the stream, so the width was converted as if it were a word: measured
before the fix,

    \\begin{spacing}{1.5}
    We collected 40,688 examples from the corpus of written English and then
    filtered them by hand. \\citep{paper}
    \\end{spacing}

converted to ``'1.5\\nWe collected ...'``.  `draft` then glued the figure to the
next line - no full stop between them, so the sentence ran on - and wrote

    quote: |
      1.5 We collected 40,688 examples from the corpus of written English ...

with ``confidence: medium`` instead of the ``high`` the same sentence earns
outside the environment, and put it back in the manuscript as a claim.  Pasting
that block back gives ``[high] quote-fuzzy`` **and** ``[high]
number-absent-in-quote: the quote says 1.5 but page 1 does not contain that
number`` - two accusations against a sentence the source prints verbatim and a
figure the author never typed.

The tests below are the shapes a journal template actually writes.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from citevouch.latex import to_text

BS = chr(92)
NL = chr(10)
B3 = chr(96) * 3
SENTENCE = (
    "We collected 40,688 examples from the corpus of written English and then "
    "filtered them by hand."
)


def _document(body: str) -> str:
    return (
        BS
        + "documentclass{article}"
        + NL
        + BS
        + "begin{document}"
        + NL
        + body
        + BS
        + "end{document}"
        + NL
    )


class TestAWidthOrACountIsNotAWord:
    @pytest.mark.parametrize(
        "environment, argument",
        [
            ("minipage", "{0.45" + BS + "textwidth}"),
            ("multicols", "{2}"),
            ("multicols*", "{2}"),
            ("spacing", "{1.5}"),
            ("column", "{0.5" + BS + "textwidth}"),
            ("adjustbox", "{width=0.8" + BS + "textwidth}"),
            ("overlaycolumn", "{0.3" + BS + "textwidth}"),
        ],
    )
    def test_the_count_does_not_become_the_first_word(self, environment, argument):
        converted = to_text(
            _document(
                BS
                + "begin{"
                + environment
                + "}"
                + argument
                + NL
                + SENTENCE
                + NL
                + BS
                + "end{"
                + environment
                + "}"
                + NL
            )
        )
        assert converted.strip().splitlines()[0] == SENTENCE, converted

    @pytest.mark.parametrize(
        "environment, arguments",
        [
            ("wrapfigure", "{r}{0.4" + BS + "textwidth}"),
            ("wraptable", "{r}{0.4" + BS + "textwidth}"),
            ("subfigure", "{0.4" + BS + "textwidth}"),
            ("subtable", "{0.4" + BS + "textwidth}"),
        ],
    )
    def test_a_float_that_takes_two_arguments_gives_none_back(self, environment, arguments):
        converted = to_text(
            _document(
                BS
                + "begin{"
                + environment
                + "}"
                + arguments
                + NL
                + SENTENCE
                + NL
                + BS
                + "end{"
                + environment
                + "}"
                + NL
            )
        )
        assert converted.strip().splitlines()[0] == SENTENCE, converted

    def test_a_space_before_the_argument_changes_nothing(self):
        # TeX does not care whether an argument touches its environment name.
        converted = to_text(
            _document(
                BS
                + "begin{minipage} {0.45"
                + BS
                + "textwidth}"
                + NL
                + SENTENCE
                + NL
                + BS
                + "end{minipage}"
                + NL
            )
        )
        assert converted.strip().splitlines()[0] == SENTENCE, converted

    def test_the_second_argument_may_follow_a_space(self):
        # `wrapfigure` takes two arguments. TeX allows spaces between them, and
        # a reader that stops skipping at the first space pastes the width back
        # into the sentence.
        converted = to_text(
            _document(
                BS
                + "begin{wrapfigure}{r}  {0.4"
                + BS
                + "textwidth}"
                + NL
                + SENTENCE
                + NL
                + BS
                + "end{wrapfigure}"
                + NL
            )
        )
        assert converted.strip().splitlines()[0] == SENTENCE, converted
        assert "0.4" not in converted, converted

    def test_an_unclosed_argument_does_not_swallow_the_body(self):
        # `{0.45` never closes. Losing the argument is the lesser error; the
        # sentence after it is the author's and must survive.
        converted = to_text(
            BS + "begin{minipage}{0.45" + NL + SENTENCE + NL + BS + "end{minipage}" + NL
        )
        assert SENTENCE in converted, converted

    def test_the_end_tag_takes_no_arguments(self):
        # `\end{minipage}` is a marker, not a command with parameters: a braced
        # group after it belongs to the author.
        converted = to_text(
            BS
            + "begin{minipage}{0.45"
            + BS
            + "textwidth}"
            + NL
            + SENTENCE
            + NL
            + BS
            + "end{minipage}"
            + NL
            + "{The appendix note stays.}"
            + NL
        )
        assert "The appendix note stays." in converted, converted


class TestAPlacementSpecifierIsNotAWord:
    @pytest.mark.parametrize("argument", ["[t]", "[htbp]", "[!ht]", "[t] "])
    def test_the_float_placement_does_not_reach_the_prose(self, argument):
        converted = to_text(
            _document(
                BS + "begin{figure}" + argument + NL + SENTENCE + NL + BS + "end{figure}" + NL
            )
        )
        assert argument.strip() not in converted, converted
        assert SENTENCE in converted, converted

    def test_a_beamer_overlay_does_not_reach_the_prose(self):
        converted = to_text(
            _document(BS + "begin{onlyenv}<2->" + NL + SENTENCE + NL + BS + "end{onlyenv}" + NL)
        )
        assert "2->" not in converted, converted
        assert SENTENCE in converted, converted


class TestATitleStaysATitle:
    @pytest.mark.parametrize(
        "environment", ["theorem", "lemma", "corollary", "proposition", "remark", "proof"]
    )
    def test_a_named_result_is_not_glued_to_its_statement(self, environment):
        converted = to_text(
            _document(
                BS
                + "begin{"
                + environment
                + "}[Main result]"
                + NL
                + SENTENCE
                + NL
                + BS
                + "end{"
                + environment
                + "}"
                + NL
            )
        )
        assert "Main result" in converted, converted
        lines = [line for line in converted.splitlines() if line.strip()]
        assert lines[0].strip() == "[Main result]", lines
        assert lines[1].strip() == SENTENCE, lines


class TestWhatMustStillReachTheProse:
    def test_a_group_the_environment_does_not_take_is_still_prose(self):
        # `center` takes no argument; a braced group after it is the author's text.
        converted = to_text(
            _document(BS + "begin{center}{" + SENTENCE + "}" + NL + BS + "end{center}" + NL)
        )
        assert SENTENCE in converted, converted

    def test_the_body_of_an_ordinary_environment_is_untouched(self):
        converted = to_text(
            _document(BS + "begin{quote}" + SENTENCE + NL + BS + "end{quote}" + NL)
        )
        assert converted.strip() == SENTENCE, converted


class TestTheVerdictOnAProject:
    def _run(self, root: Path, *argv: str) -> tuple[int, str]:
        env = {**os.environ, "PYTHONPATH": str(Path.cwd() / "src"), "PYTHONIOENCODING": "utf-8"}
        done = subprocess.run(
            [sys.executable, "-m", "citevouch", *argv],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return done.returncode, (done.stdout or "") + (done.stderr or "")

    def _project(self, root: Path, tex: str) -> None:
        (root / "page.txt").write_text(
            "Some preamble." + NL + NL + SENTENCE + NL, encoding="utf-8", newline=NL
        )
        (root / "sources.toml").write_text(
            "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
        )
        (root / "manuscript.tex").write_text(tex, encoding="utf-8", newline=NL)

    def test_the_proposal_does_not_quote_the_width(self, tmp_path):
        self._project(
            tmp_path,
            BS
            + "begin{spacing}{1.5}"
            + NL
            + SENTENCE
            + " "
            + BS
            + "citep{paper}."
            + NL
            + BS
            + "end{spacing}"
            + NL,
        )
        code, out = self._run(tmp_path, "draft", "manuscript.tex", "-o", "claims.md")
        written = (tmp_path / "claims.md").read_text(encoding="utf-8")
        assert code == 0, out
        assert "1 claim block(s) proposed (1 verbatim)" in out, out
        assert "1.5" not in written, written

    def test_the_block_it_writes_survives_the_check(self, tmp_path):
        self._project(
            tmp_path,
            BS
            + "begin{minipage}{0.5"
            + BS
            + "textwidth}"
            + NL
            + SENTENCE
            + " "
            + BS
            + "citep{paper}."
            + NL
            + BS
            + "end{minipage}"
            + NL,
        )
        code, out = self._run(tmp_path, "draft", "manuscript.tex", "-o", "claims.md")
        assert code == 0, out
        (tmp_path / "manuscript.md").write_text(
            (tmp_path / "claims.md").read_text(encoding="utf-8"), encoding="utf-8", newline=NL
        )
        code, out = self._run(tmp_path, "check", "manuscript.md")
        assert "number-absent-in-quote" not in out, out
        assert "quote-fuzzy" not in out, out
        assert code == 0, out
