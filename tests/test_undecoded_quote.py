"""A quote that was never decoded is not a quote that is not on the page.

A manuscript saved in GBK reaches ``textnorm._decode_text``, which ends in
``raw.decode("utf-8", errors="replace")``.  The fence line, the ``quote:``
label and every attribute are ASCII, so the block is still recognised; only
the quoted words themselves come out as ``\\ufffd`` characters.  Measured on a
111-byte GBK manuscript whose quoted sentence is printed verbatim on page 1:

    [high] quote-missing at manuscript.md:3 (c1): \ufffd\ufffd\ufffd\u6570\u636e
    \u2014 quote not found in page.txt

That is a verdict about the author's sentence when the fact is about the
file's encoding, and it is the one class of answer this tool must never give.
The bytes that could not be decoded are known exactly: they are the positions
where the decoder wrote a replacement character.  A claim whose quote holds
one was never read, so it was never searched, so nothing may be said about
whether it is on the page.
"""

from __future__ import annotations

from pathlib import Path

from citevouch.cli import main

NL = chr(10)
B3 = "`" * 3
QUOTE = "本文收集了六万八千个例句，全部来自语料库中的真实文本。"
PAGE = "前言" + NL + QUOTE + NL
#: Long enough that the ASCII ``[@paper]`` survives the GBK bytes being read
#: as UTF-8.  The ``[`` and the ``@`` are only swallowed when an odd byte of a
#: two-byte character lands on them, and with a short sentence it does.
FILL = "我们在三个语料库上重复了这个实验，结果与之前一致。"
CITED = QUOTE + FILL + " [@paper]"


def _project(tmp_path: Path, encoding: str = "gbk") -> Path:
    """A project whose *manuscript* (not its source) is in ``encoding``."""
    root = tmp_path / "p"
    root.mkdir(parents=True, exist_ok=True)
    (root / "page.txt").write_text(PAGE, encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
    )
    body = (
        "研究问题"
        + NL
        + NL
        + B3
        + "claim id=c1 source=paper page=1"
        + NL
        + "quote: "
        + QUOTE
        + NL
        + B3
        + NL
    )
    (root / "manuscript.md").write_bytes(body.encode(encoding))
    return root


def _run(root: Path, *argv: str) -> tuple[int, str, str]:
    import contextlib
    import io

    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main([*argv, "--root", str(root)])
    return code, out.getvalue(), err.getvalue()


def _check(root: Path, *extra: str) -> tuple[int, str]:
    code, out, _err = _run(root, "check", "manuscript.md", *extra)
    return code, out


def _codes(report: str) -> list[str]:
    return [line.split()[1] for line in report.splitlines() if line.startswith("[")]


class TestTheQuoteItselfWasNeverDecoded:
    def test_the_run_does_not_accuse_the_quote(self, tmp_path: Path):
        # The sentence is printed verbatim on page 1 of the source.  The only
        # reason the tool cannot find it is that the tool could not read the
        # manuscript it is written in.
        _code, report = _check(_project(tmp_path))
        assert "quote-missing" not in _codes(report), report
        assert "quote not found" not in report

    def test_it_says_the_words_could_not_be_decoded(self, tmp_path: Path):
        _code, report = _check(_project(tmp_path))
        assert "claim-not-decoded" in _codes(report), report

    def test_the_message_names_the_file_and_a_way_out(self, tmp_path: Path):
        # A finding the author can act on.  They cannot edit bytes they cannot
        # see, so the message has to name the file and the conversion.
        _code, report = _check(_project(tmp_path))
        line = next(line for line in report.splitlines() if "claim-not-decoded" in line)
        assert "manuscript.md" in line
        assert "iconv" in line

    def test_the_severity_is_the_one_the_table_says(self, tmp_path: Path):
        # High, like `source-encoding`: the author believes this quote was
        # checked, and it was not.
        _code, report = _check(_project(tmp_path))
        assert "[high] claim-not-decoded" in report

    def test_it_is_counted_as_skipped_not_missing(self, tmp_path: Path):
        # The tally is the sentence most authors read.  Saying "1 missing"
        # about a claim that was never searched is the same accusation in
        # fewer words.
        _code, report = _check(_project(tmp_path))
        assert "1 claim — 0 verified, 0 moved, 0 missing, 1 skipped" in report

    def test_the_ledger_route_agrees_with_the_fresh_one(self, tmp_path: Path):
        # `action.yml` runs `check --use-recorded` on every pull request, so
        # the recorded pass is the one most authors meet.  A fix in one reader
        # and not the other is this project's most repeated defect.
        root = _project(tmp_path)
        assert _run(root, "scan", "manuscript.md")[0] == 0
        fresh_code, fresh = _check(root)
        recorded_code, recorded = _check(root, "--use-recorded")
        assert recorded_code == fresh_code
        assert "claim-not-decoded" in _codes(recorded)
        assert "quote-missing" not in _codes(recorded)
        assert _codes(fresh) == _codes(recorded)


