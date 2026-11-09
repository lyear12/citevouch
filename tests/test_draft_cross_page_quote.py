"""`draft` found the cross-page match and then quoted one page of it.

The matcher gained the page-run pass so a quotation running off the bottom of
one page can still be found.  `propose_quote` then looked the hit up in
`pages` by `match.page` alone -- the *first* page of the run -- so the verbatim
branch searched a page whose own sentences do not contain the sentence.  It
missed, and the proposal fell back to the medium-confidence path, which quoted
only the half of the sentence that happened to sit on one page.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"}
NL = chr(10)
FF = chr(12)

ACROSS = (
    "We collected a very large number of examples from the corpus and then "
    "filtered them by hand before training the model on the remaining portion."
)
ABSENT = (
    "We gathered a very large number of examples from the corpus and then "
    "screened them by hand before training the model on the rest of it."
)

# The sentence starts on page 2 and runs onto page 3.
PAGES = [
    "A first page about something else entirely, with no bearing on the claim.",
    "We collected a very large number of examples from the corpus and then",
    "filtered them by hand before training the model on the remaining portion.",
    "The appendix lists every file that was touched along the way.",
]

# The same sentence, entirely on page 2.
PAGES_ONE = [
    "A first page about something else entirely, with no bearing on the claim.",
    "We collected a very large number of examples from the corpus and then "
    "filtered them by hand before training the model on the remaining portion.",
    "The appendix lists every file that was touched along the way.",
]


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "citevouch", *args, "--root", str(root)],
        cwd=ROOT,
        env=ENV,
        capture_output=True,
        encoding="utf-8",
    )


def _project(tmp_path: Path, pages: list[str], sentence: str) -> Path:
    root = tmp_path / "p"
    root.mkdir(parents=True, exist_ok=True)
    (root / "page.txt").write_text(FF.join(pages), encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
    )
    (root / "paper.md").write_text(sentence + " [@paper]" + NL, encoding="utf-8", newline=NL)
    return root


def _draft(root: Path) -> tuple[subprocess.CompletedProcess[str], str]:
    proc = _run(root, "draft", "paper.md", "-o", "claims.md")
    written = root / "claims.md"
    return proc, (written.read_text(encoding="utf-8") if written.is_file() else "")


def _quote_field(written: str) -> str:
    """The text of the `quote: |` block, however many lines it takes."""
    match = re.search(r"^quote: \|\n(?P<body>(?:  .*\n)+)", written, re.MULTILINE)
    assert match is not None, written
    return " ".join(line.strip() for line in match.group("body").splitlines()).strip()


class TestASentenceTheSourcePrintsAcrossTwoPages:
    def test_the_sentence_is_reported_as_verbatim(self, tmp_path: Path) -> None:
        root = _project(tmp_path, PAGES, ACROSS)
        _, written = _draft(root)
        assert "1 quoting the sentence verbatim" in written

    def test_the_confidence_is_high_not_medium(self, tmp_path: Path) -> None:
        root = _project(tmp_path, PAGES, ACROSS)
        _, written = _draft(root)
        assert "confidence: high" in written
        assert "confidence: medium" not in written

    def test_the_quote_is_the_whole_sentence(self, tmp_path: Path) -> None:
        root = _project(tmp_path, PAGES, ACROSS)
        _, written = _draft(root)
        assert _quote_field(written) == ACROSS

    def test_the_page_it_names_is_the_page_the_quote_starts_on(self, tmp_path: Path) -> None:
        root = _project(tmp_path, PAGES, ACROSS)
        _, written = _draft(root)
        assert "page=2" in written


class TestTheSinglePageCaseIsUnchanged:
    def test_a_sentence_on_one_page_is_still_verbatim(self, tmp_path: Path) -> None:
        root = _project(tmp_path, PAGES_ONE, ACROSS)
        _, written = _draft(root)
        assert "1 quoting the sentence verbatim" in written
        assert "confidence: high" in written
        assert "page=2" in written

    def test_a_sentence_the_source_does_not_print_still_falls_back(
        self, tmp_path: Path
    ) -> None:
        root = _project(tmp_path, PAGES_ONE, ABSENT)
        _, written = _draft(root)
        assert "0 quoting the sentence verbatim" in written
        assert "confidence: medium" in written


# The run is right, and the page before it dangles: "see also" is a fragment
# with no full stop, so a stitcher that joins the whole file reads it as the
# opening of the next sentence and loses the sentence entirely.
PAGES_DANGLING = [
    "see also",
    "We collected a very large number of examples from the corpus and then",
    "filtered them by hand before training the model on the remaining portion.",
    "The appendix lists every file that was touched along the way.",
]


class TestADanglingPageBeforeTheRun:
    """The pages the match covers, not every page in the file.

    Stitching the whole document looks like the *safer* choice - more text can
    only help, surely - and it is the one way this branch can be made to say
    "not verbatim" about a sentence the source prints exactly.  Sentence
    splitting across a page boundary has no reliable signal: a page that ends
    "see also" has no full stop, so the whole-file pass makes one sentence out
    of two pages and the real sentence is no longer a sentence in it.
    """

    def test_the_sentence_is_still_reported_as_verbatim(self, tmp_path: Path) -> None:
        root = _project(tmp_path, PAGES_DANGLING, ACROSS)
        _, written = _draft(root)
        assert "1 quoting the sentence verbatim" in written

    def test_the_confidence_is_still_high(self, tmp_path: Path) -> None:
        root = _project(tmp_path, PAGES_DANGLING, ACROSS)
        _, written = _draft(root)
        assert "confidence: high" in written
        assert "confidence: medium" not in written

    def test_the_quote_is_the_whole_sentence(self, tmp_path: Path) -> None:
        root = _project(tmp_path, PAGES_DANGLING, ACROSS)
        _, written = _draft(root)
        assert _quote_field(written) == ACROSS
