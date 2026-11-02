"""Tests for the space a removed citation marker leaves in CJK prose."""

from __future__ import annotations

from citevouch.draft import statement_of


class TestTheGapIsClosedInBothScripts:
    def test_a_chinese_sentence_has_no_space_before_its_stop(self) -> None:
        assert (
            statement_of("相关研究指出词汇与构式之间存在互动关系 [@page]。")
            == "相关研究指出词汇与构式之间存在互动关系。"
        )

    def test_the_latin_case_this_line_was_written_for_still_works(self) -> None:
        assert statement_of("The method works [@p].") == "The method works."

    def test_a_chinese_comma_is_closed_up_too(self) -> None:
        assert statement_of("甲 [@p] ，乙。") == "甲，乙。"

    def test_a_chinese_ellipsis_is_closed_up(self) -> None:
        assert statement_of("甲 [@p]…乙。") == "甲…乙。"

    def test_a_closing_bracket_wins_over_the_space(self) -> None:
        assert statement_of("他说：“好 [@p]。”") == "他说：“好。”"

    def test_a_semicolon_and_a_colon_still_close_up(self) -> None:
        assert statement_of("Alpha beta gamma [@p]; delta.") == "Alpha beta gamma; delta."


class TestTheSpacesThatAreNotGapsStay:
    def test_a_space_between_two_chinese_words_is_left_alone(self) -> None:
        assert statement_of("我们 [@p] 认为构式承载意义。") == "我们 认为构式承载意义。"

    def test_a_number_keeps_its_spaces(self) -> None:
        assert statement_of("价格是 [@p] 3.5 万元。") == "价格是 3.5 万元。"

    def test_a_space_before_a_word_is_not_removed(self) -> None:
        assert statement_of("见 [@p] 附录。") == "见 附录。"


class TestTheMarksTheFirstVersionForgot:
    """The five Latin marks are not the whole set a citation can sit before."""

    def test_every_cjk_terminal_mark_closes_up(self) -> None:
        for mark in "。！？":
            assert statement_of(f"甲 [@p]{mark}") == f"甲{mark}", mark

    def test_every_cjk_small_mark_closes_up(self) -> None:
        for mark in "，、；：":
            assert statement_of(f"甲 [@p]{mark}乙") == f"甲{mark}乙", mark

    def test_the_closing_marks_close_up(self) -> None:
        for mark in "」』】》〉〕｝":
            assert statement_of(f"甲 [@p]{mark}") == f"甲{mark}", mark