class TestWhatMustStillBeChecked:
    def test_a_readable_manuscript_still_verifies(self, tmp_path: Path):
        # The whole point of the guard is that a manuscript this tool *can*
        # read is searched exactly as before.
        root = _project(tmp_path, encoding="utf-8")
        code, report = _check(root)
        assert code == 0
        assert _codes(report) == ["quote-found"]
        assert "1 claim — 1 verified" in report

    def test_a_real_miss_is_still_a_miss(self, tmp_path: Path):
        # A UTF-8 manuscript quoting a sentence the page does not print is
        # still `quote-missing`.  A guard that swallowed this would trade one
        # silence for another.
        root = _project(tmp_path, encoding="utf-8")
        (root / "page.txt").write_text("完全不同的句子。" + NL, encoding="utf-8", newline=NL)
        code, report = _check(root)
        assert code == 1
        assert "quote-missing" in _codes(report)

    def test_a_replacement_character_in_the_page_is_not_the_guard(self, tmp_path: Path):
        # The guard is about the manuscript.  A page that legitimately holds
        # U+FFFD (an extraction artefact) must not stop the claim being judged.
        root = _project(tmp_path, encoding="utf-8")
        (root / "page.txt").write_text("\ufffd" + NL + QUOTE + NL, encoding="utf-8", newline=NL)
        code, report = _check(root)
        assert code == 0
        assert "claim-not-decoded" not in _codes(report)

    def test_an_eight_bit_source_is_still_the_source_encoding_finding(self, tmp_path: Path):
        # The neighbouring contract, unchanged: a source file this tool cannot
        # decode is `source-encoding` (high) and never `quote-missing`.  The
        # two defects look alike and are answered by different readers.
        root = _project(tmp_path, encoding="utf-8")
        (root / "page.txt").write_bytes(PAGE.encode("gbk"))
        code, report = _check(root)
        assert code == 1
        assert "source-encoding" in _codes(report)
        assert "quote-missing" not in _codes(report)


LONG = (
    "研究问题"
    + NL
    + NL
    + QUOTE
    + "我们在三个语料库上重复了这个实验，结果与之前一致。"
    + "所有数据都公开在同一个仓库里，任何人都可以复现。"
    + NL
)


def _undecoded(tmp_path: Path) -> Path:
    """A project whose *manuscript* is GBK and holds no citation at all."""
    root = tmp_path / "d"
    root.mkdir(parents=True, exist_ok=True)
    (root / "page.txt").write_text(PAGE, encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
    )
    (root / "manuscript.md").write_bytes(LONG.encode("gbk"))
    return root


