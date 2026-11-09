"""A command whose first argument names something must not paste it into prose.

Measured on the tree before the fix: ``\\captionof{table}{We collected
154,391 examples.}`` converted to ``tableWe collected 154,391 examples.``, so
``draft`` compared a sentence the author never wrote against the page and
proposed nothing - a verbatim citation became "0 claim block(s) proposed".
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from citevouch import latex

ROOT = Path(__file__).resolve().parents[1]
BS = chr(92)
NL = chr(10)
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"}
# The page carries the words; the manuscript carries the same words with a
# citation on them, which is what `draft` proposes a claim for.
WORDS = "We collected 154,391 examples."
CITED = "We collected " + BS + "citep{knuth2020} 154,391 examples."
CONVERTED = "We collected [@knuth2020] 154,391 examples."
PAGE = WORDS + NL


def _doc(body: str) -> str:
    return BS + "begin{document}" + NL + body + NL + BS + "end{document}" + NL


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "citevouch", *args],
        cwd=root,
        env=ENV,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _project(tmp_path: Path, body: str) -> Path:
    root = tmp_path / "paper"
    root.mkdir(parents=True)
    (root / "page.txt").write_text(PAGE, encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'knuth2020 = "page.txt"' + NL, encoding="utf-8", newline=NL
    )
    (root / "paper.tex").write_text(
        BS
        + "documentclass{article}"
        + NL
        + BS
        + "begin{document}"
        + NL
        + body
        + NL
        + BS
        + "end{document}"
        + NL,
        encoding="utf-8",
        newline=NL,
    )
    return root


class TestTheArgumentStaysOutOfTheSentence:
    @pytest.mark.parametrize(
        "body",
        [
            BS + "captionof{table}{" + CITED + "}",
            BS + "captionof*{figure}{" + CITED + "}",
            BS + "rotatebox{90}{" + CITED + "}",
            BS + "rotatebox[origin=c]{90}{" + CITED + "}",
            BS + "hyperref[sec:data]{" + CITED + "}",
            BS + "rotatebox{90}{\\captionof{table}{" + CITED + "}}",
        ],
        ids=[
            "captionof",
            "captionof-star",
            "rotatebox",
            "rotatebox-with-origin",
            "hyperref",
            "nested",
        ],
    )
    def test_the_words_survive_and_the_names_do_not(self, body: str) -> None:
        assert latex.to_text(_doc(body)) == CONVERTED + NL

    @pytest.mark.parametrize(
        "command",
        ["nameref", "vref", "Vref"],
    )
    def test_a_key_is_dropped_like_ref_drops_it(self, command: str) -> None:
        out = latex.to_text(_doc("see " + BS + command + "{sec:data} for details."))
        assert out == "see for details." + NL

    def test_every_skipped_command_keeps_a_word(
        self,
    ) -> None:  # The count table is a claim about how many arguments come first; a
        # command that skips one too many loses the prose it was asked to keep.
        for name in sorted(latex._SKIP_FIRST_ARGUMENT):
            args = "{x}" * (latex._SKIP_ARGUMENT_COUNT.get(name, 1) + 1)
            out = latex.to_text(_doc(BS + name + args))
            assert "{" not in out and "}" not in out, (name, out)


class TestTheBracedFormOfHyperref:
    def test_the_braced_form_keeps_its_text(self) -> None:
        # `\hyperref{url}{text}` has no bracket, so the optional-argument
        # adjustment must not fire - skipping two arguments would eat the words.
        assert (
            latex.to_text(_doc(BS + "hyperref{http://x/" + BS + "#a}{" + CITED + "}"))
            == CONVERTED + NL
        )

    def test_the_bracketed_form_skips_one_argument(self) -> None:
        assert latex.to_text(_doc(BS + "hyperref[sec:data]{" + CITED + "}")) == CONVERTED + NL


class TestWhatWasAlreadyRight:
    @pytest.mark.parametrize(
        "body",
        [
            BS + "parbox{5cm}{" + CITED + "}",
            BS + "textcolor{red}{" + CITED + "}",
            BS + "href{http://x}{" + CITED + "}",
            BS + "textbf{" + CITED + "}",
        ],
        ids=["parbox", "textcolor", "href", "textbf"],
    )
    def test_a_known_wrapper_still_keeps_its_text(self, body: str) -> None:
        assert latex.to_text(_doc(body)) == CONVERTED + NL

    def test_plain_prose_is_untouched(self) -> None:
        assert latex.to_text(_doc(CITED)) == CONVERTED + NL


class TestWhatDraftProposes:
    @pytest.mark.parametrize(
        "body",
        [
            BS + "captionof{table}{" + CITED + "}",
            BS + "rotatebox{90}{" + CITED + "}",
            BS + "captionof*{figure}{" + CITED + "}",
        ],
        ids=["captionof", "rotatebox", "captionof-star"],
    )
    def test_a_verbatim_citation_is_proposed(self, tmp_path: Path, body: str) -> None:
        root = _project(tmp_path, body)
        proc = _run(root, "draft", "paper.tex", "--root", ".")
        claims = root / "claims.md"
        assert claims.is_file()
        text = claims.read_text(encoding="utf-8")
        assert "1 claim block(s) proposed: 1 quoting the sentence verbatim" in text
        assert "confidence: high" in text
        assert WORDS in text
        assert "tableWe" not in text
        assert "90We" not in text
        assert proc.returncode == 0

    def test_the_control_still_proposes(self, tmp_path: Path) -> None:
        root = _project(tmp_path, CITED)
        proc = _run(root, "draft", "paper.tex", "--root", ".")
        assert proc.returncode == 0
        text = (root / "claims.md").read_text(encoding="utf-8")
        assert "1 claim block(s) proposed: 1 quoting the sentence verbatim" in text
