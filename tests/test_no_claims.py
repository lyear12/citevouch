"""A run that checked nothing must not look like a run that found nothing wrong.

Every other finding in this tool describes a claim that was looked at and
failed.  This one describes the case where no claim was ever looked at, and the
summary line for it is `0 claims — 0 verified, 0 moved, 0 missing` followed by
`worst severity: info`.  A reader - and a CI job - sees a green run of a check
that never happened.

The `.tex` refusal in :func:`citevouch.scan.scan` closed that hole for one file
extension.  These tests cover the same hole reached through Markdown: a file
with no claim blocks, a file whose blocks are written in a dialect the parser
does not accept, and the zero-claim state arriving through ``verify`` on a
ledger that recorded none either.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from citevouch.cli import main
from citevouch.errors import UsageError
from citevouch.scan import ScanOptions, scan


def _project(tmp_path: Path, manuscript: str) -> Path:
    (tmp_path / "a.txt").write_text("The corpus has 100 utterances.\n", encoding="utf-8")
    (tmp_path / "sources.toml").write_text('[sources]\na = "a.txt"\n', encoding="utf-8")
    (tmp_path / "m.md").write_text(manuscript, encoding="utf-8")
    return tmp_path


PROSE = "# Paper\n\nThis paper argues that constructions matter.\n"
REAL = "# P\n\n```claim id=c1 source=a\nquote: |\n  The corpus has 100 utterances.\n```\n"
FOUR_TICKS = "# P\n\n````claim id=c1 source=a\nThe corpus has 100 utterances.\n````\n"
CAPITAL = "# P\n\n```Claim id=c1 source=a\nThe corpus has 100 utterances.\n```\n"
HTML = "# P\n\n<!-- claim: c1 source=a\n>> The corpus has 100 utterances.\n-->\n"
TABLE = "# P\n\n| c1 | a | 1 | The corpus has 100 utterances. | The corpus is small. |\n"
# A README that documents the syntax: one example, indented so Markdown
# renders it as a code sample, and no real claim anywhere.
INDENTED = """A README line, then the syntax shown indented:


    ```claim id=example source=a
    quote: The corpus has 100 utterances.
    ```

Then the rest of the paper."""


class TestWhatGetsReported:
    def test_a_manuscript_with_no_blocks_is_not_clean(self, tmp_path: Path):
        root = _project(tmp_path, PROSE)
        ledger, findings = scan(ScanOptions(manuscript="m.md", root=str(root)))
        assert ledger.claims == []
        assert [f.code for f in findings] == ["no-claim-blocks"]
        assert findings[0].severity == "high"
        # No line number when there is no claim-shaped line to point at; 0 is
        # this code base's "no line", not a real line.
        assert findings[0].line == 0

    @pytest.mark.parametrize("manuscript", [FOUR_TICKS, CAPITAL])
    def test_a_block_written_in_a_near_miss_dialect_names_the_line(
        self, tmp_path: Path, manuscript: str
    ):
        """The author thought they wrote a claim block; say which line lied.

        A bare "no claim blocks" over a file that visibly contains the words
        ```claim reads as a broken tool. Naming the line and the difference is
        the whole value of the message.
        """
        root = _project(tmp_path, manuscript)
        ledger, findings = scan(ScanOptions(manuscript="m.md", root=str(root)))
        assert ledger.claims == []
        assert [f.code for f in findings] == ["no-claim-blocks"]
        assert findings[0].line == 3
        assert "line 3" in findings[0].message

    def test_the_four_backtick_message_says_how_many_ticks_were_found(self, tmp_path: Path):
        root = _project(tmp_path, FOUR_TICKS)
        _ledger, findings = scan(ScanOptions(manuscript="m.md", root=str(root)))
        assert "4 backticks" in findings[0].message

    def test_the_capitalised_message_says_the_case_is_the_problem(self, tmp_path: Path):
        root = _project(tmp_path, CAPITAL)
        _ledger, findings = scan(ScanOptions(manuscript="m.md", root=str(root)))
        assert "case" in findings[0].message

    def test_an_indented_fence_is_named_as_an_indent(self, tmp_path: Path):
        """The message must not quote a line that satisfies its own rule.

        An indented fence is a Markdown code sample, so it is a near miss
        and not a claim block. Before this it fell through to the generic
        sentence about what a claim fence looks like, and then printed
        exactly such a line, so the message contradicted itself where the
        reader is already confused.
        """
        root = _project(tmp_path, INDENTED)
        _ledger, findings = scan(ScanOptions(manuscript="m.md", root=str(root)))
        message = findings[0].message
        assert "indented by 4" in message, message
        assert "code sample" in message, message
        assert "claim fences are three backticks followed by the word" not in message

    def test_a_left_margin_fence_keeps_the_generic_sentence(self, tmp_path: Path):
        # The control: with no indent there is nothing special to report, so
        # the generic sentence has to stay available for the case it was
        # written for instead of being replaced wholesale.
        root = _project(tmp_path, PROSE)
        _ledger, findings = scan(ScanOptions(manuscript="m.md", root=str(root)))
        assert "indented by" not in findings[0].message

    def test_a_manuscript_with_a_prose_hint_suggests_draft(self, tmp_path: Path):
        root = _project(tmp_path, PROSE)
        _ledger, findings = scan(ScanOptions(manuscript="m.md", root=str(root)))
        assert "citevouch draft m.md" in findings[0].message


class TestWhatMustStaySilent:
    @pytest.mark.parametrize("manuscript", [REAL, HTML, TABLE])
    def test_every_accepted_dialect_is_clean(self, tmp_path: Path, manuscript: str):
        root = _project(tmp_path, manuscript)
        ledger, findings = scan(ScanOptions(manuscript="m.md", root=str(root)))
        assert [c.id for c in ledger.claims] == ["c1"]
        assert "no-claim-blocks" not in {f.code for f in findings}

    def test_a_broken_block_says_what_is_broken_and_not_also_that_there_are_none(
        self, tmp_path: Path
    ):
        """One fact, one vocabulary.

        ``claim-uncheckable`` already names the line and the reason. Adding
        "and there are no claim blocks either" would be the same truth in a
        second vocabulary, and the reader has to work out which to act on.
        """
        root = _project(
            tmp_path,
            "```claim id=c1\nquote: |\n  Something asserted without a source.\n```\n",
        )
        _ledger, findings = scan(ScanOptions(manuscript="m.md", root=str(root)))
        codes = [f.code for f in findings]
        assert "claim-uncheckable" in codes
        assert "no-claim-blocks" not in codes

    def test_an_unclosed_fence_says_data_loss_and_not_emptiness(self, tmp_path: Path):
        root = _project(
            tmp_path,
            "```claim id=c1 source=a\nquote: |\n  The corpus has 100 utterances.\n",
        )
        _ledger, findings = scan(ScanOptions(manuscript="m.md", root=str(root)))
        codes = [f.code for f in findings]
        assert "claim-block-unclosed" in codes
        assert "no-claim-blocks" not in codes


