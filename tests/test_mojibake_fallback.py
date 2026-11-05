"""The UTF-16 fallback must not turn a readable 8-bit file into rubbish.

The fallback exists because a file saved as UTF-16 without a byte-order mark
has to be judged from its text: notepad's "Unicode" save, Excel's text export
and PowerShell's ``>`` all produce one, and read as UTF-8 those bytes become a
replacement character between every letter.

Being *noisy* as UTF-8 is not the same as being 16-bit, and the difference is
the manuscript case.  A GBK or Big5 manuscript is mostly ASCII - its claim
fences, its ``quote:`` keys and its attribute syntax are ASCII, and only the
prose between them is double-byte - so read as UTF-8 it is noisy in proportion
to how much prose it holds.  The old rule saw that, found a UTF-16 reading
whose noise was smaller, and took it, and the whole file became ``'탑뾾쫎...'``:
fences and keys gone.  The search then found no claim blocks in a manuscript
that had them, and the author was told their manuscript was empty.

The two conditions below are facts about the two file families, not tuning.
Every genuine UTF-16-LE document scores *zero* noise, because byte pairs that
came from a real character cannot decode to a control or a replacement
character; an 8-bit file read that way nearly always scores something.  And the
noise has to be at least a tenth of the file, because a stray byte in a long
UTF-8 paper scores one or two characters and must not move.

Neither condition survives on its own, which is why both are tested here with
measured shapes: a long UTF-8 paper with a few cp1252 bytes reads *clean* as
UTF-16 (noise 0) and is saved only by the share test, and every 8-bit
manuscript measured keeps a nonzero UTF-16 noise and is saved only by that.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from citevouch.cli import main
from citevouch.sources import extract_pages
from citevouch.textnorm import _decode_text, _noise, _strip_bom, read_text

NL = chr(10)
QUOTE = "We collected 40,688 examples in total."

#: A manuscript in the shape a real author writes: prose, then a claim block.
#: The fences and the ``quote:`` key are ASCII in every encoding, and that is
#: the whole reason the old rule misfired.
MANUSCRIPT = (
    "研究问题"
    + NL
    + NL
    + "我们收集了四万零六百八十八个例句，并检验它们在构式语法中的分布。"
    + NL
    + NL
    + "```claim id=c1 source=paper page=1"
    + NL
    + "quote: "
    + QUOTE
    + NL
    + "```"
    + NL
)

TRADITIONAL = "我們收集了四萬零六百八十八個例句，並檢驗它們在構式語法中的分布。"
JAPANESE = "私たちは四万六百八十八の例文を集めました。構文を調べます。"
RUSSIAN = "Корпус содержит 154,391 предложение и 440,528 конструкций."


def _project(tmp_path: Path, manuscript: bytes) -> Path:
    root = tmp_path / "p"
    root.mkdir(parents=True, exist_ok=True)
    (root / "page.txt").write_text(QUOTE + NL, encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
    )
    (root / "manuscript.md").write_bytes(manuscript)
    return root


def _codes(captured: str) -> list[str]:
    return [line.split()[1] for line in captured.splitlines() if line.startswith("[")]


def _readings(raw: bytes) -> tuple[int, int, int]:
    """(noise as UTF-8, its length, noise as UTF-16-LE)."""
    as8 = _strip_bom(raw.decode("utf-8", errors="replace"))
    as16 = _strip_bom(raw.decode("utf-16-le", errors="replace"))
    return _noise(as8), len(as8), _noise(as16)


class TestAnEightBitManuscriptKeepsItsFences:
    """The prose is double-byte, the fence is not, and the fence is what counts."""

    @pytest.mark.parametrize(
        ("encoding", "prose"),
        [("gbk", MANUSCRIPT), ("big5", TRADITIONAL), ("shift_jis", JAPANESE)],
    )
    def test_the_block_is_still_found(self, tmp_path: Path, capsys, encoding: str, prose: str):
        body = prose if prose is MANUSCRIPT else prose + NL + NL + MANUSCRIPT.split(NL + NL)[-1]
        raw = body.encode(encoding)
        noise, length, noise16 = _readings(raw)
        assert noise >= max(4, length // 50), "the UTF-8 reading is noisy"
        assert noise * 10 >= length, "and by a share the old rule acted on"
        assert noise16 != 0, "while the UTF-16 reading is not clean"

        root = _project(tmp_path, raw)
        code = main(["check", "manuscript.md", "--root", str(root)])
        reported = capsys.readouterr().out
        assert "no-claim-blocks" not in reported
        assert code == 0
        assert _codes(reported) == ["quote-found"]

    def test_a_page_with_no_ascii_at_all_is_reported_not_guessed(self, tmp_path: Path):
        # With no ASCII in the file there is nothing to break the fallback's
        # tie, so the bytes stay ambiguous - and ambiguity must not become a
        # verdict about the author's quote.  It reaches the source-encoding
        # guard, which says the words were never searched.
        path = tmp_path / "page.txt"
        path.write_bytes(("我们收集了四万零六百八十八个例句。" + NL).encode("gbk"))
        pages, problem = extract_pages(path, tmp_path, use_cache=False)
        assert pages == []
        assert problem is not None
        assert problem.code == "source-encoding"


class TestTheGenuineSixteenBitFileStillReads:
    """The fallback earns its keep on the files it was written for."""

    @pytest.mark.parametrize(
        "body",
        [
            "研究问题" + NL + NL + "我们收集了例句。" + NL,
            RUSSIAN + NL,
            "研究问题" + NL + NL + RUSSIAN + NL,
            "The corpus contains 154,391 utterances, all annotated." + NL,
        ],
        ids=["chinese", "russian", "mixed", "english"],
    )
    def test_it_is_decoded(self, body: str):
        raw = body.encode("utf-16-le")
        assert _decode_text(raw) == body

    def test_a_manuscript_with_a_mark_is_unaffected(self, tmp_path: Path, capsys):
        # "UTF-16" writes the mark; the fallback never runs at all.
        root = _project(tmp_path, MANUSCRIPT.encode("utf-16"))
        assert main(["check", "manuscript.md", "--root", str(root)]) == 0
        assert _codes(capsys.readouterr().out) == ["quote-found"]


class TestWhatMustNotMove:
    """The cost of being wrong is turning good text into rubbish."""

    def test_a_clean_utf8_file_is_never_reinterpreted(self):
        body = "The corpus contains 154,391 utterances. 摘要：构式语法。" + NL
        assert _decode_text(body.encode("utf-8")) == body

    def test_a_few_stray_bytes_in_a_long_paper_do_not_move_it(self):
        # cp1252 bytes pasted into a UTF-8 paper: noisy enough to pass the
        # absolute threshold, far too small a share to be a 16-bit file - and
        # the UTF-16 reading happens to be clean, so the share is the only
        # thing standing between this file and rubbish.
        base = (
            "The corpus contains 154,391 utterances drawn from spoken French, "
            "and every one of them was annotated by two coders. "
        ) * 4
        raw = base.encode("utf-8") + b"\xe9" * 10
        noise, length, noise16 = _readings(raw)
        assert noise >= max(4, length // 50), "the absolute threshold did fire"
        assert noise16 == 0, "the UTF-16 reading is perfectly clean"
        assert noise * 10 < length, "and the share test is what stops it"
        assert _decode_text(raw) == _strip_bom(raw.decode("utf-8", errors="replace"))

    def test_big_endian_without_a_mark_is_still_not_guessed(self):
        # A Chinese-only big-endian document has no NUL pattern to name it, and
        # swapping a Han character's bytes yields another Han character - so the
        # wrong reading is not clean and this rule does not take it.  The case is
        # genuinely undecidable and stays that way.
        body = (
            "研究问题"
            + NL
            + NL
            + "我们收集了四万零六百八十八个例句，并检验它们在构式语法中的分布。"
            + NL
        )
        raw = body.encode("utf-16-be")
        _, _, noise16 = _readings(raw)
        assert noise16 != 0, "the wrong endianness leaves noise behind"
        assert _decode_text(raw) != body


class TestTheTwoConditionsAreSeparatelyLoadBearing:
    """Each half of the rule has a case only it can decide."""

    def test_the_utf16_reading_being_clean_is_not_enough(self):
        # A long UTF-8 paper with cp1252 bytes pasted in: noisy enough to pass
        # the absolute threshold, and clean as UTF-16, so the share is the only
        # thing that keeps it.  Named after the condition it isolates so that
        # deleting that condition from the rule fails a test that says why.
        base = ("A long UTF-8 paper about corpora and annotation. ") * 20
        raw = base.encode("utf-8") + b"\xe9" * 30
        noise, length, noise16 = _readings(raw)
        assert noise >= max(4, length // 50), "the absolute threshold did fire"
        assert noise16 == 0, "the UTF-16 reading is clean"
        assert noise * 10 < length, "the share is what stops the swap"
        assert _decode_text(raw) == _strip_bom(raw.decode("utf-8", errors="replace"))

    def test_the_noise_share_being_large_is_not_enough(self):
        # Every 8-bit manuscript measured has a large noise share *and* a
        # nonzero UTF-16 reading; the second fact is what stops the swap.
        raw = MANUSCRIPT.encode("gbk")
        noise, length, noise16 = _readings(raw)
        assert noise * 10 >= length
        assert noise16 != 0
        assert _decode_text(raw) == _strip_bom(raw.decode("utf-8", errors="replace"))

    def test_a_source_file_in_another_encoding_reports_rather_than_accuses(
        self, tmp_path: Path
    ):
        # read_text on its own cannot rescue an ambiguous page; the guard that
        # matters is the one in extract_pages, and it is high severity because
        # the words really were never searched.
        path = tmp_path / "page.txt"
        path.write_bytes(TRADITIONAL.encode("big5"))
        assert read_text(path) != TRADITIONAL, "a bare page has no tie-breaker"
        _, problem = extract_pages(path, tmp_path, use_cache=False)
        assert problem is not None
        assert problem.code == "source-encoding"
