"""The tool reads the text the file holds, whatever editor wrote it.

Two faults share one cause, and both were found by asking what happens to a
file that a normal Windows program produced.

**The encoding.**  Notepad's "Unicode" option, and Excel's text export, both
write UTF-16.  Read as UTF-8 those bytes do not fail: they become one
replacement character followed by a NUL between every letter.  The pipeline
treats that as text, so a bibliography saved that way parsed to zero entries
and the run finished with exit 0.

**The empty result.**  A bibliography that yielded no entries is not an empty
bibliography, and the difference matters because ``verify`` skips
``bib-key-missing`` entirely when the ledger recorded no entries.  So the run
over an unreadable bibliography was *quieter* than the run over one missing a
single key - the wrong way round for a tool whose whole job is to fail on the
things nobody checked.

Source text is the third case and it used to be left out on purpose: a mangled
source produces ``quote-missing`` against a page the author is looking at,
which is loud, so the argument went that it did not need a test.  Being loud is
not the same as being right.  That finding is a *high* one and it accuses the
author of misquoting a page whose only problem is how the file was saved, so
``TestADocumentWhoseCharactersAreNotLatin`` covers it too.

The detector is the interesting half.  It asks whether one side of every 16-bit
pair is zero, which is true of Latin text and false of anything else: a Han
character's high byte lies in 0x4E-0x9F.  A Chinese document saved as UTF-16
without a mark therefore had no NULs at all, missed the detector, and decoded
into replacement characters.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from citevouch.cli import main

NL = chr(10)
GOOD = "We trained on two corpora and counted 40,688 entries." + NL
CLAIM = (
    "```claim id=c1 source=p ref=paper"
    + NL
    + ">> We trained on two corpora and counted 40,688 entries."
    + NL
    + "```"
    + NL
)
BIB = "@article{paper, author={A}, title={T}, journal={J}, year={2026}}" + NL

#: Encodings a desktop program can produce by accident.
DESKTOP = (
    "utf-8-sig",
    "utf-16",
    "utf-16-le",
    "utf-16-be",
    "utf-32",
)


def _project(
    tmp_path: Path,
    encoding: str = "utf-8",
    bib_encoding: str | None = None,
    body: str = GOOD,
) -> Path:
    root = tmp_path / "p"
    root.mkdir(parents=True, exist_ok=True)
    (root / "p.txt").write_bytes(body.encode("utf-8"))
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'p = "p.txt"' + NL, encoding="utf-8", newline=NL
    )
    (root / "m.md").write_bytes(CLAIM.encode(encoding))
    (root / "refs.bib").write_bytes(BIB.encode(bib_encoding or encoding))
    return root


def _codes(captured: str) -> list[str]:
    return [line.split()[1] for line in captured.splitlines() if line.startswith("[")]


class TestTheFileIsDecodedTheWayItWasWritten:
    @pytest.mark.parametrize("encoding", DESKTOP)
    def test_every_desktop_encoding_reads_like_plain_utf8(
        self, tmp_path: Path, capsys, encoding: str
    ):
        # The comparison is against the plain file, not against what the test
        # believes the answer is: that way a change in the report for unrelated
        # reasons fails here instead of passing.
        plain = _project(tmp_path / "plain")
        assert main(["check", "m.md", "--root", str(plain), "--bib", "refs.bib"]) == 0
        baseline = capsys.readouterr().out

        other = _project(tmp_path / "other", encoding=encoding)
        assert main(["check", "m.md", "--root", str(other), "--bib", "refs.bib"]) == 0
        report = capsys.readouterr().out

        assert _codes(report) == _codes(baseline) == ["quote-found"]
        assert "bib-entry-header-unparsed" not in report

    def test_utf16_without_a_mark_is_still_decoded(self, tmp_path: Path, capsys):
        # Writing "UTF-16" adds a mark; "UTF-16-LE" does not.  A file can carry
        # the encoding without the sign that names it, so the NUL pattern has
        # to be read on its own.
        root = _project(tmp_path, encoding="utf-16-le")
        assert main(["check", "m.md", "--root", str(root), "--bib", "refs.bib"]) == 0
        assert _codes(capsys.readouterr().out) == ["quote-found"]

    def test_text_with_no_nul_bytes_is_never_reinterpreted(self, tmp_path: Path):
        from citevouch.textnorm import read_text

        # A guard over the detector, not over the decoder: if this ever starts
        # returning mojibake, the NUL heuristic is matching on prose.
        path = tmp_path / "x.txt"
        body = "The corpus contains 154,391 utterances. 摘要：构式语法。"
        path.write_bytes(body.encode("utf-8"))
        assert read_text(path) == body

    def test_binary_noise_is_not_turned_into_silence(self, tmp_path: Path, capsys):
        # Random bytes have NULs on both sides, so neither UTF-16 branch fires;
        # but the point of the test is only that the run is decided by a
        # finding rather than by whatever the decoder produced.
        root = _project(tmp_path)
        (root / "refs.bib").write_bytes(bytes(range(256)) * 4)
        code = main(["check", "m.md", "--root", str(root), "--bib", "refs.bib"])
        assert code == 1
        assert "bib-unreadable" in capsys.readouterr().out


class TestADocumentWhoseCharactersAreNotLatin:
    """The NUL heuristic asked whether one side of every pair is zero.

    That is a fact about Latin text, not about UTF-16.  A Han character encoded
    as UTF-16 has a high byte in 0x4E-0x9F and a Cyrillic one 0x04, so neither
    a Chinese nor a Russian document has any NULs at all, the detector never
    fired, the bytes decoded as UTF-8 into replacement characters, every quote
    missed, and the run ended with a high finding that accused the author of
    not quoting a page whose only problem was how the file was saved.

    The previous version of this file argued that a mangled *source* is loud
    enough not to need a test.  It is loud - and it says the wrong thing, in
    the one vocabulary this tool must never misuse.

    Every case below is little-endian, and that is not a gap in the test: with
    no mark to go on, a big-endian document in a single script is genuinely
    undecidable.  Swapping a Han character's bytes yields another Han
    character, so both readings are equally clean, equally long and both
    plausible; a decoder that picked one would be guessing.  The tool reads the
    shape exporters produce and the docstring says only that much, which is the
    difference between a limit and a lie.
    """

    CHINESE = "构式网络很小，训练语料合计 154,391 句，角色集实例 440,528 个。" + NL
    RUSSIAN = "Корпус содержит 154,391 предложение и 440,528 конструкций." + NL

    @pytest.mark.parametrize("text", (CHINESE, RUSSIAN))
    def test_a_non_latin_document_saved_as_utf16_is_still_read(self, tmp_path: Path, text: str):
        from citevouch.textnorm import read_text

        path = tmp_path / "x.txt"
        path.write_bytes(text.encode("utf-16-le"))
        assert read_text(path) == text

    def test_the_quote_is_found_instead_of_missing(self, tmp_path: Path, capsys):
        # End to end, because the encoding is only ever a problem through the
        # verdict it produces.  A file read as mojibake yields `quote-missing`
        # at high severity; a file read correctly yields `quote-found`.
        for text, name in ((self.CHINESE, "chinese"), (self.RUSSIAN, "russian")):
            root = tmp_path / name
            root.mkdir()
            claim = "```claim id=c1 source=p" + NL + ">> " + text.strip() + NL + "```" + NL
            (root / "p.txt").write_bytes(text.encode("utf-16-le"))
            (root / "sources.toml").write_text(
                "[sources]" + NL + 'p = "p.txt"' + NL, encoding="utf-8", newline=NL
            )
            (root / "m.md").write_text(claim, encoding="utf-8", newline=NL)

            code = main(["check", "m.md", "--root", str(root)])
            report = capsys.readouterr().out
            assert _codes(report) == ["quote-found"], (name, report)
            assert code == 0

    def test_big_endian_without_a_mark_is_admitted_not_guessed(self, tmp_path: Path):
        """The limit is stated, so it is pinned.

        If someone later teaches the decoder to try big-endian too, this test
        fails and forces the docstring to say so as well.  That is the point:
        an undocumented improvement is a documented promise nobody checked.
        """
        from citevouch.textnorm import read_text

        path = tmp_path / "x.txt"
        text = self.CHINESE
        path.write_bytes(text.encode("utf-16-be"))
        assert read_text(path) != text

    def test_a_clean_utf8_file_is_never_reinterpreted(self, tmp_path: Path):
        from citevouch.textnorm import read_text

        # The fallback only runs when the UTF-8 reading is self-evidently
        # wrong, so the common case must be provably untouched - including the
        # one text in this file that holds both scripts.
        for body in (self.CHINESE, self.RUSSIAN, GOOD):
            path = tmp_path / "x.txt"
            path.write_bytes(body.encode("utf-8"))
            assert read_text(path) == body


class TestABibliographyNobodyCouldReadIsNotAnEmptyOne:
    def test_zero_entries_out_of_a_file_with_content_is_a_finding(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        code = main(["check", "m.md", "--root", str(root), "--bib", "refs.bib"])
        assert code == 0, capsys.readouterr().err

        (root / "refs.bib").write_bytes(b"this is not bibtex at all, it is prose" + NL.encode())
        code = main(["check", "m.md", "--root", str(root), "--bib", "refs.bib"])
        out = capsys.readouterr().out
        assert code == 1
        assert "bib-unreadable" in out

    def test_an_empty_file_is_not_a_finding(self, tmp_path: Path, capsys):
        # Nothing in it means nothing to complain about; the claim's own
        # source-* checks are what speak for a project with no bibliography.
        root = _project(tmp_path)
        (root / "refs.bib").write_bytes(b"")
        main(["check", "m.md", "--root", str(root), "--bib", "refs.bib"])
        assert "bib-unreadable" not in capsys.readouterr().out

    def test_one_readable_entry_is_enough_to_stay_quiet(self, tmp_path: Path, capsys):
        root = _project(tmp_path)
        (root / "refs.bib").write_bytes(
            (BIB + "garbage that is not an entry" + NL).encode("utf-8")
        )
        main(["check", "m.md", "--root", str(root), "--bib", "refs.bib"])
        out = capsys.readouterr().out
        # It still complains about the stray text - just not about the whole
        # file being unreadable, which it is not.
        assert "bib-unreadable" not in out
        assert "bib-entry-header-unparsed" in out

    def test_the_finding_names_the_encoding_as_the_likely_cause(self, tmp_path: Path):
        # The message is the fix instruction.  "Not one entry could be read"
        # alone leaves the author editing braces; the encoding is what they
        # actually have to change.
        from citevouch.bibtex import parse_bib

        result = parse_bib(bytes(range(256)).decode("utf-8", errors="replace"))
        found = [f for f in result.findings if f.code == "bib-unreadable"]
        assert found, [f.code for f in result.findings]
        assert "UTF-16" in found[0].message
