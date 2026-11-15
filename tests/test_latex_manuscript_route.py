"""The `.tex` final-manuscript route, walked end to end.

`draft` accepts a `.tex` file; `scan`, `check` and `verify` refuse one. That
asymmetry is deliberate — claim blocks live in Markdown and a `.tex` file cannot
hold one the parser reads — but it means the final manuscript and the file the
gate is pointed at are two different files, and the tool never says so.

The walk below is `docs/latex-manuscript.md`, and the last measurement is the
reason the document exists: changing the number inside `paper.tex` leaves the
gate green, because nothing in the ledger names `paper.tex`.

Measured on citevouch 0.27.1:

* `draft paper.tex` proposes one verbatim block and exit 0;
* `scan paper.tex` exits 2 and names `draft` as the command that does work;
* `scan evidence.md` records `manuscript: evidence.md`;
* the recorded gate on `evidence.md` catches an edited quote (`ledger-stale`,
  high, 0 verified, 1 skipped) and a source swap (`source-changed` and
  `quote-fuzzy`, both medium, which is why `--fail-on medium` is load-bearing);
* and it does not catch the number that changed in `paper.tex`: exit 0,
  `quote-found`, verified 1.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
DOC = REPO / "docs" / "latex-manuscript.md"
README = REPO / "README.md"

ENV = {**os.environ, "PYTHONPATH": str(SRC), "PYTHONIOENCODING": "utf-8"}

BS = chr(92)
NL = chr(10)
FENCE = "`" * 3
PAGE = "We collected 40,688 examples from the corpus." + NL


def _cmd(name: str, *args: str) -> str:
    """Build a TeX control sequence without writing a backslash literal."""
    return BS + name + "".join(args)


TEX = (
    _cmd("documentclass", "{article}")
    + NL
    + _cmd("begin", "{document}")
    + NL
    + _cmd("section", "{Method}")
    + NL
    + "We collected 40,688 examples from the corpus "
    + _cmd("citep", "{paper}")
    + "."
    + NL
    + _cmd("end", "{document}")
    + NL
)

MIRROR = (
    "# Evidence for paper.tex"
    + NL
    + NL
    + FENCE
    + "claim id=corpus source=paper page=1"
    + NL
    + "quote: |"
    + NL
    + "  We collected 40,688 examples from the corpus."
    + NL
    + "claim: |"
    + NL
    + "  We collected 40,688 examples from the corpus."
    + NL
    + FENCE
    + NL
)


def _run(root: Path, *argv: str) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "citevouch", *argv],
        cwd=root,
        env=ENV,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return proc.returncode, proc.stdout, proc.stderr


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir(parents=True)
    (root / "page.txt").write_text(PAGE, encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
    )
    (root / "paper.tex").write_text(TEX, encoding="utf-8", newline=NL)
    (root / "evidence.md").write_text(MIRROR, encoding="utf-8", newline=NL)
    return root


def _codes(stdout: str) -> list[str]:
    return [f["code"] for f in json.loads(stdout)["findings"]]


def _summary(stdout: str) -> dict:
    return json.loads(stdout)["summary"]


def _recorded(root: Path, *extra: str) -> tuple[int, str]:
    rc, out, _ = _run(
        root,
        "check",
        "evidence.md",
        "--root",
        ".",
        "--use-recorded",
        "--fail-on",
        "medium",
        "--format",
        "json",
        *extra,
    )
    return rc, out


def _ledger(root: Path) -> dict:
    return json.loads((root / "citevouch.lock.json").read_text(encoding="utf-8"))


class TestTheTwoFilesAreNotTheSameFile:
    def test_draft_accepts_the_tex_file(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        rc, out, err = _run(root, "draft", "paper.tex", "--root", ".", "-o", "claims.md")
        assert rc == 0, (out, err)
        text = (root / "claims.md").read_text(encoding="utf-8")
        assert "claim id=paper" in text
        assert "We collected 40,688 examples from the corpus." in text

    def test_the_converter_reads_one_file_and_says_which_it_did_not(
        self, tmp_path: Path
    ) -> None:
        root = _project(tmp_path)
        (root / "sec").mkdir()
        (root / "sec" / "method.tex").write_text(
            _cmd("section", "{Data}") + NL + "We used " + _cmd("citep", "{paper}") + "." + NL,
            encoding="utf-8",
            newline=NL,
        )
        split = (
            _cmd("documentclass", "{article}")
            + NL
            + _cmd("begin", "{document}")
            + NL
            + _cmd("input", "{sec/method}")
            + NL
            + _cmd("end", "{document}")
            + NL
        )
        (root / "split.tex").write_text(split, encoding="utf-8", newline=NL)

        rc, out, err = _run(root, "draft", "split.tex", "--root", ".", "-o", "split.md")
        assert rc == 0, (out, err)
        # The only citation lived in the file that was never read.
        assert "0 claim block(s) proposed" in err
        text = (root / "split.md").read_text(encoding="utf-8")
        assert "sec/method" in text

    def test_scan_and_check_refuse_the_tex_file(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        for verb in ("scan", "check"):
            rc, out, err = _run(root, verb, "paper.tex", "--root", ".")
            assert rc == 2, (verb, rc, out, err)
            assert "is LaTeX" in err
            assert "`citevouch draft paper.tex -o claims.md`" in err
            # The sentence that makes it a refusal rather than a hint.
            assert "clean run for a manuscript nothing checked" in err
        assert not (root / "citevouch.lock.json").exists()

    def test_the_ledgers_subject_is_the_markdown_file(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        rc, out, err = _run(root, "scan", "evidence.md", "--root", ".")
        assert rc == 0, (out, err)
        assert _ledger(root)["manuscript"] == "evidence.md"


class TestTheGateCatchesWhatItsSubjectChanged:
    def test_an_untouched_project_is_green(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _run(root, "scan", "evidence.md", "--root", ".")
        rc, out = _recorded(root)
        assert rc == 0
        assert _codes(out) == ["quote-found"]
        assert _summary(out)["verified"] == 1

    def test_editing_the_quote_stops_the_run(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _run(root, "scan", "evidence.md", "--root", ".")
        edited = MIRROR.replace("from the corpus.", "from the entire internet.")
        (root / "evidence.md").write_text(edited, encoding="utf-8", newline=NL)
        rc, out = _recorded(root)
        assert rc == 1
        assert _codes(out) == ["ledger-stale"]
        summary = _summary(out)
        # The run stopped before it judged anything, and says so.
        assert summary["verified"] == 0
        assert summary["skipped"] == 1

    def test_a_source_swap_is_caught_at_medium(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _run(root, "scan", "evidence.md", "--root", ".")
        (root / "page.txt").write_text(
            "We collected 40,688 examples from the corpus, twice." + NL,
            encoding="utf-8",
            newline=NL,
        )
        rc, out = _recorded(root)
        assert rc == 1
        codes = _codes(out)
        assert "source-changed" in codes
        # Both drift codes are medium: a gate left on the CLI default of `high`
        # would exit 0 here while still printing the finding.
        assert _summary(out)["missing"] == 1


class TestTheGateCannotSeeTheManuscript:
    """The measurement this whole page exists to write down."""

    def test_a_number_changed_in_the_tex_leaves_the_gate_green(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _run(root, "scan", "evidence.md", "--root", ".")
        changed = TEX.replace("40,688 examples", "91,234 examples")
        (root / "paper.tex").write_text(changed, encoding="utf-8", newline=NL)

        rc, out = _recorded(root)
        assert rc == 0, "the gate is pointed at evidence.md, not at paper.tex"
        assert _codes(out) == ["quote-found"]
        assert _summary(out)["verified"] == 1

    def test_no_flag_offered_here_binds_it_to_the_tex(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _run(root, "scan", "evidence.md", "--root", ".")
        changed = TEX.replace("40,688 examples", "91,234 examples")
        (root / "paper.tex").write_text(changed, encoding="utf-8", newline=NL)
        # `--allow-stale` relaxes the ledger's binding to its own subject; it
        # does not add a second file.
        rc, out = _recorded(root, "--allow-stale")
        assert rc == 0
        assert _summary(out)["verified"] == 1

    def test_a_prose_change_in_the_tex_is_invisible_too(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _run(root, "scan", "evidence.md", "--root", ".")
        rewritten = TEX.replace("We collected", "We gathered")
        (root / "paper.tex").write_text(rewritten, encoding="utf-8", newline=NL)
        rc, out = _recorded(root)
        assert rc == 0
        assert _summary(out)["verified"] == 1


class TestThePageSaysAllOfThis:
    def test_the_page_exists_and_the_readme_points_at_it(self) -> None:
        assert DOC.is_file()
        flat = re.sub(r"\s+", " ", README.read_text(encoding="utf-8"))
        assert "docs/latex-manuscript.md" in flat

    def test_the_page_states_the_limitation_as_a_measurement(self) -> None:
        flat = re.sub(r"\s+", " ", DOC.read_text(encoding="utf-8"))
        # The four measured rows of the gate table.
        assert "the number in `paper.tex`" in flat
        assert "`quote-found`, verified 1" in flat
        assert "`ledger-stale` (high), 0 verified, 1 skipped" in flat
        assert "`source-changed` (medium) and `quote-fuzzy` (medium)" in flat
        # And the sentence the reader must not miss.
        assert "the ledger's subject is the Markdown file, not the `.tex` file" in flat

    def test_the_page_does_not_promise_that_the_gate_covers_the_tex(self) -> None:
        flat = re.sub(r"\s+", " ", DOC.read_text(encoding="utf-8"))
        for claim in (
            "protects `paper.tex`",
            "protects the .tex",
            "binds the .tex",
            "gates the .tex",
        ):
            assert claim not in flat, claim
        assert "It makes no claim that gating `evidence.md` covers `paper.tex`" in flat

    def test_the_page_names_the_converter_boundary(self) -> None:
        flat = re.sub(r"\s+", " ", DOC.read_text(encoding="utf-8"))
        assert "It reads **one file**" in flat
        assert "`\\input{sec/method}`" in flat or "\\input{sec/method}" in flat
        assert "0 claim block(s) proposed: no citations were found" in flat
        assert "a macro that expands to prose is invisible" in flat.lower()


class TestTheDocumentedCommandsRun:
    def test_every_command_the_page_prints_runs_as_shown(self, tmp_path: Path) -> None:
        """The page's four steps, in order, on the project it describes."""
        root = _project(tmp_path)
        (root / "refs.bib").write_text("", encoding="utf-8", newline=NL)

        rc, out, err = _run(
            root, "draft", "paper.tex", "--root", ".", "--bib", "refs.bib", "-o", "claims.md"
        )
        assert rc == 0, (out, err)

        rc, out, err = _run(root, "scan", "paper.tex", "--root", ".")
        assert rc == 2
        assert "is LaTeX" in err

        rc, out, err = _run(root, "scan", "evidence.md", "--root", ".")
        assert rc == 0
        assert "wrote citevouch.lock.json (1 claim)" in err

        rc, out, err = _run(
            root, "check", "evidence.md", "--root", ".", "--use-recorded", "--fail-on", "medium"
        )
        assert rc == 0, (out, err)
        assert "1 claim — 1 verified" in out or "1 claim — 1 verified" in err


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
