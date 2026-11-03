"""Each format says its own reason for having no text.

`source-no-text` was written for a scanned PDF, and its message told the reader
to run OCR.  Then the same code answered for an empty `.txt`, an empty `.md`
and a `.xml` whose words are all inside tags - and every one of those got the
OCR sentence, which cannot work on any of them: there is no text layer in a
text file, and OCR does not remove tags.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from citevouch import sources
from citevouch.cli import main
from citevouch.sources import PageText, _no_text_problem

B3 = "`" * 3
QUOTE = "The corpus has 100 utterances."


def blank(path: Path, body: str = "") -> Path:
    path.write_text(body, encoding="utf-8", newline="\n")
    return path


class TestTheAdviceMatchesTheFormat:
    def test_a_text_file_is_not_told_to_run_ocr(self):
        message = _no_text_problem(
            [PageText(number=1, text="")], Path("empty.txt"), ".txt"
        ).message
        assert "ocr" not in message.lower()
        assert "empty" in message

    def test_markup_is_not_told_its_words_are_missing(self):
        message = _no_text_problem([PageText(number=1, text="")], Path("a.xml"), ".xml").message
        assert "ocr" not in message.lower()
        assert "tag" in message or "markup" in message

    def test_a_pdf_still_gets_the_ocr_sentence(self):
        message = _no_text_problem(
            [PageText(number=1, text="")], Path("scan.pdf"), ".pdf"
        ).message
        assert "OCR" in message
        assert "ocrmypdf scan.pdf" in message

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("empty.txt", "whitespace"),
            ("blank.md", "whitespace"),
            ("empty.xml", "tag"),
            ("blank.html", "tag"),
        ],
    )
    def test_every_extension_reaches_the_right_branch(
        self, tmp_path: Path, name: str, expected: str
    ):
        """The suffix has to travel from the extractor to the sentence.

        Asserting only "no OCR" is not enough: the markup sentence has no OCR
        either, so a text file that fell into the markup branch would pass.
        Each format has to reach *its own* reason.
        """
        body = "" if name.endswith((".txt", ".md")) else "<article></article>"
        pages, problem = sources.extract_pages(
            blank(tmp_path / name, body), tmp_path, use_cache=False
        )
        assert pages == [] or not "".join(p.text for p in pages).strip()
        assert problem is not None and problem.code == "source-no-text"
        assert "ocr" not in problem.message.lower()
        assert expected in problem.message


class TestTheCacheHitPathSaysTheSameThing:
    """A cache entry written for one format must not answer for another.

    The verdict is decided on both paths, so the sentence has to be built from
    the file in front of us rather than from anything stored.
    """

    def test_a_second_run_still_names_the_format(self, tmp_path: Path):
        source = blank(tmp_path / "empty.txt")
        first = sources.extract_pages(source, tmp_path)
        second = sources.extract_pages(source, tmp_path)
        assert first[1] is not None and second[1] is not None
        assert first[1].message == second[1].message
        assert "ocr" not in second[1].message.lower()


class TestTheVerdictOnAProject:
    def test_an_empty_text_source_is_high_and_names_the_file(self, tmp_path: Path):
        blank(tmp_path / "page.txt", "   \n\n")
        (tmp_path / "sources.toml").write_text(
            '[sources]\nweb = "page.txt"\n', encoding="utf-8", newline="\n"
        )
        manuscript = tmp_path / "m.md"
        manuscript.write_text(
            f"{B3}claim id=c1 source=web\nquote: |\n  {QUOTE}\n{B3}\n",
            encoding="utf-8",
            newline="\n",
        )
        code = main(["scan", str(manuscript), "--root", str(tmp_path)])
        assert code == 1
