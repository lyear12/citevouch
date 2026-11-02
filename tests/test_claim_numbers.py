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


class TestTheRuleStaysQuietOnTextThatIsNotATypo:
    """The guards that keep this rule from accusing correct manuscripts.

    The first version of ``claim-number-differs`` compared every pair of
    numbers one keystroke apart.  Measured against 788 adjacent real sentences
    from a corpus of published papers, that flagged **38.5% of them** - every
    flag a year (`2010`/`2011`), an ordinal (`1`/`2`) or a section number.
    Reporting a correct claim is worse than missing a wrong one: it teaches
    the author to stop reading the report, and then the tool is worth nothing.
    """

    PAGE = (
        "We collected 40,688 examples in the corpus. "
        "Almost half (48.4%) of them occur only once. "
        "We also held out a separate 10,000 rows. "
        "In 2021 we reported 1 case and 2 controls."
    )

    def project(self, root, claim, quote):
        (root / "src.txt").write_text(self.PAGE, encoding="utf-8", newline=NL)
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

    def test_another_year_is_not_a_digit_slip(self, tmp_path):
        # 2022 sits one character from the quoted 2021 and is the commonest
        # shape in real text: a restatement that names a second study.
        code, out = run(
            self.project(
                tmp_path, "In 2022 we repeated the count.", "In 2021 we reported 1 case"
            )
        )
        assert code == 0
        assert "claim-number-differs" not in out

    def test_a_small_ordinal_is_not_a_digit_slip(self, tmp_path):
        # 3 against 2 is one keystroke, and both are section numbers, case
        # labels and list positions far more often than they are copied counts.
        code, out = run(
            self.project(
                tmp_path, "We excluded 3 controls.", "In 2021 we reported 1 case and 2 controls"
            )
        )
        assert code == 0
        assert "claim-number-differs" not in out

    def test_a_number_the_page_prints_elsewhere_is_not_a_slip(self, tmp_path):
        # 10,000 really is on this page, four words after the quoted sentence.
        # An author who writes it read it; the rule must not call that a typo.
        code, out = run(
            self.project(
                tmp_path, "We also used 10,000 held-out rows.", "We collected 40,688 examples"
            )
        )
        assert code == 0
        assert "claim-number-differs" not in out

    def test_the_quantity_guard_judges_the_pair_not_the_whole_quote(self, tmp_path):
        # The guard used to ask "does any number in this quote look like a
        # quantity?", which is true for 40,688 and therefore let 1/2 through.
        # It has to be asked of the two numbers actually being compared: here
        # the pair is 4 vs 2, neither written as a quantity, so it is silent.
        code, out = run(
            self.project(
                tmp_path, "We excluded 4 controls.", "We reported 1 case and 2 controls"
            )
        )
        assert code == 0
        assert "claim-number-differs" not in out

    def test_a_percent_sign_marks_a_quantity(self):
        from citevouch.verify import _is_quantity

        assert _is_quantity("48.4%")
        assert _is_quantity("40,688")
        assert _is_quantity("6.35")
        assert not _is_quantity("1")
        assert not _is_quantity("2021")

    def test_a_year_is_recognised_by_its_range_not_its_length(self):
        from citevouch.verify import _is_year

        assert _is_year("2021")
        assert _is_year("1995")
        # Four digits that are not a plausible year are a count, not a year.
        assert not _is_year("4068")
        assert not _is_year("154391")
        assert not _is_year("40,688")


class TestEachGuardIsTheOnlyThingStoppingItsShape:
    """Four guards, four shapes, each shape blind to the other three.

    The first mutation run on the guards was useless: every one of them
    survived, because each test shape tripped at least two guards at once, so
    deleting one guard changed nothing.  A guard no test can attribute is a
    guard nobody will notice the day it stops working.  These four shapes are
    built so that exactly one guard stands between the claim and a false
    accusation, which is what makes each mutation visible.
    """

    def _project(self, root, page, quote, claim):
        (root / "src.txt").write_text(page, encoding="utf-8", newline=NL)
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

    def test_the_year_guard_is_the_only_one_that_refuses_two_years(self, tmp_path):
        # 1,995 against 1,994: one keystroke apart, both four canonical
        # characters, both written with a separator so the quantity guard is
        # satisfied, and neither appears elsewhere on the page.  Only the year
        # guard separates this from a report.
        code, out = run(
            self._project(
                tmp_path,
                "The norm held at 1,994 responses in the second wave.",
                "The norm held at 1,994 responses in the second wave.",
                "The norm held at 1,995 responses in the second wave.",
            )
        )
        assert code == 0
        assert "claim-number-differs" not in out

    def test_the_quantity_guard_is_the_only_one_that_refuses_two_integers(self, tmp_path):
        # 124 against 123: three canonical characters each, neither a year,
        # neither written with a separator or a sign, so nothing but the
        # quantity guard can stop it.
        code, out = run(
            self._project(
                tmp_path,
                "We ran 123 trials on the held-out split.",
                "We ran 123 trials on the held-out split.",
                "We ran 124 trials on the held-out split.",
            )
        )
        assert code == 0
        assert "claim-number-differs" not in out

    def test_the_length_guard_is_the_only_one_that_refuses_two_single_digit_percents(
        self, tmp_path
    ):
        # `1%` is the one quantity spelling in the whole number grammar whose
        # canonical form is shorter than three characters - found by
        # enumerating 650,806 spellings and keeping the short ones.  So this
        # pair satisfies every other guard and only the length test refuses it.
        code, out = run(
            self._project(
                tmp_path,
                "The error rate was 1% across both folds.",
                "The error rate was 1% across both folds.",
                "The error rate was 2% across both folds.",
            )
        )
        assert code == 0
        assert "claim-number-differs" not in out

    def test_the_page_guard_is_the_only_one_that_refuses_a_number_it_prints(self, tmp_path):
        # 10,000 against the quoted 50,000: one keystroke, five canonical
        # characters, both quantities, neither a year - and 10,000 is printed
        # further down the same page, which is the one thing that says the
        # author read it rather than mistyped it.
        code, out = run(
            self._project(
                tmp_path,
                "We trained on 50,000 sentences in total. "
                "The held-out split was 10,000 sentences from the same source.",
                "We trained on 50,000 sentences in total.",
                "We trained on 10,000 sentences in total.",
            )
        )
        assert code == 0
        assert "claim-number-differs" not in out

    def test_the_same_two_integers_are_reported_when_nothing_else_could_be_meant(
        self, tmp_path
    ):
        # The control for the quantity shape: the same one-keystroke pair, but
        # written as quantities, is a copy error and must be reported.  Without
        # this, deleting the quantity guard and deleting the rule look alike.
        code, out = run(
            self._project(
                tmp_path,
                "We ran 1,234 trials on the held-out split.",
                "We ran 1,234 trials on the held-out split.",
                "We ran 1,235 trials on the held-out split.",
            )
        )
        assert code == 1
        assert "claim-number-differs" in out
