"""A replacement character is a character, unless the reader had to invent it.

Round 202.  Three guards - `verify`, `draft` and `doctor` - learned that a
quotation holding U+FFFD was never decoded, and all three asked the question of
the *text*: ``"\ufffd" in quote``.  That is not the same question.  A paper about
encodings quotes the character on purpose, with the same sentence printed on the
page, and every reader refused the claim, told the author to convert a file that
had lost nothing, and skipped the one comparison that would have succeeded.

The question is whether the *reading* replaced a byte.  Only the decoder knows,
so `textnorm.read_text_and_loss` reports it and `read_loses_bytes` asks it.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

NL = chr(10)
B3 = chr(96) * 3
ROOT = Path(__file__).resolve().parent.parent

#: U+FFFD written as an escape, so the source of this file stays plain ASCII.
FFFD = chr(0xFFFD)

#: A sentence that quotes a replacement character on purpose - the way a paper
#: about text encodings would.  The page prints it back verbatim.
QUOTE = f"Notepad wrote {FFFD} where the byte could not be decoded."
PAGE = "Discussion" + NL + QUOTE + NL

#: What the tool read when the file really was GBK.  Not about the page.
GBK_QUOTE = "本文收集了六万八千个例句，全部来自语料库中的真实文本。"


def _run(root: Path, *argv: str) -> tuple[int, str]:
    """Run `citevouch` in ``root`` and return its exit code and its output."""
    env = {
        **dict(__import__("os").environ),
        "PYTHONPATH": str(ROOT / "src"),
        "PYTHONIOENCODING": "utf-8",
    }
    proc = subprocess.run(
        [sys.executable, "-m", "citevouch", *argv],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )
    return proc.returncode, proc.stdout + proc.stderr


def _project(tmp_path: Path, quote: str = QUOTE, page: str = PAGE) -> Path:
    """A project whose manuscript is valid UTF-8 and prints U+FFFD on purpose."""
    (tmp_path / "page.txt").write_text(page, encoding="utf-8", newline=NL)
    (tmp_path / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
    )
    manuscript = (
        "# Method"
        + NL
        + NL
        + B3
        + "claim id=c1 source=paper page=1"
        + NL
        + "quote: |"
        + NL
        + "  "
        + quote
        + NL
        + B3
        + NL
    )
    (tmp_path / "manuscript.md").write_text(manuscript, encoding="utf-8", newline=NL)
    return tmp_path


def _codes(root: Path, *argv: str) -> tuple[int, list[str]]:
    code, output = _run(root, *argv)
    return code, [line.split()[0] for line in output.splitlines() if line.startswith("[")]


class TestTheCharacterIsInThePaper:
    """A lossless file's replacement character is a character the author wrote."""

    def test_the_quote_is_found(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        code, output = _run(root, "check", "manuscript.md", "--root", ".")
        assert code == 0, output
        assert "quote-found" in output, output
        assert "claim-not-decoded" not in output, output

    def test_the_tally_says_it_was_checked_not_skipped(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _code, output = _run(root, "check", "manuscript.md", "--root", ".")
        assert "1 claim — 1 verified, 0 moved, 0 missing" in output, output

    def test_the_file_really_did_decode_without_loss(self, tmp_path: Path) -> None:
        """The premise of the case, measured rather than assumed."""
        sys.path.insert(0, str(ROOT / "src"))
        from citevouch.textnorm import read_loses_bytes

        root = _project(tmp_path)
        raw = (root / "manuscript.md").read_bytes()
        assert raw.decode("utf-8")
        assert read_loses_bytes(root / "manuscript.md") is False

    @pytest.mark.parametrize("dialect", ["fence", "comment", "table"])
    def test_every_dialect_agrees(self, tmp_path: Path, dialect: str) -> None:
        root = _project(tmp_path)
        if dialect == "comment":
            body = (
                "# Method"
                + NL
                + NL
                + "<!-- claim id=c1 source=paper page=1 -->"
                + NL
                + QUOTE
                + NL
                + "<!-- /claim -->"
                + NL
            )
        elif dialect == "table":
            body = (
                "| id | source | page | quote | text |"
                + NL
                + "| --- | --- | --- | --- | --- |"
                + NL
                + f"| c1 | paper | 1 | {QUOTE} | t |"
                + NL
            )
        else:
            body = (
                "# Method"
                + NL
                + NL
                + B3
                + "claim id=c1 source=paper page=1"
                + NL
                + "quote: |"
                + NL
                + "  "
                + QUOTE
                + NL
                + B3
                + NL
            )
        (root / "manuscript.md").write_text(body, encoding="utf-8", newline=NL)
        code, output = _run(root, "check", "manuscript.md", "--root", ".")
        assert code == 0, (dialect, output)
        assert "quote-found" in output, (dialect, output)

    def test_the_recorded_pass_agrees_with_the_live_one(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        assert _run(root, "scan", "manuscript.md", "--root", ".")[0] == 0
        live = _codes(root, "check", "manuscript.md", "--root", ".")
        recorded = _codes(root, "check", "manuscript.md", "--root", ".", "--use-recorded")
        assert live == recorded
        assert live == (0, ["[info]"])


class TestWhatIsStillRefused:
    """The guard this round softens still has to fire on a real failed decode."""

    def test_a_gbk_manuscript_is_still_refused(self, tmp_path: Path) -> None:
        root = _project(tmp_path, quote=GBK_QUOTE, page="Preface" + NL + GBK_QUOTE + NL)
        manuscript = "# Method" + NL + NL + B3 + "claim id=c1 source=paper page=1" + NL
        manuscript += "quote: |" + NL + "  " + GBK_QUOTE + NL + B3 + NL
        (root / "manuscript.md").write_bytes(manuscript.encode("gbk"))
        code, output = _run(root, "check", "manuscript.md", "--root", ".")
        assert code == 1, output
        assert "claim-not-decoded" in output, output
        assert "quote-missing" not in output, output

    def test_a_gbk_manuscript_is_refused_by_doctor_too(self, tmp_path: Path) -> None:
        root = _project(tmp_path, quote=GBK_QUOTE, page="Preface" + NL + GBK_QUOTE + NL)
        manuscript = "# Method" + NL + NL + B3 + "claim id=c1 source=paper page=1" + NL
        manuscript += "quote: |" + NL + "  " + GBK_QUOTE + NL + B3 + NL
        (root / "manuscript.md").write_bytes(manuscript.encode("gbk"))
        code, output = _run(root, "doctor", "--root", ".", "--manuscript", "manuscript.md")
        assert code == 1, output
        assert "[FAIL] claims" in output, output

    def test_a_lossless_file_with_no_replacement_character_is_untouched(
        self, tmp_path: Path
    ) -> None:
        root = _project(
            tmp_path,
            quote="The method works.",
            page="Discussion" + NL + "The method works." + NL,
        )
        code, output = _run(root, "check", "manuscript.md", "--root", ".")
        assert code == 0, output
        assert "quote-found" in output, output

    def test_a_genuine_miss_is_still_a_miss(self, tmp_path: Path) -> None:
        root = _project(tmp_path, quote="A sentence no page prints.", page=PAGE)
        code, output = _run(root, "check", "manuscript.md", "--root", ".")
        assert code == 1, output
        assert "quote-missing" in output, output


class TestDraftReadsTheSameFlag:
    """`draft` proposes from the same text, so it needs the same answer."""

    def test_a_proposal_is_made_from_a_lossless_file(self, tmp_path: Path) -> None:
        (tmp_path / "page.txt").write_text(PAGE, encoding="utf-8", newline=NL)
        (tmp_path / "sources.toml").write_text(
            "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
        )
        (tmp_path / "manuscript.md").write_text(
            "# Method" + NL + NL + "Notepad wrote " + FFFD + " where the byte could not be"
            " decoded [@paper]." + NL,
            encoding="utf-8",
            newline=NL,
        )
        code, output = _run(tmp_path, "draft", "manuscript.md", "--root", ".")
        assert code == 0, output
        written = (tmp_path / "claims.md").read_text(encoding="utf-8")
        assert "never decoded" not in written, written
        assert "1 claim block(s) proposed" in output, output


class TestTheReaderKnowsWhichBranchItTook:
    """Each way of reading a file has to report its own loss, not a neighbour's."""

    def test_a_bomless_utf16_manuscript_lost_nothing(self, tmp_path: Path) -> None:
        """The swap branch reads a clean UTF-16 file; it did not replace a byte."""
        from citevouch.textnorm import proven_codec, read_loses_bytes, read_text

        body = "本文收集了六万八千个例句，全部来自语料库中的真实文本。" * 6
        raw = body.encode("utf-16-le")
        # The premise: no BOM and no NUL run, so the swap branch is what reads it.
        assert proven_codec(raw) is None
        with pytest.raises(UnicodeDecodeError):
            raw.decode("utf-8")
        path = tmp_path / "utf16.md"
        path.write_bytes(raw)
        assert read_text(path) == body
        assert read_loses_bytes(path) is False

    def test_a_declared_encoding_lost_nothing(self, tmp_path: Path) -> None:
        """A strict decode through the declared codec is a clean read."""
        from citevouch.textnorm import read_loses_bytes, read_text

        body = "<meta charset='gbk'>" + NL + GBK_QUOTE + NL
        raw = body.encode("gbk")
        with pytest.raises(UnicodeDecodeError):
            raw.decode("utf-8")
        path = tmp_path / "declared.html"
        path.write_bytes(raw)
        assert read_text(path) == body
        assert read_loses_bytes(path) is False


class TestWhatTheOtherReadersSayAboutALosslessFile:
    """`draft` and `doctor` may not borrow a problem the file does not have."""

    def test_draft_still_says_no_citations_were_found(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        (root / "manuscript.md").write_text(
            "# Method" + NL + NL + "Notepad wrote " + FFFD + " here, with no citation." + NL,
            encoding="utf-8",
            newline=NL,
        )
        code, output = _run(root, "draft", "manuscript.md", "--root", ".")
        assert code == 0, output
        assert "no citations were found" in output, output
        assert "never decoded" not in output, output
        assert "iconv" not in output, output

    def test_doctor_says_the_claims_check_passed(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        code, output = _run(root, "doctor", "--root", ".", "--manuscript", "manuscript.md")
        assert code == 0, output
        assert "[ok  ] claims" in output, output
        assert "never decoded" not in output, output


class TestALossThatHasNothingToDoWithReplacementCharacters:
    """The flag is measured by the decoder, so a truncated file sets it too."""

    def test_a_half_written_utf16_file_is_reported_as_lossy(self, tmp_path: Path) -> None:
        """A byte-order mark names the encoding; it does not promise even bytes.

        The file is a real UTF-16 document with one stray byte appended, which
        is what a half-written copy looks like.  `proven_codec` still answers
        ``utf-16``, so this exercises the branch a replacement character can
        never reach: the loss is a trailing byte, not a substituted one.
        """
        from citevouch.textnorm import proven_codec, read_loses_bytes, read_text

        body = "The corpus contains 154,391 utterances." + NL
        raw = body.encode("utf-16") + b"A"
        path = tmp_path / "truncated.md"
        path.write_bytes(raw)
        assert proven_codec(raw) == "utf-16"
        assert read_text(path).startswith("The corpus contains")
        assert read_loses_bytes(path) is True
