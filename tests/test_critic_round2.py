"""Regression tests for the second review round (critic 1b).

Every test here failed before the change named in its docstring. A regression
test that would have passed anyway is a test that documents the fix instead of
defending it, which is why these spell out the failing behaviour rather than
the implementation.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from citevouch import __version__
from citevouch.matching import find_in_pages
from citevouch.model import Ledger
from citevouch.scan import ScanOptions, scan
from citevouch.sources import PageText
from citevouch.textnorm import fold, numbers_in
from citevouch.verify import verify


def pages(*texts: str) -> list[PageText]:
    return [PageText(number=i + 1, text=t, folded=fold(t)) for i, t in enumerate(texts)]


def bind(root: Path, **entries: str) -> None:
    """Write the manifest that binds each claim ``source=`` to a file.

    Discovery reads ``sources.toml`` and ``--source`` and nothing else, so a
    test that expects a claim to resolve has to say so — the same thing a real
    project does. Tests that forgot this were asserting ``scan`` exits 0 about
    a claim the tool could not bind.
    """
    body = "[sources]\n" + "".join(f'{key} = "{path}"\n' for key, path in entries.items())
    (root / "sources.toml").write_text(body, encoding="utf-8")


# --------------------------------------------------------------------------
# B1: a `%` inside a quoted value in a brace-delimited entry is not a comment


def test_a_percent_inside_a_quoted_value_does_not_eat_the_bibliography():
    """The 1b blocker: `quote_counts` assumed only `(...)` entries can hold
    quotes, so in ``@article{a, title = "78% of cases"}`` the ``%`` looked like
    a comment start, the line was cut, the entry lost its closing brace and the
    rest of the file was swallowed. An entire bibliography read as empty, with
    one misleading ``bib-unparsed-entry`` to explain it."""
    from citevouch.bibtex import parse_bib

    result = parse_bib(
        textwrap.dedent(
            """\
            @article{a, author={A}, title = "A study of 78% of cases",
              journal={J}, year={2020}}
            @article{b, title={Second}, author={B}, journal={J}, year={2021}}
            """
        )
    )
    assert sorted(result.entries) == ["a", "b"], result.findings
    assert result.entries["a"].fields["title"] == "A study of 78% of cases"
    assert result.findings == []


def test_a_percent_inside_an_at_comment_never_reaches_the_next_entry():
    from citevouch.bibtex import parse_bib

    result = parse_bib(
        "@comment{ Coverage was 50% of the corpus, see LESSONS }\n"
        "@article{real, title={T}, author={A}, journal={J}, year={2020}}\n"
    )
    assert sorted(result.entries) == ["real"]
    assert result.findings == []


def test_a_percent_inside_a_quoted_value_in_a_parenthesised_entry():
    from citevouch.bibtex import parse_bib

    result = parse_bib(
        '@article(a, note = "78.5% above CRF", title = {T}, author={A}, '
        "journal={J}, year={2020})\n"
        "@article(b, title={Second}, author={B}, journal={J}, year={2021})\n"
    )
    assert sorted(result.entries) == ["a", "b"]
    assert result.entries["a"].fields["note"] == "78.5% above CRF"


# --------------------------------------------------------------------------
# B2: CJK text has no spaces, so word-boundary logic cannot assume ASCII


def test_a_short_chinese_quote_is_found_exactly():
    """The 1b blocker that mattered most for this project's own users: the word
    character class called every CJK character a word character, so no Chinese
    quote could ever end at a boundary unless a space followed it. Every short
    Chinese quote became a false ``quote-missing`` (high severity)."""
    match = find_in_pages("构式网络很小", pages("论文指出：构式网络很小。我们复核了它。"))
    assert match.tier == "exact", match.reason
    assert match.found


def test_a_chinese_quote_ending_in_a_full_stop_is_found_exactly():
    """Same bug, one level down: even with ``isalnum`` boundaries, a quote
    whose last character is ``。`` still needs a non-word character after it,
    and CJK prose does not put spaces there."""
    match = find_in_pages("构式网络很小。", pages("论文指出：构式网络很小。我们复核了它。"))
    assert match.tier == "exact", match.reason


def test_a_chinese_quote_in_the_middle_of_a_sentence_is_found():
    match = find_in_pages("我们复核了它", pages("论文指出：构式网络很小。我们复核了它。"))
    assert match.tier == "exact", match.reason


def test_english_boundaries_still_reject_a_match_inside_words():
    """The strict direction has to survive the loosening: "in the paper" must
    not be found inside "a bin the papers"."""
    assert find_in_pages("in the paper", pages("a bin the papers are listed")).tier != "exact"
    assert find_in_pages("in the paper", pages("as shown in the paper today")).tier == "exact"


def test_a_four_character_chinese_quote_is_not_refused_for_being_short():
    """The squashed tier's floor was 12 characters, a budget set for Latin
    text. Six Chinese characters carry roughly what twelve Latin ones do, so
    the floor is script-dependent; at the old floor this came back ``none``."""
    match = find_in_pages("构式网络", pages("前面构式网络后面"))
    assert match.tier != "none", match.reason


# --------------------------------------------------------------------------
# M1: a bare space is not a thousands separator


def test_a_run_of_years_does_not_become_numbers_nobody_wrote():
    """``numbers_in('2019 2020 2021')`` returned ``('2019 202','0 202','1')``.
    Those strings went into the ledger and were later compared against the
    source, so a manuscript whose only sin was listing three years reported a
    number that appeared nowhere."""
    assert numbers_in("2019 2020 2021") == ("2019", "2020", "2021")


def test_a_thousands_separator_is_still_one_number():
    assert numbers_in("154,391 sentences") == ("154,391",)
    assert numbers_in("1,269,000") == ("1,269,000",)


def test_every_reported_number_survives_masking():
    """The two patterns are allowed to differ, but only one way round: masking
    may swallow more than reporting (masking too much is harmless), never less.
    """
    from citevouch.matching import mask_numbers
    from citevouch.textnorm import MASK_PATTERN

    for text in ("1 000 and 2019 2020", "48.4% of 40,688", "pages 213–226"):
        for match in MASK_PATTERN.finditer(text):
            assert match.group(0), text
        masked = mask_numbers(text)
        for number in numbers_in(text):
            assert number in text
            assert masked.count("\x00") >= 1


# --------------------------------------------------------------------------
# M2: deleting the manuscript must not make the check pass


def test_a_deleted_manuscript_is_reported_not_ignored(tmp_path: Path):
    """``verify`` guarded with ``exists() and ...``, so a missing manuscript
    skipped the hash comparison entirely and every still-present PDF matched:
    the command printed "1 verified" and exited 0 about a document that was not
    there. Deleting the thing under review was a way to pass the check."""
    (tmp_path / "papers").mkdir()
    (tmp_path / "papers" / "src.txt").write_text("The quote is here.", encoding="utf-8")
    bind(tmp_path, src="papers/src.txt")
    (tmp_path / "m.md").write_text(
        "```claim id=c1 source=src\nquote: |\n  The quote is here.\n```\n",
        encoding="utf-8",
    )
    options = ScanOptions(manuscript="m.md", root=str(tmp_path))
    ledger, _findings = scan(options)
    assert verify(ledger, options).ok

    (tmp_path / "m.md").unlink()
    result = verify(ledger, options)
    assert not result.ok
    assert [f.code for f in result.findings] == ["ledger-stale"]
    assert "no longer exists" in result.findings[0].message
    assert result.skipped == 1


def test_a_ledger_about_a_different_document_says_so(tmp_path: Path):
    """The hash comparison is only a drift check if both sides are the same
    document. Pointed at another file it would report "your manuscript
    changed" and send the author hunting for an edit nobody made."""
    (tmp_path / "a.md").write_text(
        "```claim id=c1 source=src\nquote: |\n  x\n```\n", encoding="utf-8"
    )
    (tmp_path / "b.md").write_text("something else entirely\n", encoding="utf-8")
    (tmp_path / "src.txt").write_text("x", encoding="utf-8")
    bind(tmp_path, src="src.txt")
    options_a = ScanOptions(manuscript="a.md", root=str(tmp_path))
    ledger, _ = scan(options_a)
    options_b = ScanOptions(manuscript="b.md", root=str(tmp_path))
    result = verify(ledger, options_b)
    assert not result.ok
    assert result.findings[0].code == "ledger-stale"
    assert "a.md" in result.findings[0].message


