"""Report writers: text, JSON, SARIF.

Text is for a human at a terminal.  JSON is for another program.  SARIF is for
GitHub code scanning, where findings land as inline annotations on the pull
request — which is the only form of "review" that reliably gets read.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import quote

from .model import SEVERITIES, Finding, Ledger, worst
from .textnorm import count_of, verb_for, word_for
from .verify import VerifyResult

SARIF_RULES = {
    "quote-missing": ("A quoted passage is not in the source.", "blocking"),
    "quote-fuzzy": (
        "A quoted passage is only approximately in the source; nothing proves it.",
        "blocking",
    ),
    "quote-moved": (
        "A quoted passage is on a different page than recorded.",
        "warning",
    ),
    "quote-found": ("A quoted passage is where the ledger says it is.", "note"),
    "number-absent-in-quote": (
        "A number in a quote is not on the cited page.",
        "blocking",
    ),
    "source-missing": ("A source file is missing.", "blocking"),
    "source-changed": ("A source file differs from the recorded copy.", "warning"),
    "source-unreadable": ("A source file could not be read.", "blocking"),
    "source-no-text": ("A source file was read and held no text at all.", "blocking"),
    "bib-key-missing": ("A cited key is absent from the bibliography.", "blocking"),
    "bib-key-unused": ("A bibliography entry is never cited.", "note"),
    "bib-field-empty": ("A required bibliography field is empty.", "warning"),
    "bib-field-malformed": ("A bibliography field could not be read.", "warning"),
    "bib-field-duplicate": ("A bibliography field is given twice.", "warning"),
    "bib-duplicate-key": ("A bibliography key appears twice.", "blocking"),
    "bib-macro-unknown": ("A @string macro used by a field is not defined.", "warning"),
    "bib-entry-header-unparsed": ("An @ header is not a usable entry.", "warning"),
    "bib-unparsed-entry": (
        "An entry never closes, so the entries after it could not be read.",
        "blocking",
    ),
    "bib-unreadable": (
        "Not one entry could be read, so no reference was checked against it.",
        "blocking",
    ),
    "page-out-of-range": ("A page hint exceeds the source length.", "blocking"),
    "claim-block-unclosed": (
        "A block never closes, so later claims in the file were never read.",
        "blocking",
    ),
    "claim-uncheckable": (
        "A claim block cannot be looked up at all, so its quote was never compared to anything.",
        "blocking",
    ),
    "page-unreadable": (
        "A page hint is not a number and is being ignored.",
        "warning",
    ),
    "claim-without-evidence": ("A claim carries no verifiable evidence.", "warning"),
    "ledger-stale": ("The ledger predates the manuscript.", "blocking"),
    "no-claim-blocks": (
        "A manuscript holds no claim blocks, so nothing in it was checked.",
        "blocking",
    ),
}

_LEVEL = {"high": "error", "medium": "warning", "low": "note", "info": "note"}


def render_text(
    findings: Iterable[Finding],
    result: VerifyResult | None = None,
    show_info: bool = True,
    fail_on: str = "high",
) -> str:
    # Materialise once.  The body both prints the findings and then asks for
    # the worst severity among them; with a generator, the second pass would
    # see an exhausted iterator and report the worst of nothing.  The bug was
    # invisible because every caller happens to pass a list today.
    findings = list(findings)
    hidden = [f for f in findings if _hidden_by_quiet(f, show_info)]
    lines = [f.one_line() for f in findings if not _hidden_by_quiet(f, show_info)]
    if result is not None:
        lines.append("")
        lines.append(
            f"citevouch: {_plural(result.checked, 'claim')} — {result.verified} verified, "
            f"{result.moved} moved, {result.missing} missing"
            + (f", {result.skipped} skipped" if result.skipped else "")
        )
        # The summary describes the run, not the display.  Computing it from
        # the lines that survived `--quiet` reported `worst severity: info` for
        # a run that exited 1, because the finding that failed it had been
        # filtered out two lines earlier.
        lines.append(f"worst severity: {worst(f.severity for f in findings)}")
        if failing := _failing_hidden(hidden, fail_on):
            lines.append(
                f"{_plural(len(failing), 'finding')} at or above --fail-on {fail_on}"
                f" {_plural_verb(len(failing))} hidden by --quiet; that is why this run failed"
            )
    return "\n".join(lines).rstrip() + "\n"


def _hidden_by_quiet(finding: Finding, show_info: bool) -> bool:
    """Whether `--quiet` keeps this finding out of the printed lines."""
    return not show_info and finding.severity in ("info", "low")


def _failing_hidden(hidden: list[Finding], fail_on: str) -> list[Finding]:
    """The hidden findings that on their own are enough to fail the run."""
    threshold = SEVERITIES.index(fail_on) if fail_on in SEVERITIES else len(SEVERITIES)
    return [
        f
        for f in hidden
        if (SEVERITIES.index(f.severity) if f.severity in SEVERITIES else 0) >= threshold
    ]


def _plural_verb(count: int) -> str:
    """`was` or `were`, to agree with `_plural(count, noun)`."""
    return verb_for(count)


def _plural(count: int, noun: str) -> str:
    return count_of(count, noun)


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


def _sarif_uri(raw: str, root: Path | None) -> str:
    """Turn a finding path into a URI code scanning can attach to a file.

    GitHub resolves ``artifactLocation.uri`` against the repository, so an
    absolute local path (``C:/Users/.../m.md``) matches no artifact and the
    annotation is silently lost — the run still uploads, which is what made
    this hard to notice.  Paths are therefore re-rooted when they can be.

    A path outside ``root`` stays absolute on purpose: inventing a relative
    path for a file the checkout does not contain would move the annotation
    onto some other file that happens to share the tail.

    The result is percent-encoded, because this field is a URI and a file name
    is not one. ``draft#2.md`` is the shortest way to see the difference: as a
    URI it names the artifact ``draft`` with the fragment ``2.md``, so the
    annotation lands nowhere; ``draft%20.md`` decodes to ``draft .md``, a
    different file; ``my paper.md`` and ``论文.md`` are not URIs at all. Same
    silent-loss failure the paragraphs above are about, reached by another
    input, so it gets the same one-line treatment.
    """
    posix = raw.replace("\\", "/")
    if root is not None:
        candidate = Path(raw)
        if candidate.is_absolute():
            for base in (root, root.resolve()):
                try:
                    posix = candidate.resolve().relative_to(base.resolve()).as_posix()
                except (ValueError, OSError):
                    continue
                else:
                    break
    return quote(posix, safe="/")


def render_sarif(
    findings: Iterable[Finding],
    tool_version: str = "",
    root: str | Path | None = None,
) -> str:
    """SARIF 2.1.0 with one rule per finding code.

    The URIs are relative to ``root`` when they can be, which is what GitHub
    needs to attach an annotation; a finding without a path becomes a
    run-level notification.
    """
    findings = list(findings)
    root_path = None if root is None else Path(root)
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
                        "artifactLocation": {"uri": _sarif_uri(finding.path, root_path)},
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


def render_markdown(
    findings: Iterable[Finding],
    result: VerifyResult | None = None,
    fail_on: str = "high",
) -> str:
    """A report body suitable for a PR comment or a job summary.

    Two things in here were wrong in ways a green suite could not see.

    The summary printed `**1** claims`.  Every count in this package has a
    plural helper; this one was a template string with the plural written into
    it, so a single-claim manuscript - the shape the README walks a new user
    through - read `1 claims`.

    And the truncation was counted at the wrong level.  `bullets` capped the
    list at 200 and then each section printed at most 50, but the "and more"
    line compared the total against the first cap only.  Sixty findings printed
    fifty bullets under a heading reading `### Blocking (60)` and said nothing
    about the other ten.  A report that stops listing without saying so is the
    same defect as a run that stops checking: the reader counts what they can
    see and concludes those are all of them.

    The two section headings used to be decided by severity alone: everything
    `high` went under `### Blocking` and everything else under `### Other`.
    But what makes a run fail is `--fail-on`, and at `--fail-on medium` a
    medium finding is the reason the job is red while the report files it
    under Other.  The heading that answers "why did this fail" now answers it
    from the same threshold the exit code uses.
    """
    findings = list(findings)
    max_total = 200
    per_section = 50
    bullets = findings[:max_total]
    lines = ["## citevouch evidence report", ""]
    if result is not None:
        lines.append(
            f"**{result.checked}** {_word(result.checked, 'claim')} · "
            f"**{result.verified}** verified · "
            f"**{result.moved}** moved · **{result.missing}** missing"
        )
        lines.append("")
    threshold = SEVERITIES.index(fail_on) if fail_on in SEVERITIES else len(SEVERITIES)
    blocking_codes = [_is_blocking(f, threshold) for f in bullets]
    omitted: list[str] = []
    for title, group in (
        ("Blocking", [f for f, b in zip(bullets, blocking_codes, strict=True) if b]),
        ("Other", [f for f, b in zip(bullets, blocking_codes, strict=True) if not b]),
    ):
        if not group:
            continue
        lines.append(f"### {title} ({len(group)})")
        lines.append("")
        for finding in group[:per_section]:
            lines.append(f"- `{finding.code}` {finding.message}")
        lines.append("")
        if len(group) > per_section:
            omitted.append(f"{len(group) - per_section} more under {title}")
    if len(findings) > len(bullets):
        omitted.insert(
            0,
            f"{len(findings) - len(bullets)} beyond the first {max_total}, not counted above",
        )
    if omitted:
        lines.append("Truncated: " + "; ".join(omitted) + ".")
        lines.append("")
    return chr(10).join(lines).rstrip() + chr(10)


def _is_blocking(finding: Finding, threshold: int) -> bool:
    """Whether this finding is a reason the run exits 1.

    The same question `cli._exit_code` asks, with the same answer, so the
    section a reader is pointed at and the exit code cannot disagree.  An
    unknown severity ranks at the bottom the way `_exit_code` treats it,
    rather than raising: a crash here would escape as exit 1, and 1 means
    "findings reached the threshold" to every caller that reads it.
    """
    rank = SEVERITIES.index(finding.severity) if finding.severity in SEVERITIES else 0
    return rank >= threshold


def _word(count: int, noun: str) -> str:
    """`claim` or `claims`, for a template that wants the bare word."""
    return word_for(count, noun)
