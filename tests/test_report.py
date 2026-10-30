"""Report writers are the user-visible half; their shapes are the contract."""

from __future__ import annotations

import json

from citevouch.model import Finding
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