class TestTheCommandLine:
    def test_check_exits_one_and_says_nothing_was_checked(self, tmp_path: Path, capsys):
        root = _project(tmp_path, PROSE)
        assert main(["check", "m.md", "--root", str(root)]) == 1
        out = capsys.readouterr().out
        assert "[high] no-claim-blocks" in out
        assert "nothing was checked" in out

    def test_scan_exits_one_too(self, tmp_path: Path):
        """`scan` is the verb CI is told to run when it wants the ledger written.

        If it returns 0 over a manuscript with no blocks, the release job that
        only runs `scan` reports success over a document nothing read.
        """
        root = _project(tmp_path, PROSE)
        assert main(["scan", "m.md", "--root", str(root)]) == 1

    def test_a_clean_manuscript_still_exits_zero(self, tmp_path: Path):
        root = _project(tmp_path, REAL)
        assert main(["check", "m.md", "--root", str(root)]) == 0

    def test_the_summary_line_no_longer_claims_info_as_the_worst(self, tmp_path: Path, capsys):
        """The old output was the actual bug, so pin the shape of the new one.

        The verdict was literally `worst severity: info` next to a green exit
        code, which is the sentence a reader quotes when they say the gate
        passed.
        """
        root = _project(tmp_path, PROSE)
        main(["check", "m.md", "--root", str(root)])
        out = capsys.readouterr().out
        assert "worst severity: high" in out
        assert "worst severity: info" not in out