class TestTheDraftSaysWhyItFoundNothing:
    def test_a_zero_from_an_undecoded_file_does_not_blame_the_markers(self, tmp_path: Path):
        # The command found no citation, and that count is honest.  The reason
        # it gives is not: it reads two syntaxes, and this file never reached
        # the reader at all.  Measured before this branch existed: a GBK
        # manuscript whose citations were ordinary `[@key]` got "no citations
        # were found to propose them for (this command reads `[@key]` and
        # `\cite{key}`)", which sends the author to rewrite a correct line.
        root = _undecoded(tmp_path)
        code, out, err = _run(root, "draft", "manuscript.md", "-o", "claims.md")
        assert code == 0
        said = out + err
        assert "never decoded" in said
        assert "iconv" in said

    def test_the_proposals_file_says_it_too(self, tmp_path: Path):
        # The stderr line scrolls away; the file is what the author opens next.
        root = _undecoded(tmp_path)
        _run(root, "draft", "manuscript.md", "-o", "claims.md")
        written = (root / "claims.md").read_text(encoding="utf-8")
        assert "never decoded" in written
        assert "iconv" in written
        assert "written any other way" not in written

    def test_a_readable_file_still_gets_the_marker_advice(self, tmp_path: Path):
        # The neighbouring message, unchanged: with nothing wrong with the
        # encoding, the only reason for a zero is how the citation was
        # written, and that is what the author is told.
        root = _undecoded(tmp_path)
        (root / "manuscript.md").write_text(
            "研究问题" + NL + NL + "这句话没有任何引用。" + NL,
            encoding="utf-8",
            newline=NL,
        )
        code, out, err = _run(root, "draft", "manuscript.md", "-o", "claims.md")
        assert code == 0
        said = out + err
        assert "written any other way" in said
        assert "never decoded" not in said

    def test_a_readable_citation_is_still_proposed(self, tmp_path: Path):
        # And the guard must not stop the ordinary path from working.
        root = _undecoded(tmp_path)
        (root / "manuscript.md").write_text(
            "研究问题" + NL + NL + QUOTE + " [@paper]" + NL,
            encoding="utf-8",
            newline=NL,
        )
        code, out, err = _run(root, "draft", "manuscript.md", "-o", "claims.md")
        assert code == 0
        assert "1 claim block(s) proposed" in (out + err)


def _cited(tmp_path: Path, encoding: str = "gbk") -> Path:
    """A project whose manuscript holds a citation that *survives* the damage.

    Whether the ASCII ``[@paper]`` survives being read as UTF-8 depends on
    byte alignment: a 74-byte sentence swallows the ``[`` and the ``@``, and
    then ``draft`` finds no citation at all.  This body is long enough that
    the citation is found, which is the only way to reach the branch below.
    """
    root = tmp_path / "s"
    root.mkdir(parents=True, exist_ok=True)
    # The page prints both sentences, so the UTF-8 control below has something
    # to find.  The citation hangs off the second one.
    (root / "page.txt").write_text(PAGE + FILL + NL, encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
    )
    (root / "manuscript.md").write_bytes((CITED + NL).encode(encoding))
    return root


class TestTheSentenceItselfWasNeverDecoded:
    def test_the_page_is_not_blamed_for_the_encoding(self, tmp_path: Path):
        # Measured before this branch existed, on a GBK manuscript whose
        # `[@paper]` survived: `draft` proposed nothing and wrote "nothing on
        # any page shares enough terms with the sentence (3 needed)".  That is
        # a true sentence about a comparison nobody should have run - the
        # words it compared were 96 replacement characters - and it names the
        # one thing that was never at fault.
        root = _cited(tmp_path)
        code, _out, _err = _run(root, "draft", "manuscript.md", "-o", "claims.md")
        assert code == 0
        written = (root / "claims.md").read_text(encoding="utf-8")
        assert "shares enough terms" not in written
        assert "never decoded" in written
        assert "iconv" in written
        # The sentence is in the file that needs converting, and that is the
        # file the author has to run the command on.  A reason that says "the
        # manuscript" without naming it sends them to look at the source page.
        assert "manuscript.md is not UTF-8" in written

    def test_it_says_how_many_characters_were_lost(self, tmp_path: Path):
        # The count is the one fact the decoder recorded, and it tells the
        # author whether the file is mostly readable or mostly gone.
        root = _cited(tmp_path)
        _run(root, "draft", "manuscript.md", "-o", "claims.md")
        written = (root / "claims.md").read_text(encoding="utf-8")
        assert "characters of it are replacement characters" in written

    def test_the_readable_version_of_the_same_file_is_proposed(self, tmp_path: Path):
        # The neighbouring contract, unchanged: same words, UTF-8, one block.
        root = _cited(tmp_path, encoding="utf-8")
        code, out, err = _run(root, "draft", "manuscript.md", "-o", "claims.md")
        assert code == 0
        assert "1 claim block(s) proposed" in (out + err)

    def test_a_readable_sentence_that_matches_nothing_still_says_so(self, tmp_path: Path):
        # The other direction: a sentence the pages really do not share enough
        # terms with must keep the old reason, because for that file the page
        # *is* the fact.
        root = _cited(tmp_path, encoding="utf-8")
        (root / "manuscript.md").write_text(
            "研究问题" + NL + NL + "太阳能电池板的转换效率在阴天会显著下降 [@paper]" + NL,
            encoding="utf-8",
            newline=NL,
        )
        code, _out, _err = _run(root, "draft", "manuscript.md", "-o", "claims.md")
        assert code == 0
        written = (root / "claims.md").read_text(encoding="utf-8")
        assert "shares enough terms" in written
        assert "never decoded" not in written


