"""Report writers: text, JSON, SARIF.

Text is for a human at a terminal.  JSON is for another program.  SARIF is for
GitHub code scanning, where findings land as inline annotations on the pull
request — which is the only form of "review" that reliably gets read.
"""

from __future__ import annotations

import json
from collections.abc import Iterable

from .model import Finding, Ledger, worst
from .verify import VerifyResult

SARIF_RULES = {
    "quote-missing": ("A quoted passage is not in the source.", "blocking"),
    "quote-fuzzy": ("A quoted passage is only approximately in the source.", "warning"),
    "quote-moved": (
        "A quoted passage is on a different page than recorded.",
        "warning",
    ),
    "quote-found": ("A quoted passage is where the ledger says it is.", "note"),
    "number-absent-in-quote": (
        "A number in a quote is not on the cited page.",
        "blocking",
    ),
    "number-absent": ("A number in a quote is not in the source.", "blocking"),
    "source-missing": ("A source file is missing.", "blocking"),
    "source-changed": ("A source file differs from the recorded copy.", "warning"),
    "source-unreadable": ("A source file could not be read.", "blocking"),
    "bib-key-missing": ("A cited key is absent from the bibliography.", "blocking"),
    "bib-key-unused": ("A bibliography entry is never cited.", "note"),
    "bib-field-empty": ("A required bibliography field is empty.", "warning"),
    "bib-duplicate-key": ("A bibliography key appears twice.", "blocking"),
    "bib-doi-mismatch": ("A DOI disagrees with the recorded one.", "warning"),
    "page-out-of-range": ("A page hint exceeds the source length.", "blocking"),
    "claim-without-evidence": ("A claim carries no verifiable evidence.", "warning"),
    "ledger-stale": ("The ledger predates the manuscript.", "blocking"),
}

_LEVEL = {"high": "error", "medium": "warning", "low": "note", "info": "note"}


def render_text(
    findings: Iterable[Finding],
    result: VerifyResult | None = None,
    show_info: bool = True,
) -> str:
    lines: list[str] = []
    for finding in findings:
        if not show_info and finding.severity in ("info", "low"):
            continue
        lines.append(finding.one_line())
    if result is not None:
        lines.append("")
        lines.append(
            f"citevouch: {_plural(result.checked, 'claim')} — {result.verified} verified, "
            f"{result.moved} moved, {result.missing} missing"
            + (f", {result.skipped} skipped" if result.skipped else "")
        )
        lines.append(f"worst severity: {worst(f.severity for f in findings)}")
    return "\n".join(lines).rstrip() + "\n"


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def render_json(
    findings: Iterable[Finding],
    ledger: Ledger | None = None,
    result: VerifyResult | None = None,
) -> str:
    findings = list(findings)
    payload: dict = {"findings": [f.to_json() for f in findings]}
    if ledger is not None:
        payload["ledger"] = {
            "manuscript": ledger.manuscript,
            "claims": len(ledger.claims),
            "sources": len(ledger.sources),
            "entries": len(ledger.entries),
            "tool_version": ledger.tool_version,
            "generated_at": ledger.generated_at,
        }
    # Counts come from the verifier when it ran, and are only ever derived from
    # the findings when it did not (a bare `report`).  Counting codes instead —
    # e.g. treating one `ledger-stale` line as one skipped claim — would report
    # five skipped claims as one.
    if result is not None:
        payload["summary"] = {
            "checked": result.checked,
            "verified": result.verified,
            "moved": result.moved,
            "missing": result.missing,
            "skipped": result.skipped,
            "findings": len(findings),
        }
    else:
        payload["summary"] = {"findings": len(findings)}
    payload["worst"] = worst(f.severity for f in findings)
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def render_sarif(findings: Iterable[Finding], tool_version: str = "") -> str:
    """SARIF 2.1.0 with one rule per finding code.

    The URIs are relative paths, which is what GitHub needs to attach an
    annotation; a finding without a path becomes a run-level notification.
    """
    findings = list(findings)
    codes = sorted({f.code for f in findings})
    rules = []
    for code in codes:
        description, level = SARIF_RULES.get(code, ("citevouch finding", "warning"))
        rules.append(
            {
                "id": code,
                "name": code,
                "shortDescription": {"text": description},
                "defaultConfiguration": {"level": level},
                "helpUri": "https://github.com/lyear12/citevouch#findings",
            }
        )
    results = []
    for finding in findings:
        result: dict = {
            "ruleId": finding.code,
            "level": _LEVEL.get(finding.severity, "warning"),
            "message": {"text": finding.message},
        }
        if finding.path:
            region = {"startLine": finding.line or 1}
            result["locations"] = [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": finding.path.replace("\\", "/")},
                        "region": region,
                    }
                }
            ]
        results.append(result)
    doc = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "citevouch",
                        "informationUri": "https://github.com/lyear12/citevouch",
                        "version": tool_version or "0",
                        "rules": rules,
                    }
                },
                "results": results,
            }
        ],
    }
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def render_markdown(findings: Iterable[Finding], result: VerifyResult | None = None) -> str:
    """A report body suitable for a PR comment or a job summary."""
    findings = list(findings)
    bullets = findings[:200]
    lines = ["## citevouch evidence report", ""]
    if result is not None:
        lines.append(
            f"**{result.checked}** claims · **{result.verified}** verified · "
            f"**{result.moved}** moved · **{result.missing}** missing"
        )
        lines.append("")
    blocking = [f for f in bullets if f.severity == "high"]
    if blocking:
        lines.append(f"### Blocking ({len(blocking)})")
        lines.append("")
        for finding in blocking[:50]:
            lines.append(f"- `{finding.code}` {finding.message}")
        lines.append("")
    rest = [f for f in bullets if f.severity != "high"]
    if rest:
        lines.append(f"### Other ({len(rest)})")
        lines.append("")
        for finding in rest[:50]:
            lines.append(f"- `{finding.code}` {finding.message}")
        lines.append("")
    if len(findings) > len(bullets):
        lines.append(f"…and {len(findings) - len(bullets)} more.")
    return "\n".join(lines).rstrip() + "\n"
