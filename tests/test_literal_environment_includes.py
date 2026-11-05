"""Round 176: an `\\input` inside a verbatim body is an example, not an include."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from citevouch.latex import included_files

BS = chr(92)
NL = chr(10)

#: Environments whose body TeX reads as characters, not as commands.  A name
#: written inside one is being *shown*, the way a paper shows the syntax it is
#: talking about, and it is not a file the document pulls in.
LITERAL = ("verbatim", "verbatim*", "lstlisting", "minted", "filecontents", "comment")

#: Environments whose body TeX still executes.  `alltt` is verbatim-ish but
#: commands inside it run, and `tabular`/`tikzpicture` are dropped from the
#: converted text while their contents are still read, so a name inside one of
#: these really is pulled in and must keep being reported.
EXECUTED = ("alltt", "tabular", "tikzpicture")


def _wrapped(name: str, body: str) -> str:
    argument = "{python}" if name == "minted" else ""
    return f"{BS}begin{{{name}}}{argument}{body}{BS}end{{{name}}}{NL}Real work.{NL}"


class TestABodyTexReadsLiterallyIsNotAnInclude:
    @pytest.mark.parametrize("name", LITERAL)
    def test_the_name_inside_is_not_reported(self, name: str) -> None:
        tex = _wrapped(name, f"{BS}input{{ghost/sec}}")
        assert included_files(tex) == []

    @pytest.mark.parametrize("name", LITERAL)
    def test_the_real_include_after_it_still_is(self, name: str) -> None:
        tex = _wrapped(name, f"{BS}input{{ghost/sec}}") + f"{BS}input{{real/sec}}{NL}"
        assert included_files(tex) == ["real/sec"]

    def test_an_unclosed_one_does_not_swallow_the_rest(self) -> None:
        tex = f"{BS}begin{{verbatim}}{BS}input{{ghost/sec}}{NL}"
        assert included_files(tex) == []

    def test_a_second_listing_is_blanked_too(self) -> None:
        tex = (
            _wrapped("lstlisting", f"{BS}input{{first/ghost}}")
            + _wrapped("lstlisting", f"{BS}input{{second/ghost}}")
            + f"{BS}input{{real/sec}}{NL}"
        )
        assert included_files(tex) == ["real/sec"]

    def test_a_real_include_between_two_listings_is_found(self) -> None:
        tex = (
            _wrapped("verbatim", f"{BS}input{{ghost/one}}")
            + f"{BS}input{{real/mid}}{NL}"
            + _wrapped("verbatim", f"{BS}input{{ghost/two}}")
        )
        assert included_files(tex) == ["real/mid"]


class TestABodyTexExecutesIsStillAnInclude:
    @pytest.mark.parametrize("name", EXECUTED)
    def test_the_name_inside_is_reported(self, name: str) -> None:
        tex = _wrapped(name, f"{BS}input{{real/sec}}")
        assert included_files(tex) == ["real/sec"]


class TestTheInlineSpellingStaysOut:
    @pytest.mark.parametrize(
        "tex",
        [
            f"Use {BS}verb|{BS}input{{ghost/sec}}| here.{NL}",
            f"Use {BS}lstinline|{BS}input{{ghost/sec}}| here.{NL}",
        ],
    )
    def test_a_shown_command_is_not_a_file(self, tex: str) -> None:
        assert included_files(tex) == []


class TestWhatStillCounts:
    def test_a_real_input_is_still_reported(self) -> None:
        assert included_files(f"{BS}input{{real/sec}}{NL}") == ["real/sec"]

    def test_a_commented_out_input_is_still_not(self) -> None:
        assert included_files(f"% {BS}input{{ghost/sec}}{NL}Text.{NL}") == []


class TestTheSentenceTheAuthorSaw:
    """The warning `draft` prints must be true of the document it is about."""

    def _draft(self, root: Path) -> str:
        env = {**os.environ, "PYTHONPATH": str(Path.cwd() / "src")}
        subprocess.run(
            [sys.executable, "-m", "citevouch", "draft", "paper.tex", "--root", "."],
            cwd=root,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        return (root / "claims.md").read_text(encoding="utf-8")

    def test_a_listing_does_not_produce_a_warning(self, tmp_path: Path) -> None:
        (tmp_path / "paper.tex").write_text(
            f"{BS}documentclass{{article}}{NL}{BS}begin{{document}}{NL}"
            f"We trained on 40,688 examples {BS}cite{{known}}.{NL}"
            f"{NL}"
            f"{BS}begin{{lstlisting}}{NL}{BS}input{{chapters/intro}}{NL}"
            f"{BS}end{{lstlisting}}{NL}"
            f"{NL}The held-out set has 9,800 rolesets.{NL}{BS}end{{document}}{NL}",
            encoding="utf-8",
        )
        text = self._draft(tmp_path)
        assert "chapters/intro" not in text
        assert "pulls text in from" not in text

    def test_a_real_input_still_does(self, tmp_path: Path) -> None:
        (tmp_path / "paper.tex").write_text(
            f"{BS}documentclass{{article}}{NL}{BS}begin{{document}}{NL}"
            f"We trained on 40,688 examples {BS}cite{{known}}.{NL}"
            f"{BS}input{{chapters/intro}}{NL}"
            f"{BS}end{{document}}{NL}",
            encoding="utf-8",
        )
        text = self._draft(tmp_path)
        assert "pulls text in from chapters/intro" in text
