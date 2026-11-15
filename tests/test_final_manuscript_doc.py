"""CV-012 guard: the final-manuscript page has to keep matching the CLI.

The page is a sequence of commands with the output they produce.  A page like
that rots in one direction only - the tool changes and the page keeps printing
the old answer - so this test runs the commands and holds the page to what they
print, rather than checking that some words appear in it.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PAGE = REPO / "docs" / "final-manuscript.md"
README = REPO / "README.md"


def _text() -> str:
    return PAGE.read_text(encoding="utf-8")


def _flat(text: str) -> str:
    """Whitespace-collapsed, because every sentence in these files wraps."""
    return re.sub(r"\s+", " ", text)


def _section(heading: str) -> str:
    text = _text()
    start = text.find(heading)
    assert start >= 0, f"{heading} is not on the page"
    nxt = re.search(r"^## ", text[start + len(heading) :], re.MULTILINE)
    end = start + len(heading) + nxt.start() if nxt else len(text)
    return text[start:end]


class TestThePageExistsAndSaysWhatItIsFor:
    def test_the_page_is_linked_from_the_readme(self) -> None:
        assert "docs/final-manuscript.md" in README.read_text(encoding="utf-8"), (
            "a page nobody links to is a page nobody reads"
        )

    def test_the_first_half_and_the_second_half_are_named(self) -> None:
        flat = _flat(_text())
        assert "The first one is a person's work" in flat
        assert "second one is a CI job" in flat

    def test_it_says_what_it_does_not_claim(self) -> None:
        flat = _flat(_section("## What this page does not claim"))
        assert "does not prove that any sentence follows from its quote" in flat, (
            "the page must not let a green job stand in for a judgement about support"
        )


class TestTheStepsAreTheSteps:
    def test_the_five_steps_are_in_the_order_a_writer_does_them(self) -> None:
        headings = re.findall(r"^## (\d)\..*$", _text(), re.MULTILINE)
        assert headings == ["1", "2", "3", "4", "5"], headings

    def test_each_step_still_names_the_action_it_asks_for(self) -> None:
        """A step whose number is right and whose instruction drifted is worse.

        Reverse validation found this one: renaming step 3 to "copy the blocks
        you like anywhere" left the suite green, because only the numbers were
        checked.  The numbers say the order; the verbs say the workflow.
        """
        titles = dict(re.findall(r"^## (\d)\. (.+)$", _text(), re.MULTILINE))
        assert "Draft proposals" in titles["1"]
        assert "Read the proposals" in titles["2"]
        assert "Copy the accepted blocks into `final.md`" == titles["3"]
        assert "Record the evidence" in titles["4"]
        assert "Gate the pull request" in titles["5"]

    def test_every_documented_command_runs(self, tmp_path: Path) -> None:
        """Run the page's commands in order and require each to do its job."""
        import os

        page = tmp_path / "paper"
        page.mkdir()
        (page / "page.txt").write_text(
            "We collected 40,688 examples from the corpus, of which 1,204 were held "
            "out for evaluation.\n",
            encoding="utf-8",
            newline="\n",
        )
        (page / "sources.toml").write_text(
            '[sources]\npaper = "page.txt"\n', encoding="utf-8", newline="\n"
        )
        (page / "final.md").write_text(
            "# Method\n\nWe collected 40,688 examples from the corpus [@paper].\n",
            encoding="utf-8",
            newline="\n",
        )
        env = {
            **os.environ,
            "PYTHONPATH": str(REPO / "src"),
            "PYTHONIOENCODING": "utf-8",
        }

        def run(*argv: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [sys.executable, "-m", "citevouch", *argv],
                cwd=page,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

        drafted = run("draft", "final.md", "-o", "claims.md")
        assert drafted.returncode == 0
        assert "1 claim block(s) proposed (0 verbatim)" in (drafted.stdout + drafted.stderr)

        checked = run("check", "claims.md")
        assert checked.returncode == 0, checked.stdout + checked.stderr
        assert not (page / "citevouch.lock.json").exists(), (
            "the page says check records nothing, so it must not"
        )

        # Step 3: the writer copies the block they accept into the manuscript
        # they intend to submit, and leaves out the ones they reject.
        text = (page / "claims.md").read_text(encoding="utf-8")
        start = text.find("```claim")
        end = text.find("\n```", start) + 4
        assert start >= 0, "draft proposed nothing for this test to copy"
        (page / "final.md").write_text(
            "# Method\n\n" + text[start:end] + "\n", encoding="utf-8", newline="\n"
        )

        scanned = run("scan", "final.md")
        assert scanned.returncode == 0
        assert "wrote citevouch.lock.json (1 claim)" in (scanned.stdout + scanned.stderr)

        gated = run("check", "final.md", "--use-recorded", "--fail-on", "medium")
        assert gated.returncode == 0, gated.stdout + gated.stderr


class TestTheDocumentedAnswersAreTheRealAnswers:
    def test_the_prose_edit_answer_is_ledger_stale_then_green(self) -> None:
        section = _flat(_section("## What the two edits look like"))
        assert "[high] ledger-stale" in section
        assert "the digest cannot tell a prose edit from a claim edit" in section
        assert "The recovery is step 4 again" in section, (
            "the page must name the recovery rather than leaving the reader stuck"
        )

    def test_the_page_hint_and_the_source_answers_are_both_named(self) -> None:
        section = _flat(_section("## What the two edits look like"))
        assert "[high] page-out-of-range" in section
        assert "[medium] source-changed" in section
        assert "only it has the old digest" in section

    def test_the_page_says_the_bare_scan_is_refused(self) -> None:
        flat = _flat(_section("## 2. Read the proposals"))
        # The warning used to be a prohibition the tool did not enforce, and
        # `draft`'s own header walked the reader straight into it. Both halves
        # are fixed, so the page now describes a refusal rather than asking for
        # restraint - and it must keep naming the ledger that works.
        assert "A bare `citevouch scan claims.md` is refused" in flat
        assert "scan claims.md --ledger claims.lock.json" in flat, (
            "the reason matters more than the rule: a separate ledger is how a "
            "reader keeps both records"
        )
        assert "Do not run" not in flat, (
            "the prohibition is gone because the tool refuses the command itself"
        )
        assert "ledger-stale" in flat, "what it used to cost is the reason the guard exists"

    def test_the_gate_explains_why_the_flag_is_required(self) -> None:
        flat = _flat(_section("## 5. Gate the pull request"))
        assert "--fail-on medium" in flat
        for code in ("source-changed", "quote-moved", "quote-fuzzy"):
            assert code in flat, f"{code} is medium, which is why the flag is required"
        assert "the CLI default is `high`" in flat


class TestThePageDoesNotPromiseJudgement:
    def test_it_never_says_the_tool_proves_a_claim(self) -> None:
        flat = _flat(_text()).lower()
        for phrase in ("proves the claim", "proves your claim", "no judgement needed"):
            assert phrase not in flat

    def test_it_does_not_treat_check_as_a_review(self) -> None:
        flat = _flat(_section("## 2. Read the proposals"))
        assert "It is not a review" in flat
        assert "cannot tell you whether the passage backs the sentence" in flat
