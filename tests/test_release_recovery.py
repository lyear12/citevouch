"""A release that exists is not a release that is published.

v0.22.14 was lost this way. `gh release create` does three things: create a
*draft* release, upload the assets to it, publish it. The create call answered
``HTTP 502: Server Error`` - and the draft existed anyway. The recovery step
found it, uploaded the wheel and the sdist, and exited zero, so the run was
green, the assets were attached, and the release was a draft nobody could see.
It was republished by hand minutes later, which is exactly the human step this
project exists to not need.

The step's old test would not have caught it: the old body asked ``gh release
view "$tag"`` whether the release exists, and the answer was yes. So these
tests run the real shell body of the recovery step against a ``gh`` stub whose
*existence* and *draftness* are separate state, and they check the exit code
rather than the presence of certain strings. A string assertion would stay
green if the step published nothing and merely said it had.

The stub is a bash function named ``gh``, not a file on PATH, for the reason
``tests/test_tag_push.py`` records: an executable on PATH needs an exec bit,
Windows honours that bit only sometimes, and the real ``gh`` would then run
against the real repository.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "release.yml"

# The stub keeps its state in files because each `gh` call is a separate
# invocation of the function, and a shell variable would not survive it.
STUB = """
gh() {
  if [ "$1" = "release" ]; then
    shift
    case "$1" in
      view)
        shift
        tag="$1"
        shift
        exists=$(cat stub_exists 2>/dev/null || echo 0)
        if [ "$exists" != "1" ]; then
          echo "release not found" >&2
          return 1
        fi
        case "$*" in
          *--json*isDraft*)
            cat stub_draft 2>/dev/null || echo "false"
            ;;
        esac
        return 0
        ;;
      upload)
        echo "UPLOAD $*" >> stub_log.txt
        return 0
        ;;
      edit)
        echo "EDIT $*" >> stub_log.txt
        # Only a real publish flips the state; every other edit leaves it, so a
        # body that edits the wrong field keeps the release a draft. A stuck
        # stub reports success and changes nothing, which is the shape of a
        # publish the API accepted and did not perform.
        if [ -f stub_stuck ]; then
          return 0
        fi
        case "$*" in
          *--draft=false*) echo "false" > stub_draft ;;
        esac
        return 0
        ;;
    esac
  fi
  return 0
}
"""


def _bash() -> str:
    """A bash that really runs, or a failure rather than a skip.

    On Windows, `bash` on PATH is often the WSL launcher, which answers "no
    installed distributions" and exits 1 with UTF-16 noise on stdout. A skip
    here would turn the guard off on the platform the releases are cut from.
    """
    found = shutil.which("bash")
    candidates = [
        found,
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
        "/bin/bash",
        "/usr/bin/bash",
    ]
    for candidate in candidates:
        if not candidate or not Path(candidate).exists():
            continue
        probe = subprocess.run(
            [candidate, "-c", "echo ok"],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ},
        )
        if probe.returncode == 0 and "ok" in probe.stdout:
            return candidate
    pytest.fail("no usable bash: the release recovery cannot be exercised at all")


def _recovery_step() -> str:
    """The step's shell body, with GitHub's expression already evaluated.

    `${{ steps.v.outputs.tag }}` is not shell - bash reads it as a bad
    substitution - so leaving it in place would test the stub's error handling
    rather than the body. Substituting here is what the runner does before it
    hands the script to bash. The value is fixed rather than parametric
    because the body only ever uses the tag as an opaque name.
    """
    action = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for step in action["jobs"]["release"]["steps"]:
        if str(step.get("name", "")).startswith("Re-attach"):
            return step["run"].replace("${{ steps.v.outputs.tag }}", "v9.9.9")
    raise AssertionError("no `Re-attach` step in release.yml")


def _run_recovery(
    tmp_path: Path,
    *,
    exists: bool,
    draft: bool,
    publish_works: bool = True,
) -> tuple[int, str, str, list[str]]:
    """Run the real shell body of the recovery step with the stub in scope."""
    (tmp_path / "stub_exists").write_text("1" if exists else "0", encoding="utf-8")
    (tmp_path / "stub_draft").write_text("true" if draft else "false", encoding="utf-8")
    if not publish_works:
        # Publishing is attempted and the release stays a draft, which is the
        # shape of a partial repair: the API refuses and nothing else changes.
        (tmp_path / "stub_stuck").write_text("1", encoding="utf-8")

    body = _recovery_step()
    script = tmp_path / "recovery.sh"
    script.write_text(STUB + body, encoding="utf-8", newline="\n")

    done = subprocess.run(
        [_bash(), "-e", script.name],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "GITHUB_REF_NAME": "v9.9.9"},
        cwd=tmp_path,
    )
    log_file = tmp_path / "stub_log.txt"
    lines = log_file.read_text(encoding="utf-8").splitlines() if log_file.exists() else []
    return done.returncode, done.stdout, done.stderr, lines


class TestTheStubIsWhatRuns:
    def test_a_function_shadows_the_real_command(self, tmp_path: Path) -> None:
        """Without this the rest is a test of whatever `gh` PATH happens to hold."""
        script = tmp_path / "probe.sh"
        script.write_text(
            STUB + "type -t gh\n",
            encoding="utf-8",
            newline="\n",
        )
        done = subprocess.run(
            [_bash(), "-e", script.name],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ},
            cwd=tmp_path,
        )
        assert done.returncode == 0, done.stderr
        assert done.stdout.splitlines()[0] == "function", (
            f"gh resolved to something other than the stub: {done.stdout!r}"
        )


class TestADraftIsNotARecoveredRelease:
    def test_a_recovered_draft_is_published(self, tmp_path: Path) -> None:
        code, out, err, log = _run_recovery(tmp_path, exists=True, draft=True)
        assert code == 0, f"the recovery gave up on a draft: {out}{err}"
        assert any(line.startswith("EDIT") for line in log), (
            f"the release was never published, and the step exited zero: {log}"
        )
        assert (tmp_path / "stub_draft").read_text(encoding="utf-8").strip() == "false"
        assert "is published" in out, f"the run did not say what it did: {out}"

    def test_the_assets_are_attached_before_the_publish(self, tmp_path: Path) -> None:
        """Publishing an empty release is worse than leaving it a draft."""
        _code, _out, _err, log = _run_recovery(tmp_path, exists=True, draft=True)
        uploads = [i for i, line in enumerate(log) if line.startswith("UPLOAD")]
        edits = [i for i, line in enumerate(log) if line.startswith("EDIT")]
        assert uploads and edits, f"one of the two never happened: {log}"
        assert uploads[0] < edits[0], f"the release was published empty: {log}"

    def test_a_release_that_is_already_published_is_left_alone(self, tmp_path: Path) -> None:
        code, out, err, log = _run_recovery(tmp_path, exists=True, draft=False)
        assert code == 0, f"a published release was treated as a failure: {out}{err}"
        assert not any(line.startswith("EDIT") for line in log), (
            f"a published release was edited again: {log}"
        )

    def test_a_release_that_would_not_publish_fails_the_run(self, tmp_path: Path) -> None:
        """The one outcome that must never be green: still a draft."""
        code, out, err, _log = _run_recovery(
            tmp_path, exists=True, draft=True, publish_works=False
        )
        assert code == 1, f"a release left as a draft was reported as a success: {out}{err}"
        assert "still a draft" in out, f"the failure did not say what is wrong: {out}"


class TestTheMissingReleaseStaysRed:
    def test_a_release_that_does_not_exist_fails_the_run(self, tmp_path: Path) -> None:
        code, out, err, log = _run_recovery(tmp_path, exists=False, draft=False)
        assert code == 1
        assert "could not be created" in out, out + err
        assert not any(line.startswith("EDIT") for line in log), (
            f"the step tried to publish a release that does not exist: {log}"
        )


class TestTheWorkflowStillSaysWhatItMeans:
    def test_the_create_step_is_not_a_successful_recovery(self) -> None:
        """The repair may not run when the create step worked."""
        action = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        for step in action["jobs"]["release"]["steps"]:
            if str(step.get("name", "")).startswith("Re-attach"):
                assert step.get("if") == "steps.create.outcome == 'failure'", (
                    "the recovery runs even when the release was created normally"
                )
                return
        raise AssertionError("no `Re-attach` step in release.yml")
