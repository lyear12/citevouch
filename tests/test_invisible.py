"""Characters that render as nothing and still change the verdict.

A format character (Unicode category ``Cf``) is an instruction to the text
engine, not a glyph: it is in the string and invisible on the page.  That
combination is what makes it dangerous here, because this tool decides whether
a quote is on a page by comparing characters.  If the page carries one and the
author's quote does not, the two differ, the quote falls through every tier, and
the run reports ``quote-missing`` at high severity - an accusation that the
author did not quote a page they are looking at.

Right-to-left text is where they arrive in bulk.  Word and InDesign mark every
direction change with RLM (U+200F), ALM (U+061C) or an embedding pair
(U+202B/U+202C), and a PDF extraction that keeps them puts one in the middle of
a sentence.  Arabic and Hebrew authors have no way to see that this happened.

The fix is a compiled character class covering every format character, verified
here against ``unicodedata.category`` for the whole of Unicode rather than
against a list someone typed.  If a Unicode release adds a format character,
this file fails; a hand-maintained list would have gone on passing.
"""

from __future__ import annotations

import unicodedata

import pytest

from citevouch.matching import PageText, find_in_pages
from citevouch.textnorm import normalize, strip_format

#: Every character this tool has to treat as present-but-invisible.
INVISIBLE = (
    "\u00ad",  # SOFT HYPHEN
    "\u061c",  # ARABIC LETTER MARK
    "\u180e",  # MONGOLIAN VOWEL SEPARATOR
    "\u200b",  # ZERO WIDTH SPACE
    "\u200c",  # ZERO WIDTH NON-JOINER
    "\u200d",  # ZERO WIDTH JOINER
    "\u200e",  # LEFT-TO-RIGHT MARK
    "\u200f",  # RIGHT-TO-LEFT MARK
    "\u202a",  # LEFT-TO-RIGHT EMBEDDING
    "\u202b",  # RIGHT-TO-LEFT EMBEDDING
    "\u202c",  # POP DIRECTIONAL FORMATTING
    "\u202d",  # LEFT-TO-RIGHT OVERRIDE
    "\u202e",  # RIGHT-TO-LEFT OVERRIDE
    "\u2060",  # WORD JOINER
    "\u2061",  # FUNCTION APPLICATION
    "\u2066",  # LEFT-TO-RIGHT ISOLATE
    "\u2067",  # RIGHT-TO-LEFT ISOLATE
    "\u2068",  # FIRST STRONG ISOLATE
    "\u2069",  # POP DIRECTIONAL ISOLATE
    "\ufeff",  # ZERO WIDTH NO-BREAK SPACE
)

ENGLISH = "the grammar network among constructions"
ARABIC = "تشير البيانات إلى أن البنية تشمل الجمل"
HEBREW = "הרשת הבלשנית כוללת מבנים רבים"


