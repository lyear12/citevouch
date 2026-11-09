"""Tests for a document that names its own encoding.

A file that says "I am GBK" has answered a question the tool otherwise guesses
at from a byte share, and the guess is what went wrong: an HTML header is
ASCII, so it dilutes the share of undecodable bytes.  Measured on a one-claim
project whose only source was a 239-byte GBK page carrying
``<meta http-equiv="Content-Type" content="text/html; charset=gbk">``:

    [high] quote-missing at m.md:5 (paper): 本文收集了六万八千个例句，…
    — quote not found in page.html

with exit 1, about a sentence printed verbatim in that file.  The byte share
was 0.172 against a 0.25 threshold.

Reading the declaration is not the same as trusting it.  ``declared_reading``
returns text only when the declared encoding also decodes the bytes cleanly, so
a UTF-8 page labelled ``gb2312`` keeps its UTF-8 reading - that case is
measured in ``TestAWrongDeclarationIsNotBelieved``, because believing it would
turn a file that reads perfectly into rubbish.
"""

from __future__ import annotations

import contextlib
import io
from pathlib import Path

from citevouch import sources, textnorm
from citevouch.cli import main

NL = chr(10)
B3 = "`" * 3
SENTENCE = "本文收集了六万八千个例句，全部来自语料库中的真实文本。"

HEAD = (
    '<!DOCTYPE html><html><head><meta http-equiv="Content-Type" '
    'content="text/html; charset=gbk"><link rel="stylesheet" href="a.css">'
    "<title>论文摘要</title></head><body>"
)


def project(tmp_path: Path, raw: bytes, quote: str = SENTENCE) -> Path:
    """A one-claim project whose only source is these exact bytes."""
    root = tmp_path / "p"
    root.mkdir(parents=True, exist_ok=True)
    (root / "page.html").write_bytes(raw)
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.html"' + NL, encoding="utf-8", newline=NL
    )
    body = (
        f"{B3}claim id=paper source=paper page=1"
        + NL
        + "quote: |"
        + NL
        + f"  {quote}"
        + NL
        + B3
        + NL
    )
    (root / "manuscript.md").write_text(body, encoding="utf-8", newline=NL)
    return root


def check(root: Path, *extra: str) -> tuple[int, str]:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = main(["check", "manuscript.md", "--root", str(root), *extra])
    return code, buffer.getvalue()


def codes(report: str) -> list[str]:
    return [line.split()[1] for line in report.splitlines() if line.startswith("[")]


def head_without_title() -> str:
    """The same header minus the Chinese title.

    Big5 and Shift-JIS cannot encode 论文摘要, so a test that asks them to would
    be measuring ``str.encode`` rather than the tool.
    """
    return HEAD.replace("<title>论文摘要</title>", "")


def page(
    body: str, charset: str = "gbk", encoding: str | None = None, head: str | None = None
) -> bytes:
    return ((head if head is not None else HEAD) + f"<p>{body}</p></body></html>").encode(
        encoding or charset
    )


class TestThePageSaysWhichEncodingItIsIn:
    def test_a_gbk_page_is_read_and_its_sentence_verifies(self, tmp_path: Path):
        """The measured defect: this answered `[high] quote-missing`, exit 1."""
        code, report = check(project(tmp_path, page(SENTENCE)))
        assert code == 0
        assert codes(report) == ["quote-found"]
        assert "quote not found" not in report

    def test_the_byte_share_really_was_under_the_line(self, tmp_path: Path):
        """The fixture has to be the one that slipped through, not a stand-in."""
        raw = page(SENTENCE)
        assert textnorm.invalid_utf8_share(raw) < sources.MAX_UNDECODABLE_SHARE

    def test_without_the_declaration_the_file_is_still_refused(self, tmp_path: Path):
        """The declaration is what changed the answer, not the bytes' length.

        One sentence is too short to reach the share threshold on its own - that
        is the whole defect - so the comparison uses a page that is long enough
        for the old rule to fire.
        """
        undeclared = head_without_title().replace(
            '<meta http-equiv="Content-Type" content="text/html; charset=gbk">', ""
        )
        raw = page(SENTENCE * 2, head=undeclared)
        assert textnorm.invalid_utf8_share(raw) >= sources.MAX_UNDECODABLE_SHARE
        code, report = check(project(tmp_path, raw))
        assert code == 1
        assert "source-encoding" in codes(report)

    def test_a_big5_page_is_read_too(self, tmp_path: Path):
        text = "我們收集了六萬八千個例句，全部來自語料庫中的真實文本。"
        head = head_without_title().replace("charset=gbk", "charset=big5")
        code, report = check(
            project(tmp_path, page(text, head=head, encoding="big5"), quote=text)
        )
        assert code == 0
        assert codes(report) == ["quote-found"]

    def test_a_shift_jis_page_is_read_too(self, tmp_path: Path):
        text = "私たちは六万八千の例文を集め、その分布を調べた。"
        head = head_without_title().replace("charset=gbk", "charset=shift_jis")
        code, report = check(
            project(tmp_path, page(text, head=head, encoding="shift_jis"), quote=text)
        )
        assert code == 0
        assert codes(report) == ["quote-found"]


