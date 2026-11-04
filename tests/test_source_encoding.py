"""A text file this tool cannot decode is not a file full of mojibake.

``textnorm._decode_text`` ends in ``raw.decode("utf-8", errors="replace")``.
That line is why the tool never crashes on a file it cannot read, and it is
also why the tool lies about one.  Measured: a page saved in GBK gave 54
characters of mojibake with **one** replacement character in them, and the
noise score that decides whether a reading is plausible is
``max(4, len // 50)`` - four.  One is below four.  So the GBK page was
accepted as text, searched, found to contain nothing, and the run answered the
author's quote with

    [high] quote-missing at manuscript.md:1 (c1): 我们收集了 40,688 个例句…
    — quote not found in page.txt

which is a verdict about the author's sentence when the fact is about the
file's encoding.  Big5 was 2 replacement characters, Shift-JIS 3, a cp1252
em dash 1: no desktop encoding reached the threshold, so no file saved in one
was ever refused.

The old detector cannot be fixed by lowering the threshold, because the same
score protects text that legitimately contains a stray byte.  What separates
the two cases is that a *mixture* fails strict UTF-8 while ASCII alone does
not: a file that decodes as UTF-8 without replacement is UTF-8, and a file
that does not is in some other encoding - 8-bit or 16-bit - and neither of
those is a thing this tool knows how to read.

Only the second kind is refused.  A manuscript whose prose happens to be
mostly English still fails strict UTF-8 for its one Chinese sentence, so the
refusal is limited to text whose undecodable bytes are most of its letters.
"""

from __future__ import annotations

from pathlib import Path

from citevouch.cli import main

NL = chr(10)
B3 = "`" * 3
QUOTE = "我们收集了 40,688 个例句，并检验它们的分布。" + NL
BIB = "@article{paper, author={张三}, title={构式语法研究}, year={2026}}" + NL


def _project(
    tmp_path: Path,
    page_encoding: str = "utf-8",
    bib_encoding: str = "utf-8",
    quote: str = QUOTE,
) -> Path:
    """A project whose source file is saved in ``page_encoding``."""
    root = tmp_path / "p"
    root.mkdir(parents=True, exist_ok=True)
    (root / "page.txt").write_bytes(quote.encode(page_encoding))
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
    )
    body = (
        f"{B3}claim id=c1 source=paper page=1" + NL + "quote: |" + NL + f"  {quote}" + B3 + NL
    )
    (root / "manuscript.md").write_text(body, encoding="utf-8", newline=NL)
    (root / "refs.bib").write_bytes(BIB.encode(bib_encoding))
    return root


def _check(root: Path, *extra: str) -> tuple[int, str]:
    import contextlib
    import io

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = main(["check", "manuscript.md", "--root", str(root), *extra])
    return code, buffer.getvalue()


def _codes(report: str) -> list[str]:
    return [line.split()[1] for line in report.splitlines() if line.startswith("[")]


class TestTheFactIsAboutTheFileNotTheQuote:
    def test_the_run_names_the_encoding_instead_of_the_quote(self, tmp_path: Path):
        code, report = _check(_project(tmp_path, page_encoding="gbk"))
        assert code == 1
        assert "source-encoding" in _codes(report)
        assert "quote-missing" not in _codes(report)

    def test_the_quote_is_not_searched_against_the_rubbish(self, tmp_path: Path):
        # The finding has to stop the search, not decorate it.  A run that
        # reports both is still telling the author their quote is wrong.
        _code, report = _check(_project(tmp_path, page_encoding="gbk"))
        assert "quote not found" not in report

    def test_the_message_says_the_bytes_were_not_utf8(self, tmp_path: Path):
        _code, report = _check(_project(tmp_path, page_encoding="gbk"))
        assert "not UTF-8" in report
        assert "page.txt" in report

    def test_every_desktop_encoding_reaches_the_same_verdict(self, tmp_path: Path):
        # No desktop encoding reached the noise threshold, so each one used to
        # be read as text and searched.  All of them are the same fact.  Each
        # case speaks a language its own encoding can actually hold: Big5
        # cannot spell the simplified characters, and a test that asks it to
        # would be measuring `str.encode`, not the tool.
        cases = (
            ("gbk", "我们收集了 40,688 个例句，并检验它们的分布。"),
            ("big5", "我們收集了 40,688 個例句，並檢驗它們的分布。"),
            ("shift_jis", "私たちは 40,688 の例文を集め、その分布を調べた。"),
        )
        for index, (encoding, text) in enumerate(cases):
            root = _project(tmp_path / f"case{index}", page_encoding=encoding, quote=text + NL)
            code, report = _check(root)
            assert code == 1, encoding
            assert "source-encoding" in _codes(report), encoding

    def test_the_severity_is_the_one_the_manifest_says(self, tmp_path: Path):
        # High, like `source-no-text` and `source-unreadable`, and for the same
        # reason: the author believes this source was searched, and it was not.
        # The low ones are about things they can see for themselves.
        _code, report = _check(_project(tmp_path, page_encoding="gbk"))
        assert "[high] source-encoding" in report

    def test_it_fails_the_default_gate(self, tmp_path: Path):
        root = _project(tmp_path, page_encoding="gbk")
        assert _check(root)[0] == 1
        assert _check(root, "--fail-on", "high")[0] == 1
        assert _check(root, "--fail-on", "info")[0] == 1


