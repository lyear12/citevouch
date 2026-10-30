"""Report writers are the user-visible half; their shapes are the contract."""

from __future__ import annotations

import io
import json
import os
from contextlib import redirect_stdout
from pathlib import Path
from typing import ClassVar
from urllib.parse import unquote

from citevouch.cli import main
from citevouch.model import SEVERITIES, Finding
from citevouch.report import (
    SARIF_RULES,
    render_json,
    render_markdown,
    render_sarif,
    render_text,
)
from citevouch.verify import VerifyResult


def _findings() -> list[Finding]:
    return [
        Finding(
            code="quote-found",
            message="claim c1: found",
            claim_id="c1",
            path="m.md",
            line=3,
        ),
        Finding(
            code="quote-missing",
            message="claim c2: gone",
            claim_id="c2",
            path="m.md",
            line=9,
        ),
        Finding(code="bib-key-unused", message="ghost is unused"),
    ]


class TestTheSarifLevelIsALevel:
    """The level in a SARIF rule has to be one the schema allows.

    Fifteen rules used to say "blocking", which is not a SARIF 2.1.0 level at
    all - the schema allows exactly none, note, warning and error.  The whole
    point of ``--format sarif`` is to upload the document to code scanning, and
    an unknown level makes that document invalid.

    Every test in this module until now compared the *key sets* of ``CODES``
    and ``SARIF_RULES`` and never their values, which is how a level nobody
    reads back survived sixteen releases looking like data.
    """

    VALID: ClassVar[frozenset[str]] = frozenset({"none", "note", "warning", "error"})

    def test_every_severity_the_tool_can_report_becomes_a_legal_level(self):
        # The dictionary that does the translation, not just the document it
        # produces: a severity added to ``SEVERITIES`` with no entry here would
        # raise KeyError in the SARIF writer only when someone uploaded it.
        from citevouch.model import SEVERITIES
        from citevouch.report import _LEVEL

        assert set(_LEVEL) == set(SEVERITIES)
        bad = {severity: level for severity, level in _LEVEL.items() if level not in self.VALID}
        assert not bad, f"severities mapped to a level that does not exist: {bad}"

    def test_every_rule_level_is_one_the_schema_allows(self):
        from citevouch.model import CODES

        document = json.loads(render_sarif([Finding(code=code, message="x") for code in CODES]))
        rules = document["runs"][0]["tool"]["driver"]["rules"]
        assert len(rules) == len(CODES)
        bad = sorted(
            rule["id"]
            for rule in rules
            if rule["defaultConfiguration"]["level"] not in self.VALID
        )
        assert not bad, f"rules with a level that does not exist: {bad}"

    def test_the_rule_level_is_the_severity_the_rest_of_the_tool_uses(self):
        from citevouch.model import CODES, severity_of
        from citevouch.report import _LEVEL

        document = json.loads(render_sarif([Finding(code=code, message="x") for code in CODES]))
        wrong = {}
        for rule in document["runs"][0]["tool"]["driver"]["rules"]:
            expected = _LEVEL[severity_of(rule["id"])]
            if rule["defaultConfiguration"]["level"] != expected:
                wrong[rule["id"]] = (rule["defaultConfiguration"]["level"], expected)
        assert not wrong, f"rule level disagrees with CODES: {wrong}"

    def test_a_rule_and_its_result_never_disagree(self):
        # The result's level was always derived from the finding, so a
        # hand-written rule column could make one document contradict itself.
        from citevouch.model import CODES

        document = json.loads(render_sarif([Finding(code=code, message="x") for code in CODES]))
        run = document["runs"][0]
        rules = {
            rule["id"]: rule["defaultConfiguration"]["level"]
            for rule in run["tool"]["driver"]["rules"]
        }
        results = {result["ruleId"]: result["level"] for result in run["results"]}
        disagree = {
            code: (rules[code], results[code]) for code in rules if rules[code] != results[code]
        }
        assert not disagree, f"rule level and result level disagree: {disagree}"

    def test_the_low_severity_is_a_note_and_not_a_warning(self):
        # claim-without-evidence is ``low`` in CODES and said ``warning`` in
        # the old table, so the same finding was a note in the text report and
        # a warning in GitHub.
        document = json.loads(
            render_sarif([Finding(code="claim-without-evidence", message="x")])
        )
        rule = document["runs"][0]["tool"]["driver"]["rules"][0]
        assert rule["defaultConfiguration"]["level"] == "note"


