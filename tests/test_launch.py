"""The launch material is copy, so the only thing worth testing is its shape.

`docs/backlog.md` promises four files under `docs/launch/`, each of which has to
carry the two things that make it postable: the words, and the notes about how to
post them. Both halves rot differently. The copy goes stale when the install line
changes; the notes disappear when somebody tidies a file down to "just the text".

So: every file exists, every file fences its title so it survives a copy out,
every file pins the version the package declares, and every file carries posting
notes. What the copy *says* is a judgement call and is not tested here.

Two guards here were written badly first and fixed after the reverse check in
`_reverse_launch.py` caught them:

- `len(text) > 1200` stood in for "has enough copy". That is a number invented to
  make a test pass, not a fact about a good post, so it is gone.
- `"```" in text` stood in for "the title is fenced". Every one of these files
  contains a fence somewhere - the claim block, the install line - so removing
  the fence around the title left the guard green. It now looks at the title
  region specifically.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LAUNCH = ROOT / "docs" / "launch"

EXPECTED = ("show-hn.md", "v2ex.md", "xiaohongshu.md", "douyin-30s.md")

# The four files address four audiences, so they do not share a heading.
# What they do share is that the last thing in the file is advice to the person
# about to post it, not more copy.
NOTES_HEADINGS = (
    "## Notes for whoever posts this",
    "## 发帖备注",
    "## 制作备注",
)

# Where the title lives in each file, and what ends the title region.
TITLE_MARKERS = ("**Title**", "**标题")
REGION_ENDS = ("\n**", "\n## ")

FENCE = re.compile(r"^```[^\n]*\n(?P<body>.*?)^```", re.MULTILINE | re.DOTALL)


def _version() -> str:
    text = (ROOT / "src" / "citevouch" / "_version.py").read_text(encoding="utf-8")
    found = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    assert found is not None
    return found.group(1)


def _title_region(text: str) -> str:
    """The title, and nothing after it until the next bold label or heading.

    The marker is matched, not assumed: `**Title**` is nine characters and
    `**标题**` is six, and slicing both by nine started the region three
    characters into the fence, where an anchored search cannot see it.
    """
    found = [(text.index(marker), marker) for marker in TITLE_MARKERS if marker in text]
    assert found, "no **Title** / **标题 marker at all"
    start, marker = min(found)
    rest = text[start + len(marker) :]
    ends = [rest.index(ending) for ending in REGION_ENDS if ending in rest]
    return rest[: min(ends)] if ends else rest


def test_every_promised_file_exists() -> None:
    missing = [name for name in EXPECTED if not (LAUNCH / name).is_file()]
    assert missing == [], f"docs/backlog.md promises these; they are gone: {missing}"


@pytest.mark.parametrize("name", EXPECTED)
def test_the_title_is_fenced_so_it_survives_a_copy(name: str) -> None:
    region = _title_region((LAUNCH / name).read_text(encoding="utf-8"))
    fenced = [match.group("body").strip() for match in FENCE.finditer(region)]
    fenced = [body for body in fenced if body]
    assert fenced, (
        f"{name} does not fence its title. These posts open with a title copied "
        "out of this file by hand; unfenced, the asterisks and line breaks come "
        "along with it and the title has to be retyped from memory"
    )
    # A title that is only whitespace inside a fence is the same problem wearing
    # the fence as a disguise.
    assert all(len(body) > 8 for body in fenced), f"{name}: a fenced title is too short to post"


@pytest.mark.parametrize("name", EXPECTED)
def test_nothing_advertises_a_version_the_package_does_not_declare(name: str) -> None:
    text = (LAUNCH / name).read_text(encoding="utf-8")
    pins = sorted(set(re.findall(r"citevouch@v(\d+\.\d+\.\d+)", text)))
    stale = [pin for pin in pins if pin != _version()]
    assert stale == [], (
        f"{name} tells people to install {stale} but the package is {_version()}; "
        "the auto-release bump only rewrites the two READMEs, so launch copy is "
        "the one place a pin can be left behind by hand"
    )


@pytest.mark.parametrize("name", EXPECTED)
def test_the_file_carries_how_to_post_it(name: str) -> None:
    text = (LAUNCH / name).read_text(encoding="utf-8")
    assert any(heading in text for heading in NOTES_HEADINGS), (
        f"{name} has no posting notes. The copy is the part that gets rewritten; "
        "the notes are the part that stops the post being a gimmick"
    )


def test_the_one_thing_that_must_not_lead_is_named() -> None:
    # Every file warns against opening with "an agent wrote this", because that
    # is the true answer to a question nobody asked yet, and as a lead it turns
    # the post into an argument about AI instead of about citations.
    silent = [
        name for name in EXPECTED if "AI" not in (LAUNCH / name).read_text(encoding="utf-8")
    ]
    assert silent == [], (
        f"these files never mention the AI question: {silent}. Posting them "
        "unprepared is how the first comment ends up being the only one"
    )
