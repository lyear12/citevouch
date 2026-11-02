"""Two zeros that look alike, and only one of them is about the machine.

``draft`` ends by saying "read it, then ``citevouch check <file>`` to see what
it got wrong".  That advice is right when the file holds proposals and wrong
when it holds five comment lines, which is what a manuscript with no citation
the parser recognises produces.  Measured before this: a draft with no markers
and a draft whose single marker pointed at a missing PDF gave the same stderr
summary, the same exit 0 and almost the same file, so an author whose citations
were written ``(Van Eecke 2026)`` was told to go read proposals that had never
been made.
"""

from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from citevouch.cli import main

NL = chr(10)


def _draft(root: Path, body: str) -> tuple[int, str, str]:
    (root / "p.md").write_text(body, encoding="utf-8", newline=NL)
    out = io.StringIO()
    with redirect_stdout(out), redirect_stderr(out):
        code = main(["draft", "p.md", "-o", "o.md", "--root", str(root)])
    written = (root / "o.md").read_text(encoding="utf-8")
    return code, out.getvalue(), written


class TestTheTwoZerosAreNotTheSameZero:
    def test_no_citations_says_so_in_the_summary(self, tmp_path):
        code, said, _ = _draft(tmp_path, "# Draft" + NL + NL + "Plain prose." + NL)
        assert code == 0
        assert "no citations were found" in said
        # The old summary claimed a count of citations left as comments, which
        # is a statement about a set this run never formed.
        assert "0 citation(s) left as comments" not in said

    def test_no_citations_does_not_send_the_reader_to_a_report_about_nothing(self, tmp_path):
        _, said, _ = _draft(tmp_path, "# Draft" + NL + NL + "Plain prose." + NL)
        assert "to see what it got wrong" not in said

    def test_no_citations_names_the_forms_that_are_read(self, tmp_path):
        _, said, _ = _draft(tmp_path, "# Draft" + NL + NL + "Plain prose." + NL)
        assert "[@key]" in said
        assert chr(92) + "cite{key}" in said

    def test_no_citations_says_so_in_the_file_too(self, tmp_path):
        # stderr is not what gets committed and read six months later; the file
        # is, and it is the thing the advice points at.
        _, _, written = _draft(tmp_path, "# Draft" + NL + NL + "Plain prose." + NL)
        assert "No citations were found" in written

    def test_a_citation_with_no_pdf_keeps_the_old_advice(self, tmp_path):
        # The control: this zero IS about the machine, the file does hold
        # something to read, and the advice is correct.
        code, said, written = _draft(
            tmp_path, "# D" + NL + NL + "A sentence [@nowhere2019]." + NL
        )
        assert code == 0
        assert "1 citation(s) left as comments" in said
        assert "to see what it got wrong" in said
        assert "No citations were found" not in written

    def test_the_flag_is_false_whenever_a_site_was_found(self):
        from citevouch.draft import citation_sites

        assert citation_sites("nothing here") == []
        assert citation_sites("see [@a2020]") != []
        assert citation_sites("see " + chr(92) + "cite{a2020}") != []