def test_every_code_has_a_sarif_rule():
    # A missing rule means a finding surfaces in GitHub with no explanation.
    from citevouch.model import CODES

    missing = sorted(set(CODES) - set(SARIF_RULES))
    assert not missing


def test_text_rendering_is_one_line_per_finding():
    out = render_text(_findings())
    assert len(out.strip().splitlines()) == 3


def test_text_rendering_summarises_with_a_result():
    result = VerifyResult(checked=2, verified=1, missing=1)
    out = render_text(_findings(), result)
    assert "2 claims" in out
    assert "worst severity: high" in out


def test_text_rendering_hides_info_when_asked():
    out = render_text(_findings(), show_info=False)
    assert "quote-found" not in out
    assert "quote-missing" in out


class TestTheJsonDescribesTheRunAndSaysWhatItLeftOut:
    """`--quiet` shortened the list and the payload did not mention it.

    Every count in one object has to be about the same thing.  The four claim
    counts came from the verifier and described the run; ``findings`` counted
    the list; so ``--quiet`` produced ``verified: 1, missing: 1`` beside
    ``findings: 1`` with nothing explaining the gap.  ``worst`` was computed
    over the shortened list too, so a run that failed on a hidden ``low``
    reported ``worst: info`` - the same defect the text report was fixed for,
    in the writer the fix never reached.
    """

    RUN: ClassVar[list[Finding]] = [
        Finding(code="quote-missing", message="gone", severity="high"),
        Finding(code="quote-found", message="found", severity="info"),
    ]

    def test_the_counts_add_up_to_the_claims_that_were_checked(self):
        result = VerifyResult(checked=2, verified=1, missing=1)
        payload = json.loads(render_json(self.RUN, None, result, everything=self.RUN))
        summary = payload["summary"]
        total = summary["verified"] + summary["moved"] + summary["missing"] + summary["skipped"]
        assert total == summary["checked"]
        assert summary["findings"] == summary["checked"]
        assert len(payload["findings"]) == len(self.RUN)
        assert "hidden" not in payload

    def test_a_hidden_finding_is_named_not_merely_absent(self):
        result = VerifyResult(checked=2, verified=1, missing=1)
        payload = json.loads(render_json(self.RUN[:1], None, result, everything=self.RUN))
        assert payload["hidden"] == 1
        assert payload["summary"]["hidden"] == 1
        # The run's numbers, not the list's.
        assert payload["summary"]["findings"] == 2
        assert payload["summary"]["verified"] == 1
        assert len(payload["findings"]) == 1

    def test_worst_is_the_worst_of_the_run_not_of_the_screen(self):
        result = VerifyResult(checked=2, verified=1, missing=1)
        payload = json.loads(render_json(self.RUN[:1], None, result, everything=self.RUN))
        assert payload["worst"] == "high"

    def test_a_run_that_only_produced_a_hidden_low_still_says_low(self):
        # `--fail-on low` fails this run; the payload used to say `info`,
        # because the only finding had been filtered out before `worst` ran.
        low = [Finding(code="claim-without-evidence", message="no evidence", severity="low")]
        payload = json.loads(render_json([], None, VerifyResult(checked=1), everything=low))
        assert payload["worst"] == "low"
        assert payload["hidden"] == 1
        assert payload["summary"]["findings"] == 1

    def test_without_a_run_the_two_lists_are_the_same_list(self):
        # The argument is optional so that every existing caller keeps working.
        payload = json.loads(render_json(self.RUN))
        assert payload["summary"]["findings"] == len(self.RUN)
        assert "hidden" not in payload
        assert payload["worst"] == "high"

    def test_the_command_line_names_the_shortening(self):
        import subprocess
        import sys

        root = Path(__file__).resolve().parent.parent
        for flags in ([], ["--quiet"]):
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "citevouch",
                    "check",
                    str(root / "demo" / "manuscript.md"),
                    "--root",
                    str(root / "demo"),
                    "--no-cache",
                    "--format",
                    "json",
                    *flags,
                ],
                cwd=root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env={
                    **os.environ,
                    "PYTHONPATH": str(root / "src"),
                    "PYTHONIOENCODING": "utf-8",
                },
            )
            payload = json.loads(proc.stdout)
            summary = payload["summary"]
            # The invariant is that the object accounts for every finding the
            # run produced.  It is not ``checked``: a claim can produce more
            # than one finding, and some findings (an unused bibliography
            # entry) belong to no claim at all, so the demo's five claims
            # produce six findings.
            assert summary["findings"] == len(payload["findings"]) + payload.get("hidden", 0), (
                flags,
                summary,
            )
            if flags:
                assert payload["hidden"] > 0, (flags, payload)
            else:
                assert "hidden" not in payload, (flags, payload)


