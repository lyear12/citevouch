"""The documents describing automation have to describe the automation that runs.

Three claims in this repository were statements about machinery, and nobody ran
the machinery to check them:

1. `docs/maintenance.md` drew a loop in which the nightly reads the day's commits
   and promotes lessons. The job it points at installs the newest wheel, replays
   the first commands, and files an issue when that fails. It does not read
   commits, so the retrospective half of the loop is an intention, and
   `LESSONS.md` still says `reviewed-through: none`.
2. The same document described issue consumption, review and merging as stages of
   an automated loop. Nothing consumes an issue, no reviewer runs on a pull
   request (`main` is unprotected with no rulesets), and there is no merge bot.
3. `docs/metrics.md` documented a measurement command whose numbers were a
   truncation: `gh api repos/.../releases` returns thirty releases by default, so
   on 2026-11-15 the documented command said 30 releases / 83 downloads while the
   paginated one said 255 / 732. The file's whole purpose is repeatable
   measurement, and its one command silently measured a slice.

These tests hold the documents to the machinery. They cannot tell whether a claim
is *useful*; they can tell whether it is about a thing that exists.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MAINTENANCE = ROOT / "docs" / "maintenance.md"
METRICS = ROOT / "docs" / "metrics.md"
NIGHTLY = ROOT / ".github" / "workflows" / "nightly.yml"
LESSONS = ROOT / "LESSONS.md"


def _nightly() -> dict:
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load(NIGHTLY.read_text(encoding="utf-8"))


def _nightly_step_names() -> list[str]:
    names: list[str] = []
    for job in _nightly()["jobs"].values():
        for step in job.get("steps", []):
            name = step.get("name")
            if name:
                names.append(str(name))
    return names


def _section(text: str, heading: str) -> str:
    """The body of one `##`/`###` section, without its heading line."""
    start = text.index(heading)
    rest = text[start + len(heading) :]
    match = re.search(r"^#{2,3} ", rest, re.MULTILINE)
    return rest[: match.start()] if match else rest


def _commands(text: str) -> list[str]:
    """Every `gh api …` command line in the file, continuations joined."""
    joined: list[str] = []
    pending = ""
    for raw in text.splitlines():
        line = raw.strip()
        if pending:
            pending += " " + line.rstrip("\\").strip()
            if not line.endswith("\\"):
                joined.append(pending)
                pending = ""
        elif line.startswith("gh api"):
            if line.endswith("\\"):
                pending = line.rstrip("\\").strip()
            else:
                joined.append(line)
    return joined


class TestTheDocumentedMeasurementDoesNotTruncate:
    """`docs/metrics.md` is a file about measurement; an unpaginated call is a lie."""

    def test_every_release_command_asks_for_a_full_page_and_paginates(self) -> None:
        commands = _commands(METRICS.read_text(encoding="utf-8"))
        releases = [c for c in commands if "/releases" in c]
        assert releases, "no gh api call against /releases is documented"
        for command in releases:
            # The default page is thirty releases, and this repository has more
            # than two hundred, so the bare call is always a slice.
            assert "per_page=" in command, (
                "a documented measurement calls GitHub without `per_page`; the "
                f"default page hides releases: {command}"
            )
            assert "--paginate" in command, (
                "a documented measurement reads only the first page, so its total "
                f"is a slice of the real one: {command}"
            )

    def test_the_document_says_why_per_page_is_not_optional(self) -> None:
        text = METRICS.read_text(encoding="utf-8")
        assert "per_page" in text
        # The measured numbers, so a reader can see the size of the mistake.
        assert "83" in text and "732" in text, (
            "the document no longer shows what the truncated command reported "
            "next to the real total, which is the only reason to believe the "
            "warning instead of skipping it"
        )
        assert "255" in text, "the real release count is not written down"


class TestTheLoopSaysWhichStagesRun:
    """A diagram of a pipeline is a claim about machinery; eight of ten stages exist."""

    def test_the_nightly_is_not_described_as_a_retrospective(self) -> None:
        names = " | ".join(_nightly_step_names()).lower()
        assert "commit" not in names, (
            "nightly.yml gained a step that reads commits; this test and the "
            "documents were written when the nightly only dogfooded the release"
        )
        # And the document must not claim it either.
        text = MAINTENANCE.read_text(encoding="utf-8")
        loop = _section(text, "## The loop")
        assert "retrospective" in loop.lower(), (
            "the loop diagram no longer names the retrospective stage at all, "
            "so this guard is not looking at the thing it was written for"
        )
        # The retrospective entry must be marked as not built. The diagram puts
        # it on its own arrow, so the marker lives on a continuation line: read
        # the two lines after the arrow rather than requiring them to share one.
        lines = loop.splitlines()
        entries = [index for index, line in enumerate(lines) if "retrospective" in line.lower()]
        assert entries, "the diagram no longer mentions the retrospective"
        window = " ".join(lines[entries[0] : entries[0] + 2]).lower()
        assert "not built" in window, (
            "the loop diagram introduces the retrospective without saying it is "
            f"not built: {window!r}"
        )

    def test_the_stages_that_do_not_run_are_named(self) -> None:
        """Naming a stage is not saying whether it runs; the table must say."""
        text = MAINTENANCE.read_text(encoding="utf-8")
        section = _section(text, "### What is automated, and what is not")
        rows = [
            line
            for line in section.splitlines()
            if line.strip().startswith("|") and line.count("|") >= 3
        ]
        table = "\n".join(rows).lower()
        for noun in ("issue", "review", "merge", "retrospective"):
            assert noun in table, (
                f"the automation table does not name the `{noun}` stage, so a "
                "reader cannot tell whether it runs"
            )
        # Each of the four rows must state the state, not merely the noun.
        assert "nothing consumes it" in table, "no row says what reads a new issue"
        assert "no reviewer runs" in section.lower(), (
            "the review row no longer says that no reviewer runs on a pull "
            "request, which is the sentence the whole table exists for"
        )
        assert "no merge bot" in table, "the merge row no longer says there is no merge bot"

    def test_the_retrospective_section_says_it_is_not_automated(self) -> None:
        text = MAINTENANCE.read_text(encoding="utf-8")
        heading = re.search(r"^##+ .*retrospective.*$", text, re.MULTILINE | re.IGNORECASE)
        assert heading is not None, "maintenance.md lost its retrospective section"
        assert "not yet automated" in heading.group(0).lower(), (
            "the retrospective section is titled as if it runs; the heading is "
            f"the part a skimming reader reads: {heading.group(0)!r}"
        )

    def test_the_lessons_file_does_not_promise_a_nightly_review(self) -> None:
        """LESSONS.md said "each night the day's commits are reviewed" while its
        own marker said `none`. The file that a reader consults for method was
        describing a method nobody runs."""
        lessons = re.sub(r"\s+", " ", LESSONS.read_text(encoding="utf-8"))
        assert "does not run yet" in lessons, (
            "LESSONS.md no longer admits that the retrospective does not run, so "
            "its opening paragraph reads as a description of a working process"
        )
        assert "Each night the day's commits are reviewed for" not in lessons, (
            "the present-tense claim that commits are reviewed each night is back"
        )

    def test_the_lessons_marker_agrees_with_the_document(self) -> None:
        text = MAINTENANCE.read_text(encoding="utf-8")
        marker = re.search(r"reviewed-through:\s*(\S+)", LESSONS.read_text(encoding="utf-8"))
        assert marker is not None, "LESSONS.md lost its reviewed-through marker"
        state = marker.group(1)
        if not state.startswith("none"):
            return
        # The sentence, not the word: `none has been harvested` contains "none"
        # too, which is how the first version of this test passed against a
        # document that claimed a date.
        flattened = re.sub(r"\s+", " ", text)
        assert re.search(r"marker currently reads `?none`?", flattened, re.IGNORECASE), (
            "LESSONS.md says no retrospective has run, but maintenance.md does "
            "not say the marker reads none"
        )


class TestTheNumbersSayWhatTheyCannotProve:
    """Zero issues means nobody reported anything, not that nobody is using it."""

    def test_zero_is_not_read_as_nobody_uses_it(self) -> None:
        """Naming the mistake is fine; making it is not.

        A bare substring check would fail on the correction itself - the file now
        says zero is *not* evidence that nobody uses it - so this reads the
        assertion instead of the vocabulary: the phrase may appear only inside a
        sentence that denies it.
        """
        text = METRICS.read_text(encoding="utf-8")
        flattened = re.sub(r"\s+", " ", text)
        pattern = r"nobody (?:has )?(?:use[sd]?|used)(?: it| this| the tool)?\b"
        for match in re.finditer(pattern, flattened, re.IGNORECASE):
            before = flattened[max(0, match.start() - 140) : match.start()].lower()
            # Naming the mistake is the point of the section that carries it, so
            # the phrase is allowed when the sentence denies it. What is not
            # allowed is using it as the conclusion.
            denies = any(
                mark in before
                for mark in (
                    "is not evidence",
                    "not evidence that",
                    "no evidence that",
                    # Quoting the mistake in order to reject it is the file's
                    # whole method, so a quotation mark is not the failure.
                    "narrower than",
                    "instead of",
                )
            )
            assert denies, (
                "metrics.md converts a zero count into a claim about users "
                f"instead of stating what the count cannot prove: {before[-120:]!r}"
            )
        # The superseded sentences are gone for good.
        for gone in ("nobody has used it yet", "nobody uses it.", "nobody uses this."):
            assert gone not in flattened, f"the old absolute claim came back: {gone!r}"

    def test_automation_is_separated_from_people(self) -> None:
        text = METRICS.read_text(encoding="utf-8")
        section = re.sub(
            r"\s+", " ", _section(text, "## What counts, and what does not")
        ).lower()
        # The distinction has to be stated, not merely implied by two nouns
        # appearing somewhere in the section.
        assert "automation this project runs, or a person who arrived" in section, (
            "the counts section no longer draws the line between behaviour this "
            "project produced and behaviour a stranger produced"
        )
        assert "the nightly fetches the newest wheel daily" in section, (
            "the download row does not name the nightly job, so a reader cannot "
            "tell that every download total contains this project's own fetching"
        )
        assert "a person arrives at one release and stays there" in section, (
            "nothing says what a person's downloads would look like instead of "
            "the even dusting that automation produces"
        )

    def test_a_zero_count_carries_its_own_limitation(self) -> None:
        text = METRICS.read_text(encoding="utf-8")
        section = re.sub(r"\s+", " ", _section(text, "## What would make me change course"))
        assert "zero downloads" in section.lower()
        # The row itself must carry its limitation, not a later paragraph.
        row = next(
            (line for line in section.splitlines() if "zero downloads" in line.lower()),
            "",
        )
        assert "cannot demonstrate pain" in row, (
            "the 30-day row states its trigger without stating that a tool "
            f"nobody can install cannot demonstrate need either way: {row!r}"
        )
        assert "the funnel was open" in section, (
            "the paragraph explaining why the zero-count row used to overreach is "
            "gone, so the row now looks like a plain conclusion again"
        )
        assert "nobody could install it" in section, (
            "the caveat no longer names the other explanation an empty column "
            "supports (the 404 funnel), which is the whole reason it is a caveat"
        )
        assert "cannot tell those apart" in section, (
            "the paragraph names both explanations but never says the measurement "
            "cannot separate them, which is the only actionable part of the caveat"
        )