def _mixed(tmp_path: Path) -> Path:
    """A GBK manuscript holding one decodable citation and one that is not.

    The page is printed by the source, so the ASCII sentence is quotable; the
    Chinese one is not, because its own characters are replacement characters.
    A guard that looks at the whole file cannot tell these two apart, and a
    guard that looks at the whole file is what a first draft would write.
    """
    root = tmp_path / "m"
    root.mkdir(parents=True, exist_ok=True)
    ascii_sentence = "We collected 40,688 examples from the corpus."
    chinese = QUOTE + FILL + " [@paper]"
    (root / "alpha.txt").write_text(ascii_sentence + NL, encoding="utf-8", newline=NL)
    (root / "page.txt").write_text(QUOTE + FILL + NL, encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'alpha = "alpha.txt"' + NL + 'paper = "page.txt"' + NL,
        encoding="utf-8",
        newline=NL,
    )
    body = NL.join([ascii_sentence + " [@alpha]", "", chinese, ""])
    (root / "manuscript.md").write_bytes(body.encode("gbk"))
    return root


class TestAFileCanBeHalfReadable:
    def test_the_readable_citation_is_still_proposed(self, tmp_path: Path):
        # Measured: a guard keyed on the whole file (`text.count(UNDECODED)`)
        # skipped *both* citations, including the ASCII one whose sentence was
        # never damaged.  The file is bad; the sentence is what matters.
        root = _mixed(tmp_path)
        code, _out, _err = _run(root, "draft", "manuscript.md", "-o", "claims.md")
        assert code == 0
        written = (root / "claims.md").read_text(encoding="utf-8")
        assert "```claim" in written
        assert "id=alpha" in written

    def test_the_damaged_citation_is_the_one_left_as_a_comment(self, tmp_path: Path):
        root = _mixed(tmp_path)
        _run(root, "draft", "manuscript.md", "-o", "claims.md")
        written = (root / "claims.md").read_text(encoding="utf-8")
        comments = [ln for ln in written.splitlines() if ln.startswith("<!-- line ")]
        assert len(comments) == 1
        assert "paper" in comments[0]
        assert "never decoded" in comments[0]

    def test_the_summary_line_counts_one_of_each(self, tmp_path: Path):
        # "1 claim block(s) proposed (1 verbatim), 1 citation(s) left as
        # comments" - the older reason would have been true of the file and
        # false of the citation.
        root = _mixed(tmp_path)
        _code, out, err = _run(root, "draft", "manuscript.md", "-o", "claims.md")
        said = out + err
        assert "1 claim block(s) proposed" in said
        assert "1 citation(s) left as comments" in said


class TestTheDoctorMayNotBeMoreOptimisticThanTheRun:
    def test_a_readable_project_passes(self, tmp_path: Path):
        # The neighbouring contract, unchanged.
        root = _project(tmp_path, encoding="utf-8")
        code, out, err = _run(root, "doctor", "--manuscript", "manuscript.md")
        assert code == 0
        assert "1 of 9 checks failed" not in (out + err)

    def test_an_undecodable_manuscript_is_not_all_ok(self, tmp_path: Path):
        # `doctor` exists to explain a run that found nothing.  Measured on the
        # GBK manuscript: nine `[ok  ]` lines and exit 0, while `check` on the
        # same project was accusing the author's quote of not being on a page
        # that prints it.  A diagnostic is not allowed to be more optimistic
        # than the command it explains.
        root = _project(tmp_path)
        code, out, err = _run(root, "doctor", "--manuscript", "manuscript.md")
        said = out + err
        assert code == 1
        assert "[FAIL] claims" in said
        assert "never decoded" in said
        assert "1 of 9 checks failed" in said

    def test_the_doctor_names_the_conversion(self, tmp_path: Path):
        # A problem report without the sentence that fixes it is a riddle.
        root = _project(tmp_path)
        _code, out, err = _run(root, "doctor", "--manuscript", "manuscript.md")
        said = out + err
        assert "iconv" in said
        assert "manuscript.md" in said