def test_json_rendering_carries_the_ledger_summary():
    from citevouch.model import Ledger

    ledger = Ledger(
        manuscript="m.md", tool_version="0.1.0", generated_at="2026-01-01T00:00:00Z"
    )
    payload = json.loads(render_json(_findings(), ledger))
    assert payload["worst"] == "high"
    assert payload["ledger"]["manuscript"] == "m.md"
    assert len(payload["findings"]) == 3


def test_sarif_levels_map_from_severity():
    doc = json.loads(render_sarif(_findings(), "0.1.0"))
    results = doc["runs"][0]["results"]
    levels = {r["ruleId"]: r["level"] for r in results}
    assert levels["quote-missing"] == "error"
    assert levels["quote-found"] == "note"
    assert levels["bib-key-unused"] == "note"


def test_sarif_paths_use_forward_slashes():
    findings = [Finding(code="quote-missing", message="x", path="a\\b.md", line=2)]
    doc = json.loads(render_sarif(findings))
    uri = doc["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"][
        "uri"
    ]
    assert uri == "a/b.md"


def test_sarif_without_a_path_has_no_locations():
    findings = [Finding(code="bib-key-unused", message="x")]
    doc = json.loads(render_sarif(findings))
    assert "locations" not in doc["runs"][0]["results"][0]


def _sarif_uri_of(path: str) -> str:
    doc = json.loads(render_sarif([Finding(code="quote-missing", message="x", path=path)]))
    return doc["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"][
        "uri"
    ]


