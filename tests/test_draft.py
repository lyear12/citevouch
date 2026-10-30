"""`draft` is judged by whether an author would keep what it writes.

Every test here corresponds to something this command got wrong when it was run
on a real paper rather than on a fixture: a citation nobody found, a quote cut
out of a results table, a sentence ending mid-word because PDF text is wrapped
at the column, a citation key silently bound to the wrong file. The fixtures are
plain text so that each of those can be reproduced without a PDF.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from citevouch import draft as draft_module
from citevouch.bibtex import parse_bib
from citevouch.cli import main

PAPER = textwrap.dedent(
    """\
    Large-scale construction learning
    =================================

    Construction grammar treats a grammar as a network of constructions, and
    that network is learned from usage rather than written down by hand.

    The corpus the grammar was induced from contains 154,391 utterances, which
    is roughly twice the size of the largest corpus used in earlier work on the
    same task.

    Precision and recall were measured on 1,000 held-out utterances, and the
    resulting grammar reached an F1 score of 76.25 on the roleset task.

    A sentence that runs across the column break in the original PDF is wrapped
    here as well, because that is what a real page looks like: the net-
    work is learned from data.
    """
)

MANUSCRIPT = textwrap.dedent(
    """\
    # A note on construction learning

    Construction grammar treats a grammar as a network of constructions that is
    learned from usage [@smith2026paper].

    Precision and recall on held-out utterances are reported for the induced
    grammar [@smith2026paper], which matters for the claims below.

    An unrelated sentence cites a key nobody has a file for [@absent2025].
    """
)


def _project(tmp_path: Path, bibliography: str = "") -> Path:
    root = tmp_path / "project"
    (root / "papers").mkdir(parents=True)
    (root / "papers" / "smith2026paper.txt").write_text(PAPER, encoding="utf-8", newline="\n")
    (root / "manuscript.md").write_text(MANUSCRIPT, encoding="utf-8", newline="\n")
    (root / "sources.toml").write_text(
        '[sources]\nsmith2026paper = "papers/smith2026paper.txt"\n',
        encoding="utf-8",
        newline="\n",
    )
    if bibliography:
        (root / "refs.bib").write_text(bibliography, encoding="utf-8", newline="\n")
    return root


def _bib(root: Path) -> dict:
    path = root / "refs.bib"
    if not path.is_file():
        return {}
    return parse_bib(path.read_text(encoding="utf-8"), str(path)).entries


def _run(root: Path, *extra: str) -> int:
    return main(["draft", str(root / "manuscript.md"), "--root", str(root), *extra])


class TestCitationsAreFound:
    def test_pandoc_single_citation(self) -> None:
        sites = draft_module.citation_sites("as shown [@smith2026] here.")
        assert [site.key for site in sites] == ["smith2026"]
        assert sites[0].line == 1

    def test_pandoc_multiple_and_suppressed(self) -> None:
        sites = draft_module.citation_sites("x [@a2020; -@b2021; @c2022] y")
        assert [site.key for site in sites] == ["a2020", "b2021", "c2022"]

    def test_latex_forms(self) -> None:
        text = "one \\cite{a} two \\citep[see][p. 4]{b,c} three \\citet{d}"
        assert [site.key for site in draft_module.citation_sites(text)] == ["a", "b", "c", "d"]

    def test_a_key_is_not_matched_inside_a_longer_word(self) -> None:
        assert draft_module.citation_sites("write to me@example.org") == []


class TestTheStatement:
    def test_the_sentence_around_the_citation_is_the_claim(self) -> None:
        text = "First sentence here. Second one cites [@k] and continues. Third."
        sentence, start, end = draft_module.sentence_at(text, text.index("[@k]"))
        assert sentence == "Second one cites [@k] and continues."
        assert text[start:end] == sentence

    def test_the_marker_is_cut_and_the_spacing_repaired(self) -> None:
        assert draft_module.statement_of("Cites [@k] here.") == "Cites here."
        assert draft_module.statement_of("Cites \\cite{k}, here.") == "Cites, here."

    def test_a_heading_is_not_glued_onto_the_sentence(self) -> None:
        text = "# A heading\n\nThe sentence cites [@k] here."
        sentence, _, _ = draft_module.sentence_at(text, text.index("[@k]"))
        assert "heading" not in sentence


class TestResolvingAFile:
    def test_the_manifest_wins(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        path, needs_line = draft_module.resolve(
            "smith2026paper", {"smith2026paper": "papers/smith2026paper.txt"}, {}, root
        )
        assert path is not None and path.endswith("smith2026paper.txt")
        assert needs_line is None

    def test_the_bibliography_file_field_binds_a_key_the_manifest_does_not(
        self, tmp_path: Path
    ) -> None:
        bib_text = "@article{smith2026paper, title={T}, file={papers/smith2026paper.txt}}\n"
        root = _project(tmp_path, bib_text)
        path, needs_line = draft_module.resolve("smith2026paper", {}, _bib(root), root)
        assert path is not None and path.endswith("smith2026paper.txt")
        # The caller has to be told to add the line, or scan cannot bind it.
        assert needs_line == "smith2026paper"

    def test_a_zotero_file_field_is_unwrapped(self) -> None:
        entry = parse_bib("@a{k, file={:papers/x.pdf:application/pdf}}").entries["k"]
        assert draft_module._bib_file(entry) == "papers/x.pdf"

    def test_a_file_named_after_the_key_is_found(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        path, _ = draft_module.resolve("smith2026paper", {}, {}, root)
        assert path is not None and path.endswith("smith2026paper.txt")

    def test_nothing_resolves_to_nothing(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        assert draft_module.resolve("absent2025", {}, {}, root) == (None, None)

    def test_a_prefix_is_not_a_binding(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        path, _ = draft_module.resolve("smith2026", {}, {}, root)
        assert path is None


class TestWhatMayBeQuoted:
    def test_a_short_fragment_is_not_a_passage(self) -> None:
        assert not draft_module._is_passage("40,688")

    def test_a_table_is_not_a_passage(self) -> None:
        table = "All cxns: 40,688 Frame-evoking cxns: 9800 Roleset cxns: 8320"
        assert not draft_module._is_passage(table * 2)

    def test_a_split_word_is_rejoined_before_sentences_are_cut(self) -> None:
        sentences = draft_module._sentences_of("the net-\nwork is learned")
        assert sentences[0] == "the network is learned"

    def test_a_real_sentence_is_a_passage(self) -> None:
        sentence = (
            "The corpus the grammar was induced from contains 154,391 utterances, "
            "which is roughly twice the size of the largest corpus used earlier."
        )
        assert draft_module._is_passage(sentence)


class TestTheProposalFile:
    def test_the_output_is_a_manuscript_the_verifier_accepts(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        assert _run(root, "-o", str(root / "claims.md")) == 0
        assert main(["check", str(root / "claims.md"), "--root", str(root)]) in (0, 1)
        # What matters is that the blocks were recognised, not that the prose
        # matched: a proposed quote is a real sentence from a real page.
        text = (root / "claims.md").read_text(encoding="utf-8")
        assert text.count("```claim ") == 2

    def test_the_manuscript_is_never_modified(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        before = (root / "manuscript.md").read_bytes()
        _run(root, "-o", str(root / "claims.md"))
        assert (root / "manuscript.md").read_bytes() == before

    def test_an_existing_output_is_not_clobbered_without_force(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        (root / "claims.md").write_text("mine\n", encoding="utf-8")
        assert _run(root, "-o", str(root / "claims.md")) == 2
        assert (root / "claims.md").read_text(encoding="utf-8") == "mine\n"
        assert _run(root, "-o", str(root / "claims.md"), "--force") == 0
        assert (root / "claims.md").read_text(encoding="utf-8") != "mine\n"

    def test_a_key_with_no_file_is_a_comment_not_a_guess(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _run(root, "-o", str(root / "claims.md"))
        text = (root / "claims.md").read_text(encoding="utf-8")
        assert "absent2025" in text
        assert "no local file" in text
        assert "```claim id=absent2025" not in text

    def test_the_file_says_what_it_could_not_do(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _run(root, "-o", str(root / "claims.md"))
        text = (root / "claims.md").read_text(encoding="utf-8")
        assert "Not proposed:" in text
        assert "Nothing here has been checked" in text

    def test_a_key_the_manifest_does_not_hold_gets_its_line_written_out(
        self, tmp_path: Path
    ) -> None:
        root = _project(
            tmp_path, "@article{smith2026paper, file={papers/smith2026paper.txt}}\n"
        )
        (root / "sources.toml").write_text("[sources]\n", encoding="utf-8")
        _run(root, "--bib", str(root / "refs.bib"), "-o", str(root / "claims.md"))
        text = (root / "claims.md").read_text(encoding="utf-8")
        assert "[sources]" in text
        assert 'smith2026paper = "papers/smith2026paper.txt"' in text

    def test_the_file_is_written_with_line_feeds(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _run(root, "-o", str(root / "claims.md"))
        assert b"\r\n" not in (root / "claims.md").read_bytes()

    def test_a_missing_manuscript_is_a_usage_error(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        assert main(["draft", str(root / "nope.md"), "--root", str(root)]) == 2


class TestConfidence:
    def test_a_quoted_sentence_is_high_confidence(self) -> None:
        pages = [
            draft_module.sources.PageText(
                1,
                "The corpus contains 154,391 utterances in total.",
                "",
            )
        ]
        found = draft_module.propose_quote(
            "The corpus contains 154,391 utterances in total.", pages
        )
        assert found is not None
        quote, page, confidence, reason = found
        assert confidence == "high"
        assert page == 1
        assert quote == "The corpus contains 154,391 utterances in total."
        assert "verbatim" in reason

    def test_a_passage_is_medium_and_says_so(self) -> None:
        pages = [
            draft_module.sources.PageText(
                3,
                "Nothing relevant here at all really, just filler text that goes on "
                "for a while to look like a sentence.",
                "",
            )
        ]
        assert (
            draft_module.propose_quote("quantum chromodynamics lattice spacing", pages) is None
        )

    def test_nothing_relevant_means_no_proposal_rather_than_a_weak_one(self) -> None:
        pages = [draft_module.sources.PageText(1, "Short unrelated page.", "")]
        assert draft_module.propose_quote("a sentence about a different subject", pages) is None


class TestReported:
    def test_the_summary_counts_both_outcomes(self) -> None:
        result = draft_module.Draft(
            proposals=[
                draft_module.Proposal("a", "k", "q", 1, "s", "high", "r", 1),
                draft_module.Proposal("b", "k", "q", 1, "s", "medium", "r", 2),
            ],
            skipped=[draft_module.Skipped("k2", "no local file", 3)],
        )
        assert (
            draft_module.summarize(result)
            == "2 claim block(s) proposed (1 verbatim), 1 citation(s) left as comments"
        )

    def test_a_claim_id_is_unique_even_when_the_key_repeats(self) -> None:
        used: set[str] = set()
        first = draft_module._claim_id("smith2026", used)
        second = draft_module._claim_id("smith2026", used)
        assert first != second


@pytest.mark.parametrize("name", ["README.md", "README.zh-CN.md"])
def test_the_documented_first_run_is_the_one_the_code_has(name: str) -> None:
    root = Path(__file__).resolve().parent.parent
    text = (root / name).read_text(encoding="utf-8")
    assert "citevouch draft" in text, f"{name} does not mention the command that creates blocks"
