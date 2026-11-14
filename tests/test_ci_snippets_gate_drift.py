"""Every CI gate this project documents has to fail when the evidence drifts.

The audit found the sections disagreeing with each other in two ways, and both
were sentences rather than code:

  * The action example uploads SARIF in a step that follows the gate. GitHub
    skips a step after a failed one, so the upload ran only when there was
    nothing to upload - the one case a code-scanning comment would have helped.
  * The hand-written "three lines do the same job" snippet left out
    `--fail-on medium`, so it ran at the CLI default `high` while the action
    defaults to `medium`. A replaced source file is `source-changed`, which is
    `medium`: the action failed and the snippet exited `0`, on the same tree.

Measured on a project whose ledger and source differed by one appended
sentence, with the quoted words and every number untouched:

    documented snippet without the flag  ->  rc=0, codes=[source-changed, quote-found]
    the same command with --fail-on medium ->  rc=1, codes=[source-changed, quote-found]

The tests below run the command the documents print, rather than looking for
the flag by name, because a snippet can carry a flag and still be wrong about
where it points, and a snippet can be right about the flag in one README and
wrong in the other. They also assert the measured contrast, so that removing
the flag from the documents fails here instead of silently weakening the gate.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
READMES = ("README.md", "README.zh-CN.md")

QUOTE = "We collected 40,688 examples from the corpus."
PAGE = QUOTE + "\n"

#: The threshold that lets `source-changed` and `quote-moved` (both `medium`)
#: fail the job. A gate may choose a *lower* one; it may not choose a higher.
GATE_THRESHOLD = "medium"
SEVERITY_ORDER = ["info", "low", "medium", "high"]

ENV = {
    **os.environ,
    "PYTHONPATH": str(SRC),
    "PYTHONIOENCODING": "utf-8",
}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _yaml_blocks(name: str) -> list[str]:
    text = (ROOT / name).read_text(encoding="utf-8")
    return re.findall(r"```yaml\n(.*?)```", text, re.DOTALL)


def _documented_gate_commands() -> list[tuple[str, list[str]]]:
    """Every `citevouch check ... --use-recorded` a README tells CI to run.

    Returns `(readme, argv)` with the shell redirect removed, because the
    question is what the command decides, not where its SARIF lands.
    """
    found: list[tuple[str, list[str]]] = []
    for name in READMES:
        for block in _yaml_blocks(name):
            for step in yaml.safe_load(block) or []:
                body = step.get("run")
                if not isinstance(body, str):
                    continue
                if "citevouch check" not in body or "--use-recorded" not in body:
                    continue
                command = body.split(">", 1)[0].strip()
                argv = shlex.split(command)
                assert argv[0].endswith("citevouch"), f"{name}: {argv[0]!r} is not citevouch"
                found.append((name, argv[1:]))
    return found


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / "sources").mkdir(parents=True)
    (root / "sources" / "page.txt").write_text(PAGE, encoding="utf-8", newline="\n")
    (root / "sources.toml").write_text(
        '[sources]\npaper = "sources/page.txt"\n', encoding="utf-8", newline="\n"
    )
    (root / "manuscript.md").write_text(
        f"# Methods\n\n```claim\nid: c1\nsource: paper\npage: 1\nquote: |\n  {QUOTE}\n```\n",
        encoding="utf-8",
        newline="\n",
    )
    return root


def _citevouch(root: Path, argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "citevouch", *argv],
        cwd=root,
        env=ENV,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _drifted(tmp_path: Path) -> Path:
    """A recorded project whose source then gained a sentence.

    The appended sentence touches neither the quoted words nor any number, so
    the only finding is `source-changed` (medium): exactly the drift the action
    description promises to catch, and exactly the finding a `high` threshold
    cannot see.
    """
    root = _project(tmp_path)
    scanned = _citevouch(root, ["scan", "manuscript.md", "--root", "."])
    assert scanned.returncode == 0, scanned.stderr
    (root / "sources" / "page.txt").write_text(
        QUOTE + "\nAn appendix was added later.\n", encoding="utf-8", newline="\n"
    )
    return root


# --------------------------------------------------------------------------- #
# what the documents print actually gates
# --------------------------------------------------------------------------- #
class TestTheDocumentedGateFailsOnDrift:
    def test_every_documented_gate_carries_a_threshold_that_can_see_drift(self):
        commands = _documented_gate_commands()
        assert commands, "no documented `check --use-recorded` command found in any README"
        for name, argv in commands:
            assert "--fail-on" in argv, (
                f"{name}: `citevouch {' '.join(argv)}` is presented as a CI gate but carries no "
                f"--fail-on, so it runs at the CLI default `high` and lets `source-changed` "
                f"({GATE_THRESHOLD}) exit 0"
            )
            written = argv[argv.index("--fail-on") + 1]
            assert written in SEVERITY_ORDER, f"{name}: --fail-on {written!r} is not a severity"
            assert SEVERITY_ORDER.index(written) <= SEVERITY_ORDER.index(GATE_THRESHOLD), (
                f"{name}: --fail-on {written} cannot fail on `source-changed`, which is "
                f"{GATE_THRESHOLD}"
            )

    def test_running_the_documented_command_rejects_a_replaced_source(self, tmp_path):
        commands = _documented_gate_commands()
        root = _drifted(tmp_path)
        for name, argv in commands:
            # The real argv, format included: the exit code is the claim under
            # test, and `--format sarif` only changes stdout, not the verdict.
            result = _citevouch(root, argv)
            assert result.returncode == 1, (
                f"{name}: `citevouch {' '.join(argv)}` exited {result.returncode} on a replaced "
                f"source; stdout={result.stdout[:200]!r} stderr={result.stderr[:200]!r}"
            )


class TestTheThresholdIsWhatMakesItAGate:
    """The contrast that justifies writing the flag out.

    Without these two assertions, the flag in the snippet is a style choice; with
    them, it is the difference between a gate and a report.
    """

    def test_the_default_threshold_would_let_the_drift_through(self, tmp_path):
        root = _drifted(tmp_path)
        result = _citevouch(
            root,
            ["check", "manuscript.md", "--root", ".", "--use-recorded", "--format", "json"],
        )
        assert result.returncode == 0, (
            "the CLI default is documented as not failing on medium drift; if this now exits 1, "
            "the README paragraph explaining that contrast has become false"
        )
        payload = result.stdout
        assert "source-changed" in payload, (
            "the drift must still be reported, just not fatal at the default threshold"
        )

    def test_the_documented_threshold_does_fail_on_the_same_tree(self, tmp_path):
        root = _drifted(tmp_path)
        result = _citevouch(
            root,
            [
                "check",
                "manuscript.md",
                "--root",
                ".",
                "--use-recorded",
                "--fail-on",
                GATE_THRESHOLD,
                "--format",
                "json",
            ],
        )
        assert result.returncode == 1, result.stdout[:300]
        assert "source-changed" in result.stdout


class TestTheUploadRunsEvenWhenTheGateFails:
    """A step after a failed step does not run unless it says `always()`."""

    def test_every_documented_upload_step_is_unconditional(self):
        uploads: list[tuple[str, dict]] = []
        for name in READMES:
            for block in _yaml_blocks(name):
                for step in yaml.safe_load(block) or []:
                    uses = step.get("uses", "")
                    if isinstance(uses, str) and "upload-sarif" in uses:
                        uploads.append((name, step))
        assert uploads, "no documented SARIF upload step found in any README"
        for name, step in uploads:
            condition = str(step.get("if", ""))
            assert "always()" in condition, (
                f"{name}: the upload step has if: {condition!r}. A step after a failed step is "
                f"skipped by default, so without `if: always()` the findings reach code scanning "
                f"only on the runs where nothing was found."
            )

    def test_the_upload_step_reads_the_path_the_gate_publishes(self):
        for name in READMES:
            for block in _yaml_blocks(name):
                steps = yaml.safe_load(block) or []
                ids = {
                    step.get("id")
                    for step in steps
                    if isinstance(step.get("uses"), str)
                    and step["uses"].startswith("lyear12/citevouch")
                }
                for step in steps:
                    if "upload-sarif" not in str(step.get("uses", "")):
                        continue
                    path = (step.get("with") or {}).get("sarif_file", "")
                    named = re.findall(r"steps\.([A-Za-z0-9_-]+)\.outputs\.sarif", str(path))
                    assert named, f"{name}: the upload does not read a step output: {path!r}"
                    for step_id in named:
                        assert step_id in ids, (
                            f"{name}: the upload reads steps.{step_id}.outputs.sarif but no "
                            f"citevouch step declares id {step_id!r} (ids: {sorted(ids)})"
                        )


class TestTheRecordedGateSaysWhatItCovers:
    """`--use-recorded` is broader than "the PDF moved", and the docs said otherwise.

    The README used to say the job "fails only when the PDFs or the manuscript
    moved underneath the evidence". Measured, that is half the story: the
    recorded pass takes its claim list from the ledger, then re-reads the
    sources and re-matches every quote, so a quote the ledger holds and the
    source never printed comes back as `quote-fuzzy` (medium) and exits 1 on the
    same tree nothing moved on. A reader who believed the old sentence would
    treat that red job as a false alarm.

    The narrow half is just as load-bearing: a manuscript edited after the
    ledger was written is `ledger-stale` (high), reported *instead of* matching,
    so `--fail-on medium` never sees a quote verdict it cannot justify.
    """

    QUOTE_NEVER_PRINTED = "The construction inventory was annotated by nine coders."

    PRINTED = "The construction inventory was annotated by two coders.\n"

    def _projects(self, tmp_path: Path) -> dict[str, Path]:
        base = tmp_path / "base"
        (base / "sources").mkdir(parents=True)
        (base / "sources" / "page.txt").write_text(self.PRINTED, encoding="utf-8", newline="\n")
        (base / "sources.toml").write_text(
            '[sources]\npaper = "sources/page.txt"\n', encoding="utf-8", newline="\n"
        )
        projects = {}
        for name, quote in {
            "printed": self.PRINTED.strip(),
            "absent": self.QUOTE_NEVER_PRINTED,
        }.items():
            root = tmp_path / name
            (root / "sources").mkdir(parents=True)
            (root / "sources" / "page.txt").write_text(
                self.PRINTED, encoding="utf-8", newline="\n"
            )
            (root / "sources.toml").write_text(
                '[sources]\npaper = "sources/page.txt"\n', encoding="utf-8", newline="\n"
            )
            (root / "manuscript.md").write_text(
                "# Methods\n\n```claim\nid: c1\nsource: paper\npage: 1\nquote: |\n  "
                + quote
                + "\n```\n",
                encoding="utf-8",
                newline="\n",
            )
            assert _citevouch(root, ["scan", "manuscript.md", "--root", "."]).returncode == 0
            projects[name] = root
        return projects

    def test_a_quote_the_ledger_holds_still_fails_the_recorded_gate(self, tmp_path):
        root = self._projects(tmp_path)["absent"]
        result = _citevouch(
            root,
            [
                "check",
                "manuscript.md",
                "--root",
                ".",
                "--use-recorded",
                "--fail-on",
                GATE_THRESHOLD,
                "--format",
                "json",
            ],
        )
        assert result.returncode == 1, (
            "nothing moved here - the ledger and the source are the files that were scanned - so this "
            "is the recorded pass judging the quote itself; if it exits 0 the README may claim the gate "
            "only watches for drift"
        )
        assert "quote-fuzzy" in result.stdout, result.stdout[:300]

    @pytest.mark.parametrize("name", READMES)
    def test_the_readme_names_both_halves(self, name: str):
        text = re.sub(r"\s+", " ", (ROOT / name).read_text(encoding="utf-8"))
        assert "quote-fuzzy" in text
        assert "ledger-stale" in text
        flat = text.lower()
        assert "only when" not in flat or "fails only when" not in flat, (
            f"{name}: the recorded gate is described as failing only on drift, which the measurement "
            f"above contradicts"
        )

    def test_an_edited_manuscript_stops_before_matching(self, tmp_path):
        projects = self._projects(tmp_path)
        root = projects["printed"]
        manuscript = root / "manuscript.md"
        manuscript.write_text(
            manuscript.read_text(encoding="utf-8") + "\nA new paragraph was added.\n",
            encoding="utf-8",
            newline="\n",
        )
        result = _citevouch(
            root,
            [
                "check",
                "manuscript.md",
                "--root",
                ".",
                "--use-recorded",
                "--fail-on",
                GATE_THRESHOLD,
                "--format",
                "json",
            ],
        )
        assert result.returncode == 1
        payload = result.stdout
        assert "ledger-stale" in payload
        assert "quote-found" not in payload, (
            "an edited manuscript must not also produce quote verdicts: every one of them would be a "
            "sentence about a document the ledger no longer describes"
        )


class TestTheParagraphsAreNotClaimsTheSnippetsContradict:
    def test_the_action_default_is_named_where_the_manual_snippet_is(self):
        """The snippet must say why it writes the flag the action defaults to."""
        for name in READMES:
            text = (ROOT / name).read_text(encoding="utf-8")
            assert "--fail-on medium" in text, (
                f"{name}: the CI section lost the explicit threshold"
            )
            assert "medium" in text, name

    def test_the_cli_default_is_still_documented_as_a_person_reading_output(self):
        """The contrast is what makes the action's default a decision, not a guess."""
        english = (ROOT / "README.md").read_text(encoding="utf-8")
        # Normalised because the sentence wraps, and the wrap point is not the claim.
        flat = re.sub(r"\s+", " ", english)
        assert "default is still `high`, because you are reading the output" in flat, (
            "the README must keep explaining why the CLI default differs from the action's: "
            "that contrast is the only justification for the action overriding it"
        )
