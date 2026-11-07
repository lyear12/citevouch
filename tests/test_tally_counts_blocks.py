"""The summary line has to describe the document, not just the run.

`citevouch: N claims — V verified, M moved, X missing` is the last line of
every run. It counted `ledger.claims`, and the ledger records only the blocks
the parser *accepted*: a block with no `source=` is refused, so it reaches
neither `verified` nor `missing` nor `skipped`, and the headline claims the
file is smaller than it is.

Measured before the fix, on a manuscript holding one accepted claim and one
block with no `source=`:

    [high] claim-uncheckable at manuscript.md:6 (c2): claim c2 names no source= ...
    [info] quote-found at manuscript.md:1 (c1): quote found on page 1
    citevouch: 1 claim — 1 verified, 0 moved, 0 missing

Two blocks were in the file. The finding above the line says why the second was
not checked, so the run is not green - but the arithmetic sentence is still
false, and a reader who reads only it learns that the document has one claim.
"""

from __future__ import annotations

import sys
from pathlib import Path

from citevouch.cli import main

NL = chr(10)
B3 = chr(96) * 3
PAGE = "We collected 154,391 examples from the corpus."
MANIFEST = "[sources]" + NL + 'paper = "page.txt"' + NL


def good(cid: str) -> str:
    return (
        B3
        + f"claim id={cid} source=paper page=1"
        + NL
        + "quote: |"
        + NL
        + "  "
        + PAGE
        + NL
        + B3
        + NL
    )


def no_source(cid: str) -> str:
    """A block the parser finds, describes, and cannot record.

    Deliberately *not* a block with no `id=`: that one is refused earlier and
    is covered by `tests/test_recorded_parse.py`. This shape reaches
    `_claim_from` with an id and a quote, so the only thing wrong with it is
    what the claim is missing.
    """
    return B3 + f"claim id={cid} page=1" + NL + "quote: |" + NL + "  " + PAGE + NL + B3 + NL


