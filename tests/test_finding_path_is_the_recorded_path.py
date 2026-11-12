"""One run must not hold two names for the manuscript it read.

Measured before this patch, with ``sources.toml`` at the repository root and
the manuscript at ``paper/m.md`` - the shape ``action.yml`` documents - run as
``check paper/m.md --root .``:

    [high] quote-missing at m.md:3 (c1): We collected 40,688 examples ...
    ledger: manuscript = 'paper/m.md'

Two names for one file.  The ledger's is the one that resolves: GitHub code
scanning reads a SARIF ``uri`` against the repository root, where ``m.md`` does
not exist, so the annotation is dropped and the pull request shows nothing -
the failure ``report._sarif_uri`` documents and repairs only for absolute
paths.

The finding's own ``path`` used to be the bare basename on the reasoning that
"a report of the same project reads identically wherever it is checked out".
A path relative to ``--root`` has that property too; a basename additionally
loses the directory as soon as the project has one.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from citevouch import scan as scan_module
from citevouch.scan import ScanOptions

NL = chr(10)
B3 = "`" * 3
QUOTE = "We collected 40,688 examples from the corpus."
ABSENT = "This sentence is on no page at all, and the report should say so."
SRC = Path(__file__).resolve().parents[1] / "src"


def _project(tmp_path: Path, *, nested: bool = True, body: str | None = None) -> Path:
    """A project whose manuscript sits in a directory, or at the root."""
    paper = tmp_path / "paper" if nested else tmp_path
    paper.mkdir(parents=True, exist_ok=True)
    (paper / "page.txt").write_text("Nothing to see here." + NL, encoding="utf-8", newline=NL)
    (tmp_path / "sources.toml").write_text(
        "[sources]" + NL + 'paper = "paper/page.txt"' + NL, encoding="utf-8", newline=NL
    )
    block = (
        body
        if body is not None
        else (
            f"# t{NL}{NL}{B3}claim id=c1 source=paper page=1{NL}quote: |{NL}"
            f"  {ABSENT}{NL}{B3}{NL}"
        )
    )
    (paper / "m.md").write_text(block, encoding="utf-8", newline=NL)
    return tmp_path


def _run(root: Path, *argv: str) -> tuple[int, str]:
    env = {**os.environ, "PYTHONPATH": str(SRC), "PYTHONIOENCODING": "utf-8"}
    done = subprocess.run(
        [sys.executable, "-m", "citevouch", *argv],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return done.returncode, done.stdout + done.stderr


def _json(root: Path, *argv: str) -> dict:
    code, out = _run(root, *argv, "--format", "json")
    assert code in (0, 1), out
    # `scan` adds a one-line note on stderr after the payload (`wrote
    # citevouch.lock.json (0 claims)`), and the two streams are concatenated
    # here so a failure message shows both.  Parse up to the end of the object.
    return json.loads(out[: out.rindex("}") + 1])


def _finding_paths(root: Path, *argv: str) -> list[str]:
    """The path of every finding, read from the JSON the command prints."""
    return [entry["path"] for entry in _json(root, *argv)["findings"]]


# A manuscript whose block the parser reads and refuses: it produces a finding
# from the parser itself, which is the shape `scan` reports without running a
# verdict, so both commands can be compared on one file.
REFUSED = f"# t{NL}{NL}{B3}claim{NL}quote: |{NL}  {QUOTE}{NL}{B3}{NL}"


class TestTheFindingIsSpelledLikeTheLedger:
    def test_a_nested_manuscript_is_not_reduced_to_its_basename(self, tmp_path: Path):
        root = _project(tmp_path)
        paths = _finding_paths(root, "check", "paper/m.md", "--root", ".")
        assert paths == ["paper/m.md"], paths

    def test_the_finding_and_the_ledger_agree(self, tmp_path: Path):
        """The claim is about one file; two readers must spell it one way."""
        root = _project(tmp_path, body=REFUSED)
        ledger, findings = scan_module.scan(
            ScanOptions(manuscript="paper/m.md", root=str(root))
        )
        assert ledger.manuscript == "paper/m.md"
        assert findings, "the refused block should have produced a finding"
        assert [finding.path for finding in findings] == [ledger.manuscript] * len(findings)

    def test_the_root_is_what_decides_the_spelling(self, tmp_path: Path):
        # Standing inside `paper` and reading `m.md` against `--root paper`,
        # the same file is correctly called `m.md` - that name resolves there.
        root = _project(tmp_path)
        paths = _finding_paths(root, "check", "m.md", "--root", "paper")
        assert paths == ["m.md"], paths

    def test_a_manuscript_at_the_project_root_keeps_its_plain_name(self, tmp_path: Path):
        root = _project(tmp_path, nested=False)
        paths = _finding_paths(root, "check", "m.md", "--root", ".")
        assert paths == ["m.md"], paths

    def test_an_absolute_manuscript_still_names_the_project_file(self, tmp_path: Path):
        root = _project(tmp_path)
        absolute = (root / "paper" / "m.md").as_posix()
        paths = _finding_paths(root, "check", absolute, "--root", ".")
        assert paths == ["paper/m.md"], paths

    def test_sarif_carries_the_path_that_resolves(self, tmp_path: Path):
        # This is the reader that mattered: a `uri` is resolved against the
        # repository root by the code-scanning viewer.
        root = _project(tmp_path)
        code, out = _run(root, "check", "paper/m.md", "--root", ".", "--format", "sarif")
        assert code == 1, out
        blob = json.loads(out)
        uris = [
            result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
            for result in blob["runs"][0]["results"]
        ]
        assert "paper/m.md" in uris, uris
        assert "m.md" not in uris, uris


class TestEveryReaderOfTheManuscriptAgrees:
    def test_scan_and_check_print_the_same_path(self, tmp_path: Path):
        root = _project(tmp_path, body=REFUSED)
        scanned = _finding_paths(root, "scan", "paper/m.md", "--root", ".")
        checked = _finding_paths(root, "check", "paper/m.md", "--root", ".")
        assert scanned == checked == ["paper/m.md"]

    def test_recorded_check_reports_the_ledger_name(self, tmp_path: Path):
        root = _project(tmp_path)
        assert _run(root, "scan", "paper/m.md", "--root", ".")[0] == 0
        paths = _finding_paths(root, "check", "paper/m.md", "--root", ".", "--use-recorded")
        assert paths == ["paper/m.md"], paths

    def test_the_zero_claim_sentence_names_the_file(self, tmp_path: Path):
        # `no-claim-blocks` takes a different branch that names the file inside
        # the message as well as in `path`; both have to carry the directory.
        root = _project(tmp_path, body="prose only" + NL)
        code, out = _run(root, "check", "paper/m.md", "--root", ".")
        assert code == 1, out
        assert "paper/m.md contains no claim blocks" in out, out

    def test_the_unbound_marker_sentence_names_the_file(self, tmp_path: Path):
        """The marker scan is a second reader of the same lines."""
        root = _project(
            tmp_path, body="【原文】 the corpus is large" + NL + NL + "Some prose." + NL
        )
        code, out = _run(root, "check", "paper/m.md", "--root", ".")
        assert code == 1, out
        assert "claim-without-evidence at paper/m.md" in out, out
        assert " at m.md" not in out, out

    def test_the_doctor_names_it_the_same_way(self, tmp_path: Path):
        root = _project(tmp_path, body="prose only" + NL)
        code, out = _run(root, "doctor", "--root", ".", "--manuscript", "paper/m.md")
        assert code == 1, out
        assert "paper/m.md" in out, out
        assert " in m.md:" not in out, out

    def test_the_diagnosis_of_an_undecoded_block_names_the_file(self, tmp_path: Path):
        """The `claims` line prints the name in its own sentence, too.

        A quote holding replacement characters is the one `claims` branch that
        spells the manuscript inside the detail rather than in `path`, so it is
        the only place a basename regression in `doctor` shows up.  The file has
        to be *actually* undecodable: the character alone refused a lossless
        manuscript that quotes a replacement character on purpose.
        """
        root = _project(tmp_path)
        block = (
            f"# t{NL}{NL}{B3}claim id=c1 source=paper page=1{NL}quote: |{NL}"
            f"  本文收集了六万八千个例句。{NL}{B3}{NL}"
        )
        (root / "paper" / "m.md").write_bytes(block.encode("gbk"))
        code, out = _run(root, "doctor", "--root", ".", "--manuscript", "paper/m.md")
        assert code == 1, out
        assert "in paper/m.md:" in out, out
        assert "in m.md:" not in out, out

    def test_a_finding_no_longer_names_a_file_that_does_not_exist(self, tmp_path: Path):
        root = _project(tmp_path)
        code, out = _run(root, "check", "paper/m.md", "--root", ".")
        assert code == 1, out
        assert "at m.md:" not in out, out
        assert "at paper/m.md:" in out, out


class TestTheDefectItReplaced:
    def test_the_ledger_was_already_right(self, tmp_path: Path):
        """The measurement, kept as a test.

        If this ever fails, the ledger changed its spelling rather than the
        findings, and every assertion above is measuring the wrong side.
        """
        root = _project(tmp_path)
        assert _run(root, "scan", "paper/m.md", "--root", ".")[0] == 0
        blob = json.loads((root / "citevouch.lock.json").read_text(encoding="utf-8"))
        assert blob["manuscript"] == "paper/m.md"


class TestTheGuardsThatFireBeforeAnyParsing:
    def test_a_ledger_about_another_document_names_this_one_relatively(self, tmp_path: Path):
        """`ledger-stale` is emitted before the parser runs, from its own code.

        It spelled the manuscript with ``str(manuscript_path)`` - the resolved
        absolute path - so a run inside the checkout printed
        ``C:\\...\\paper\\m.md`` where every other finding of the same project
        printed ``paper/m.md``.  The record and the verdict have to agree on
        what the file is called.
        """
        root = _project(tmp_path)
        assert _run(root, "scan", "paper/m.md", "--root", ".")[0] == 0
        other = root / "paper" / "other.md"
        other.write_text(
            f"# t{NL}{NL}{B3}claim id=c9 source=paper page=1{NL}quote: |{NL}"
            f"  {ABSENT}{NL}{B3}{NL}",
            encoding="utf-8",
            newline=NL,
        )
        code, out = _run(root, "verify", "paper/other.md", "--root", ".")
        assert code == 1, out
        assert "ledger-stale" in out, out
        paths = _finding_paths(root, "verify", "paper/other.md", "--root", ".")
        assert paths == ["paper/other.md"], paths

    def test_a_ledger_whose_recorded_manuscript_is_gone_names_it_relatively(
        self, tmp_path: Path
    ):
        """The other pre-parse guard: the file the ledger names is gone.

        Asked through `check --use-recorded` with a manuscript that is still
        here - the ledger's own/manuscript is the one that vanished from the
        record, which is the branch that fires from the ledger rather than from
        the command line.
        """
        root = _project(tmp_path)
        assert _run(root, "scan", "paper/m.md", "--root", ".")[0] == 0
        ledger = root / "citevouch.lock.json"
        blob = json.loads(ledger.read_text(encoding="utf-8"))
        blob["manuscript"] = "paper/gone.md"
        ledger.write_text(json.dumps(blob, indent=2), encoding="utf-8", newline=NL)
        code, out = _run(root, "check", "paper/gone.md", "--root", ".", "--use-recorded")
        assert code == 1, out
        paths = _finding_paths(root, "check", "paper/gone.md", "--root", ".", "--use-recorded")
        assert paths == ["paper/gone.md"], paths


class TestWhatMustNotChange:
    def test_a_path_is_never_absolute_in_a_finding(self, tmp_path: Path):
        root = _project(tmp_path)
        paths = _finding_paths(root, "check", "paper/m.md", "--root", ".")
        assert paths
        assert all(not Path(item).is_absolute() for item in paths), paths

    def test_the_path_uses_forward_slashes(self, tmp_path: Path):
        root = _project(tmp_path)
        paths = _finding_paths(root, "check", "paper/m.md", "--root", ".")
        assert all(chr(92) not in item for item in paths), paths

    def test_the_claim_verdict_still_names_its_line(self, tmp_path: Path):
        root = _project(tmp_path)
        found = _run(root, "check", "paper/m.md", "--root", ".")[1]
        assert "[high] quote-missing at paper/m.md:3 (c1):" in found, found

    def test_the_zero_claim_verdict_still_names_its_line(self, tmp_path: Path):
        root = _project(tmp_path, body="prose only" + NL)
        found = _run(root, "check", "paper/m.md", "--root", ".")[1]
        assert "[high] no-claim-blocks at paper/m.md:" in found, found
