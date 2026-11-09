"""The UTF-16 swap must not eat a manuscript whose length happens to be even.

Measured before the fix, on a GBK manuscript of 114 bytes - one byte longer than
a 113-byte twin that was read correctly:

    $ citevouch check manuscript.md
    [high] no-claim-blocks at manuscript.md: manuscript.md contains no claim
    blocks, so nothing was checked ... This file has none.

The file had two claim blocks.  Its fences, its ``quote:`` keys and its
``id=``/``source=`` attributes are all ASCII and all survived the UTF-8 reading;
the UTF-16 reading re-paired those bytes into clean-looking text and made every
one of them disappear.  ``draft`` on the same file said no citations had been
written in the style it reads, and ``doctor`` blamed the claim blocks.

The test is not "does it decode to the original" - an 8-bit file never can - but
"does the ASCII skeleton survive", because that skeleton is what the rest of the
tool reads a manuscript through.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from citevouch.cli import main
from citevouch.textnorm import (
    STRUCTURE_RUN,
    _decode_text_and_loss,
    _keeps_the_structure,
    _longest_printable_run,
    _noise,
    _strip_bom,
    read_loses_bytes,
)

NL = chr(10)
B3 = chr(96) * 3
ZH = "本文收集了六万八千个例句，全部来自语料库中的真实文本。"
TRAD = "我們收集了四萬零六百八十八個例句，並檢驗它們在構式語法中的分布。"
JA = "私たちは四万六百八十八の例文を集めました。構文を調べます。"
RU = "Корпус содержит 154,391 предложение и 440,528 конструкций."
FR = "Le corpus contient 40,688 exemples annotés."
QUOTE = "We collected 40,688 examples in total."

MANUSCRIPT = (
    "研究问题"
    + NL
    + NL
    + ZH
    + NL
    + NL
    + B3
    + "claim id=c1 source=paper page=1"
    + NL
    + "quote: |"
    + NL
    + "  "
    + ZH
    + NL
    + B3
    + NL
)


def _project(tmp_path: Path, manuscript: bytes) -> Path:
    root = tmp_path / "p"
    root.mkdir(parents=True, exist_ok=True)
    (root / "page.txt").write_text(ZH + NL, encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
    )
    (root / "manuscript.md").write_bytes(manuscript)
    return root


def _codes(captured: str) -> list[str]:
    return [line.split()[1] for line in captured.splitlines() if line.startswith("[")]


def _readings(raw: bytes) -> tuple[str, str]:
    return (
        _strip_bom(raw.decode("utf-8", errors="replace")),
        _strip_bom(raw.decode("utf-16-le", errors="replace")),
    )


class TestTheSkeletonSurvives:
    """Both halves of the manuscript are readable after the swap decision."""

    @pytest.mark.parametrize("pad", ["", "A"], ids=["even-length", "odd-length"])
    def test_a_gbk_manuscript_keeps_its_fences(self, pad: str):
        raw = (MANUSCRIPT + pad).encode("gbk")
        decoded, _lost_flag = _decode_text_and_loss(raw)
        assert decoded.count(B3) == 2, "the fences are gone from " + repr(decoded[:40])
        assert "quote:" in decoded
        assert "id=c1" in decoded
        assert "source=paper" in decoded

    def test_the_two_lengths_agree(self):
        # The tell was that appending one byte changed the verdict completely.
        even = _decode_text_and_loss(MANUSCRIPT.encode("gbk"))[0]
        odd = _decode_text_and_loss((MANUSCRIPT + "A").encode("gbk"))[0]
        assert odd == even + "A"

    def test_the_prose_is_read_as_mojibake_not_as_hakka(self):
        # The swap produced text that looked like a language, which is why it
        # was invisible: the fences went and nothing else complained.
        decoded, _lost_flag = _decode_text_and_loss(MANUSCRIPT.encode("gbk"))
        assert _noise(decoded) >= 4, "the loss has to still be visible"

    @pytest.mark.parametrize(
        "text,encoding",
        [
            (TRAD + NL, "big5"),
            (JA + NL, "shift_jis"),
            (RU + NL, "cp1251"),
            (FR + NL, "cp1252"),
        ],
        ids=["big5", "sjis", "cp1251", "cp1252"],
    )
    def test_no_other_eight_bit_family_is_swapped(self, text: str, encoding: str):
        raw = text.encode(encoding)
        decoded, _lost_flag = _decode_text_and_loss(raw)
        assert decoded == _strip_bom(raw.decode("utf-8", errors="replace"))


class TestTheRuleItself:
    """Pin the two halves of the rule, so a mutation cannot quietly drop one."""

    def test_a_long_run_in_one_reading_and_not_the_other_is_refused(self):
        assert not _keeps_the_structure(B3 + "claim id=c1 source=paper", "研究问题")
        assert _longest_printable_run(B3 + "claim id=c1") >= STRUCTURE_RUN

    def test_equal_runs_are_kept(self):
        both = B3 + "claim id=c1 source=paper page=1"
        assert _keeps_the_structure(both, both)

    def test_a_longer_run_on_the_other_side_is_kept(self):
        assert _keeps_the_structure("研究问题", B3 + "claim id=c1 source=paper")

    def test_short_runs_say_nothing_either_way(self):
        # A page that carries a figure in ASCII keeps a run of nine there, and
        # the rule must not read that as structure - the runs it compares come
        # from raw bytes, where a UTF-16 page has no run longer than one letter.
        assert _longest_printable_run("构式 154,391 句") >= STRUCTURE_RUN
        raw = ZH.encode("gbk")
        decoded, candidate = _readings(raw)
        assert _longest_printable_run(decoded) < STRUCTURE_RUN
        assert _keeps_the_structure(decoded, candidate)


class TestAGenuineSixteenBitFileStillMoves:
    @pytest.mark.parametrize(
        "text",
        [
            "构式网络很小，训练语料合计 154,391 句，角色集实例 440,528 个。" + NL,
            RU + NL,
            ZH * 6,
            MANUSCRIPT,
        ],
        ids=["chinese", "russian", "no-newline", "fenced"],
    )
    def test_it_is_decoded(self, text: str):
        raw = text.encode("utf-16-le")
        decoded, _lost_flag = _decode_text_and_loss(raw)
        assert decoded == text

    def test_the_swap_still_happens_with_no_nul_in_the_bytes(self):
        # A Han character's high byte is never zero, so a pure Chinese UTF-16
        # file holds no NUL at all - which is why a detector built on counting
        # NULs would skip it, and why the rule is about structure instead.
        body = ZH * 3
        raw = body.encode("utf-16-le")
        assert b"\x00" not in raw, "this fixture is meant to carry no NUL"
        decoded, _lost_flag = _decode_text_and_loss(raw)
        assert decoded == body


class TestTheVerdictOnAProject:
    def test_the_even_length_manuscript_is_checked_not_dismissed(self, tmp_path: Path, capsys):
        root = _project(tmp_path, MANUSCRIPT.encode("gbk"))
        code = main(["check", "manuscript.md", "--root", str(root)])
        report = capsys.readouterr().out
        assert "no-claim-blocks" not in report, report
        assert _codes(report) == ["claim-not-decoded"], report
        assert code == 1

    def test_the_odd_length_twin_says_the_same_thing(self, tmp_path: Path, capsys):
        root = _project(tmp_path, (MANUSCRIPT + "A").encode("gbk"))
        code = main(["check", "manuscript.md", "--root", str(root)])
        report = capsys.readouterr().out
        assert _codes(report) == ["claim-not-decoded"], report
        assert code == 1

    def test_an_even_length_utf8_manuscript_is_untouched(self, tmp_path: Path, capsys):
        root = _project(tmp_path, MANUSCRIPT.encode("utf-8"))
        code = main(["check", "manuscript.md", "--root", str(root)])
        report = capsys.readouterr().out
        assert _codes(report) == ["quote-found"], report
        assert code == 0
        assert read_loses_bytes(root / "manuscript.md") is False
