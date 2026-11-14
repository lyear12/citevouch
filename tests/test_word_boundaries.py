"""CV-001: the whitespace-free tier may not certify a quote.

The ``squashed`` tier removes every space before comparing.  That rescue is
real - PDF extractors do run words together and do split columns - but it
deletes the only evidence that separates one word from two.  A page printing
``nowhere`` and a quote writing ``now here`` flatten to the same string, so the
tier cannot tell a lost space from a moved one.

Until this existed the tier counted as a match: measured on v0.23.0, the page
``The suspect is nowhere in this room.`` plus the quote ``The suspect is now
here in this room.`` gave ``exit 0``, ``1 verified`` and only ``quote-found``.
That is the tool certifying a claim about words the source does not print,
which is the one thing it exists to refuse.

Two answers are dishonest here and the tests below pin the third one:

* ``quote-missing`` accuses the author of inventing a quotation the page very
  nearly holds;
* ``quote-found`` certifies words nobody printed.

So the run counts the claim as *skipped* and raises
``quote-word-boundaries-unclear`` at ``high``: the author is asked to read the
page.  No new exit-code special case is added - ``--fail-on high`` already
turns this into exit 1, which is the reason the code is ``high`` and not a
branch in the exit path.

The positives matter just as much.  Every comparison the tool is *allowed* to
trust is enumerated below and must keep working: exact, ordinary whitespace
normalisation, a hyphen at a line end, CJK, legal number spellings, and a quote
that runs across a page break.  A fix that refuses everything would pass the
negative tests and destroy the tool.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from citevouch import draft, matching
from citevouch.cli import main
from citevouch.sources import PageText

B3 = "```"
NL = "\n"
SRC = Path(__file__).resolve().parents[1] / "src"
LEDGER = "citevouch.lock.json"


def _pages(*texts: str) -> list[PageText]:
    return [PageText(number=index, text=text) for index, text in enumerate(texts, start=1)]


def _claim_block(quote: str, *, page: str = "1", cid: str = "c1") -> str:
    return (
        f"{B3}claim id={cid} source=paper page={page}{NL}"
        f"quote: |{NL}  {quote}{NL}"
        "claim: |\n  a sentence\n"
        f"{B3}{NL}"
    )


def _project(tmp_path: Path, page: str, quote: str) -> Path:
    (tmp_path / "page.txt").write_text(page + NL, encoding="utf-8", newline=NL)
    (tmp_path / "sources.toml").write_text(
        '[sources]\npaper = "page.txt"\n', encoding="utf-8", newline=NL
    )
    (tmp_path / "m.md").write_text(_claim_block(quote), encoding="utf-8", newline=NL)
    return tmp_path


def _run(root: Path, monkeypatch: pytest.MonkeyPatch, capsys, *argv: str):
    monkeypatch.chdir(root)
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out + captured.err


def _json(root: Path, monkeypatch: pytest.MonkeyPatch, capsys, *argv: str):
    monkeypatch.chdir(root)
    code = main([*argv, "--format", "json"])
    captured = capsys.readouterr()
    return code, json.loads(captured.out), captured.out + captured.err


class TestTheTierIsNotFound:
    """``Match.found`` is the single place a tier claims to have proved text."""

    def test_a_whitespace_free_match_is_not_a_match(self):
        match = matching.find_in_pages(
            "The suspect is now here in this room.",
            _pages("The suspect is nowhere in this room."),
            None,
        )
        # The tier is still reachable and still reports where it looked - that
        # is what makes the finding useful - but it is not a certification.
        assert match.tier == "squashed"
        assert match.page == 1
        assert match.found is False

    @pytest.mark.parametrize(
        "printed, quoted",
        [
            ("The suspect is nowhere in this room.", "The suspect is now here in this room."),
            (
                "The evidence is nowhere in the repository.",
                "The evidence is now here in the repository.",
            ),
            ("Wetrainontwocorpora.", "We train on two corpora."),
        ],
    )
    def test_the_word_boundary_is_the_whole_question(self, printed, quoted):
        match = matching.find_in_pages(quoted, _pages(printed), None)
        assert match.tier == "squashed"
        assert not match.found

    def test_a_word_for_word_match_is_still_found(self):
        match = matching.find_in_pages(
            "The suspect is now here in this room.",
            _pages("The suspect is now here in this room."),
            None,
        )
        assert match.tier == "exact"
        assert match.found


class TestWhatMustStillWork:
    """The comparisons this tool is allowed to trust.  A fix that refuses all
    of these would pass the negatives above and destroy the product."""

    @pytest.mark.parametrize(
        "printed, quoted, tier",
        [
            # exact
            ("We train on two corpora.", "We train on two corpora.", "exact"),
            # ordinary whitespace normalisation: the answer does not depend on
            # where a line wrapped in the .txt the author exported.
            ("We train on\ntwo corpora.", "We train on two corpora.", "exact"),
            ("We  train   on two corpora.", "We train on two corpora.", "exact"),
            # a hyphen at a line end: the page printed it, so the quote may
            # keep it and be compared like with like
            ("the con-\nstruction inventory", "the con-struction inventory", "hyphen"),
            # CJK: no spaces to lose, so the tier never applies
            (
                "我们收集了四万零六百八十八个例子。",
                "我们收集了四万零六百八十八个例子。",
                "exact",
            ),
            # legal spellings of one number
            ("We collected 40,688 examples.", "We collected 40688 examples.", "canonical"),
            ("We collected 40,688 examples.", "We collected 40 688 examples.", "canonical"),
        ],
    )
    def test_an_earned_match_still_certifies(self, printed, quoted, tier):
        match = matching.find_in_pages(quoted, _pages(printed), None)
        assert match.tier == tier, (match.tier, match.reason)
        assert match.found

    def test_a_quote_that_runs_across_a_page_break_still_certifies(self):
        match = matching.find_in_pages(
            "We train on two corpora drawn from the same distribution.",
            _pages(
                "We train on two corpora drawn",
                "from the same distribution.",
            ),
            None,
        )
        assert match.found
        assert match.spanned == (1, 2)


class TestTheThreeCommands:
    """Live check, recorded check and verify must all say the same thing.

    Three readers of one fact is the defect family this project keeps meeting:
    a guard taught to one of them is a licence for the other two to lie.
    """

    def test_live_check_stops_and_says_why(self, tmp_path, monkeypatch, capsys):
        root = _project(
            tmp_path,
            "The suspect is nowhere in this room.",
            "The suspect is now here in this room.",
        )
        code, payload, out = _json(root, monkeypatch, capsys, "check", "m.md", "--root", ".")
        assert code == 1, out
        assert payload["summary"]["verified"] == 0
        assert payload["summary"]["moved"] == 0
        assert payload["summary"]["skipped"] == 1
        assert [f["code"] for f in payload["findings"]] == ["quote-word-boundaries-unclear"]
        assert payload["findings"][0]["severity"] == "high"
        # The message has to hand the author the passage, or "read the page" is
        # an instruction with no page in it.
        assert "nowhere in this room" in payload["findings"][0]["message"]

    def test_recorded_check_stops_and_says_why(self, tmp_path, monkeypatch, capsys):
        root = _project(
            tmp_path,
            "The suspect is nowhere in this room.",
            "The suspect is now here in this room.",
        )
        assert main(["scan", "m.md", "--root", str(root)]) == 0
        code, payload, out = _json(
            root, monkeypatch, capsys, "check", "m.md", "--root", ".", "--use-recorded"
        )
        assert code == 1, out
        assert payload["summary"]["verified"] == 0
        assert payload["summary"]["skipped"] == 1
        assert [f["code"] for f in payload["findings"]] == ["quote-word-boundaries-unclear"]

    def test_verify_stops_and_says_why(self, tmp_path, monkeypatch, capsys):
        root = _project(
            tmp_path,
            "The suspect is nowhere in this room.",
            "The suspect is now here in this room.",
        )
        assert main(["scan", "m.md", "--root", str(root)]) == 0
        code, payload, out = _json(root, monkeypatch, capsys, "verify", "m.md", "--root", ".")
        assert code == 1, out
        assert payload["summary"]["verified"] == 0
        assert [f["code"] for f in payload["findings"]] == ["quote-word-boundaries-unclear"]

    def test_the_ledger_does_not_record_the_claim_as_moved(self, tmp_path):
        root = _project(
            tmp_path,
            "The suspect is nowhere in this room.",
            "The suspect is now here in this room.",
        )
        assert main(["scan", "m.md", "--root", str(root)]) == 0
        before = json.loads((root / LEDGER).read_text(encoding="utf-8"))
        assert before["claims"][0]["page"] == 1


class TestTheCacheDoesNotRescueIt:
    """A cached extraction is a hint, and a hint may not turn a refusal into a
    certification.  Both directions, because the cache was once the reason a
    warm run answered differently from a cold one."""

    def _codes(self, tmp_path: Path, *, no_cache: bool) -> list[str]:
        argv = [
            sys.executable,
            "-m",
            "citevouch",
            "check",
            "m.md",
            "--root",
            ".",
            "--format",
            "json",
        ]
        if no_cache:
            argv.append("--no-cache")
        env = {
            **os.environ,
            "PYTHONPATH": str(SRC),
            "PYTHONIOENCODING": "utf-8",
        }
        proc = subprocess.run(
            argv,
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert proc.returncode == 1, (proc.returncode, proc.stdout, proc.stderr)
        payload = json.loads(proc.stdout)
        assert payload["summary"]["verified"] == 0
        return [finding["code"] for finding in payload["findings"]]

    def test_cold_then_warm_agree(self, tmp_path):
        root = _project(
            tmp_path,
            "The suspect is nowhere in this room.",
            "The suspect is now here in this room.",
        )
        assert self._codes(root, no_cache=True) == ["quote-word-boundaries-unclear"]
        assert self._codes(root, no_cache=False) == ["quote-word-boundaries-unclear"]


class TestTheDraftStopsProposing:
    """``draft`` proposes a quote only when the sentence is verbatim on the page.

    It reads the same ``Match.found``, so a tier that stopped certifying must
    stop enabling proposals too - otherwise the tool writes the bad quote into
    the manuscript for the author to copy.

    The matcher is not the only place that compared whitespace-free text:
    ``draft._verbatim_sentence`` did too, one layer below ``Match.found``, and
    a test that only looked at the written proposal passed while that helper
    still answered "the same sentence" for ``nowhere`` against ``now here``.
    These tests pin the helper itself, because it is the seam that decides
    whether a proposal is labelled verbatim at all.
    """

    PRINTED = "The suspect is nowhere in this room."
    QUOTED = "The suspect is now here in this room."

    def test_the_helper_does_not_call_a_lost_space_a_verbatim_sentence(self):
        assert draft._verbatim_sentence(self.PRINTED, self.QUOTED) == ""

    def test_a_sentence_the_page_really_prints_is_still_returned(self):
        assert draft._verbatim_sentence(self.QUOTED, self.QUOTED) == self.QUOTED

    def test_whitespace_differences_are_still_forgiven(self):
        # A page break or a re-wrapped line does not change which words were
        # printed, so the same sentence must still come back verbatim.
        assert draft._verbatim_sentence(
            "We train on" + NL + "two corpora.", "We train on two corpora."
        )

    def test_no_verbatim_proposal_is_made_for_a_boundary_that_was_lost(self):
        pages = _pages(self.PRINTED)
        assert draft.propose_quote(self.QUOTED, pages) is None

    def test_a_verbatim_proposal_is_still_made_for_printed_text(self):
        proposal = draft.propose_quote(self.QUOTED, _pages(self.QUOTED))
        assert proposal is not None
        assert proposal[2] == "high"

    def test_text_with_lost_boundaries_is_proposed_at_medium_not_high(self):
        # The refusal above must not turn into "never propose anything": a page
        # whose words the extractor ran together is still offered, but as text
        # the author has to read.
        pages = _pages("Wetrainontwocorpora. We train on two corpora and one heldout set.")
        statement = "We train on two corpora and one held-out set."
        proposal = draft.propose_quote(statement, pages)
        assert proposal is not None, "the medium-confidence path must still find this"
        assert proposal[2] == "medium"
        assert proposal[2] != "high"

    def test_a_whitespace_free_sentence_is_not_offered_as_verbatim(
        self, tmp_path, monkeypatch, capsys
    ):
        (tmp_path / "page.txt").write_text(
            "The suspect is nowhere in this room. " + NL, encoding="utf-8", newline=NL
        )
        (tmp_path / "sources.toml").write_text(
            '[sources]\npaper = "page.txt"\n', encoding="utf-8", newline=NL
        )
        (tmp_path / "m.md").write_text(
            "The suspect is now here in this room [@paper].\n", encoding="utf-8", newline=NL
        )
        code, out = _run(tmp_path, monkeypatch, capsys, "draft", "m.md", "--root", ".")
        assert code == 0, out
        written = (
            (tmp_path / "claims.md").read_text(encoding="utf-8")
            if (tmp_path / "claims.md").is_file()
            else out
        )
        assert "quote: |" not in written or "now here" not in written, written
        assert "0 claim block(s) proposed (0 verbatim)" in out, out
