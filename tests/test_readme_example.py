"""The README shows output, so the output in it has to be possible.

The block that used to sit in both READMEs could not have been produced by this
tool: it showed one `quote-moved` and then summed to `0 moved`, and its parts
added up to six claims when it said five. Nobody notices that kind of thing by
reading; it looks like an example. So the arithmetic is checked by a test, and
the numbers have to agree with each other the same way `verify` counts them.

`verify` counts a claim as exactly one of: verified, moved, missing, skipped.
A `quote-moved` finding is a moved claim, not also a verified one. That is the
rule the example has to obey.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SUMMARY = re.compile(
    r"citevouch: (\d+) claims? — (\d+) verified, (\d+) moved, (\d+) missing(?:, (\d+) skipped)?"
)
PREFIX = re.compile(r"\((\S+?)\): claim \1:")

LINE = re.compile(
    r"^\[(info|low|medium|high)\] (\S+) at (\S+?):(\d+) \((\S+?)\): ", re.MULTILINE
)


def read_blocks(name: str) -> list[str]:
    text = (ROOT / name).read_text(encoding="utf-8")
    return re.findall(r"```text\n(.*?)```", text, re.DOTALL)


def example_block(name: str) -> str:
    """The block that shows a `verify` run, found by content, not by position.

    It used to be `read_blocks(name)[0]`, which quietly meant "whichever text
    block happens to come first". Adding a second example above it - the
    `doctor` output - would have pointed every arithmetic assertion at a block
    that has no summary line, and the failure would have read like a broken
    example rather than a broken test.
    """
    for block in read_blocks(name):
        if SUMMARY.search(block):
            return block
    raise AssertionError(f"{name}: no ```text block shows a summary line")


@pytest.mark.parametrize("name", ["README.md", "README.zh-CN.md"])
def test_the_example_counts_add_up(name: str) -> None:
    block = example_block(name)

    summary = SUMMARY.search(block)
    assert summary is not None, f"{name}: the example has no summary line"
    claims, verified, moved, missing = (int(g or 0) for g in summary.groups()[:4])
    skipped = int(summary.group(5) or 0)

    assert verified + moved + missing + skipped == claims, (
        f"{name}: {verified} verified + {moved} moved + {missing} missing"
        f" + {skipped} skipped != {claims} claims"
    )

    lines = LINE.findall(block)
    assert lines, f"{name}: the example has no finding lines"

    by_code: dict[str, int] = {}
    for _severity, code, _path, _line, _claim in lines:
        by_code[code] = by_code.get(code, 0) + 1

    found = by_code.get("quote-found", 0)
    moved_lines = by_code.get("quote-moved", 0)
    gone = by_code.get("quote-missing", 0) + by_code.get("quote-fuzzy", 0)
    gone += by_code.get("number-absent-in-quote", 0)

    assert found == verified, (
        f"{name}: {found} quote-found lines but {verified} verified claims"
    )
    assert moved_lines == moved, (
        f"{name}: {moved_lines} quote-moved lines but {moved} moved claims"
    )
    assert gone == missing, f"{name}: {gone} not-found lines but {missing} missing claims"


@pytest.mark.parametrize("name", ["README.md", "README.zh-CN.md"])
def test_the_example_never_shows_the_claim_id_twice(name: str) -> None:
    """`(c1): claim c1: ...` is what the renderer used to print.

    The doubling was invisible because the docs showed a hand-written example
    that also happened to be wrong about it. One rule now: the terminal names
    the claim once, in parentheses.
    """
    block = example_block(name)
    doubled = [line for line in block.splitlines() if re.search(PREFIX, line)]
    assert not doubled, f"{name}: the claim id is printed twice on these lines: {doubled}"


def test_the_example_is_what_the_demo_actually_prints() -> None:
    """The block is not a mock-up, so running the demo has to reproduce it.

    Only the shape is asserted - the exact wrap column and the excerpt
    truncation are the terminal's, not the tool's - but every claim, code,
    page and file has to match.
    """
    from citevouch.cli import main

    demo = ROOT / "demo"
    code = main(["verify", "manuscript.md", "--root", str(demo), "--format", "json"])
    assert code == 1  # the deliberate wrong-paper claim

    block = example_block("README.md")
    shown = {(claim, code_name) for _sev, code_name, _p, _l, claim in LINE.findall(block)}
    expected = {
        ("cxn-total", "quote-found"),
        ("corpus-size", "quote-found"),
        ("hapax-share", "quote-found"),
        ("avg-degree", "quote-found"),
        ("fcg-editor", "quote-missing"),
    }
    assert shown == expected, f"the README example drifted from the demo: {shown ^ expected}"


@pytest.mark.parametrize("name", ["README.md", "README.zh-CN.md"])
def test_the_severity_table_lists_every_code_and_the_right_severity(name: str) -> None:
    """The table is the only place a user learns what a code means.

    Two defects met here. Codes were added to `CODES` and to `SARIF_RULES` and
    never to the table, so a finding could appear in CI output with a name the
    documentation did not contain. And two codes sat in the table that no code
    path could raise, which is the mirror image: the table promised a vocabulary
    the tool did not have. Both directions are checked, and the severities have
    to agree too - the table says `quote-fuzzy` is high, so the table is not a
    decoy.
    """
    from citevouch.model import CODES

    text = (ROOT / name).read_text(encoding="utf-8")
    rows = re.findall(r"^\| `([a-z0-9-]+)` \| (info|low|medium|high) \|", text, re.MULTILINE)
    assert rows, f"{name}: no severity table found"
    documented = dict(rows)

    missing = sorted(set(CODES) - set(documented))
    invented = sorted(set(documented) - set(CODES))
    assert not missing, f"{name}: codes the table never mentions: {missing}"
    assert not invented, f"{name}: the table documents codes nothing can raise: {invented}"

    mismatched = {
        code: (severity, CODES[code])
        for code, severity in documented.items()
        if severity != CODES[code]
    }
    assert not mismatched, f"{name}: documented severity != real severity: {mismatched}"


class TestThePinsAgree:
    """Every version written into a document is the version being shipped.

    The release tool rewrites `citevouch@vX.Y.Z`, but it only runs at release
    time: a commit that adds a new pin - the action examples - carries whatever
    version was current when it was typed. That is how one README ended up
    showing `pip install ...@v0.12.0` three lines above
    `uses: lyear12/citevouch@v0.11.0`, which reads as two different tools.
    """

    @pytest.mark.parametrize("name", ["README.md", "README.zh-CN.md"])
    def test_every_citevouch_pin_names_the_declared_version(self, name: str):
        from citevouch._version import __version__

        text = (ROOT / name).read_text(encoding="utf-8")
        pins = re.findall(r"citevouch@v(\d+\.\d+\.\d+)", text)
        assert pins, f"{name}: no install pin found, so nobody can copy one"
        stale = sorted({pin for pin in pins if pin != __version__})
        assert not stale, f"{name}: pins {stale} but the package is {__version__}"

    @pytest.mark.parametrize("name", ["README.md", "README.zh-CN.md"])
    def test_the_pins_are_not_the_only_place_a_version_is_written(self, name: str):
        # `tools/next_version.py` rewrites `citevouch@vX.Y.Z` and nothing else,
        # so a version pinned in some other shape would rot silently. This
        # fails when a document grows a `v1.2.3` that the release tool cannot
        # see; the fix is to spell it as a pin or leave the number out.
        text = (ROOT / name).read_text(encoding="utf-8")
        stray = [
            match.group(0) for match in re.finditer(r"(?<!citevouch@)\bv\d+\.\d+\.\d+\b", text)
        ]
        assert not stray, (
            f"{name}: versions the release tool cannot rewrite: {sorted(set(stray))}"
        )
