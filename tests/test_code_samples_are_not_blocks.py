"""A code sample in the prose is not a claim block.

`citevouch: N claims` is followed, when the file holds more claim blocks than
the ledger recorded, by `M claim blocks — K of which this run could not check`.
That second number is the parser's count of the blocks the author wrote.

`ParseResult.spans` is not that count. It records every region the parser
consumed, and a plain ````python` fence is one of them on purpose: prose inside
a sample must not be reported as an unread claim opener, and the only way to
know a `claim` line is sample text is to know which lines the sample covers.

The two were the same list, so a manuscript holding one claim and one code
sample was described as holding two blocks:

    citevouch: 1 claim — 1 verified, 0 moved, 0 missing
    2 claim blocks — 1 of which this run could not check

Nothing in that output names the second block, because there is no second
block. The reader is told their document is twice the size it is, by the one
line that is supposed to summarise it, and sent looking for a claim that
never existed. `doctor` said the same thing in its own words ("2 claim blocks,
1 of which the parser could read").

`ParseResult.claim_spans` is the narrower list: the spans `accept()` opened, in
all three dialects, whether or not the block was recorded. Both counts use it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from citevouch.cli import main
from citevouch.manuscript import parse_manuscript

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


def refused(cid: str) -> str:
    """A block the parser opens and cannot record: no `source=`."""
    return B3 + f"claim id={cid} page=1" + NL + "quote: |" + NL + "  " + PAGE + NL + B3 + NL


PYTHON_SAMPLE = B3 + "python" + NL + "x = 1" + NL + B3 + NL
TEXT_SAMPLE = B3 + NL + "just some words" + NL + B3 + NL
TILDE_SAMPLE = "~~~" + NL + "still a sample" + NL + "~~~" + NL


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
    lines = printed.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("citevouch: "):
            block = [line]
            for follow in lines[index + 1 :]:
                if follow.startswith("worst severity:"):
                    break
                if follow.strip():
                    block.append(follow)
            return "\n".join(block)
    raise AssertionError(f"no summary line in:\n{printed}")


class TestASampleIsNotABlock:
    def test_one_claim_and_one_sample_is_one_block(self, tmp_path: Path, capsys):
        root = _project(tmp_path / "p", good("c1") + NL + PYTHON_SAMPLE)
        code, printed = _run(root, capsys, "check")
        assert code == 0
        line = _summary(printed)
        assert "1 claim — 1 verified" in line
        assert "claim block" not in line, line

    def test_two_samples_do_not_make_three_blocks(self, tmp_path: Path, capsys):
        root = _project(tmp_path / "p", good("c1") + NL + PYTHON_SAMPLE + NL + TEXT_SAMPLE)
        code, printed = _run(root, capsys, "check")
        assert code == 0
        assert "claim block" not in _summary(printed)

    def test_a_tilde_sample_is_not_a_block_either(self, tmp_path: Path, capsys):
        root = _project(tmp_path / "p", good("c1") + NL + TILDE_SAMPLE)
        code, printed = _run(root, capsys, "check")
        assert code == 0
        assert "claim block" not in _summary(printed)

    def test_a_sample_and_a_refused_block_are_one_block(self, tmp_path: Path, capsys):
        """The refused block is counted, the sample beside it is not."""
        root = _project(tmp_path / "p", good("c1") + NL + refused("c2") + NL + PYTHON_SAMPLE)
        code, printed = _run(root, capsys, "check")
        assert code == 1
        line = _summary(printed)
        assert "2 claim blocks" in line
        assert "1 of which this run could not check" in line

    def test_a_sample_alone_is_still_no_claim_blocks(self, tmp_path: Path, capsys):
        """A file of code samples has no blocks, and says so once."""
        root = _project(tmp_path / "p", PYTHON_SAMPLE)
        code, printed = _run(root, capsys, "check")
        assert code == 1
        line = _summary(printed)
        assert "0 claims" in line
        assert "claim block" not in line.replace("no claim blocks", ""), line


class TestDoctorCountsTheSameThing:
    @pytest.mark.parametrize(
        "body, expected",
        [
            (good("c1"), "1 claim block"),
            (good("c1") + NL + PYTHON_SAMPLE, "1 claim block"),
            (good("c1") + NL + refused("c2"), "2 claim blocks"),
            (good("c1") + NL + refused("c2") + NL + PYTHON_SAMPLE, "2 claim blocks"),
        ],
    )
    def test_the_claims_line_agrees_with_the_summary(
        self, tmp_path: Path, capsys, body: str, expected: str
    ):
        root = _project(tmp_path / "p", body)
        main(["doctor", "--manuscript", "manuscript.md", "--root", str(root)])
        printed = capsys.readouterr().out
        claims = next(line for line in printed.splitlines() if "claim block" in line)
        assert expected in claims, claims


class TestTheParserKeepsBothLists:
    def test_a_sample_is_in_spans_but_not_in_claim_spans(self):
        parsed = parse_manuscript(good("c1") + NL + PYTHON_SAMPLE, "manuscript.md")
        assert len(parsed.spans) == 2
        assert len(parsed.claim_spans) == 1

    def test_a_refused_block_is_in_both(self):
        parsed = parse_manuscript(refused("c1"), "manuscript.md")
        assert parsed.claims == []
        assert len(parsed.spans) == 1
        assert len(parsed.claim_spans) == 1

    @pytest.mark.parametrize(
        "body",
        [
            "<!-- claim id=c1 source=paper page=1 quote: " + PAGE + " -->" + NL,
            "| c1 | paper | 1 | " + PAGE + " | |" + NL,
            B3 + "claim id=c1 source=paper page=1" + NL + "quote: |" + NL + "  " + PAGE + NL,
        ],
        ids=["comment", "table", "unclosed-fence"],
    )
    def test_every_dialect_lands_in_claim_spans(self, body: str):
        parsed = parse_manuscript(body, "manuscript.md")
        assert len(parsed.claim_spans) == 1

    def test_the_wider_list_still_covers_the_sample_for_prose_checks(self):
        """`spans` keeps its other job: no unread-opener finding inside a sample.

        A `claim` line written *inside* a ````python` sample is sample text.
        If `spans` were narrowed to claim blocks, that line would be reported as
        a claim the parser walked past.
        """
        body = B3 + "python" + NL + "```claim id=c1 source=paper page=1" + NL + B3 + NL
        parsed = parse_manuscript(body, "manuscript.md")
        assert not any(f.code == "claim-block-unread" for f in parsed.findings)