class TestTheSarifUriIsAUri:
    """`artifactLocation.uri` is a URI, and a file name is not one.

    Every case here is a way the annotation stops pointing at the file the
    finding is about, without the upload failing: the run stays green and the
    comment is on the wrong line of the wrong file, or on nothing.
    """

    def test_a_space_is_encoded(self) -> None:
        assert _sarif_uri_of("my paper.md") == "my%20paper.md"

    def test_a_hash_does_not_become_a_fragment(self) -> None:
        # `draft#2.md` as a URI is the artifact `draft` plus the fragment
        # `2.md`: everything after the hash is never part of the path.
        assert _sarif_uri_of("draft#2.md") == "draft%232.md"

    def test_a_literal_percent_is_escaped_once(self) -> None:
        # A file really named `draft%20.md` must not be sent as the URI for
        # `draft .md`, and it must not be encoded twice either.
        assert _sarif_uri_of("draft%20.md") == "draft%2520.md"

    def test_a_name_that_is_not_ascii_survives(self) -> None:
        uri = _sarif_uri_of("\u8bba\u6587.md")
        assert uri == "%E8%AE%BA%E6%96%87.md"
        assert uri.isascii(), "a URI with raw non-ASCII bytes is not a URI"

    def test_every_one_of_them_parses_back_to_the_original_name(self) -> None:
        # The whole point: encoding is only right if it round-trips.

        for name in ("m.md", "my paper.md", "draft#2.md", "draft%20.md", "论文.md"):
            assert unquote(_sarif_uri_of(name)) == name, name

    def test_the_slash_is_left_alone(self) -> None:
        # Separators are part of the URI's structure; encoding them would turn
        # one path into one file name and break every nested finding.
        assert _sarif_uri_of("papers/a b.md") == "papers/a%20b.md"

    def test_a_rerooted_absolute_path_is_encoded_too(self, tmp_path: Path) -> None:
        # The relative path comes from `relative_to`, not from the raw string,
        # so it is the branch that a naive fix leaves unencoded.
        target = tmp_path / "my paper.md"
        target.write_text("x", encoding="utf-8")
        doc = json.loads(
            render_sarif(
                [Finding(code="quote-missing", message="x", path=str(target))],
                root=tmp_path,
            )
        )
        uri = doc["runs"][0]["results"][0]["locations"][0]["physicalLocation"][
            "artifactLocation"
        ]["uri"]
        assert uri == "my%20paper.md"


def test_markdown_splits_blocking_from_other():
    out = render_markdown(_findings(), VerifyResult(checked=2, verified=1, missing=1))
    assert "### Blocking (1)" in out
    assert "### Other (2)" in out


def test_markdown_marks_truncation():
    findings = [Finding(code="quote-fuzzy", message=f"n{i}") for i in range(250)]
    out = render_markdown(findings)
    assert "more" in out


class TestTheMarkdownReportCountsWhatItPrints:
    """Two defects that no test could see, because both live in formatting.

    The header said `**1** claims` for a one-claim manuscript - the exact shape
    the README walks a new user through.  And each section printed at most 50
    of the findings it was handed while the header counted all of them, so
    sixty findings produced fifty visible bullets under `### Blocking (60)`
    with no line anywhere saying ten were missing.  The existing truncation
    test used 250 findings, which is above every cap, so it never reached the
    middle band where the two caps disagreed.
    """

    def test_one_claim_is_not_called_claims(self):
        out = render_markdown(
            [Finding(code="quote-found", severity="info", message="x")],
            VerifyResult(checked=1, verified=1),
        )
        summary = out.split("\n")[2]
        assert "**1** claim " in summary
        assert "1** claims" not in summary

    def test_two_claims_are_called_claims(self):
        out = render_markdown(
            [Finding(code="quote-found", severity="info", message="x")],
            VerifyResult(checked=2, verified=2),
        )
        assert "**2** claims" in out

    def test_a_section_that_stops_early_says_how_many_it_dropped(self):
        findings = [
            Finding(code="quote-missing", severity="high", message=f"m{i}") for i in range(60)
        ]
        out = render_markdown(findings)
        bullets = [ln for ln in out.split("\n") if ln.startswith("- ")]
        assert len(bullets) == 50
        assert "### Blocking (60)" in out
        assert "Truncated:" in out
        assert "10 more under Blocking" in out

    def test_a_list_short_enough_to_fit_says_nothing_about_truncation(self):
        findings = [
            Finding(code="quote-missing", severity="high", message=f"m{i}") for i in range(50)
        ]
        out = render_markdown(findings)
        assert "Truncated" not in out

    def test_both_caps_are_reported_when_both_bite(self):
        findings = [
            Finding(code="quote-missing", severity="high", message=f"m{i}") for i in range(260)
        ]
        out = render_markdown(findings)
        # 260 findings: 200 are counted, 50 of those are printed, so 60 fall
        # outside the total cap and 150 behind the per-section one.
        assert "60 beyond the first 200" in out
        assert "150 more under Blocking" in out


def test_markdown_without_a_result_still_renders():
    out = render_markdown(_findings())
    assert out.startswith("## citevouch evidence report")


