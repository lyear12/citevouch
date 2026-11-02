"""Chinese prose has no spaces, and every threshold here was counted in them.

Measured before this file existed, on this repository's own Chinese prose:

* ``_sentences_of("第一句话。第二句话。第三句话。")`` returned **one** run.  The
  full stop was in the character class, but the branch after it requires
  ``\\s+`` or end-of-string, and Chinese puts nothing after a full stop, so
  nothing ever matched.
* A paragraph that long is refused by ``_is_passage`` for exceeding the ceiling,
  and ``draft`` then reported "nothing on any page shares enough terms with the
  sentence (3 needed)" about a paragraph that shared eighteen of them.
* The ceiling and the floor were both counted in characters.  A character in a
  Chinese sentence is a syllable; a character in an English one is a letter.
  Measured on real sentences: the character window 40..400 kept 37% of Chinese
  sentences and 84% of English ones; the word window 7..70 keeps 86% and 84%.

So the splitter now breaks after CJK terminal punctuation without consuming
anything, and the window is counted in words - a run of letters, or one CJK
character.
"""

from __future__ import annotations

import pytest

from citevouch import draft as draft_module


class TestTheFullStopEndsASentenceWithoutASpace:
    """The defect was one branch of one regex, invisible from English."""

    @pytest.mark.parametrize(
        "text",
        [
            "第一句话。第二句话。第三句话。",
            "第一句话！第二句话？第三句话。",
            "真的吗？是的。好。",
        ],
    )
    def test_a_chinese_paragraph_is_several_sentences(self, text: str) -> None:
        assert len(draft_module._sentences_of(text)) == 3

    def test_the_sentences_are_the_ones_the_author_wrote(self) -> None:
        found = draft_module._sentences_of("第一句话。第二句话。第三句话。")
        assert found == ["第一句话。", "第二句话。", "第三句话。"]

    def test_a_decimal_point_is_not_a_full_stop(self) -> None:
        """3.5 is one number, and a full stop that is not terminal must not split."""
        found = draft_module._sentences_of("价格是3.5万元。收工。")
        assert found == ["价格是3.5万元。", "收工。"]

    def test_a_closing_bracket_stays_with_the_sentence_it_closes(self) -> None:
        """The break consumes nothing, so the bracket is not deleted from the text."""
        found = draft_module._sentences_of("他说。「好的。」然后离开。")
        assert found == ["他说。", "「好的。」", "然后离开。"]
        assert "".join(found) == "他说。「好的。」然后离开。"


class TestTheSpacedScriptIsUnchanged:
    """A fix for one script must not move the other; both are asserted, not implied."""

    def test_english_still_splits_on_a_full_stop_and_a_space(self) -> None:
        assert draft_module._sentences_of("We show A. We show B.") == [
            "We show A.",
            "We show B.",
        ]

    def test_a_percentage_does_not_split(self) -> None:
        assert draft_module._sentences_of("100.5% done. Next one.") == [
            "100.5% done.",
            "Next one.",
        ]

    def test_a_mixed_paragraph_splits_at_both_kinds_of_stop(self) -> None:
        assert draft_module._sentences_of("英文句。Next one. 中文句。") == [
            "英文句。",
            "Next one.",
            "中文句。",
        ]


