"""Report writers are the user-visible half; their shapes are the contract."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import unquote

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
