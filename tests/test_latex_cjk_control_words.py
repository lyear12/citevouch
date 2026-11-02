"""A control word with no space before Chinese prose used to eat the sentence."""

from pathlib import Path

import pytest

from citevouch.latex import included_files, to_text

BS = chr(92)
SENTENCE = "我们展示该方法。"
COFFEE = "构式语法认为句法结构本身承载意义。"


class TestTheSentenceSurvives:
    """The defect: `str.isalpha()` is true for CJK, so the whole sentence was
    read as the rest of the control word's name and was dropped with it."""

    @pytest.mark.parametrize(
        "command",
        [
            "noindent",
            "indent",
            "par",
            "item",
            "heiti",
            "songti",
            "bfseries",
            "bigskip",
            "newpage",
            "clearpage",
            "maketitle",
            "centering",
        ],
    )
    def test_the_words_after_a_control_word_are_still_words(self, command: str) -> None:
        assert to_text(BS + command + SENTENCE) == SENTENCE + "\n"

    def test_a_space_was_never_the_problem(self) -> None:
        # The same command with a space always worked; that is why the defect
        # only showed up in manuscripts that omit the space, which is the norm
        # in Chinese LaTeX.
        assert to_text(BS + "noindent " + SENTENCE) == SENTENCE + "\n"

    def test_a_four_line_document_survives(self) -> None:
        document = (
            BS
            + "begin{document}\n"
            + BS
            + "noindent"
            + COFFEE
            + "\n"
            + BS
            + "par相关研究指出词汇与构式之间存在互动关系。\n"
            + BS
            + "begin{itemize}\n"
            + BS
            + "item第一点很重要。\n"
            + BS
            + "end{itemize}\n"
            + BS
            + "end{document}\n"
        )
        converted = to_text(document)
        assert COFFEE in converted
        assert "相关研究指出词汇与构式之间存在互动关系。" in converted
        assert "第一点很重要。" in converted

    def test_the_citation_inside_the_sentence_is_still_a_citation(self) -> None:
        text = to_text(BS + "noindent 相关研究 [@page] 指出。")
        assert "[@page]" in text


class TestTheNamesThatStillWork:
    """ASCII control words have to keep scanning exactly as before."""

    def test_a_latin_command_name_is_read_whole(self) -> None:
        assert to_text(BS + "textbf{bold} plain") == "bold plain\n"

    def test_a_command_glued_to_latin_text_keeps_working(self) -> None:
        # ``\LaTeX`` is not a command this converter knows; its name is dropped
        # and the word after it is the author's.  The point is that the word
        # does not become part of the name.
        assert to_text(BS + "LaTeX is used") == "is used\n"

    def test_a_letter_extends_the_name_exactly_as_tex_does(self) -> None:
        # ``\noindentWe`` is one control word to TeX, because `W` is a letter,
        # and this converter has to agree with TeX about where a name ends.
        # Only the non-ASCII characters above are a different case - see the
        # class docstring.
        assert to_text(BS + "noindentWe show it.") == "show it.\n"

    def test_a_digit_ends_the_name_exactly_as_tex_does(self) -> None:
        # TeX's control words are letters only; a digit after one is the
        # author's text.  Accepting digits would drop the first character of
        # `\item1.`-style labels and of any sentence that starts with a number.
        assert to_text(BS + "item1. 第一点很重要。") == "1. 第一点很重要。\n"
        assert to_text(BS + "noindent3 个例子。") == "3 个例子。\n"
        assert to_text(BS + "centering40,688 个例子。") == "40,688 个例子。\n"

    def test_the_digits_after_a_command_are_not_a_name(self) -> None:
        assert to_text(BS + "if1 甲" + BS + "else 乙" + BS + "fi") == "甲\n"


class TestTheOtherReadersAgree:
    """`included_files` and the conditional scanner use the same scan, so a file
    or a `\\fi` glued to Chinese text has to be found too."""

    def test_an_input_glued_to_chinese_still_reports_its_file(self) -> None:
        assert included_files(BS + "input{sec/intro}" + SENTENCE) == ["sec/intro"]

    def test_a_dead_branch_glued_to_chinese_ends_where_it_says(self) -> None:
        text = BS + "iffalse 死文字" + BS + "fi" + SENTENCE
        assert to_text(text) == SENTENCE + "\n"

    def test_the_next_word_is_not_swallowed_by_the_conditional(self) -> None:
        # A `\fi` followed by Chinese used to consume that Chinese as part of
        # the name `fi构式`, so the scanner never saw the closing keyword.
        text = BS + "iftrue" + SENTENCE + BS + "fi"
        assert SENTENCE in to_text(text)


class TestTheDraftProposesSomething:
    """The end-to-end shape: a `ctexart` manuscript whose prose survives."""

    def test_a_glued_document_still_yields_a_claim(self, tmp_path: Path) -> None:
        source = tmp_path / "page.txt"
        source.write_text("相关研究指出词汇与构式之间存在互动关系。\n", encoding="utf-8")
        manuscript = tmp_path / "m.tex"
        manuscript.write_text(
            BS
            + "begin{document}\n"
            + BS
            + "noindent相关研究指出词汇与构式之间存在互动关系"
            + BS
            + "citep{page}。\n"
            + BS
            + "end{document}\n",
            encoding="utf-8",
            newline="\n",
        )
        (tmp_path / "sources.toml").write_text(
            '[sources]\npage = "page.txt"\n', encoding="utf-8", newline="\n"
        )
        from citevouch.draft import draft

        result = draft(
            manuscript.read_text(encoding="utf-8"),
            bib={},
            known={},
            root=str(tmp_path),
            table=None,
        )
        assert result.proposals, "the sentence was never read, so nothing was proposed"
