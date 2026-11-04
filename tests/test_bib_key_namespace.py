"""Two namespaces, and the sentence that mixes them up.

`source` names a local document (a PDF on disk).  `ref` names a bibliography
entry.  `Claim`'s docstring says the two are "deliberately kept apart" because
conflating them "produces false 'key not in bibliography' findings" — but the
checker falls back to the source name when no `ref` was written, and the
sentence it printed then was:

    claim c1 cites 'paper', which is not in the bibliography the ledger recorded

Measured on a project whose claim writes `source=paper` and no `ref=`, with a
`refs.bib` holding `knuth2020`.  Nothing in the manuscript ever names that
bibliography key, so the sentence tells the author they cited something they
never wrote.  The finding itself is right (a bibliography is present and this
claim names nothing in it); the words pointing at it were not.

These tests pin the two halves that must both hold at once: the fallback keeps
working (a project that names its PDF and its entry the same way stays green),
and the sentence never claims the author wrote a key they did not write.
"""

from __future__ import annotations

from pathlib import Path

from citevouch.cli import main

NL = chr(10)
PAGE = "We collected 40,688 examples in total." + NL
BIB = "@article{knuth2020, author={A}, title={T}, journal={J}, year={2020}}" + NL


def _project(root: Path, attrs: str = "", source_key: str = "paper", bib: bool = True) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "page.txt").write_text(PAGE, encoding="utf-8", newline=NL)
    (root / "sources.toml").write_text(
        "[sources]" + NL + f'{source_key} = "page.txt"' + NL, encoding="utf-8", newline=NL
    )
    if bib:
        (root / "refs.bib").write_text(BIB, encoding="utf-8", newline=NL)
    (root / "m.md").write_text(
        f"```claim id=c1 source={source_key} {attrs}page=1"
        + NL
        + "quote: |"
        + NL
        + "  We collected 40,688 examples in total."
        + NL
        + "```"
        + NL,
        encoding="utf-8",
        newline=NL,
    )
    return root


def _lines(captured: str) -> list[str]:
    return [line for line in captured.splitlines() if line.startswith("[")]


class TestTheSentenceNamesTheNamespaceItUsed:
    def test_a_claim_with_no_ref_is_not_said_to_cite_its_source(self, tmp_path: Path, capsys):
        root = _project(tmp_path / "p")
        code = main(["check", "m.md", "--root", str(root), "--bib", "refs.bib"])
        out = capsys.readouterr().out
        assert code == 1
        missing = [line for line in _lines(out) if "bib-key-missing" in line]
        assert len(missing) == 1
        assert "cites 'paper'" not in missing[0], missing[0]
        # The fix is one attribute, so the sentence has to say which one.  The
        # first clause already says `ref=` was not written, so assert on the
        # advice: a reader who is told "write the key" has to go and find the
        # syntax themselves.
        assert "Write `ref=" in missing[0], missing[0]
        # The complaint is that the *source's* name was used, so the sentence
        # has to name the thing it looked up - otherwise it describes a lookup
        # the reader cannot repeat.
        assert "'paper'" in missing[0], missing[0]

    def test_a_claim_that_names_a_key_is_still_said_to_cite_it(self, tmp_path: Path, capsys):
        root = _project(tmp_path / "p", attrs="ref=phantom ")
        code = main(["check", "m.md", "--root", str(root), "--bib", "refs.bib"])
        out = capsys.readouterr().out
        assert code == 1
        missing = [line for line in _lines(out) if "bib-key-missing" in line]
        assert len(missing) == 1
        assert "cites 'phantom'" in missing[0], missing[0]

    def test_the_severity_does_not_change(self, tmp_path: Path, capsys):
        """The words were wrong; the verdict was not.  Nothing here softens it."""
        root = _project(tmp_path / "p")
        code = main(["check", "m.md", "--root", str(root), "--bib", "refs.bib"])
        out = capsys.readouterr().out
        assert code == 1
        assert "[high] bib-key-missing" in out, out

    def test_the_entry_nothing_cites_is_still_reported(self, tmp_path: Path, capsys):
        root = _project(tmp_path / "p")
        main(["check", "m.md", "--root", str(root), "--bib", "refs.bib"])
        out = capsys.readouterr().out
        unused = [line for line in _lines(out) if "bib-key-unused" in line]
        assert unused and "knuth2020" in unused[0], out


class TestTheFallbackStillEarnsItsKeep:
    def test_a_source_named_like_an_entry_needs_no_ref(self, tmp_path: Path, capsys):
        """The reason the fallback exists: one name for the PDF and the entry."""
        root = _project(tmp_path / "p", source_key="knuth2020")
        code = main(["check", "m.md", "--root", str(root), "--bib", "refs.bib"])
        out = capsys.readouterr().out
        assert code == 0, out
        assert "bib-key-missing" not in out
        assert "bib-key-unused" not in out

    def test_the_recorded_path_says_the_same_thing(self, tmp_path: Path, capsys):
        root = _project(tmp_path / "p")
        assert main(["scan", "m.md", "--root", str(root), "--bib", "refs.bib"]) == 0
        capsys.readouterr()
        code = main(["check", "--use-recorded", "m.md", "--root", str(root)])
        out = capsys.readouterr().out
        assert code == 1
        missing = [line for line in _lines(out) if "bib-key-missing" in line]
        assert missing and "cites 'paper'" not in missing[0], out


class TestWithoutABibliography:
    def test_nothing_is_said_about_keys(self, tmp_path: Path, capsys):
        root = _project(tmp_path / "p", bib=False)
        code = main(["check", "m.md", "--root", str(root)])
        out = capsys.readouterr().out
        assert code == 0, out
        assert "bib-" not in out