class TestTheClassIsTheCategory:
    """The table is an optimisation; the category is the definition."""

    def test_every_format_character_in_unicode_is_removed(self):
        # Walks all 1,114,112 code points.  Slow in the way a guard should be
        # slow: once, and only when something changed.
        missing = [
            cp
            for cp in range(0x110000)
            if unicodedata.category(chr(cp)) == "Cf" and strip_format(chr(cp)) != ""
        ]
        assert missing == [], [hex(cp) for cp in missing]

    def test_nothing_outside_the_table_is_removed(self):
        # The other direction matters as much: a class that also swallowed
        # ordinary letters would silently change what a quote says.  The
        # expectation here is the table, not `unicodedata.category`, because
        # the table is a snapshot of a *later* Unicode version than some
        # interpreters ship: U+0890/U+0891 and the Egyptian hieroglyph format
        # controls are `Cf` in Unicode 14 and ordinary assigned characters in
        # Unicode 13, which is what CPython 3.10 carries.  Removing them there
        # is forward-looking and harmless; what must never happen is removing
        # something the table does not name.
        from citevouch.textnorm import _FORMAT_RANGES

        allowed = {cp for lo, hi in _FORMAT_RANGES for cp in range(lo, hi + 1)}
        extra = [
            cp
            for cp in range(0x110000)
            if cp not in allowed and strip_format(chr(cp)) != chr(cp)
        ]
        assert extra == [], [hex(cp) for cp in extra]

    def test_the_table_never_drops_a_character_this_interpreter_calls_format(self):
        # The direction that must hold on every interpreter: whatever this
        # `unicodedata` knows to be invisible has to be in the table.  If a
        # Unicode release adds one, this is where it fails - the direction
        # above cannot see a character its own database does not have.
        missing = [
            cp
            for cp in range(0x110000)
            if unicodedata.category(chr(cp)) == "Cf" and strip_format(chr(cp)) != ""
        ]
        assert missing == [], [hex(cp) for cp in missing]

    def test_the_table_may_be_ahead_of_this_interpreter(self):
        """A snapshot newer than the runtime is fine, and worth stating.

        CPython 3.10 ships Unicode 13; the table was written from 14.  The
        characters in between are removed on 3.10 for no benefit - nobody
        writes them yet - and that is a limit on being *newer*, not a fault.
        Pinning it here means a later reader sees the asymmetry explained
        rather than meeting it as a mystery failing matrix cell.
        """
        from citevouch.textnorm import _FORMAT_RANGES

        ahead = [
            cp
            for lo, hi in _FORMAT_RANGES
            for cp in range(lo, hi + 1)
            if unicodedata.category(chr(cp)) != "Cf"
        ]
        # Whatever the interpreter, these are only ever extra removals.
        assert all(strip_format(chr(cp)) == "" for cp in ahead)
        # On this interpreter that set is either empty (Unicode >= 14) or made
        # only of exactly the characters that became format characters in 14.
        assert set(ahead) <= {
            0x0890,
            0x0891,
            0x13439,
            0x1343A,
            0x1343B,
            0x1343C,
            0x1343D,
            0x1343E,
            0x1343F,
        }, [hex(cp) for cp in ahead]

    def test_the_sample_in_this_file_is_really_invisible(self):
        # Otherwise the test data could quietly become ordinary letters.
        assert [ch for ch in INVISIBLE if unicodedata.category(ch) != "Cf"] == []


class TestTheVerdictDoesNotDependOnThem:
    @pytest.mark.parametrize("mark", INVISIBLE)
    def test_a_mark_inside_the_source_text_does_not_hide_the_quote(self, mark):
        spaced = ENGLISH.replace(" ", mark + " ", 1)
        page = PageText(1, f"Intro. {spaced}. More.", "")
        assert find_in_pages(ENGLISH, [page], None).tier == "exact"

    @pytest.mark.parametrize("text", (ARABIC, HEBREW))
    @pytest.mark.parametrize("mark", ("\u200f", "\u061c", "\u202b", "\u202c"))
    def test_a_right_to_left_page_marked_up_by_its_exporter_still_matches(self, text, mark):
        # The shape a Word or InDesign export produces: an embedding pair
        # around the run, or a directional mark next to it.
        page = PageText(1, "نص. " + mark + text + mark + ". نص.", "")
        assert find_in_pages(text, [page], None).tier == "exact"

    @pytest.mark.parametrize("mark", INVISIBLE)
    def test_normalize_removes_it_from_both_sides(self, mark):
        assert normalize(ENGLISH + mark) == normalize(mark + ENGLISH) == normalize(ENGLISH)

    def test_a_mark_carrying_no_layout_meaning_is_still_content(self):
        # A guard against over-reach: only category Cf is removed, so a
        # combining mark that renders as part of a letter stays.
        combining = "\u0301"  # COMBINING ACUTE ACCENT, category Mn
        assert normalize("e" + combining) != normalize("e")


class TestTheReportCanStillSayWhatHappened:
    def test_the_quote_is_found_not_missing(self, tmp_path, capsys):
        """End to end, because the verdict is the only thing a user sees.

        Before the fix a single RLM in the source produced
        `[high] quote-missing`; the claim was correct and the file was correct
        and the tool accused the author anyway.
        """
        from citevouch.cli import main

        nl = chr(10)
        root = tmp_path
        page = "Intro. " + ARABIC.replace(" ", "\u200f ", 1) + ". More." + nl
        (root / "p.txt").write_bytes(page.encode("utf-8"))
        (root / "sources.toml").write_text(
            "[sources]" + nl + 'p = "p.txt"' + nl, encoding="utf-8", newline=nl
        )
        (root / "m.md").write_text(
            "```claim id=c1 source=p" + nl + ">> " + ARABIC + nl + "```" + nl,
            encoding="utf-8",
            newline=nl,
        )

        code = main(["check", "m.md", "--root", str(root)])
        report = capsys.readouterr().out
        assert "quote-missing" not in report, report
        assert "quote-found" in report, report
        assert code == 0