class TestTheHeadingAgreesWithTheExitCode:
    """The section that answers "why did this fail" is decided by the same rule.

    Both headings used to come from severity alone: everything `high` under
    `### Blocking`, everything else under `### Other`.  But the failing
    threshold is `--fail-on`, so at `--fail-on medium` a medium finding is the
    entire reason the job is red while the report files it under Other.  The
    reader looking for the cause of a red build is sent to the wrong section -
    by a report they are reading precisely because they do not trust the exit
    code alone.
    """

    def test_a_medium_finding_is_blocking_at_medium(self):
        findings = [Finding(code="page-unreadable", severity="medium", message="m")]
        out = render_markdown(findings, fail_on="medium")
        assert "### Blocking (1)" in out
        assert "### Other" not in out

    def test_the_same_finding_is_merely_other_at_high(self):
        findings = [Finding(code="page-unreadable", severity="medium", message="m")]
        out = render_markdown(findings, fail_on="high")
        assert "### Other (1)" in out
        assert "### Blocking" not in out

    def test_every_severity_lands_where_the_exit_code_says_it_does(self):
        for threshold in SEVERITIES:
            for severity in SEVERITIES:
                findings = [Finding(code="page-unreadable", severity=severity, message="m")]
                out = render_markdown(findings, fail_on=threshold)
                should_block = SEVERITIES.index(severity) >= SEVERITIES.index(threshold)
                assert ("### Blocking" in out) is should_block, (threshold, severity)

    def test_an_unknown_severity_does_not_raise(self):
        findings = [Finding(code="page-unreadable", severity="bogus", message="m")]
        out = render_markdown(findings, fail_on="high")
        assert "### Other (1)" in out

    def test_the_default_is_the_default_threshold(self):
        findings = [Finding(code="page-unreadable", severity="medium", message="m")]
        assert render_markdown(findings) == render_markdown(findings, fail_on="high")


class TestTheSummaryDescribesTheRunNotTheScreen:
    """`--quiet` hid the line and then the summary lied about why the run failed.

    The filtered list was handed to the renderer, which computed `worst
    severity` from it.  So `check --fail-on low --quiet` exited 1 while
    printing `worst severity: info` and not one finding: the reader of a CI
    log could not tell why the job was red, and the report actively said
    nothing was wrong.
    """

    def _finding(self, severity, message="m"):
        return Finding(code="page-unreadable", severity=severity, message=message)

    def _result(self):
        # The summary line only prints when a result is supplied, and it is
        # the summary line that carries `worst severity`.
        return VerifyResult(checked=1, verified=1)

    def test_the_worst_severity_counts_hidden_findings(self):
        findings = [self._finding("medium"), self._finding("info")]
        out = render_text(findings, self._result(), show_info=False, fail_on="medium")
        # `--quiet` hides info and low, so the medium line does print; the
        # info line does not, and `worst severity` still names the run's worst.
        assert "worst severity: medium" in out
        assert "[info]" not in out

    def test_a_run_failed_by_a_hidden_finding_says_so(self):
        findings = [self._finding("low")]
        out = render_text(findings, self._result(), show_info=False, fail_on="low")
        assert "hidden by --quiet" in out
        assert "1 finding at or above --fail-on low" in out
        assert "was hidden" in out

    def test_a_hidden_finding_below_the_threshold_is_not_blamed(self):
        findings = [self._finding("low")]
        out = render_text(findings, self._result(), show_info=False, fail_on="high")
        assert "hidden by --quiet" not in out

    def test_several_hidden_findings_agree_with_the_plural(self):
        findings = [self._finding("low", "a"), self._finding("low", "b")]
        out = render_text(findings, self._result(), show_info=False, fail_on="low")
        assert "2 findings at or above --fail-on low were hidden" in out

    def test_showing_everything_changes_only_which_lines_print(self):
        findings = [self._finding("high")]
        shown = render_text(findings, self._result(), show_info=True)
        hidden = render_text(findings, self._result(), show_info=False)
        assert "worst severity: high" in shown
        assert "worst severity: high" in hidden
        assert "hidden by --quiet" not in hidden


