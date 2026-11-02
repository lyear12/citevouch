"""`draft` must not hand an author a block whose id is already taken.

The command proposes blocks for a manuscript, and the only instruction it gives
is to read the file and copy the blocks in.  When a block's id repeats one the
manuscript already holds, `check` answers `claim-uncheckable ... the second is
ignored` - and the second one is the block the author just pasted, the newest
work in the file.  Measured before `taken_ids` existed: a manuscript with
`id=paper` and one uncited-looking sentence got a proposal also named `paper`,
and appending it turned a project that ran clean into one with a `[high]`.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from citevouch import draft as draft_module
from citevouch.cli import main

PAPER = textwrap.dedent(
    """\
    Construction grammar treats a grammar as a network of constructions.

    The corpus the grammar was induced from contains 154,391 utterances.

    The grammar was induced from that corpus by hand and then evaluated.
    """
)

#: A manuscript that already holds one claim block, and one sentence citing the
#: same key again.  `draft` reads the citation; the block is invisible to it
#: unless the caller says which ids are taken.
MANUSCRIPT = textwrap.dedent(
    """\
    # A note on construction learning

    ```claim id=paper source=paper page=1
    quote: |
      The corpus the grammar was induced from contains 154,391 utterances.
    claim: |
      The grammar came from a corpus of 154,391 utterances.
    ```

    The grammar was induced from that corpus by hand and then evaluated [@paper].
    """
)


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "papers").mkdir(parents=True)
    (root / "papers" / "paper.txt").write_text(PAPER, encoding="utf-8", newline="\n")
    (root / "manuscript.md").write_text(MANUSCRIPT, encoding="utf-8", newline="\n")
    (root / "sources.toml").write_text(
        '[sources]\npaper = "papers/paper.txt"\n', encoding="utf-8", newline="\n"
    )
    return root


def _run(root: Path, *extra: str) -> int:
    return main(["draft", str(root / "manuscript.md"), "--root", str(root), *extra])


def _proposed(root: Path) -> str:
    assert _run(root, "-o", "proposals.md", "--quiet") == 0
    return (root / "proposals.md").read_text(encoding="utf-8")


def _proposed_ids(written: str) -> set[str]:
    """The ids the proposal file names, read the way a reader would."""
    return {
        line.split("id=", 1)[1].split()[0]
        for line in written.splitlines()
        if line.startswith("```claim ")
    }


class TestTheTakenIdsAreAvoided:
    """`taken_ids` seeds the id set; the id de-duplication must still work.

    Note the ``known`` mapping holds the resolved absolute path, the way
    `read_source_table` hands it to `cmd_draft`: `extract_pages` opens the path
    it is given, so a relative one would be read against the process's working
    directory rather than against ``root``.
    """

    def _known(self, project: Path) -> dict[str, str]:
        return {"paper": str(project / "papers" / "paper.txt")}

    def test_a_proposal_does_not_reuse_an_id_the_caller_named(self, project: Path) -> None:
        text = (project / "manuscript.md").read_text(encoding="utf-8")
        result = draft_module.draft(
            text,
            bib={},
            known=self._known(project),
            root=project,
            taken_ids={"paper"},
        )
        assert [p.claim_id for p in result.proposals] == ["paper-2"]

    def test_the_same_key_twice_still_gets_two_ids(self, project: Path) -> None:
        # `taken_ids` seeds the set; it must not replace the de-duplication that
        # was there before it, or two citations of one key collide with each
        # other instead of with the manuscript.
        text = (
            "The corpus the grammar was induced from contains 154,391 utterances [@paper].\n\n"
            "The grammar was induced from that corpus by hand and then evaluated [@paper].\n"
        )
        result = draft_module.draft(
            text,
            bib={},
            known=self._known(project),
            root=project,
            taken_ids={"paper"},
        )
        ids = [p.claim_id for p in result.proposals]
        assert ids == ["paper-2", "paper-3"], ids

    def test_no_taken_ids_keeps_the_plain_key(self, project: Path) -> None:
        # The common case is a manuscript with no blocks at all, and it must not
        # grow a suffix it does not need.
        text = "The corpus the grammar was induced from contains 154,391 utterances [@paper].\n"
        result = draft_module.draft(text, bib={}, known=self._known(project), root=project)
        assert [p.claim_id for p in result.proposals] == ["paper"]


class TestTheCommandReadsTheIdsItWillCollideWith:
    def test_the_written_file_holds_no_id_the_manuscript_already_has(
        self, project: Path
    ) -> None:
        written = _proposed(project)
        assert "```claim id=paper-2 " in written, written
        assert "```claim id=paper " not in written, written

    def test_pasting_the_proposal_does_not_create_a_duplicate_id(self, project: Path) -> None:
        """The whole point: the block an author copies must be checkable.

        Asserted through `check` rather than by comparing strings, because a
        duplicate id is only a problem through the verdict it produces.
        """
        proposals = _proposed(project)
        block = proposals[proposals.index("```claim") :]
        block = block[: block.index("\n```\n", len("```claim")) + len("\n```\n")]
        merged = project / "merged.md"
        manuscript = (project / "manuscript.md").read_text(encoding="utf-8")
        merged.write_text(manuscript + "\n" + block, encoding="utf-8", newline="\n")
        assert main(["check", str(merged), "--root", str(project), "--quiet"]) == 0

    def test_the_manuscript_keeps_the_id_it_had(self, project: Path) -> None:
        """`draft` reads the manuscript; it must not change what it reads."""
        before = (project / "manuscript.md").read_text(encoding="utf-8")
        _proposed(project)
        after = (project / "manuscript.md").read_text(encoding="utf-8")
        assert before == after

    def test_a_manuscript_with_no_blocks_keeps_the_plain_id(self, project: Path) -> None:
        (project / "manuscript.md").write_text(
            "The corpus the grammar was induced from contains 154,391 utterances [@paper].\n",
            encoding="utf-8",
            newline="\n",
        )
        written = _proposed(project)
        assert "```claim id=paper " in written, written

    def test_the_id_that_collides_is_not_necessarily_the_first_one(self, project: Path) -> None:
        """Every existing id has to be read, not just the first.

        A manuscript normally holds several blocks, and the key being proposed
        is only sometimes the one the first block used.  Reading one id and
        stopping looks identical on a one-block fixture.
        """
        first = (
            "```claim id=alpha source=paper page=1\n"
            "quote: |\n"
            "  Construction grammar treats a grammar as a network of constructions.\n"
            "```\n"
        )
        second = (
            "```claim id=paper source=paper page=1\n"
            "quote: |\n"
            "  The corpus the grammar was induced from contains 154,391 utterances.\n"
            "```\n"
        )
        (project / "manuscript.md").write_text(
            first + "\n" + second + "\n"
            "The grammar was induced from that corpus by hand and then evaluated [@paper].\n",
            encoding="utf-8",
            newline="\n",
        )
        written = _proposed(project)
        taken = {"alpha", "paper"}
        proposed = _proposed_ids(written)
        assert proposed, written
        assert not (proposed & taken), written