def _project(root: Path, body: str) -> Path:
    root.mkdir(parents=True)
    (root / "page.txt").write_text(PAGE + NL, encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(MANIFEST, encoding="utf-8", newline=NL)
    (root / "manuscript.md").write_text(body, encoding="utf-8", newline=NL)
    return root


def _run(root: Path, capsys, *args: str) -> tuple[int, str]:
    code = main([*args, "manuscript.md", "--root", str(root)])
    out = capsys.readouterr()
    return int(code or 0), out.out + out.err


def _summary(printed: str) -> str:
    """The summary block: the `citevouch:` line and whatever it continues into.

    Reading only the line that starts with `citevouch: ` is what this file was
    written to stop doing — the numbers and the sentence about them are one
    statement, and a helper that returns half of it can only assert on half.
    """
    lines = printed.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("citevouch: "):
            block = [line]
            for follow in lines[index + 1 :]:
                if follow.startswith("worst severity:"):
                    break
                if not follow.strip():
                    continue
                block.append(follow)
            return "\n".join(block)
    raise AssertionError(f"no summary line in:\n{printed}")


class TestTheLineCountsTheBlocksInTheFile:
    def test_one_accepted_and_one_refused_is_two_blocks(self, tmp_path: Path, capsys):
        root = _project(tmp_path / "p", good("c1") + NL + no_source("c2"))
        code, printed = _run(root, capsys, "check")
        assert code == 1
        line = _summary(printed)
        assert "1 claim — 1 verified" in line
        assert "2 claim blocks" in line
        assert "1 of which this run could not check" in line

    def test_two_accepted_and_one_refused(self, tmp_path: Path, capsys):
        root = _project(tmp_path / "p", good("c1") + NL + good("c2") + NL + no_source("c3"))
        code, printed = _run(root, capsys, "check")
        assert code == 1
        line = _summary(printed)
        assert "2 claims — 2 verified" in line
        assert "3 claim blocks" in line

    def test_a_refused_block_on_its_own_says_zero_claims(self, tmp_path: Path, capsys):
        root = _project(tmp_path / "p", no_source("c1"))
        code, printed = _run(root, capsys, "check")
        assert code == 1
        line = _summary(printed)
        assert "0 claims" in line
        assert "1 claim block" in line

    def test_the_recorded_pass_says_it_too(self, tmp_path: Path, capsys):
        root = _project(tmp_path / "p", good("c1") + NL + no_source("c2"))
        _run(root, capsys, "scan")
        code, printed = _run(root, capsys, "check", "--use-recorded")
        assert code == 1
        assert "2 claim blocks" in _summary(printed)

    def test_verify_says_it_too(self, tmp_path: Path, capsys):
        root = _project(tmp_path / "p", good("c1") + NL + no_source("c2"))
        _run(root, capsys, "scan")
        code, printed = _run(root, capsys, "verify")
        assert code == 1
        assert "2 claim blocks" in _summary(printed)


class TestTheLineStaysQuietWhenThereIsNothingToSay:
    def test_a_clean_project_gets_no_extra_clause(self, tmp_path: Path, capsys):
        root = _project(tmp_path / "p", good("c1") + NL + good("c2"))
        code, printed = _run(root, capsys, "check")
        assert code == 0
        line = _summary(printed)
        assert "2 claims — 2 verified" in line
        assert "claim block" not in line

    def test_every_block_readable_means_no_arithmetic_to_correct(self, tmp_path, capsys):
        root = _project(tmp_path / "p", good("c1"))
        code, printed = _run(root, capsys, "check")
        assert code == 0
        assert "claim block" not in _summary(printed)

    def test_an_unclosed_fence_is_a_reading_problem_not_a_missing_block(
        self, tmp_path: Path, capsys
    ):
        """The block is recorded, so it is counted; the fence is the complaint.

        `claim-block-unclosed` reports that the parser could not tell where the
        block ended, and it still produces a claim. Saying "2 blocks, 1 not
        checked" here would be false in the other direction.
        """
        body = B3 + "claim id=c1 source=paper page=1" + NL + "quote: |" + NL + "  " + PAGE + NL
        root = _project(tmp_path / "p", body)
        code, printed = _run(root, capsys, "check")
        assert code == 1
        line = _summary(printed)
        assert "1 claim — 1 verified" in line
        assert "claim block" not in line


class TestTheDemoIsUnchanged:
    def test_a_run_with_every_block_readable_has_no_clause(self):
        from citevouch.report import render_text
        from citevouch.verify import VerifyResult

        result = VerifyResult(checked=5, verified=4, missing=1)
        text = render_text([], result)
        assert "5 claims — 4 verified, 0 moved, 1 missing" in text
        assert "claim block" not in text


def test_the_verb_and_the_clause_agree(tmp_path: Path):
    """A `scan` that recorded 1 claim still knows the file held 2 blocks.

    `scan` writes its own sentence to stderr (`citevouch: wrote ... (1 claim)`).
    That number is a fact about the ledger and is left alone; what this test
    holds is that the parser still reports the second block, so no verb has to
    guess.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from citevouch.manuscript import parse_manuscript
    from citevouch.textnorm import read_text

    root = _project(tmp_path / "p", good("c1") + NL + no_source("c2"))
    parsed = parse_manuscript(read_text(root / "manuscript.md"), "manuscript.md")
    assert len(parsed.spans) == 2
    assert len(parsed.claims) == 1


class TestTheOtherTwoFormatsSayItAsWell:
    """`--format json` and `--format markdown` are the ones machines read.

    A clause only `--format text` carries leaves a CI dashboard, a SARIF
    upload and a pasted report all describing the smaller document. The three
    writers are separate code, so each one has to be asked.
    """

    def test_the_json_summary_counts_the_blocks(self, tmp_path: Path, capsys):
        import json

        root = _project(tmp_path / "p", good("c1") + NL + no_source("c2"))
        code, printed = _run(root, capsys, "check", "--format", "json")
        assert code == 1
        summary = json.loads(printed)["summary"]
        assert summary["checked"] == 1
        assert summary["unrecorded"] == 1
        assert summary["blocks"] == 2

    def test_the_json_summary_is_quiet_when_there_is_nothing_to_say(self, tmp_path, capsys):
        import json

        root = _project(tmp_path / "p", good("c1"))
        code, printed = _run(root, capsys, "check", "--format", "json")
        assert code == 0
        summary = json.loads(printed)["summary"]
        assert summary["unrecorded"] == 0
        assert summary["blocks"] == summary["checked"]

    def test_the_markdown_report_counts_the_blocks(self, tmp_path: Path, capsys):
        root = _project(tmp_path / "p", good("c1") + NL + no_source("c2"))
        code, printed = _run(root, capsys, "check", "--format", "markdown")
        assert code == 1
        assert "**2** claim blocks · **1** of which this run could not check" in printed

    def test_the_markdown_report_is_quiet_on_a_clean_run(self, tmp_path: Path, capsys):
        root = _project(tmp_path / "p", good("c1"))
        code, printed = _run(root, capsys, "check", "--format", "markdown")
        assert code == 0
        assert "could not check" not in printed
