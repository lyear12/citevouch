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

    def test_the_four_backtick_message_says_how_many_ticks_were_found(
        self, tmp_path: Path
    ):
        root = _project(tmp_path, FOUR_TICKS)
        _ledger, findings = scan(ScanOptions(manuscript="m.md", root=str(root)))
        assert "4 backticks" in findings[0].message

    def test_the_capitalised_message_says_the_case_is_the_problem(
        self, tmp_path: Path
    ):
        root = _project(tmp_path, CAPITAL)
        _ledger, findings = scan(ScanOptions(manuscript="m.md", root=str(root)))
        assert "case" in findings[0].message

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

    def test_the_summary_line_no_longer_claims_info_as_the_worst(
        self, tmp_path: Path, capsys
    ):
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


class TestTheLatexRefusalStillStands:
    def test_a_tex_file_is_refused_rather_than_read_as_empty(self, tmp_path: Path):
        (tmp_path / "paper.tex").write_text(
            "\\documentclass{article}\\begin{document}x\\end{document}\n", encoding="utf-8"
        )
        with pytest.raises(UsageError):
            scan(ScanOptions(manuscript="paper.tex", root=str(tmp_path)))
