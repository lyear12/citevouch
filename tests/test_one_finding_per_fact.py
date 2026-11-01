"""Six shapes where two facts shared one coordinate, all at once.

Each of these was found separately, one heartbeat run at a time, by noticing
that a run reported fewer lines than there were mistakes:

* four in ``bibtex.py`` - a repeated field, two undefined macros, two malformed
  fragments, two required fields missing (0.19.34-0.19.36);
* two in ``verify.py`` - two wrong numbers in one quote, and the summary that
  outranked the specifics (0.19.37).

The dedup pass keys on ``(code, claim_id, path, line)``.  Anything a producer
emits twice under that key is a fact the author will not be told.  So the guard
here is one comparison rather than six assertions about wording: run a project
that carries all six shapes and require the producer's count to equal the
writer's.  When they differ, some site has started emitting two findings per
coordinate again and the message about *which* site is the follow-up.

This is the assertion the last two lessons asked for and did not have.  It is
also the cheapest one to keep: it does not need to know what any message says.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from citevouch import cli

NL = chr(10)


def _project(root: Path) -> Path:
    """A manuscript and bibliography carrying every shape that once collapsed."""
    manuscript = NL.join(
        [
            "```claim id=nums source=page",
            "quote: |",
            "  alpha beta gamma 11,111 and 22,222",
            "```",
            "",
            "```claim id=one source=page ref=bare",
            "quote: |",
            "  alpha beta gamma 33,333 and 44,444",
            "```",
            "",
            "```claim",
            "quote: |",
            "  alpha beta gamma",
            "```",
            "",
            "```claim",
            "quote: |",
            "  alpha beta gamma",
            "```",
            "",
        ]
    )
    (root / "m.md").write_text(manuscript, encoding="utf-8", newline=NL)
    (root / "page.txt").write_text(
        "alpha beta gamma 55,555 and 66,666", encoding="utf-8", newline=NL
    )
    (root / "sources.toml").write_text(
        "[sources]" + NL + 'page = "page.txt"' + NL, encoding="utf-8", newline=NL
    )
    (root / "refs.bib").write_text(
        NL.join(
            [
                "@article{bare,",
                "  note = {only a note},",
                "}",
                "",
                "@article{doubled,",
                "  author = {A. Author},",
                "  title = {First},",
                "  title = {Second},",
                "  year = {2020},",
                "  journal = {J},",
                "  doi = {10.1/x},",
                "}",
                "",
                "@article{macros,",
                "  author = {B. Author},",
                "  title = {T},",
                "  year = {2021},",
                "  journal = jalpha # jbeta,",
                "  publisher = pgamma,",
                "}",
                "",
                "@article{broken,",
                "  badone,",
                "  author = {C. Author},",
                "  title = {T},",
                "  year = {2022},",
                "  journal = {J},",
                "  badtwo,",
                "}",
                "",
            ]
        ),
        encoding="utf-8",
        newline=NL,
    )
    return root


def _run(root: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[list, list]:
    """Return (producer findings, writer findings) for one run of ``check``."""
    monkeypatch.chdir(root)

    collected: dict[str, list] = {}

    real = cli._deconflict

    def _capture(findings: list) -> list:
        collected["raw"] = list(findings)
        return real(findings)

    monkeypatch.setattr(cli, "_deconflict", _capture)
    import io
    from contextlib import redirect_stdout

    with redirect_stdout(io.StringIO()):
        cli.main(["check", "m.md", "--root", ".", "--bib", "refs.bib", "--format", "json"])

    return collected["raw"], real(collected["raw"])


class TestNoFactIsDroppedByTheDuplicatePass:
    def test_the_writer_prints_everything_the_producers_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        raw, deduped = _run(_project(tmp_path), monkeypatch)
        keys = [(f.code, f.claim_id, f.path, f.line) for f in raw]
        assert len(set(keys)) == len(raw), (
            "two producers reached the same coordinate, so the duplicate pass "
            f"drops one of them and the author never reads it: {sorted(keys)}"
        )
        assert len(deduped) == len(raw)

    def test_every_shape_this_guards_actually_appears(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The comparison above is only worth running if the shapes are here."""
        raw, _ = _run(_project(tmp_path), monkeypatch)
        codes = {f.code for f in raw}
        for expected in (
            "bib-field-duplicate",
            "bib-macro-unknown",
            "bib-field-malformed",
            "bib-field-empty",
            "number-absent-in-quote",
            "claim-uncheckable",
        ):
            assert expected in codes, (expected, sorted(codes))

    def test_each_message_names_all_of_its_members(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """One line per fact is only a fix if the line carries every member."""
        raw, _ = _run(_project(tmp_path), monkeypatch)
        by_code = {}
        for finding in raw:
            by_code.setdefault(finding.code, []).append(finding.message)

        repeated = by_code["bib-field-duplicate"][0]
        assert "'title'" in repeated and "given twice" in repeated

        macros = by_code["bib-macro-unknown"][0]
        for name in ("jalpha", "jbeta", "pgamma"):
            assert name in macros, (name, macros)

        malformed = by_code["bib-field-malformed"][0]
        for name in ("badone", "badtwo"):
            assert name in malformed, (name, malformed)

        empty = by_code["bib-field-empty"][0]
        for name in ("'author'", "'title'", "'journal'", "'year'"):
            assert name in empty, (name, empty)

        numbers = [m for m in by_code["number-absent-in-quote"] if "11,111" in m]
        assert numbers, [m for m in by_code["number-absent-in-quote"]]
        assert "22,222" in numbers[0], numbers[0]
