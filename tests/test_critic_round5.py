"""The sixth review: three majors and the smaller things next to them.

Each test here failed before its fix. A regression test that was already green
records a fix; it does not defend one.

M1  the one-line HTML dialect - the exact shape both READMEs show - parsed to
    zero claims and exited 0, because the branch required that the line carry
    no `-->`.
M2  `~~~` fences were not recognised, so a claim inside a tilde-fenced sample
    was read as a real claim and reported `quote-found`: a verified verdict on
    a specimen nobody meant to check.
M3  `_mini_toml` raised on any non-string value, and the caller swallows that
    into an empty manifest - so on Python 3.10 one `enabled = true` unbound
    every key in the file, while 3.11+ read it fine.
m1  the extraction cache was keyed by content hash alone, so a changed reader
    (a pypdf upgrade) reused text it did not produce.
m2  the release notes were "the last forty commits" rather than the range
    since the previous tag.
m3  the acceptance list told Windows readers to run `.venv/bin/pip`.
m4  the four-backtick rule was enforced but never written down anywhere a
    manuscript author would look.
"""

from __future__ import annotations

import pathlib
import re
import sys

from citevouch import sources
from citevouch.cli import main
from citevouch.manuscript import parse_manuscript
from citevouch.sources import _mini_toml

REPO = pathlib.Path(__file__).resolve().parent.parent


def _project(tmp_path):
    (tmp_path / "papers").mkdir()
    (tmp_path / "papers" / "p.txt").write_text(
        "The corpus contains 154,391 utterances.\n", encoding="utf-8"
    )
    (tmp_path / "sources.toml").write_text('[sources]\np = "papers/p.txt"\n', encoding="utf-8")
    return tmp_path


# --- M1: the documented one-line HTML form --------------------------------


def test_the_one_line_html_form_in_the_readme_parses(tmp_path, capsys):
    """The shape both READMEs show, verbatim, must produce a claim."""
    root = _project(tmp_path)
    (root / "m.md").write_text(
        "<!-- claim: c2 source=p page=1 -->\n>> The corpus contains 154,391 utterances.\n",
        encoding="utf-8",
    )
    parsed = parse_manuscript((root / "m.md").read_text(encoding="utf-8"), path="m.md")
    assert parsed.findings == []
    assert [claim.id for claim in parsed.claims] == ["c2"]
    assert parsed.claims[0].page == 1

    code = main(["check", "m.md", "--root", str(root)])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "1 claim — 1 verified" in out


def test_the_one_line_form_stops_at_the_next_construct():
    """It has no terminator of its own, so a following claim must not be eaten."""
    text = (
        "<!-- claim: c1 source=p page=1 -->\n"
        ">> first quote\n"
        "```claim id=c2 source=p page=2\n"
        "quote: |\n"
        "  second quote\n"
        "```\n"
    )
    parsed = parse_manuscript(text, path="m.md")
    assert [claim.id for claim in parsed.claims] == ["c1", "c2"]
    assert parsed.claims[0].quote == "first quote"


def test_the_one_line_form_ends_at_a_blank_line():
    text = (
        "<!-- claim: c1 source=p page=1 -->\n"
        ">> first quote\n"
        "\n"
        "Some prose that is not part of the claim.\n"
    )
    parsed = parse_manuscript(text, path="m.md")
    assert len(parsed.claims) == 1
    assert parsed.claims[0].quote == "first quote"


# --- M2: tilde fences -----------------------------------------------------


def test_a_claim_inside_a_tilde_fenced_sample_is_not_a_claim():
    text = (
        "Here is what a claim looks like:\n"
        "\n"
        "~~~markdown\n"
        "```claim id=c1 source=p page=1\n"
        "quote: |\n"
        "  a sentence that is not in any source\n"
        "```\n"
        "~~~\n"
    )
    parsed = parse_manuscript(text, path="m.md")
    assert parsed.claims == []
    assert parsed.findings == []


def test_a_tilde_fence_is_closed_by_tildes_only():
    """```claim``` inside ~~~ must not be closed by the sample's backticks."""
    text = "~~~\n```claim id=c1 source=p page=1\nquote: |\n  x\n```\n~~~\n"
    parsed = parse_manuscript(text, path="m.md")
    assert parsed.claims == []


def test_an_unclosed_tilde_sample_that_swallowed_a_claim_is_reported():
    text = (
        "~~~\n"  # never closed
        "\n"
        "```claim id=c1 source=p page=1\n"
        "quote: |\n"
        "  x\n"
        "```\n"
    )
    parsed = parse_manuscript(text, path="m.md")
    assert [finding.code for finding in parsed.findings] == ["claim-block-unclosed"]
    assert parsed.findings[0].line == 1


# --- M3: a non-string value must not take the whole manifest ---------------


def test_a_boolean_value_does_not_discard_the_other_keys(tmp_path, capsys):
    root = _project(tmp_path)
    (root / "sources.toml").write_text(
        '[sources]\np = "papers/p.txt"\nenabled = true\nratio = 3.5\n', encoding="utf-8"
    )
    (root / "m.md").write_text(
        "```claim id=c1 source=p page=1\nquote: |\n  The corpus contains 154,391 utterances.\n```\n",
        encoding="utf-8",
    )
    assert sources.load_manifest(root) == {"p": "papers/p.txt"}
    code = main(["check", "m.md", "--root", str(root)])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "1 claim — 1 verified" in out