class TestTheRecordedLedger:
    def test_verify_over_an_empty_ledger_does_not_call_it_clean(self, tmp_path: Path):
        """The zero-claim state also exists on disk, in a ledger written before
        this guard existed. `verify` reads that file, so it has to reach the
        same verdict as `scan` rather than trusting the recording.
        """
        root = _project(tmp_path, PROSE)
        (root / "citevouch.lock.json").write_text(
            json.dumps(
                {
                    "schema": 1,
                    "tool_version": "0.17.1",
                    "generated_at": "2026-10-30T00:00:00+00:00",
                    "manuscript": "m.md",
                    "manuscript_sha256": "",
                    "claims": [],
                    "sources": {},
                    "entries": {},
                }
            ),
            encoding="utf-8",
        )
        assert main(["verify", "m.md", "--root", str(root), "--allow-stale"]) == 1

    def test_a_ledger_that_recorded_none_does_not_blame_the_manuscript(
        self, tmp_path: Path, capsys
    ):
        """An empty ledger and a manuscript with no blocks are not the same fault.

        The message for the second one names the closest thing to a claim block
        and explains why the parser rejected it.  Reusing that message for the
        first says a line "reads like a claim block but is not one the parser
        accepts" about a line the parser *does* accept - the file is fine and
        the recording is stale.  Whoever reads it edits a block that needed no
        edit and still fails the build.
        """
        root = _project(tmp_path, PROSE)
        nl = chr(10)
        # A real, accepted block, which the ledger below will fail to mention.
        (root / "m.md").write_text(
            "```claim id=c1 source=s" + nl + ">> one two three" + nl + "```" + nl,
            encoding="utf-8",
            newline=nl,
        )
        (root / "citevouch.lock.json").write_text(
            json.dumps(
                {
                    "schema": 1,
                    "tool_version": "0.17.1",
                    "generated_at": "2026-10-30T00:00:00+00:00",
                    "manuscript": "m.md",
                    "manuscript_sha256": "",
                    "claims": [],
                    "sources": {},
                    "entries": {},
                }
            ),
            encoding="utf-8",
        )
        assert main(["verify", "m.md", "--root", str(root), "--allow-stale"]) == 1
        report = capsys.readouterr().out
        assert "no-claim-blocks" in report
        assert "not one the parser accepts" not in report
        assert "the ledger recorded none" in report
        assert "citevouch scan" in report

    def test_a_ledger_that_recorded_none_does_not_call_a_real_block_imaginary(
        self, tmp_path: Path, capsys
    ):
        """A block the parser found and refused is not a file with no blocks.

        The branch above asked the parser only whether it produced *claims*, so
        a block missing its `id=` produced none and was then described as "no
        claim blocks" - while the parser's own finding, one line up, named the
        block.  Two statements about one file, and the second one false.

        `scan` has never had this bug: it checks `parsed.findings` before
        deciding the file is empty.  The asymmetry is the whole point of the
        test - the verdict has to be the same whichever command produced the
        ledger.
        """
        root = _project(tmp_path, PROSE)
        nl = chr(10)
        (root / "m.md").write_text(
            "```claim source=s" + nl + ">> one two three" + nl + "```" + nl,
            encoding="utf-8",
            newline=nl,
        )
        (root / "citevouch.lock.json").write_text(
            json.dumps(
                {
                    "schema": 1,
                    "tool_version": "0.19.5",
                    "generated_at": "2026-10-31T00:00:00+00:00",
                    "manuscript": "m.md",
                    "manuscript_sha256": "",
                    "claims": [],
                    "sources": {},
                    "entries": {},
                }
            ),
            encoding="utf-8",
        )
        assert main(["verify", "m.md", "--root", str(root), "--allow-stale"]) == 1
        report = capsys.readouterr().out
        assert "claim-uncheckable" in report
        assert "no id=" in report
        # The false half: this file has a block, so it does not have none.
        assert "no-claim-blocks" not in report

    def test_scan_and_verify_agree_about_the_same_manuscript(self, tmp_path: Path):
        """The two commands share one verdict, measured rather than assumed.

        `check` runs `scan` and then `verify` over the result, so a divergence
        between the two guards is invisible there: whichever finding survives
        looks like the intended one.  Run each pass over the same file and
        compare the codes.
        """
        root = _project(tmp_path, PROSE)
        nl = chr(10)
        (root / "m.md").write_text(
            "```claim source=s" + nl + ">> one two three" + nl + "```" + nl,
            encoding="utf-8",
            newline=nl,
        )
        ledger, scan_findings = scan(ScanOptions(manuscript="m.md", root=str(root)))
        from citevouch.verify import verify as _verify

        verify_result = _verify(ledger, ScanOptions(manuscript="m.md", root=str(root)))
        from_scan = {f.code for f in scan_findings}
        from_verify = {f.code for f in verify_result.findings}
        assert from_scan == {"claim-uncheckable"}
        assert from_verify == from_scan


class TestTheLatexRefusalStillStands:
    def test_a_tex_file_is_refused_rather_than_read_as_empty(self, tmp_path: Path):
        (tmp_path / "paper.tex").write_text(
            "\\documentclass{article}\\begin{document}x\\end{document}\n", encoding="utf-8"
        )
        with pytest.raises(UsageError):
            scan(ScanOptions(manuscript="paper.tex", root=str(tmp_path)))


def _project_with_paper(tmp_path: Path) -> Path:
    (tmp_path / "sources.toml").write_text('[sources]\na = "a.txt"\n', encoding="utf-8")
    (tmp_path / "a.txt").write_text("x\n", encoding="utf-8")
    (tmp_path / "paper").mkdir()
    (tmp_path / "paper" / "m.md").write_text(PROSE, encoding="utf-8")
    return tmp_path


