"""TeX does not care whether an argument touches its command; the reader did.

Measured on the tree before the fix: for each of the 104 command names in the
tables whose whole purpose is that their arguments must *not* reach the prose,
`\\name {ARG}` was converted with `ARG` in the sentence - 85 of them.  Only the
touching spelling `\\name{ARG}` was understood.  `\\input {sec/intro}` came out
as `... examples. sec/intro The end.`, so a file path was read as two words of
the paper, and every citation inside the part it named was missing.

The same probe found the directions that must NOT change:

* `\\footnote {note}` puts the note body in the notes, not the sentence.
* `\\footnotemark[1]` takes a bracket argument and no brace argument.  Whitespace
  must not be swallowed there, or the reader eats the space and `Text
  continues.` becomes `Textcontinues.`.

Compressed: the fix holds whitespace pending and only spends it when a brace
group follows, so `*` and `[..]` (arguments in their own right) still win.
"""

from __future__ import annotations

import pytest

from citevouch.latex import included_files, to_text

BS = chr(92)
NL = chr(10)
SENTENCE = "We collected 40,688 examples. "
TAIL = "The grammar is large."


def _wraps(body: str) -> str:
    return SENTENCE + body + TAIL


class TestTheSpaceTeXPutsBetweenACommandAndItsArgument:
    @pytest.mark.parametrize(
        "command",
        ["input", "include", "subfile", "label", "ref", "bibliography"],
    )
    def test_one_space_does_not_paste_the_argument_into_the_prose(self, command: str) -> None:
        converted = to_text(_wraps(BS + command + " {sec/intro}"))
        assert "sec/intro" not in converted
        assert converted.strip() == (SENTENCE + TAIL).strip()

    @pytest.mark.parametrize("gap", [" ", chr(9), NL, "  " + NL])
    def test_every_kind_of_space_tex_allows(self, gap: str) -> None:
        converted = to_text(_wraps(BS + "label" + gap + "{fig:one}"))
        assert "fig:one" not in converted

    def test_the_touching_spelling_still_works(self) -> None:
        assert to_text(_wraps(BS + "label{fig:one}")).strip() == (SENTENCE + TAIL).strip()

    def test_the_commands_that_take_two_arguments_take_two(self) -> None:
        converted = to_text(_wraps(BS + "setcounter {page}{3}"))
        assert "page" not in converted
        assert "3" not in converted

    def test_an_included_file_is_still_named(self) -> None:
        # The prose must not carry the path; the `included_files` report must.
        assert included_files(BS + "input {sec/intro}") == ["sec/intro"]
        assert included_files(BS + "subfile {sec/method}") == ["sec/method"]

    def test_the_braceless_tex_spelling_did_not_regress(self) -> None:
        assert to_text(_wraps(BS + "input sec/intro ")).strip() == (SENTENCE + TAIL).strip()
        assert included_files(BS + "input sec/intro") == ["sec/intro"]


class TestWhatMustNotChange:
    def test_a_note_body_goes_to_the_notes_and_not_the_sentence(self) -> None:
        converted = to_text(_wraps(BS + "footnote {A note about the corpus.}"))
        assert "A note about the corpus." not in converted.split(NL + NL)[0]
        assert "A note about the corpus." in converted

    def test_a_kept_argument_stays_in_the_prose(self) -> None:
        converted = to_text(_wraps(BS + "emph {kept words}"))
        assert "kept words" in converted
        assert BS + "emph" not in converted

    def test_a_command_that_only_takes_a_bracket_keeps_the_space_after_it(
        self,
    ) -> None:
        # `\footnotemark` has no brace argument, so the space after it belongs
        # to the sentence.  Swallowing it glues "Text" to "continues".
        assert to_text("Text" + BS + "footnotemark[1] continues.") == ("Text continues." + NL)
        assert to_text("Text" + BS + "footnotemark continues.") == ("Text continues." + NL)

    def test_an_optional_argument_survives_the_space_before_it(self) -> None:
        # `\footnotemark [1]` is the same command as `\footnotemark[1]`.
        assert to_text("Text" + BS + "footnotemark [1] continues.") == ("Text continues." + NL)

    @pytest.mark.parametrize("gap", [" ", chr(9), NL])
    def test_a_switch_command_eats_nothing(self, gap: str) -> None:
        converted = to_text("She" + BS + "bfseries" + gap + "collected data.")
        assert "collected data." in converted
        assert BS + "bfseries" not in converted

    def test_a_star_is_an_argument_and_is_consumed(self) -> None:
        # `\footnotemark*` takes no brace argument but does take the star; if
        # the star is not counted as consumed, the reader falls back to the
        # command name and the asterisk reaches the sentence.
        assert to_text("Text" + BS + "footnotemark* continues.") == ("Text continues." + NL)
        assert to_text("Text" + BS + "footnotemark*[1] continues.") == ("Text continues." + NL)