class TestTheMarkdownReportSaysWhyTheJobIsRed:
    """The same defect as the one above, in the writer a reviewer actually reads.

    `--quiet` was honoured by the text renderer alone; `_render` shortened the
    list before handing it to markdown.  A run that exited 1 under `--quiet
    --format markdown` produced a report with a clean summary, no `### Blocking`
    section, and not one word about what failed - in a PR comment, which is the
    one place a reader goes to find out why the job is red.

    The fix moved the decision into the renderer, the way `render_text` already
    did, so the summary can describe the run while the body lists only what
    `--quiet` allowed.
    """

    def _finding(self, severity, message="m"):
        return Finding(code="page-unreadable", severity=severity, message=message)

    def _result(self):
        return VerifyResult(checked=1, verified=1)

    def test_a_hidden_finding_still_decides_the_worst_severity(self):
        findings = [self._finding("low", "hidden one"), self._finding("info")]
        out = render_markdown(findings, self._result(), show_info=False)
        # The low line is hidden by --quiet, and it is still the run's worst.
        assert "**worst severity:** low" in out
        # Hidden means hidden: the bullet is gone.  Asserting on the message
        # rather than the code, because the code is the same one this report
        # would print if it printed the line.
        assert "hidden one" not in out

    def test_a_run_failed_by_a_hidden_finding_says_so(self):
        findings = [self._finding("low")]
        out = render_markdown(findings, self._result(), fail_on="low", show_info=False)
        assert "hidden by `--quiet`" in out
        assert "that is why this run failed" in out
        assert "**1** finding at or above `--fail-on low`" in out

    def test_a_hidden_finding_below_the_threshold_is_not_blamed(self):
        findings = [self._finding("low")]
        out = render_markdown(findings, self._result(), fail_on="high", show_info=False)
        assert "hidden by `--quiet`" not in out

    def test_several_hidden_findings_agree_with_the_plural(self):
        findings = [self._finding("low", "a"), self._finding("low", "b")]
        out = render_markdown(findings, self._result(), fail_on="low", show_info=False)
        assert "**2** findings at or above" in out
        assert "were hidden" in out

    def test_showing_everything_changes_only_which_lines_print(self):
        findings = [self._finding("high")]
        shown = render_markdown(findings, self._result(), show_info=True)
        hidden = render_markdown(findings, self._result(), show_info=False)
        assert shown == hidden
        assert "hidden by `--quiet`" not in hidden

    def test_the_command_line_hides_the_line_and_keeps_the_reason(self, tmp_path: Path):
        """The unit tests above can pass while `_render` still shortens the list.

        This one goes through `main`, because that is where the filter used to
        live: the renderer could compute the right answer from the wrong input
        and no assertion on the renderer alone would notice.
        """
        root = tmp_path
        (root / "p.txt").write_text("We train on two corpora.\n", encoding="utf-8")
        (root / "sources.toml").write_text('[sources]\np = "p.txt"\n', encoding="utf-8")
        (root / "m.md").write_text(
            "```claim id=c1 source=p page=1\nWe train on two corpora.\n```\n"
            "\n"
            "\u3010\u63a8\u6d4b\u3011the trend probably holds elsewhere.\n",
            encoding="utf-8",
        )
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(
                [
                    "check",
                    "m.md",
                    "--root",
                    str(root),
                    "--format",
                    "markdown",
                    "--fail-on",
                    "low",
                    "--quiet",
                ]
            )
        assert code == 1
        text = out.getvalue()
        # It failed, so the report has to say why.
        assert "hidden by `--quiet`" in text
        assert "that is why this run failed" in text
        # And `--quiet` still does its job: the low line does not get printed
        # as a bullet.  Without this the report could print everything and the
        # flag would be a no-op in the one writer that ignores it.
        assert "the trend probably holds elsewhere" not in text