def _advice(root: Path, typed: str, run: bool = False, root_arg: str = ".") -> str:
    """The draft command printed for ``typed``, read the way a reader typed it.

    ``root`` is the directory the reader is standing in, and ``root_arg`` is
    the ``--root`` they passed - a *relative* string, because that is what a
    command line carries.  Handing ``scan`` an absolute root instead would make
    every assertion below pass against advice naming
    ``C:\\Windows\\Temp\\pytest-of-...``, which no reader ever types.
    """
    import contextlib
    import io
    import os
    import re

    previous = Path.cwd()
    try:
        os.chdir(root)
        with (
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            findings = scan(ScanOptions(manuscript=typed, root=root_arg))[1]
    finally:
        os.chdir(previous)
    message = next(f.message for f in findings if f.code == "no-claim-blocks")
    found = re.search(r"`(citevouch draft [^`]+)`", message)
    assert found is not None, message
    command = found.group(1)
    if run:
        # A path only means what it meant alongside the `--root` it was read
        # against: `check m.md --root paper` printed `citevouch draft m.md`,
        # which resolved against the working directory and answered "manuscript
        # m.md does not exist".  No assertion on the string catches that,
        # because the string was right about the manuscript and wrong about the
        # pair.
        _run(root, command)
    return command


def _run(root: Path, command: str) -> None:
    """Run a printed command exactly as written, from ``root``."""
    import contextlib
    import io
    import os
    import shlex

    argv = shlex.split(command)
    assert argv[0] == "citevouch", command
    out = io.StringIO()
    previous = Path.cwd()
    try:
        os.chdir(root)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = main(argv[1:])
    finally:
        os.chdir(previous)
    assert code == 0, f"{command} answered exit {code}: {out.getvalue()}"


class TestTheAdviceCanBeFollowed:
    """A command the tool prints has to be a command the tool accepts.

    Both halves of this were broken at once, and neither showed up in a test:
    the message named the manuscript by *basename* - which is right for the
    finding's ``path`` and wrong for something a reader pastes into a shell -
    so checking ``paper/m.md`` from the project root printed
    ``citevouch draft m.md``, which answers ``manuscript m.md does not exist``
    and exit 2.  And the output name was always ``claims.md``, so a
    ``claims.md`` that still has no blocks was told to run ``draft claims.md
    -o claims.md``, which ``draft`` refuses by design because the output would
    land on the input.
    """

    def test_the_advice_names_the_directory_the_reader_typed(self, tmp_path: Path):
        action = _advice(_project_with_paper(tmp_path), "paper/m.md")
        assert action.startswith("citevouch draft paper/m.md "), action

    def test_the_advice_does_not_write_over_the_manuscript_it_reads(self, tmp_path: Path):
        (tmp_path / "sources.toml").write_text('[sources]\na = "a.txt"\n', encoding="utf-8")
        (tmp_path / "a.txt").write_text("x\n", encoding="utf-8")
        (tmp_path / "claims.md").write_text(PROSE, encoding="utf-8")
        action = _advice(tmp_path, "claims.md")
        assert "-o claims.md" not in action, action
        assert action.endswith("-o proposals.md"), action

    def test_the_plain_case_still_suggests_the_documented_default(self, tmp_path: Path):
        root = _project(tmp_path, PROSE)
        assert _advice(root, "m.md") == "citevouch draft m.md -o claims.md"

    def test_the_advice_is_runnable_even_at_the_plain_default(self, tmp_path: Path):
        # The plain sentence must stay byte-identical *and* still run, so this
        # one executes it rather than pattern-matching it.
        root = _project(tmp_path, PROSE)
        _advice(root, "m.md", run=True)
        assert (root / "claims.md").exists()

    def test_the_advice_carries_the_root_it_was_read_against(self, tmp_path: Path):
        # `check m.md --root paper` reads `paper/m.md`.  The command it printed
        # resolved `m.md` against the working directory instead, answered
        # "manuscript m.md does not exist", and exit 2 - a reader standing one
        # directory up with a correct file in front of them.
        root = _project_with_paper(tmp_path)
        command = _advice(root, "m.md", run=True, root_arg="paper")
        assert command == "citevouch draft m.md --root paper -o claims.md", command
        assert (root / "paper" / "claims.md").exists()

    def test_the_finding_still_names_the_basename(self, tmp_path: Path):
        # The advice may carry a directory; the finding's own path must not, or
        # the same project reported from two machines stops reading alike.
        root = _project_with_paper(tmp_path)
        findings = scan(ScanOptions(manuscript="paper/m.md", root=str(root)))[1]
        finding = next(f for f in findings if f.code == "no-claim-blocks")
        assert finding.path == "m.md"