class TestTheDeclarationsThatCount:
    def test_the_meta_charset_spelling(self):
        assert textnorm.declared_charset(b'<meta charset="gbk">') == "gbk"

    def test_the_http_equiv_spelling(self):
        raw = b'<meta http-equiv="Content-Type" content="text/html; charset=gbk">'
        assert textnorm.declared_charset(raw) == "gbk"

    def test_the_xml_declaration(self):
        raw = b'<?xml version="1.0" encoding="gb2312"?><root/>'
        assert textnorm.declared_charset(raw) == "gb2312"

    def test_a_bare_value_needs_no_quotes(self):
        assert textnorm.declared_charset(b"<meta charset=gbk>") == "gbk"

    def test_the_case_of_the_name_does_not_matter(self):
        assert textnorm.declared_charset(b'<meta charset="GBK">') == "gbk"


class TestWhatIsNotADeclaration:
    def test_a_page_with_no_tag_at_all(self):
        assert textnorm.declared_charset(b"just prose") is None

    def test_a_declaration_inside_a_comment(self):
        """A tutorial page that *shows* the tag is not declaring anything."""
        raw = b'<!-- <meta charset="gbk"> --><p>hi</p>'
        assert textnorm.declared_charset(raw) is None

    def test_a_name_python_does_not_know(self):
        """A name nobody can decode with is not an answer, it is a spell error."""
        assert textnorm.declared_charset(b'<meta charset="not-a-codec-xyz">') is None

    def test_a_declaration_that_only_appears_after_the_first_kilobyte(self):
        raw = b"<p>" + b"x" * 5000 + b'</p><meta charset="gbk">'
        assert textnorm.declared_charset(raw) is None

    def test_a_declaration_deep_in_a_long_header_is_still_read(self):
        """The boundary has to be pinned from both sides or it is a free number.

        A real page can spend a few kilobytes on comments, scripts and link tags
        before it gets to the encoding, so the window is wider than the first
        screenful; that is a decision, not an accident, and it is asserted.
        """
        filler = b"<!-- " + b"y" * 3000 + b" -->"
        assert textnorm.declared_charset(filler + b'<meta charset="gbk">') == "gbk"


class TestAWrongDeclarationIsNotBelieved:
    def test_utf8_bytes_labelled_gbk_still_read_as_utf8(self, tmp_path: Path):
        """The direction that costs a morning if the declaration is trusted."""
        raw = (HEAD + f"<p>{SENTENCE}</p></body></html>").encode("utf-8")
        assert textnorm._decode_text(raw).count(SENTENCE) == 1
        code, report = check(project(tmp_path, raw))
        assert code == 0
        assert codes(report) == ["quote-found"]

    def test_the_reading_helper_returns_none_rather_than_rubbish(self):
        raw = (HEAD + f"<p>{SENTENCE}</p></body></html>").encode("utf-8")
        assert textnorm.declared_reading(raw) is None

    def test_a_declared_utf8_is_left_to_the_normal_reader(self):
        """`charset=utf-8` says nothing the UTF-8 reader does not already do."""
        raw = b'<meta charset="utf-8"><p>plain</p>'
        assert textnorm.declared_reading(raw) is None


class TestTheTwoReadersAgree:
    def test_a_file_that_decodes_by_declaration_is_never_refused(self, tmp_path: Path):
        """`encoding_problem` and `_decode_text` must not disagree.

        One refusing what the other can read is the shape of this whole family:
        the refusal tells the author nothing was read, and the reader would have
        read it.
        """
        raw = page(SENTENCE)
        assert textnorm.declared_reading(raw) is not None
        path = tmp_path / "page.html"
        path.write_bytes(raw)
        assert sources.encoding_problem(path, ".html") is None

    def test_a_file_that_does_not_decode_is_still_refused(self, tmp_path: Path):
        raw = b'<meta charset="gbk"><p>' + "本文".encode("gbk")
        # Truncate so the declared codec cannot finish the last character.
        raw = raw[:-1]
        path = tmp_path / "page.html"
        path.write_bytes(raw)
        assert textnorm.declared_reading(raw) is None
