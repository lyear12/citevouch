"""CV-002: the promise the documentation makes has to be the promise the code keeps.

The README used to open with "bind every claim to the page of the PDF that
proves it", the comparison table promised it catches "wrong numbers, drifted
paraphrases", the draft section said a verbatim proposal "needs no judgement",
and the LaTeX section promised the converter is "never a false pass".  Each of
those is a stronger claim than the code can honour, and they were not small
words - they were the sentence a reader decides whether to trust the tool on.

Measured on this build, with a page printing ``the treatment did not improve
accuracy`` and a claim writing ``the treatment improved accuracy``, ``check``
exits ``0`` with ``1 verified``.  A quote saying ``40,688`` against a claim
saying ``91,234`` does the same.  So ``verified`` counts located quotes, never
supported claims, and the documentation has to say so in words a reader cannot
mistake.

These tests pin:

* that the four questions (location / source integrity / numbers / support) are
  spelled out separately, in both languages;
* that the absolute promises are gone from the READMEs, the package
  description and the CLI help;
* that the CLI, the metadata and the READMEs agree with each other, because a
  user meets whichever one they meet first;
* that the counterexamples the tool misses are written down, so a future
  improvement that starts catching them is a doc change its author is told to
  make rather than a silent contradiction.

They do not check that the numbers quoted in the prose stay true for ever -
that would need running the tool inside a docs test - but the section names the
build they were measured on, and ``tests/test_readme_example.py`` still pins the
demo output that the rest of the README shows.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from citevouch.cli import build_parser

ROOT = Path(__file__).resolve().parent.parent

# Wording that claims more than the code can keep.  Every entry here was in the
# shipped documentation at some point; that is why each one has an assertion
# rather than a comment.
ABSOLUTE_PROMISES = (
    "that proves it",
    "proves it,",
    "needs no judgement",
    "no judgement",
    "never a false pass",
    "not a false pass",
)

ABSOLUTE_PROMISES_ZH = (
    "不需要判断",
    "绝不会是假通过",
    "不会是假通过",
    "证明它的那份 PDF",
)


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _package_description() -> str:
    """Read `project.description` without importing `tomllib`.

    `tomllib` arrived in 3.11 and this package supports 3.10, so a module-level
    import here would make the whole file uncollectable on a supported
    interpreter - the exact hole `tests/test_extras.py` describes at length. The
    value under test is one quoted line, so the line is read directly, the same
    way `tests/test_critic_round2.py` reads `dynamic`.
    """
    text = _read("pyproject.toml").split("[project]", 1)[1].split("\n[", 1)[0]
    match = re.search(r'^description\s*=\s*"(?P<value>[^"]*)"', text, re.M)
    assert match is not None, "pyproject.toml has no project.description"
    return match.group("value")


def _section(text: str, heading: str) -> str:
    """The text under one Markdown heading, up to the next heading of any level."""
    match = re.search(rf"^{re.escape(heading)}$", text, re.MULTILINE)
    assert match is not None, f"section {heading!r} is missing"
    rest = text[match.end() :]
    following = re.search(r"^#{2,3} ", rest, re.MULTILINE)
    return rest[: following.start()] if following else rest


class TestTheFourQuestionsAreSeparate:
    """A reader has to be able to tell what is answered and what is not."""

    @pytest.mark.parametrize(
        "name, heading",
        [
            ("README.md", "## What it checks, and what it does not"),
            ("README.zh-CN.md", "## 它核对什么、不核对什么"),
        ],
    )
    def test_both_readmes_carry_the_section(self, name: str, heading: str) -> None:
        body = _section(_read(name), heading)
        assert len(body.splitlines()) > 10, f"{name}: the section is a stub"

    def test_the_support_question_is_answered_with_no(self) -> None:
        """The fourth question is the one `verified` gets mistaken for."""
        body = _section(_read("README.md"), "## What it checks, and what it does not")
        assert "Does the passage support the sentence?" in body
        assert "**No.**" in body
        # And it says plainly what `verified` does and does not mean.
        assert "It counts quotes whose passage" in body
        assert "not count claims whose sentence was shown to follow" in body

    def test_the_chinese_section_says_the_same_thing(self) -> None:
        body = _section(_read("README.zh-CN.md"), "## 它核对什么、不核对什么")
        assert "这段引文支持这句话吗" in body
        assert "**不**" in body
        assert "引文被定位到了" in body
        assert "不是「这句话被证明" in body

    def test_the_number_heuristic_is_described_as_narrow(self) -> None:
        body = _section(_read("README.md"), "## What it checks, and what it does not")
        row = next(line for line in body.splitlines() if "Are the numbers right?" in line)
        assert "A narrow heuristic only" in row
        # The two omissions a reader will otherwise assume are covered.
        assert "Two changed digits" in row
        # `claim-number-differs` is the code that exists; the row has to name
        # the family rather than promise a general numeric check.
        assert "claim-number-differs" in row

    def test_the_source_integrity_answer_is_honest_about_what_a_hash_can_do(self) -> None:
        body = _section(_read("README.md"), "## What it checks, and what it does not")
        row = next(
            line for line in body.splitlines() if "Is the source the one you recorded?" in line
        )
        assert "Partly" in row
        assert "cannot authenticate a file it has never seen" in row


class TestTheCounterexamplesAreWrittenDown:
    """The measured misses belong in the docs, not only in a commit message."""

    def test_the_negation_counterexample_is_stated(self) -> None:
        body = _section(_read("README.md"), "## What it checks, and what it does not")
        assert "did not improve accuracy" in body
        assert "exits `0` with `1 verified`" in body

    def test_the_gross_number_counterexample_is_stated(self) -> None:
        body = _section(_read("README.md"), "## What it checks, and what it does not")
        assert "40,688" in body and "91,234" in body

    def test_the_chinese_section_carries_them_too(self) -> None:
        body = _section(_read("README.zh-CN.md"), "## 它核对什么、不核对什么")
        assert "未能" in body and "改善了准确率" in body
        assert "40,688" in body and "91,234" in body


class TestNoAbsolutePromiseSurvives:
    """The wording that made the tool sound like it judged support."""

    @pytest.mark.parametrize("name", ["README.md", "README.zh-CN.md"])
    def test_the_readmes_do_not_promise_proof(self, name: str) -> None:
        text = _read(name)
        # The severity table's own wording for `quote-fuzzy` is the one place
        # the word may appear, and it says the opposite of a promise.
        offenders = []
        for phrase in ABSOLUTE_PROMISES + ABSOLUTE_PROMISES_ZH:
            for match in re.finditer(re.escape(phrase), text):
                line = text[: match.start()].count("\n") + 1
                context = text.splitlines()[line - 1]
                if "nothing proves it" in context:
                    continue  # `quote-fuzzy`'s honest description
                offenders.append(f"{name}:{line}: {phrase!r} in {context.strip()[:80]!r}")
        assert not offenders, "absolute promises came back:\n" + "\n".join(offenders)

    def test_the_package_description_does_not_promise_proof(self) -> None:
        description = _package_description()
        assert "proves it" not in description
        assert "support" in description, "the description must say support is not judged"

    def test_the_cli_description_does_not_promise_proof(self) -> None:
        description = build_parser().description
        assert "proves it" not in description
        assert "not whether it supports" in description


class TestTheEntryPointsAgree:
    """A user meets the CLI, the metadata or the README first; all three must match."""

    def test_the_cli_and_the_metadata_describe_the_same_tool(self) -> None:
        description = _package_description()
        cli = build_parser().description
        # Both name what is bound and both bound the claim the same way.
        for text in (description, cli):
            assert "cites" in text
            assert "fail CI" in text
            assert "proves it" not in text

    def test_the_draft_help_does_not_claim_the_manuscript_proves_nothing(self) -> None:
        """It proposes quotes for citations that have no verbatim quote yet.

        The line lives in the subcommand list (`citevouch --help`), not on the
        `manuscript` argument, so the test has to read the same place a user
        reads: the summary line next to `draft`.
        """
        group = build_parser()._subparsers._group_actions[0]
        summary = next(a.help for a in group._choices_actions if a.dest == "draft")
        assert "proves nothing" not in summary
        assert "verbatim" in summary

    @pytest.mark.parametrize("name", ["README.md", "README.zh-CN.md"])
    def test_the_readme_does_not_call_the_converter_false_pass_proof(self, name: str) -> None:
        """A converter that mangles a sentence can still propose a real quote.

        The old sentence promised that a mangled manuscript could not make a
        citation look verified.  The quote does come from the PDF, so that half
        is true; but the proposal it lands on can be a wholly different
        passage, which is why the wording now says so.
        """
        text = _read(name)
        assert "never a\nfalse pass" not in text
        assert "绝不会是假通过" not in text

    def test_the_recorded_pass_is_not_described_as_never_opening_the_bibliography(self) -> None:
        """The recorded pass re-reads the `.bib` files the ledger names.

        `verify.verify()` walks `ledger.bibliographies` with `read_text` when
        the manuscript digest still matches, so a README sentence saying it
        does not open a `.bib` at all sends an author looking for a file that
        was in fact read.
        """
        for name in ("README.md", "README.zh-CN.md"):
            text = _read(name)
            assert "does not open a `.bib` at all" not in text
            assert "根本不会打开" not in text
        assert "re-reads them" in _read("README.md")
        assert "重新读它们" in _read("README.zh-CN.md")
