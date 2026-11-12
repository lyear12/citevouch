"""An attribute written on the opening line and again in the body.

Measured before any of this existed, on a project whose quote is printed in
``alt.txt`` and nowhere in ``paper.txt``:

    ```claim id=c1 source=paper page=1
    quote: |
      We collected 154,391 examples from the corpus.
    source: alt
    ```

    -> [high] quote-missing at m.md:1 (c1): We collected 154,391 examples from
       the corpus. - quote not found in paper.txt

The author wrote the right source three lines below the fence, and the run
accused them of quoting a passage that file does not contain.  Writing the two
in the other order is worse in a quieter way: ``source=alt`` on the fence with
``source: paper`` in the body verifies and says nothing at all, so the body
line is gone without a word.

The rule that the opening line wins is deliberate and stays - the fence is
where the format is documented, and both layers hold the author's own text.
What was missing is the sentence saying the other value was dropped.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from citevouch.cli import main
from citevouch.manuscript import parse_manuscript

NL = chr(10)
B3 = chr(96) * 3
QUOTE = "We collected 154,391 examples from the corpus."
OTHER = "This page is about something else entirely."

CODE = "claim-field-shadowed"


def _block(opener: str, *extra: str) -> str:
    return NL.join([B3 + "claim " + opener, "quote: |", "  " + QUOTE, *extra, B3, ""])


def _findings(text: str):
    return parse_manuscript(text, "m.md").findings


def _codes(text: str) -> list[str]:
    return [finding.code for finding in _findings(text)]


def _shadowed(text: str):
    return [finding for finding in _findings(text) if finding.code == CODE]


def _project(root: Path, text: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "paper.txt").write_text(OTHER + NL, encoding="utf-8", newline=NL)
    (root / "alt.txt").write_text(QUOTE + NL, encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "paper.txt"' + NL + 'alt = "alt.txt"' + NL,
        encoding="utf-8",
        newline=NL,
    )
    (root / "m.md").write_text(text, encoding="utf-8", newline=NL)
    return root


def _run(capsys: pytest.CaptureFixture[str], root: Path, *argv: str) -> tuple[int, str]:
    capsys.readouterr()
    try:
        code = main([*argv, "--root", str(root)])
    except SystemExit as exc:  # pragma: no cover - argparse
        code = int(exc.code or 0)
    captured = capsys.readouterr()
    return code, captured.out + captured.err


class TestTheDroppedValueIsNamed:
    @pytest.mark.parametrize(
        "name,opener_value,body_value",
        [
            ("source", "paper", "alt"),
            ("page", "1", "2"),
            ("id", "c1", "c9"),
            ("marker", "A", "B"),
            ("ref", "knuth", "smith"),
        ],
    )
    def test_it_reports_the_attribute(
        self, name: str, opener_value: str, body_value: str
    ) -> None:
        text = _block(
            f"id=c1 source=paper page=1 {name}={opener_value}", f"{name}: {body_value}"
        )
        found = _shadowed(text)
        assert found, f"{name}: written in both layers with two values, and silent"
        assert name in found[0].message

    def test_it_names_both_values_and_says_which_won(self) -> None:
        finding = _shadowed(_block("id=c1 source=paper page=1", "source: alt"))[0]
        assert "'paper'" in finding.message
        assert "'alt'" in finding.message
        # Which one is called the opening line is the whole finding: swapped,
        # the sentence names the loser as the winner and reads as a lie.
        assert "'paper' on the opening line" in finding.message
        assert "'alt' in the body" in finding.message

    def test_it_points_at_the_line_of_the_loser(self) -> None:
        text = "Intro." + NL + NL + _block("id=c1 source=paper page=1", "source: alt")
        finding = _shadowed(text)[0]
        assert finding.line == 6
        assert finding.path == "m.md"
        assert text.splitlines()[finding.line - 1].strip() == "source: alt"

    def test_two_attributes_named_in_both_layers_are_two_findings(self) -> None:
        text = _block("id=c1 source=paper page=1", "source: alt", "page: 2")
        found = _shadowed(text)
        assert len(found) == 2
        assert any("source" in f.message for f in found)
        assert any("page" in f.message for f in found)


class TestWhatMustStaySilent:
    def test_the_same_value_twice_says_nothing(self) -> None:
        assert CODE not in _codes(_block("id=c1 source=paper page=1", "source: paper"))

    def test_a_body_attribute_the_opener_does_not_name_is_fine(self) -> None:
        assert CODE not in _codes(_block("id=c1 source=paper", "page: 2"))

    def test_the_opening_line_alone_is_fine(self) -> None:
        assert CODE not in _codes(_block("id=c1 source=paper page=1"))

    def test_the_alias_pair_keeps_its_own_finding(self) -> None:
        codes = _codes(_block("id=c1 source=paper ref=phantom", "cite: knuth2020"))
        assert codes.count("claim-field-conflict") == 1
        assert CODE not in codes


class TestTheRuleItKeeps:
    def test_the_opening_line_still_wins(self) -> None:
        claim = parse_manuscript(
            _block("id=c1 source=paper page=1", "source: alt"), "m.md"
        ).claims[0]
        assert claim.source == "paper"

    def test_a_body_value_the_opener_lacks_is_still_applied(self) -> None:
        claim = parse_manuscript(_block("id=c1 source=paper", "page: 2"), "m.md").claims[0]
        assert claim.page == 2


class TestTheVerdictOnAProject:
    def test_the_accusation_now_comes_with_its_reason(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # The opening line wins, so the claim really is about `paper.txt`, and
        # the quote really is absent from it: `quote-missing` is the honest
        # verdict and this fix does not change it.  What it adds is the line
        # that says the author also wrote `source: alt` and that value was
        # dropped - which is the difference between "you quoted nothing" and
        # "you put the right source in the wrong place".
        root = _project(tmp_path / "proj", _block("id=c1 source=paper page=1", "source: alt"))
        code, out = _run(capsys, root, "check", "m.md")
        assert "quote-missing" in out
        assert CODE in out
        assert code == 1

    def test_it_breaks_the_silence_when_the_body_points_away(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root = _project(tmp_path / "proj", _block("id=c1 source=alt page=1", "source: paper"))
        code, out = _run(capsys, root, "check", "m.md")
        assert "quote-found" in out
        assert CODE in out
        assert code == 0

    def test_the_ledger_records_the_value_that_won(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root = _project(tmp_path / "proj", _block("id=c1 source=paper page=1", "source: alt"))
        code, _ = _run(capsys, root, "scan", "m.md")
        assert code == 0
        blob = json.loads((root / "citevouch.lock.json").read_text(encoding="utf-8"))
        assert blob["claims"][0]["source"] == "paper"