def test_the_subset_reader_agrees_with_tomllib_on_non_string_values():
    text = '[sources]\np = "papers/p.txt"\nenabled = true\n'
    assert _mini_toml(text)["sources"] == {"p": "papers/p.txt"}
    try:
        import tomllib
    except ImportError:  # 3.10: nothing to compare against
        return
    full = tomllib.loads(text)["sources"]
    for key, value in _mini_toml(text)["sources"].items():
        assert full[key] == value


def test_a_structural_error_still_discards_the_manifest(tmp_path):
    """Tolerance for values must not become tolerance for a broken file."""
    root = _project(tmp_path)
    (root / "sources.toml").write_text('[sources]\np = "papers/p.txt"\nthis is not a pair\n')
    assert sources.load_manifest(root) == {}


# --- m1: the cache remembers which reader produced it ----------------------


def test_a_cache_written_by_another_reader_is_not_trusted(tmp_path):
    root = _project(tmp_path)
    path = root / "papers" / "p.txt"
    pages, problem = sources.extract_pages(path, root)
    assert problem is None
    cached = sources.cache_root(root) / f"{sources.sha256_file(path)}.json"
    assert cached.is_file()

    import json

    blob = json.loads(cached.read_text(encoding="utf-8"))
    assert blob["tool"] and blob["extractor"] == "plain"
    blob["extractor"] = "some-other-extractor"
    cached.write_text(json.dumps(blob), encoding="utf-8")

    again, _ = sources.extract_pages(path, root)
    assert [page.text for page in again] == [page.text for page in pages]
    rewritten = json.loads(cached.read_text(encoding="utf-8"))
    assert rewritten["extractor"] == "plain"


def test_the_cache_names_every_extractor_that_could_run():
    assert sources.extractor_candidates(".txt") == ("plain",)
    assert sources.extractor_candidates(".MD") == ("plain",)
    pdf = sources.extractor_candidates(".pdf")
    assert pdf[-1] == "pdftotext" and pdf[0].startswith(("pypdf-", "pdftotext"))
    # An unknown suffix goes through pdftotext and falls back to a plain read,
    # so both names must be acceptable on a cache hit.
    assert sources.extractor_candidates(".docx") == ("pdftotext", "plain")


# --- m2: release notes describe this release ------------------------------


def test_the_release_notes_come_from_the_range_since_the_previous_tag():
    """The logic lives in tools/release_notes.sh so a test can run it. Asserting
    on the workflow text would only prove the string was typed."""
    script = (REPO / "tools" / "release_notes.sh").read_text(encoding="utf-8")
    assert "git describe --tags --abbrev=0" in script
    assert 'range="${previous}..${tag}"' in script
    assert "-n 40" not in script, "the last forty commits is not a release range"


# --- m3 / m4: what the documents promise ----------------------------------


def test_the_acceptance_list_names_a_venv_path_that_exists_on_windows():
    agents = (REPO / "AGENTS.md").read_text(encoding="utf-8")
    standards = (REPO / "docs" / "code-standards.md").read_text(encoding="utf-8")
    for name, text in (("AGENTS.md", agents), ("docs/code-standards.md", standards)):
        assert ".venv/Scripts/pip install -e ." in text, name
        for line in text.splitlines():
            if ".venv/bin/pip" in line:
                assert "posix" in line.lower(), f"{name}: {line}"


def test_both_readmes_tell_authors_to_fence_samples_with_four_backticks():
    for name in ("README.md", "README.zh-CN.md"):
        text = (REPO / name).read_text(encoding="utf-8")
        assert re.search(r"four\*{0,2} ?\*{0,2}backticks|四个\*{0,2}反引号", text), name
        assert "claim-block-unclosed" in text, name


def test_the_finding_says_how_to_fix_it():
    text = (REPO / "src" / "citevouch" / "manuscript.py").read_text(encoding="utf-8")
    assert text.count("four backticks") >= 3


# --- m5: a redirected console is still a usable console --------------------


def test_a_pipe_through_a_legacy_console_keeps_the_exit_code(tmp_path, monkeypatch):
    """`| cat` and `> file` are how CI captures this tool; the code must survive."""
    root = _project(tmp_path)
    (root / "m.md").write_text(
        "```claim id=c1 source=p page=1\nquote: |\n  a sentence that is not there\n```\n"
        "【原文】a bare marker with no claim block\n",
        encoding="utf-8",
    )
    out = root / "out.txt"
    with open(out, "w", encoding="cp1252") as handle:
        monkeypatch.setattr(sys, "stdout", handle)
        code = main(["check", "m.md", "--root", str(root)])
    assert code == 1
    payload = out.read_bytes()
    assert b"quote-missing" in payload
    assert "【原文】".encode() in payload  # UTF-8 even to a cp1252 stream