class TestTheWindowIsCountedInWords:
    """The floor and ceiling decide what a reader is ever shown; they are not free."""

    def test_a_character_is_a_word_in_chinese(self) -> None:
        assert draft_module._words("中文句子") == 4

    def test_a_run_of_letters_is_a_word_in_english(self) -> None:
        assert draft_module._words("three words here") == 3

    def test_the_numbers_are_pinned_as_numbers(self) -> None:
        """Pinned rather than referenced: a test that reads the constant is a mirror."""
        assert draft_module.MIN_SENTENCE_WORDS == 7
        assert draft_module.MAX_SENTENCE_WORDS == 70

    def test_a_short_chinese_sentence_clears_the_floor(self) -> None:
        """A Chinese sentence is short in characters and ordinary in words.

        The old floor was forty *characters*, which a Chinese sentence of nine
        words (sixteen characters) never reaches - so the whole class of
        sentences a Chinese abstract is written in was refused, and the refusal
        arrived as "nothing on any page shares enough terms".
        """
        short = "构式语法认为句法结构本身承载意义。"
        assert draft_module._words(short) >= draft_module.MIN_SENTENCE_WORDS, (
            "the fixture has to clear the word floor for this test to be about the characters"
        )
        assert len(short) < 40, (
            "and it has to be under the old character floor, or the test passes "
            "for the reason the old code already had"
        )
        assert draft_module._is_passage(short)

    def test_a_three_word_chinese_fragment_is_refused(self) -> None:
        assert draft_module._words("好的。") < draft_module.MIN_SENTENCE_WORDS
        assert not draft_module._is_passage("好的。")

    def test_a_six_word_english_fragment_is_still_refused(self) -> None:
        assert not draft_module._is_passage("the grammar is a network")

    def test_a_seventy_one_word_run_is_still_refused(self) -> None:
        assert not draft_module._is_passage(" ".join(["word"] * 71))
        assert draft_module._is_passage(" ".join(["word"] * 70))


class TestTheDraftProposesFromChinese:
    """The end of the chain: a Chinese manuscript getting a proposal, or not."""

    PAGE = (
        "构式语法认为句法结构本身承载意义。相关研究指出词汇与构式之间存在互动关系。"
        "我们据此提出了一个分析框架。后续讨论将围绕三个层面展开。"
    )

    def _project(self, tmp_path, manuscript: str, filename: str = "m.md"):
        root = tmp_path / "p"
        root.mkdir()
        (root / filename).write_text(manuscript, encoding="utf-8")
        (root / "page.txt").write_text(self.PAGE + "\n", encoding="utf-8")
        (root / "refs.bib").write_text(
            "@article{page,\n  title = {T},\n  author = {A},\n  year = {2020},\n}\n",
            encoding="utf-8",
        )
        return root

    def _draft(self, root, capsys):
        from citevouch.cli import main

        code = main(
            [
                "draft",
                "m.md",
                "--root",
                str(root),
                "--bib",
                str(root / "refs.bib"),
                "-o",
                "claims.md",
                "--force",
            ]
        )
        capsys.readouterr()
        return code, (root / "claims.md").read_text(encoding="utf-8")

    def test_a_chinese_manuscript_gets_a_proposal(self, tmp_path, capsys) -> None:
        root = self._project(
            tmp_path, "构式语法认为句法结构承载意义，这一点已有论述[@page]。\n"
        )
        code, written = self._draft(root, capsys)
        assert code == 0
        assert "```claim" in written, (
            "the paragraph shares twelve terms with the page; before the fix this "
            "wrote 'nothing on any page shares enough terms (3 needed)'"
        )

    def test_the_reason_is_not_the_false_one(self, tmp_path, capsys) -> None:
        root = self._project(
            tmp_path, "构式语法认为句法结构承载意义，这一点已有论述[@page]。\n"
        )
        _, written = self._draft(root, capsys)
        assert "shares enough terms" not in written

    def test_the_quote_is_one_sentence_not_the_paragraph(self, tmp_path, capsys) -> None:
        """A quote is what fits on the cited page, and a paragraph is not a quote."""
        root = self._project(
            tmp_path, "构式语法认为句法结构承载意义，这一点已有论述[@page]。\n"
        )
        _, written = self._draft(root, capsys)
        quote = written.split("quote: |", 1)[-1].split("claim:", 1)[0].strip()
        assert quote.count("。") == 1, f"one sentence, not a run of them: {quote!r}"

    def test_the_claim_text_is_one_sentence_too(self, tmp_path, capsys) -> None:
        """The claim is the author's own words, and quoting them wrong is twice wrong."""
        root = self._project(
            tmp_path,
            "构式语法认为句法结构承载意义，这一点已有论述[@page]。后续讨论展开。\n",
        )
        _, written = self._draft(root, capsys)
        claim = written.split("claim: |", 1)[-1]
        assert "后续讨论展开" not in claim, (
            "the marker's sentence is the one before it; the next one is not part of it"
        )
