"""CV-009 (second pass): the trigger has to name a workflow that has runs.

The first version of publish.yml said `workflow_run: workflows: ["Release"]`.
`release.yml` is reusable, so it never has a run of its own: GitHub's run list for
this repository, 100 entries deep, contains `Auto release`, `Test` and `Nightly
dogfood` and no `Release` at all.  A trigger naming it matches nothing, which is
the same class of defect as the one this workflow was written to fix - a name
that looks right in the file and is wrong in the system.

These tests read the trigger against the workflows that exist, and run the two
gates that decide whether a run does any work, because "most runs should do
nothing and stay green" is behaviour, not a comment.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
PUBLISH = WORKFLOWS / "publish.yml"
MAINTENANCE = ROOT / "docs" / "maintenance.md"


def _yaml():
    return pytest.importorskip("yaml")


def _load(path: Path) -> dict:
    return _yaml().safe_load(path.read_text(encoding="utf-8"))


def _steps() -> list[dict]:
    steps: list[dict] = []
    for job in _load(PUBLISH)["jobs"].values():
        steps.extend(job.get("steps", []))
    return steps


def _step(prefix: str) -> dict:
    for step in _steps():
        if str(step.get("name", "")).startswith(prefix):
            return step
    raise AssertionError(f"publish.yml has no step starting with {prefix!r}")


def _triggers() -> dict:
    data = _load(PUBLISH)
    return data.get("on", data.get(True)) or {}


def _bash() -> str:
    for candidate in (
        shutil.which("bash"),
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
        "/bin/bash",
        "/usr/bin/bash",
    ):
        if candidate and Path(candidate).is_file():
            return candidate
    pytest.fail("no bash on this machine, so no step body could be run")


class TestTheTriggerNamesAWorkflowThatHasRuns:
    def test_the_watched_workflow_is_the_caller_not_the_called(self) -> None:
        watched = _triggers()["workflow_run"]["workflows"]
        assert watched == ["Auto release"], (
            "release.yml is reusable, so it has no runs of its own; a "
            f"workflow_run trigger naming it matches nothing: {watched!r}"
        )

    def test_the_watched_workflow_is_not_itself_reusable(self) -> None:
        watched = _triggers()["workflow_run"]["workflows"]
        for name in watched:
            path = next(p for p in WORKFLOWS.glob("*.yml") if _load(p).get("name") == name)
            triggers = _load(path).get("on", _load(path).get(True)) or {}
            assert "workflow_call" not in triggers, (
                f"{path.name} is reusable; it cannot be watched by workflow_run"
            )

    def test_the_manual_door_still_exists(self) -> None:
        assert "workflow_dispatch" in _triggers()

    def test_the_page_states_the_run_counts_that_settle_the_name(self) -> None:
        text = MAINTENANCE.read_text(encoding="utf-8")
        assert "`Release` **zero**" in text, (
            "the page has to carry the measurement, or the next reader will "
            "restore the obvious-looking name"
        )
        assert "Auto release" in text and "43793698436" in text


class TestMostRunsDoNothingAndStayGreen:
    def _run_gate(
        self,
        tmp_path: Path,
        *,
        release: str | None,
        index: str,
        run_jobs: str = "success",
    ) -> tuple[int, str, str]:
        """Run the gate with `gh` and `curl` replaced by bash functions.

        A stub on `PATH` is not enough on Windows: Git Bash resolves `curl` to the
        real `curl.exe` before it looks at a script named `curl`, so the suite
        measured this machine's network instead of the step - which passed here
        and failed on all three Windows CI jobs.  Shell functions win over
        executables for a non-builtin name, so the step cannot reach the real
        tools at all.
        """
        body = _step("Stop quietly")["run"]
        body = body.replace("${{ steps.v.outputs.tag }}", "v9.9.9")
        body = body.replace("${{ steps.v.outputs.version }}", "9.9.9")
        body = body.replace("${{ github.repository }}", "lyear12/citevouch")
        body = body.replace("${{ github.event.workflow_run.id }}", "12345")
        stub = (
            "set -eu\n"
            f'release_tag="{release or ""}"\n'
            f'run_jobs="{run_jobs}"\n'
            "used=$(pwd)/tools_used.txt\n"
            "gh() {\n"
            '  echo "gh $*" >> "$used"\n'
            '  if [ "$1" = "api" ]; then echo "$run_jobs"; return 0; fi\n'
            '  if [ "$1 $2" = "release view" ]; then\n'
            '    if [ -n "$release_tag" ]; then echo "ok"; return 0; fi\n'
            '    echo "release not found" >&2\n'
            "    return 1\n"
            "  fi\n"
            '  echo "unexpected gh: $*" >&2\n'
            "  return 1\n"
            "}\n"
            "curl() {\n"
            '  echo "curl $*" >> "$used"\n'
            f"  printf %s '{index}'\n"
            "  return 0\n"
            "}\n"
        )
        script = tmp_path / "gate.sh"
        script.write_text(stub + body, encoding="utf-8", newline=chr(10))
        outputs = tmp_path / "out.txt"
        outputs.write_text("", encoding="utf-8", newline=chr(10))
        env = {
            **os.environ,
            "GITHUB_OUTPUT": str(outputs),
            "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
            "PYTHONIOENCODING": "utf-8",
        }
        done = subprocess.run(
            [_bash(), str(script)],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
        used = (tmp_path / "tools_used.txt").read_text(encoding="utf-8")
        assert "gh " in used, (
            "the step reached a tool other than the stub; on Windows Git Bash "
            "finds curl.exe and gh.exe before any script on PATH, which is how "
            "this gate was measured here and failed on CI"
        )
        return (
            done.returncode,
            done.stdout + done.stderr,
            outputs.read_text(encoding="utf-8"),
        )

    def test_a_run_that_published_no_tag_does_nothing(self) -> None:
        code, printed, written = self._run_gate(
            _fake(), release="v9.9.9", index="404", run_jobs="skipped"
        )
        assert code == 0, printed
        assert "publish=false" in written
        assert "published no tag" in printed, (
            "the first production run retried a version released minutes "
            f"earlier; the watched run's own conclusion answers this.  Got {printed!r}"
        )

    def test_an_unreleased_tag_does_nothing_and_exits_zero(self) -> None:
        code, printed, written = self._run_gate(_fake(), release=None, index="404")
        assert code == 0, printed
        assert "publish=false" in written
        assert "nothing to publish" in printed

    def test_a_version_pypi_already_serves_does_nothing_and_exits_zero(self) -> None:
        code, printed, written = self._run_gate(_fake(), release="v9.9.9", index="200")
        assert code == 0, printed
        assert "publish=false" in written
        assert "already serves 9.9.9" in printed

    def test_a_released_version_the_index_does_not_have_is_published(self) -> None:
        code, printed, written = self._run_gate(_fake(), release="v9.9.9", index="404")
        assert code == 0, printed
        assert "publish=true" in written

    def test_the_upload_is_skipped_when_the_gate_says_so(self) -> None:
        gate = _step("Download the assets")
        assert gate["if"].strip() == "steps.gate.outputs.publish == 'true'", (
            "the download, the digest check and the upload all have to read the "
            "same gate, or a run with nothing to do still fetches and verifies"
        )
        for name in ("The bytes about to be uploaded", "Publish to PyPI"):
            assert _step(name)["if"].strip() == "steps.gate.outputs.publish == 'true'"

    def test_the_summary_explains_a_run_that_uploaded_nothing(self) -> None:
        body = _step("Summarise")["run"]
        assert "Nothing was uploaded" in body, (
            "a green run that printed nothing reads as a publish that silently did not happen"
        )


class TestTheVersionComesFromTheCommit:
    def test_the_checkout_is_the_finished_run_not_main(self) -> None:
        checkout = next(
            s for s in _steps() if str(s.get("uses", "")).startswith("actions/checkout")
        )
        assert "workflow_run.head_sha" in str(checkout.get("with", {}).get("ref", "")), (
            "the bytes belong to the commit whose release exists; checking out "
            "main publishes whatever it says by the time the run starts"
        )

    def test_the_tag_comes_from_the_release_not_the_version_file(self) -> None:
        body = _step("Resolve the tag")["run"]
        assert "gh release view --json tagName" in body, (
            "the payload names the commit that *started* the watched run, which "
            "is the commit before the version bump; reading the version file "
            "there offers the previous number, which is what run 43801727572 did"
        )
        assert "src/citevouch/_version.py" not in body, (
            "the version file is the right answer to a different question"
        )

    def test_a_tree_without_a_release_is_a_usage_error(self) -> None:
        body = _step("Resolve the tag")["run"]
        assert "no release to publish" in body

    def test_a_branch_name_is_still_refused(self) -> None:
        body = _step("Resolve the tag")["run"]
        assert 'case "$tag" in' in body and "v?*" in body


def _fake() -> Path:
    return Path(tempfile.mkdtemp())