class TestWhatIsStillRead:
    def test_a_utf8_file_is_untouched(self, tmp_path: Path):
        code, report = _check(_project(tmp_path))
        assert code == 0
        assert _codes(report) == ["quote-found"]

    def test_utf16_with_a_mark_is_still_decoded(self, tmp_path: Path):
        # The decoder knows this one; it is named by a byte-order mark.
        code, report = _check(_project(tmp_path, page_encoding="utf-16"))
        assert code == 0
        assert _codes(report) == ["quote-found"]

    def test_a_named_encoding_is_not_refused_for_its_share(self, tmp_path: Path):
        # A UTF-16 page of Chinese scores 0.33 on the bytes-not-UTF-8 scale -
        # past the line - and it is perfectly readable, because the file says
        # which reading it wants.  Refusing it would swap a working reading for
        # a complaint about bytes, which is the same trade pointing the other
        # way.  This test is the reason `proven_codec` is consulted first.
        text = (
            "构式语法理论认为语言知识的基本单位是构式，构式是形式与意义的配对，"
            "这一观点近年来在认知语言学中得到广泛讨论。" + NL
        )
        root = _project(tmp_path, page_encoding="utf-16", quote=text)
        from citevouch.textnorm import invalid_utf8_share

        assert invalid_utf8_share((root / "page.txt").read_bytes()) > 0.25
        code, report = _check(root)
        assert "source-encoding" not in _codes(report)
        assert code == 0
        assert _codes(report) == ["quote-found"]

    def test_a_mostly_english_manuscript_with_one_chinese_sentence(self, tmp_path: Path):
        # Strict UTF-8 fails on this file too, and refusing it would be a new
        # false accusation in exchange for the old one.
        body = "The corpus holds 154,391 utterances. 摘要：构式语法。" + NL
        root = _project(tmp_path, quote=body)
        code, report = _check(root)
        assert code == 0
        assert "source-encoding" not in _codes(report)
        assert _codes(report) == ["quote-found"]

    def test_a_stray_high_byte_in_english_prose_is_not_refused(self, tmp_path: Path):
        root = _project(tmp_path, quote="The corpus holds 154,391 utterances." + NL)
        (root / "page.txt").write_bytes(
            b"The corpus holds 154,391 utterances.\n" + b"A stray \xe9 byte.\n"
        )
        _code, report = _check(root)
        assert "source-encoding" not in _codes(report)

    def test_a_cp1252_em_dash_is_still_read(self, tmp_path: Path):
        # The line, on purpose: 2.6% of that file's bytes are not UTF-8, and
        # refusing it would trade one false accusation for another.  What the
        # author sees is the honest failure - the quote does not match - and
        # not a claim about a file that was never opened.
        text = "We collected 40,688 examples — twice." + NL
        root = _project(tmp_path, page_encoding="cp1252", quote=text)
        _code, report = _check(root)
        assert "source-encoding" not in _codes(report)

    def test_the_demo_pdf_is_not_affected(self, tmp_path: Path):
        # The PDF reader owns that suffix; this branch must not reach it.  The
        # paper scores 0.33 on this scale - compressed bytes are not UTF-8
        # either - so a guard that judged every suffix would refuse the demo.
        # (This test used to look for `demo/page.txt`, which is not a file, and
        # returned early: it was green about a file that does not exist.)
        from citevouch import sources
        from citevouch.textnorm import invalid_utf8_share

        paper = (
            Path(__file__).resolve().parent.parent
            / "demo"
            / "papers"
            / "2020_TayyarMadabushi-etal_CxGBERT.pdf"
        )
        assert paper.is_file()
        assert invalid_utf8_share(paper.read_bytes()) > 0.25
        # `root` is where the extraction cache is written, and it is written
        # even when reading is skipped; pointing it at tmp_path keeps the
        # checked-in demo directory out of the run.
        pages, problem = sources.extract_pages(paper, tmp_path, use_cache=False)
        assert problem is None
        assert pages


class TestTheBibliographyIsNotJudgedHere:
    # Not an oversight, and the reason is a measurement.  A Chinese .bib is
    # mostly ASCII, so a GBK one scores 0.11-0.24 where a GBK page scores
    # 0.62; a line low enough to catch the bibliography would be cleared by a
    # cp1252 French page (0.085) by a hair.  Refusing a file the author can
    # read is the same class of error as accusing their quote.
    def test_a_gbk_bibliography_is_still_read_and_reported_by_its_own_finding(
        self, tmp_path: Path
    ):
        root = _project(tmp_path, bib_encoding="gbk")
        code, report = _check(root, "--bib", "refs.bib")
        assert "source-encoding" not in _codes(report)
        assert code in (0, 1)


class TestTheVerdictSurvivesTheCache:
    def test_a_second_run_says_the_same_thing(self, tmp_path: Path):
        root = _project(tmp_path, page_encoding="gbk")
        first = _check(root)
        second = _check(root)
        assert first[0] == second[0] == 1
        assert _codes(second[1]) == _codes(first[1])

    def test_the_rubbish_is_not_stored_as_text(self, tmp_path: Path):
        root = _project(tmp_path, page_encoding="gbk")
        _check(root)
        stored = list((root / ".citevouch" / "cache").glob("*.json"))
        assert stored == []
