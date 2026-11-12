"""What the rule line above a `doctor` result says.

A SARIF result carries two sentences: the rule the tab groups it under, and
the message under it.  The message is written by the check that failed and has
always been specific.  The rule was chosen in one place, `doctor.findings()`,
and for two repairs running that one place named a problem other than the one
the check had found:

* `source-unreadable` made a missing PDF library display as "A source file
  could not be read."
* `check-unavailable` made a manuscript holding no claim blocks display as
  "This machine cannot run the checks at all."

Measured before this fix, on a project whose only claim block names no
`source=` - so `check` exits 1 with `claim-uncheckable`:

    doctor --format sarif   ruleId check-unavailable
                            "This machine cannot run the checks at all."
    check  --format sarif   ruleId claim-uncheckable

The reader of the code-scanning tab is told they have an installation problem
when they have a manuscript problem, and the one file they would go and look
at is the wrong one.

The codes stay separate rather than reusing the verdict codes (`no-claim-blocks`,
`claim-uncheckable`, `source-missing`) because `doctor` measured something
weaker: that it could not get the checks to run.  A rule line stating the
weaker, true thing is better than one stating a verdict `doctor` never reached.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from citevouch import doctor as doctor_module
from citevouch.cli import main
from citevouch.model import CODES
from citevouch.report import SARIF_RULES

NL = chr(10)
QUOTE = "We collected 40,688 examples from the corpus."
PAGE = "Nothing to see here." + NL + QUOTE + NL

MACHINE = "check-unavailable"
MANUSCRIPT = "manuscript-unusable"
PROJECT = "project-unusable"


def _project(tmp_path: Path, body: str, *, manifest: bool = True) -> Path:
    """A project holding one claim block in the state *body* describes."""
    root = tmp_path / "p"
    root.mkdir()
    (root / "page.txt").write_text(PAGE, encoding="utf-8", newline=NL)
    if manifest:
        (root / "sources.toml").write_text(
            "[sources]" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
        )
    (root / "m.md").write_text(body, encoding="utf-8", newline=NL)
    return root


def _rules(root: Path, capsys) -> list[str]:
    main(["doctor", "--root", str(root), "--manuscript", "m.md", "--format", "sarif"])
    payload = json.loads(capsys.readouterr().out)
    return [entry["ruleId"] for entry in payload["runs"][0]["results"]]


def _json_checks(root: Path, capsys) -> list[dict]:
    main(["doctor", "--root", str(root), "--manuscript", "m.md", "--format", "json"])
    return json.loads(capsys.readouterr().out)["checks"]


GOOD = (
    chr(96) * 3
    + "claim id=c1 source=paper"
    + NL
    + "quote: |"
    + NL
    + "  "
    + QUOTE
    + NL
    + chr(96) * 3
    + NL
)

NO_SOURCE = (
    chr(96) * 3 + "claim id=c1" + NL + "quote: |" + NL + "  " + QUOTE + NL + chr(96) * 3 + NL
)


class TestTheProjectCodesAreNotBorrowed:
    @pytest.mark.parametrize(
        "body, expected",
        [
            (NO_SOURCE, PROJECT),
            (GOOD.replace("source=paper", "source=ghost"), PROJECT),
            ("Just prose, no claim blocks at all." + NL, PROJECT),
        ],
    )
    def test_a_project_problem_is_a_project_code(self, tmp_path: Path, capsys, body, expected):
        assert _rules(_project(tmp_path, body), capsys) == [expected]

    def test_a_missing_manifest_names_the_project(self, tmp_path: Path, capsys):
        root = _project(tmp_path, GOOD, manifest=False)
        assert _rules(root, capsys) == [PROJECT]

    def test_a_manifest_that_cannot_be_parsed_names_the_project(self, tmp_path: Path, capsys):
        """The manifest branch, not the missing-file branch: broken TOML, not absent."""
        root = _project(tmp_path, GOOD)
        (root / "sources.toml").write_text(
            "[sources" + NL + 'paper = "page.txt"' + NL, encoding="utf-8", newline=NL
        )
        assert _rules(root, capsys) == [PROJECT]

    def test_an_unreadable_source_names_the_project(self, tmp_path: Path, capsys):
        """A PNG where a page should be is a project problem, not a broken install."""
        root = tmp_path / "p"
        root.mkdir()
        (root / "page.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
        (root / "sources.toml").write_text(
            "[sources]" + NL + 'paper = "page.png"' + NL, encoding="utf-8", newline=NL
        )
        (root / "m.md").write_text(GOOD, encoding="utf-8", newline=NL)
        assert _rules(root, capsys) == [PROJECT]

    def test_the_manuscript_code_has_its_own_word(self, tmp_path: Path, capsys):
        root = tmp_path / "p"
        root.mkdir()
        (root / "m.tex").write_text(
            chr(92) + "documentclass{article}" + NL, encoding="utf-8", newline=NL
        )
        main(["doctor", "--root", str(root), "--manuscript", "m.tex", "--format", "sarif"])
        payload = json.loads(capsys.readouterr().out)
        codes = [entry["ruleId"] for entry in payload["runs"][0]["results"]]
        assert codes == [MANUSCRIPT]

    def test_a_machine_failure_keeps_the_machine_code(
        self, monkeypatch, tmp_path: Path, capsys
    ):
        root = _project(tmp_path, GOOD)

        def missing_pypdf() -> doctor_module.Report:
            return doctor_module.Report(
                name="pypdf", ok=False, detail="not installed", fix="`pip install pypdf`"
            )

        monkeypatch.setattr(doctor_module, "_pypdf", missing_pypdf)
        assert MACHINE in _rules(root, capsys)


class TestTheRuleLineIsAboutTheProblem:
    def test_each_code_explains_itself(self):
        assert "machine" in SARIF_RULES[MACHINE].lower()
        assert "manuscript" in SARIF_RULES[MANUSCRIPT].lower()
        assert "project" in SARIF_RULES[PROJECT].lower()

    def test_the_machine_line_does_not_claim_the_manuscript_is_at_fault(self):
        """The sentence a reader sees must not send them to the wrong file."""
        sentence = SARIF_RULES[MACHINE].lower()
        assert "claim" not in sentence
        assert "manifest" not in sentence

    def test_every_code_is_a_known_code(self):
        for code in (MACHINE, MANUSCRIPT, PROJECT):
            assert code in CODES
            assert code in SARIF_RULES


class TestJsonCarriesTheSameWord:
    def test_the_check_that_failed_is_named(self, tmp_path: Path, capsys):
        checks = _json_checks(_project(tmp_path, NO_SOURCE), capsys)
        refused = [check for check in checks if not check["ok"]]
        assert [check["name"] for check in refused] == ["claims"]
        assert [check["code"] for check in refused] == [PROJECT]

    def test_a_passing_project_has_no_codes_to_report(self, tmp_path: Path, capsys):
        checks = _json_checks(_project(tmp_path, GOOD), capsys)
        assert [check["name"] for check in checks if not check["ok"]] == []


class TestTheVerdictDoesNotChange:
    def test_a_broken_project_still_exits_one(self, tmp_path: Path):
        assert (
            main(
                ["doctor", "--root", str(_project(tmp_path, NO_SOURCE)), "--manuscript", "m.md"]
            )
            == 1
        )

    def test_a_sound_project_still_exits_zero(self, tmp_path: Path):
        assert (
            main(["doctor", "--root", str(_project(tmp_path, GOOD)), "--manuscript", "m.md"])
            == 0
        )
