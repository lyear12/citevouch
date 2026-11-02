"""A claim that restates its quote with a different digit.

``claim.numbers`` holds the numbers inside the quote, because those are what
the cited page has to contain.  Nothing compared the claim's own sentence
against them, so `the quote says 40,688 and the claim says 80,688` verified:
measured before this file existed, that run was exit 0.  A mistyped statistic
is the error this tool exists to catch and the one that reads as correct for
months, so it gets a code of its own at `high`.
"""

import contextlib
import io
from pathlib import Path

from citevouch.cli import main

NL = chr(10)

PAGE = (
    "We collected 40,688 examples in the corpus. "
    "Almost half (48.4%) of them occur only once. "
    "The corpus covers 154,391 types in total."
)


def write_project(root: Path, claim: str, quote: str) -> Path:
    """A project whose single claim quotes PAGE and restates it as `claim`."""
    (root / "src.txt").write_text(PAGE, encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'p = "src.txt"' + NL, encoding="utf-8", newline=NL
    )
    (root / "m.md").write_text(
        NL.join(
            [
                "```claim id=c1 source=p page=1",
                "quote: |",
                "  " + quote,
                "claim: |",
                "  " + claim,
                "```",
                "",
            ]
        ),
        encoding="utf-8",
        newline=NL,
    )
    return root


def run(root: Path) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = main(["check", "m.md", "--root", str(root)])
    return code, out.getvalue()


class TestTheDigitsHaveToAgree:
    def test_a_transposed_digit_fails_the_run(self, tmp_path):
        code, out = run(
            write_project(
                tmp_path, "We collected 80,688 examples.", "We collected 40,688 examples"
            )
        )
        assert code == 1
        assert "claim-number-differs" in out

    def test_the_message_quotes_the_spelling_the_page_prints(self, tmp_path):
        _, out = run(
            write_project(
                tmp_path, "We collected 80,688 examples.", "We collected 40,688 examples"
            )
        )
        # 40,688 is what the author will find on the page; 40688 is only what
        # the comparison uses internally.
        assert "its quote says 40,688" in out
        assert "its quote says 40688" not in out

    def test_a_percentage_slip_fails_the_run(self, tmp_path):
        code, out = run(
            write_project(
                tmp_path,
                "Almost half (48.5%) occur once.",
                "Almost half (48.4%) of them occur only once",
            )
        )
        assert code == 1
        assert "48.5%" in out and "48.4%" in out


class TestWhatIsNotAClipboardError:
    def test_a_claim_that_agrees_verifies(self, tmp_path):
        code, out = run(
            write_project(
                tmp_path, "We collected 40,688 examples.", "We collected 40,688 examples"
            )
        )
        assert code == 0
        assert "claim-number-differs" not in out

    def test_a_year_the_author_supplied_is_not_a_digit_slip(self, tmp_path):
        # 2020 is in no quote and is not one keystroke from a quoted number.
        code, out = run(
            write_project(
                tmp_path,
                "In 2020 we collected 40,688 examples.",
                "We collected 40,688 examples",
            )
        )
        assert code == 0
        assert "claim-number-differs" not in out

    def test_a_derived_total_is_not_a_digit_slip(self, tmp_path):
        # 4,068 differs from 40,688 in more than a keystroke, so this project
        # stays quiet rather than guess that the author meant to quote it.
        code, out = run(
            write_project(
                tmp_path, "We collected 4,068 examples.", "We collected 40,688 examples"
            )
        )
        assert code == 0
        assert "claim-number-differs" not in out

    def test_a_claim_with_no_numbers_is_not_compared(self, tmp_path):
        code, out = run(
            write_project(tmp_path, "The corpus is large.", "We collected 40,688 examples")
        )
        assert code == 0
        assert "claim-number-differs" not in out


class TestAgreeingWithOneNumberIsEnough:
    def test_a_correct_restatement_is_not_a_slip_against_a_neighbouring_figure(self):
        from citevouch.manuscript import parse_manuscript
        from citevouch.verify import _claim_number_checks

        # The page states both 40,688 and 40,689.  A claim quoting 40,688
        # agrees with the quote; it must not be measured against 40,689.
        text = NL.join(
            [
                "```claim id=c1 source=p page=1",
                "quote: |",
                "  We counted 40,688 and 40,689 tokens in two runs",
                "claim: |",
                "  We counted 40,688 tokens",
                "```",
                "",
            ]
        )
        claim = parse_manuscript(text, path="m.md").claims[0]
        assert _claim_number_checks(claim) == []


class TestItOnlySpeaksWhenTheQuoteIsConfirmed:
    def test_a_missing_quote_does_not_also_report_the_claim_number(self, tmp_path):
        # When the quote itself is not on the page, comparing the claim against
        # it would be comparing against text that has not been established.
        _, out = run(
            write_project(
                tmp_path,
                "We collected 80,688 examples.",
                "A sentence that appears nowhere in the source at all",
            )
        )
        assert "claim-number-differs" not in out
        assert "quote-missing" in out


class TestTheNearMissRule:
    def test_one_character_is_a_slip(self):
        from citevouch.verify import _near_miss

        assert _near_miss("80688", "40688")

    def test_two_characters_is_a_different_number(self):
        from citevouch.verify import _near_miss

        assert not _near_miss("80689", "40688")

    def test_a_shorter_number_is_a_different_number(self):
        from citevouch.verify import _near_miss

        assert not _near_miss("4068", "40688")

    def test_a_shorter_number_that_would_line_up_inside_one_is_still_refused(self):
        # Without the length guard, zip() would stop at the shorter string and
        # compare "4088" against the first four characters of "40688" - one
        # difference - and call ten thousand and forty thousand a typo.
        from citevouch.verify import _near_miss

        assert not _near_miss("4088", "40688")