# --------------------------------------------------------------------------
# M3: a hand-edited ledger must not crash out of the exit-code contract


@pytest.mark.parametrize(
    ("value", "expected"),
    [("3", 3), ("3.0", 3), (3.0, 3), (3, 3), (None, None), ("x", None), (True, None)],
)
def test_a_page_value_from_a_hand_edited_ledger_is_coerced(value, expected):
    from citevouch.model import _as_page

    assert _as_page(value) == expected


def test_a_ledger_with_a_string_page_still_verifies(tmp_path: Path):
    """``page=raw.get("page")`` kept whatever JSON held. A quoted page number
    reached ``claim.page != match.page`` as a string, and the TypeError escaped
    as an uncaught traceback - exit code 1, which in this tool means "findings
    reached the threshold"."""
    (tmp_path / "src.txt").write_text("The quote is here.", encoding="utf-8")
    bind(tmp_path, src="src.txt")
    (tmp_path / "m.md").write_text(
        "```claim id=c1 source=src page=1\nquote: |\n  The quote is here.\n```\n",
        encoding="utf-8",
    )
    options = ScanOptions(manuscript="m.md", root=str(tmp_path))
    ledger, _ = scan(options)
    blob = ledger.to_json()
    blob["claims"][0]["page"] = "1"
    restored = Ledger.from_json(blob)
    assert restored.claims[0].page == 1
    result = verify(restored, ScanOptions(manuscript="m.md", root=str(tmp_path)))
    assert result.verified == 1


