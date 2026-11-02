"""Tests for the Chinese LaTeX stacks: ctex, xeCJK and CJKutf8 commands.

Every one of these commands names a font, a point size, a line spread or a
registry code.  None of them is a word of the thesis, and before these lines
existed the converter's fallthrough - "drop the command name, keep what it
wraps" - pasted the argument into the sentence.  Measured on a ctexart
manuscript: `{\\zihao{5} 相关研究 ...}` converted to `5 相关研究 ...`, so `draft`
wrote a claim whose text opens with the point size.
"""

from __future__ import annotations

from citevouch.latex import to_text

SENTENCE = "我们展示该方法。"


class TestTheArgumentIsNotAWord:
    def test_a_point_size_does_not_open_the_sentence(self) -> None:
        assert to_text(r"{\zihao{5} " + SENTENCE + "}") == SENTENCE + "\n"

    def test_a_point_size_in_the_middle_leaves_one_space(self) -> None:
        assert to_text("我们 " + r"\zihao{5} " + "展示该方法。") == "我们 展示该方法。\n"

    def test_a_negative_point_size_leaves_no_minus_sign(self) -> None:
        assert to_text(r"{\zihao{-4} " + SENTENCE + "}") == SENTENCE + "\n"

    def test_a_font_family_name_is_not_a_word(self) -> None:
        assert to_text(r"{\CJKfamily{zhsong} " + SENTENCE + "}") == SENTENCE + "\n"

    def test_a_font_name_is_not_a_word(self) -> None:
        assert to_text(r"\setCJKmainfont{SimSun} " + SENTENCE) == SENTENCE + "\n"

    def test_a_sans_font_name_is_not_a_word(self) -> None:
        assert to_text(r"\setCJKsansfont{SimHei} " + SENTENCE) == SENTENCE + "\n"

    def test_a_mono_font_name_is_not_a_word(self) -> None:
        assert to_text(r"\setCJKmonofont{FangSong} " + SENTENCE) == SENTENCE + "\n"

    def test_a_line_spread_is_not_a_number_in_the_sentence(self) -> None:
        assert to_text(r"\linespread{1.5} " + SENTENCE) == SENTENCE + "\n"

    def test_a_font_size_pair_does_not_join_itself_to_the_sentence(self) -> None:
        assert to_text(r"\fontsize{12}{14}\selectfont " + SENTENCE) == SENTENCE + "\n"

    def test_a_character_class_is_not_a_word(self) -> None:
        assert to_text(r"\xeCJKDeclareCharClass{CJK}{4E00} " + SENTENCE) == SENTENCE + "\n"

    def test_an_ecglue_setting_does_not_reach_the_sentence(self) -> None:
        assert to_text(r"\xeCJKsetup{CJKecglue={}} " + SENTENCE) == SENTENCE + "\n"


class TestTheConfigurersLeaveNothingBehind:
    def test_ctexset_takes_its_optional_argument_too(self) -> None:
        assert to_text(r"\ctexset{section/format=\bfseries}" + SENTENCE) == SENTENCE + "\n"

    def test_ctexsetup_drops_its_bracket_and_its_word(self) -> None:
        assert (
            to_text(r"\CTEXsetup[format={\Large\bfseries}]{section}" + SENTENCE)
            == SENTENCE + "\n"
        )

    def test_a_section_name_setting_is_not_a_word(self) -> None:
        assert to_text(r"\CTEXsetup[name={第,章}]{section}" + SENTENCE) == SENTENCE + "\n"


class TestWhatTheCommandsWrapSurvives:
    def test_the_words_after_a_command_are_untouched(self) -> None:
        for command in (
            r"\zihao{5}",
            r"\CJKfamily{zhsong}",
            r"\CJK{4E00}",
            r"\chinese{page}",
            r"\setCJKmainfont{SimSun}",
            r"\linespread{1.5}",
        ):
            assert to_text(command + " " + SENTENCE) == SENTENCE + "\n", command

    def test_a_plain_sentence_is_unchanged(self) -> None:
        assert to_text(SENTENCE) == SENTENCE + "\n"

    def test_the_latin_size_commands_still_behave_as_before(self) -> None:
        assert to_text(r"{\Large\bfseries " + SENTENCE + "}") == SENTENCE + "\n"


class TestACitationInsideStillCounts:
    def test_a_citation_after_a_point_size_is_still_a_citation(self) -> None:
        from citevouch.draft import citation_sites

        text = to_text(r"{\zihao{5} 相关研究 [@page] 指出。}")
        assert text == "相关研究 [@page] 指出。\n"
        assert [site.key for site in citation_sites(text)] == ["page"]
