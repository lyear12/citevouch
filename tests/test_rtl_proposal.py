"""CV-020: a test that pins the proposal page to the measurements behind it.

The page is a proposal, so nothing here may drift into a promise the tool does not
keep. Every number quoted on the page is re-measured from text the page's own
description produces, and the "not supported yet" claims are asserted to still be
true of the shipped tool.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
DOC = REPO / "docs" / "rtl-proposal.md"
README = REPO / "README.md"

ENV = {**os.environ, "PYTHONPATH": str(SRC), "PYTHONIOENCODING": "utf-8"}
B3 = chr(96) * 3
NL = chr(10)

# The sentence the page names, and the two readings the two producers give.
SENTENCE = (
    "\u05e0\u05d8\u05e2\u05df \u05db\u05d9 \u05d4\u05de\u05e9\u05ea\u05ea\u05e4\u05d9\u05dd "
    "\u05e7\u05d9\u05d1\u05dc\u05d5 40,688 \u05d3\u05d5\u05d2\u05de\u05d0\u05d5\u05ea "
    "\u05d1\u05de\u05d9\u05dc\u05d5\u05df."
)
REVERSED_LINE = (
    "\u05df\u05e2\u05d8\u05e0  \u05d9\u05db  \u05dd\u05d9\u05e4\u05ea\u05ea\u05e9\u05de\u05d4  "
    "\u05d5\u05dc\u05d1\u05d9\u05e7 40,688 \u05ea\u05d5\u05d0\u05de\u05d2\u05d5\u05d3  "
    "\u05df\u05d5\u05dc\u05d9\u05de\u05d1 ."
)
JOINED_LINE = (
    "    \u05e0\u05d8\u05e2\u05df\u05db\u05d9\u05d4\u05de\u05e9\u05ea\u05ea\u05e4\u05d9\u05dd"
    "\u05e7\u05d9\u05d1\u05dc\u05d5 40,688  \u05d3\u05d5\u05d2\u05de\u05d0\u05d5\u05ea"
    "\u05d1\u05de\u05d9\u05dc\u05d5\u05df ."
)

LATIN_LINE = "We collected 40,688 examples from the corpus."

RANGES = (
    (0x0590, 0x05FF),
    (0x0600, 0x06FF),
    (0x0700, 0x074F),
    (0x0750, 0x077F),
    (0x08A0, 0x08FF),
    (0xFB1D, 0xFB4F),
    (0xFB50, 0xFDFF),
    (0xFE70, 0xFEFF),
    (0x10800, 0x10FFF),
    (0x1E800, 0x1EFFF),
)


def _flat(text: str) -> str:
    return " ".join(text.split())


def _rtl_share(text: str) -> float:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    rtl = sum(1 for ch in letters if any(lo <= ord(ch) <= hi for lo, hi in RANGES))
    return round(rtl / len(letters), 4)


def _project(root: Path, page_text: str, quote: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "page.txt").write_text(page_text, encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
    )
    body = (
        B3
        + "claim id=c1 source=paper"
        + NL
        + "quote: |"
        + NL
        + "  "
        + quote
        + NL
        + "claim: |"
        + NL
        + "  We collected 40,688 examples."
        + NL
        + B3
        + NL
    )
    (root / "m.md").write_text(body, encoding="utf-8", newline=NL)
    return root


def _check(root: Path) -> dict:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "citevouch",
            "check",
            "m.md",
            "--root",
            ".",
            "--format",
            "json",
            "--no-cache",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=ENV,
        timeout=300,
    )
    payload = json.loads(result.stdout)
    return {
        "rc": result.returncode,
        "codes": [f["code"] for f in payload["findings"]],
        "worst": payload.get("worst"),
        "summary": payload["summary"],
    }


def test_the_page_exists_and_says_it_is_only_a_proposal() -> None:
    text = DOC.read_text(encoding="utf-8")
    flat = _flat(text)
    assert "**Status: a proposal waiting for one Owner decision.**" in text
    assert "Nothing in this document changes how the tool behaves." in flat
    assert flat.count("Question (one, for the Owner):") == 1
    for answer in ("Answer A", "Answer B", "Answer C"):
        assert answer in text


def test_the_page_records_both_producers_with_their_readings() -> None:
    flat = _flat(DOC.read_text(encoding="utf-8"))
    assert "pymupdf" in flat and "LibreOffice" in flat
    # The two readings it quotes are the two readings measured.
    assert _flat(REVERSED_LINE) in flat
    assert _flat(JOINED_LINE) in flat
    assert "pypdf" in flat


def test_every_hebrew_word_reported_as_a_reverse_really_is_one() -> None:
    """Five of six are exact reverses; the sixth loses its full stop."""
    expected = [w for w in SENTENCE.split() if any("\u0590" <= ch <= "\u05ff" for ch in w)]
    got = [w for w in REVERSED_LINE.split() if any("\u0590" <= ch <= "\u05ff" for ch in w)]
    assert len(expected) == len(got) == 6

    exact = [want for want, came in zip(expected, got, strict=True) if came == want[::-1]]
    assert len(exact) == 5, (exact, expected, got)

    last_want, last_got = expected[-1], got[-1]
    assert last_want.endswith(".")
    assert last_got == last_want[:-1][::-1], (last_want, last_got)
    assert " ." in REVERSED_LINE or REVERSED_LINE.rstrip().endswith(".")


def test_the_prose_counts_the_same_reversals_the_fixture_does() -> None:
    """The page says "five of six"; the fixture decides whether that is true."""
    expected = [w for w in SENTENCE.split() if any("\u0590" <= ch <= "\u05ff" for ch in w)]
    got = [w for w in REVERSED_LINE.split() if any("\u0590" <= ch <= "\u05ff" for ch in w)]
    reverses = [w for w, g in zip(expected, got, strict=True) if g == w[::-1]]
    flat = _flat(DOC.read_text(encoding="utf-8"))
    word = {5: "Five", 6: "Six"}.get(len(reverses))
    assert word, len(reverses)
    assert (
        f"**{word} of six Hebrew words are exact character-for-character reverses**" in flat
    ), (
        len(reverses),
        flat[:0],
    )


def test_the_joined_reading_has_lost_the_hebrew_spaces_and_nothing_else() -> None:
    assert SENTENCE.count(" ") == 6
    # Two spaces survive (around the number); the Hebrew spaces are gone.
    assert JOINED_LINE.count(" ") == 8
    assert "40,688" in JOINED_LINE
    joined_words = [
        w for w in JOINED_LINE.split() if any("\u0590" <= ch <= "\u05ff" for ch in w)
    ]
    assert any(len(w) > 12 for w in joined_words), joined_words


def test_the_rtl_share_separates_these_pages_from_the_real_ones() -> None:
    # The page carries the Hebrew line and a Latin one, which is why a page that is
    # entirely RTL in its own script scores 0.50 rather than 1.00.
    page_reversed = REVERSED_LINE + NL + LATIN_LINE
    page_joined = JOINED_LINE + NL + LATIN_LINE
    assert _rtl_share(page_reversed) == 0.5
    assert _rtl_share(page_joined) == 0.5
    assert _rtl_share(REVERSED_LINE) == 1.0
    assert _rtl_share(JOINED_LINE) == 1.0
    assert _rtl_share(SENTENCE) == 1.0
    assert _rtl_share(LATIN_LINE) == 0.0
    assert _rtl_share("We collected 40,688 examples from the corpus.") == 0.0
    assert _rtl_share("The study (\u05e0\u05d8\u05e2\u05df) reports 40,688 examples.") == 0.1481
    # The demo's own papers are pure LTR, so a threshold cannot misfire on them.
    from citevouch import sources

    for pdf in sorted((REPO / "demo" / "papers").glob("*.pdf")):
        pages, problem = sources.extract_pages(pdf, REPO / "demo", use_cache=False)
        assert problem is None, (pdf.name, problem)
        assert _rtl_share(NL.join(page.text for page in pages)) == 0.0, pdf.name


def test_the_threshold_the_page_names_is_the_threshold_the_numbers_support() -> None:
    flat = _flat(DOC.read_text(encoding="utf-8"))
    match = re.search(r"threshold of (\d\.\d\d)", flat)
    assert match, flat[:400]
    threshold = float(match.group(1))
    assert threshold == 0.30
    # It sits between the mixed-script sentence and the RTL pages.
    assert (
        _rtl_share("The study (\u05e0\u05d8\u05e2\u05df) reports 40,688 examples.") < threshold
    )
    assert _rtl_share(REVERSED_LINE) > threshold
    assert _rtl_share(REVERSED_LINE + NL + LATIN_LINE) > threshold


def test_the_page_does_not_overstate_the_corpus_it_measured() -> None:
    flat = _flat(DOC.read_text(encoding="utf-8"))
    assert "one page per producer and three controls, not a corpus" in flat


def test_a_reversed_page_still_accuses_the_author_today(tmp_path: Path) -> None:
    """Option A/B/C are undecided, so the shipped behaviour is the accusation."""
    root = _project(tmp_path / "reversed", REVERSED_LINE, SENTENCE)
    result = _check(root)
    assert result["codes"] == ["quote-missing"], result
    assert result["worst"] == "high"
    assert result["rc"] == 1
    assert result["summary"]["verified"] == 0


def test_a_joined_page_already_gives_the_third_answer(tmp_path: Path) -> None:
    root = _project(tmp_path / "joined", JOINED_LINE, SENTENCE)
    result = _check(root)
    assert result["codes"] == ["quote-word-boundaries-unclear"], result
    assert result["worst"] == "high"
    assert result["rc"] == 1
    assert result["summary"]["verified"] == 0


def test_quoting_the_number_alone_succeeds_on_both_readings(tmp_path: Path) -> None:
    """The earlier note said this failed; it does not, on either producer."""
    for name, page in (("reversed", REVERSED_LINE), ("joined", JOINED_LINE)):
        root = _project(tmp_path / name, page, "40,688")
        result = _check(root)
        assert result["codes"] == ["quote-found"], (name, result)
        assert result["rc"] == 0, (name, result)
        assert result["summary"]["verified"] == 1, (name, result)


def test_the_page_says_exactly_this_about_the_number(tmp_path: Path) -> None:
    flat = _flat(DOC.read_text(encoding="utf-8"))
    assert "quoting `40,688` alone is `quote-found`" in flat
    assert "Not reproduced on either file" in flat
    # And the claim the test above just re-measured.
    root = _project(tmp_path / "num", JOINED_LINE, "40,688")
    assert _check(root)["summary"]["verified"] == 1


def test_the_page_does_not_promise_that_anything_is_fixed() -> None:
    flat = _flat(DOC.read_text(encoding="utf-8"))
    for forbidden in (
        "rtl pages are supported",
        "right-to-left is handled",
        "quotes from rtl pages verify",
        "we now read rtl correctly",
    ):
        assert forbidden not in flat.lower()
    # The three options all have to be described as not applied.
    assert "Nothing in this document changes how the tool behaves." in flat


def test_the_readme_says_right_to_left_is_not_supported() -> None:
    """A capability gap that only lives in a proposal page will never be read."""
    flat = _flat(README.read_text(encoding="utf-8"))
    assert "right-to-left page is **not supported**" in flat, flat[:0]
    assert "docs/rtl-proposal.md" in flat
    # And it must not be softened into a claim that the tool copes.
    lowered = flat.lower()
    for forbidden in ("rtl pages are supported", "handles right-to-left", "rtl is supported"):
        assert forbidden not in lowered
    # The two measured outcomes are named, so a reader knows what to expect.
    assert "quote-missing" in flat and "quote-word-boundaries-unclear" in flat


def test_the_readme_is_honest_about_the_scope_it_claims() -> None:
    """Whatever the README claims about scripts must not contradict the page."""
    flat = _flat(README.read_text(encoding="utf-8"))
    page = _flat(DOC.read_text(encoding="utf-8"))
    if "right-to-left" in flat or "RTL" in flat:
        # If the README mentions it at all, it must be to say it is not supported.
        lowered = flat.lower()
        index = lowered.find("right-to-left")
        if index == -1:
            index = lowered.find("rtl")
        window = lowered[index : index + 400]
        assert "not supported" in window or "not handled" in window or "proposal" in window, (
            window
        )
    assert "not a corpus" in page


def test_the_three_options_each_state_a_cost() -> None:
    text = DOC.read_text(encoding="utf-8")
    flat = _flat(text)
    for phrase in (
        "Does not promise: that the quote verifies",
        "Does not promise anything for producer B",
        "Cheapest in engineering and worst for the author",
    ):
        assert phrase in flat, phrase


def test_no_dependency_was_added_for_this() -> None:
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert "pymupdf" not in pyproject.lower()
    assert "fitz" not in pyproject.lower()
    # And the tool still only reaches for pypdf, as the page says.
    sources = (SRC / "citevouch" / "sources.py").read_text(encoding="utf-8")
    assert "from pypdf import PdfReader" in sources
    assert "import fitz" not in sources
    assert "import pymupdf" not in sources


def test_the_ledger_and_the_page_agree_on_what_is_missing() -> None:
    """The page must not claim a decision the ledger has not recorded as pending."""
    state = json.loads((REPO / "docs" / "iteration-state.json").read_text(encoding="utf-8"))
    task = next(t for t in state["tasks"] if t["id"] == "CV-020")
    assert task["status"] in {"needs_owner", "ready", "implementing"}, task["status"]
    if task["status"] == "needs_owner":
        assert task["blocker"]["party"] == "owner"
        assert "silence is not an answer" in task["blocker"]["release_condition"]
        assert "docs/rtl-proposal.md" in (task["last_evidence"] or "")
    flat = _flat(DOC.read_text(encoding="utf-8"))
    assert "A timeout is not an answer." in flat


def test_this_file_does_not_skip_its_way_to_green() -> None:
    """A guard against this file becoming one that skips everything.

    The count is taken over the file *minus this function*, so the guard cannot
    count its own source text.
    """
    source = Path(__file__).read_text(encoding="utf-8")
    head, _, _ = source.partition("def test_this_file_does_not_skip_its_way_to_green")
    assert "pytest.skip" not in head
    assert "pytest.mark.skip" not in head