def test_a_zero_schema_ledger_is_refused(tmp_path: Path):
    """Schema numbers start at 1; a 0 was not written by this tool, and
    guessing which generation of neither is not a service."""
    (tmp_path / "ledger.json").write_text(
        json.dumps({"schema": 0, "claims": []}), encoding="utf-8"
    )
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "citevouch",
            "verify",
            "m.md",
            "--root",
            str(tmp_path),
            "--ledger",
            "ledger.json",
        ],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "schemas start at 1" in proc.stderr


# --------------------------------------------------------------------------
# M4: an unreadable source is one finding, not a pile of false verdicts


def test_an_unreadable_source_does_not_manufacture_quote_missing(tmp_path: Path):
    """A PDF nobody could read has no pages; searching no pages can only say
    "not found", which is a verdict about the author's quote that is really a
    verdict about the file. It was also reported two or three times over, once
    per pass."""
    (tmp_path / "broken.pdf").write_text("not really a pdf", encoding="utf-8")
    bind(tmp_path, broken="broken.pdf")
    (tmp_path / "m.md").write_text(
        "```claim id=c1 source=broken\nquote: |\n  Some words that are not there\n```\n",
        encoding="utf-8",
    )
    options = ScanOptions(manuscript="m.md", root=str(tmp_path))
    ledger, _ = scan(options)
    result = verify(ledger, options)
    codes = [f.code for f in result.findings]
    assert "quote-missing" not in codes, codes
    assert codes.count("source-unreadable") == 1, codes
    assert result.skipped == 1


def test_the_same_finding_is_not_listed_twice(tmp_path: Path):
    """`check` runs scan and verify and concatenates their findings; the same
    unreadable PDF is discovered by both passes. One line per fact."""
    from citevouch.cli import main

    (tmp_path / "broken.pdf").write_text("not really a pdf", encoding="utf-8")
    bind(tmp_path, broken="broken.pdf")
    (tmp_path / "m.md").write_text(
        "```claim id=c1 source=broken\nquote: |\n  Some words that are not there\n```\n",
        encoding="utf-8",
    )
    code = main(["check", "m.md", "--root", str(tmp_path)])
    assert code == 1


# --------------------------------------------------------------------------
# M5: a fuzzy match is never a success


def test_a_fuzzy_match_fails_even_at_fail_on_high(tmp_path: Path):
    """AGENTS.md rule 2 says a fuzzy match "must never exit 0 on its own".
    That was true of the severity table and false of the code: quote-fuzzy is
    medium, the default threshold is high, so the run reported success about a
    claim the tool had just said it could not verify."""
    from citevouch.cli import main

    (tmp_path / "src.txt").write_text(
        "We trained the model on a large corpus of annotated sentences.", encoding="utf-8"
    )
    bind(tmp_path, src="src.txt")
    (tmp_path / "m.md").write_text(
        "```claim id=c1 source=src\nquote: |\n  We trained the model on a huge corpus "
        "of annotated sentences.\n```\n",
        encoding="utf-8",
    )
    main(["scan", "m.md", "--root", str(tmp_path)])
    code = main(["verify", "m.md", "--root", str(tmp_path), "--fail-on", "high"])
    assert code == 1


# --------------------------------------------------------------------------
# M6: --use-recorded is still a check on the recorded document


def test_use_recorded_refuses_a_ledger_for_another_manuscript(tmp_path: Path):
    from citevouch.cli import main

    (tmp_path / "src.txt").write_text("The quote is here.", encoding="utf-8")
    (tmp_path / "a.md").write_text(
        "```claim id=c1 source=src page=1\nquote: |\n  The quote is here.\n```\n",
        encoding="utf-8",
    )
    (tmp_path / "b.md").write_text("a different document\n", encoding="utf-8")
    bind(tmp_path, src="src.txt")
    assert main(["scan", "a.md", "--root", str(tmp_path)]) == 0
    code = main(["check", "b.md", "--root", str(tmp_path), "--use-recorded"])
    assert code == 1


# --------------------------------------------------------------------------
# The version is written once


def test_the_package_reports_the_declared_version():
    """``__version__`` was a literal in ``__init__.py`` while the release tool
    rewrote ``pyproject.toml``. For four releases ``citevouch --version``, the
    SARIF driver version and every ledger's ``tool_version`` said 0.1.0 while
    the wheel was something else."""
    import tomllib

    repo = Path(__file__).resolve().parents[1]
    project = tomllib.loads((repo / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["dynamic"] == ["version"], "the version should not be a second literal"
    assert "version" not in project
    assert (repo / "src" / "citevouch" / "_version.py").exists()
    assert __version__ == _read_version_module(repo)


def _read_version_module(repo: Path) -> str:
    text = (repo / "src" / "citevouch" / "_version.py").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("__version__"):
            return line.split('"')[1]
    raise AssertionError("no __version__ in _version.py")


def test_nothing_else_writes_the_version_down():
    """A second copy is how the first copy went stale."""
    repo = Path(__file__).resolve().parents[1]
    for path in (repo / "src").rglob("*.py"):
        if path.name == "_version.py":
            continue
        assert "__version__ =" not in path.read_text(encoding="utf-8"), path
