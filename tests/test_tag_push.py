"""The tag push is the one step that cannot be re-run.

`Commit the version bump` pushes to main before `Tag it` runs. So a rejected
tag push leaves the version bumped and the Unreleased section empty, and a
re-run of the workflow decides there is nothing to release - the number is
stranded and nothing in the log says so. That is what happened to v0.19.6:
`! [remote rejected] v0.19.6 -> v0.19.6 (failed)`, no reason given, seconds
after the branch push to the same remote succeeded.

These tests run the step's shell body against a stub, rather than asserting
that certain strings appear in the YAML. A string assertion would stay green if
the retry loop ran the wrong command, and it cannot tell whether the recovery
text survives on the path that needs it.

The stub is a bash **function** named `git`, not a file on PATH. The first
version of this file put an executable in a directory prepended to PATH, which
works on the POSIX runners and silently did not on Windows: `chmod` there does
not produce a file MSYS will execute, so the real `git` ran instead, in a
temporary directory that is not a repository - `fatal: not a git repository`
three times. Every assertion was about the right thing, which is the only
reason it was noticed. A function shadows the PATH lookup on every platform and
needs neither an exec bit nor a shebang.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "auto-release.yml"

# The stub, and the two files it keeps state in. Relative names, because an
# absolute Windows path reaching bash arrives with backslashes that MSYS does
# not read as separators - the first version lost its counters that way.
STUB = """
sleep() {
  # The pauses are real in CI; one minute per test is not.
  :
}

git() {
  case "$1" in
    rev-parse)
      return 1
      ;;
    tag)
      echo "TAGGED $*" >> stub_log.txt
      return 0
      ;;
    push)
      n=$(cat stub_counter 2>/dev/null || echo 0)
      n=$((n + 1))
      echo "$n" > stub_counter
      echo "PUSH $n $*" >> stub_log.txt
      if [ "$n" -ge "$STUB_SUCCEEDS_ON" ]; then
        return 0
      fi
      echo "! [remote rejected] $3 (failed)" >&2
      return 1
      ;;
    ls-remote)
      echo "LSREMOTE $*" >> stub_log.txt
      return "$STUB_LSREMOTE"
      ;;
  esac
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
    pytest.fail("no usable bash: the tag push cannot be exercised at all")


def _tag_step() -> str:
    action = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for step in action["jobs"]["decide"]["steps"]:
        if step.get("name") == "Tag it":
            return step["run"]
    raise AssertionError("no `Tag it` step in auto-release.yml")


def _run_tag_step(
    tmp_path: Path,
    *,
    succeeds_on: int,
    lsremote: int,
) -> tuple[int, str, str, list[str]]:
    """Run the real shell body of `Tag it` with the stub in scope."""
    script = tmp_path / "tag_step.sh"
    script.write_text(STUB + _tag_step(), encoding="utf-8", newline="\n")

    env = {
        **os.environ,
        "VERSION": "9.9.9",
        "STUB_SUCCEEDS_ON": str(succeeds_on),
        "STUB_LSREMOTE": str(lsremote),
    }
    # `-e` because that is what GitHub's `shell: bash` uses; a body that only
    # works without it would pass here and fail there.
    done = subprocess.run(
        [_bash(), "-e", script.name],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=tmp_path,
    )
    log_file = tmp_path / "stub_log.txt"
    lines = log_file.read_text(encoding="utf-8").splitlines() if log_file.exists() else []
    return done.returncode, done.stdout, done.stderr, lines


class TestTheStubIsWhatRuns:
    def test_a_function_shadows_the_real_command(self, tmp_path: Path) -> None:
        """Without this the rest is a test of whatever `git` PATH happens to hold."""
        script = tmp_path / "probe.sh"
        script.write_text(
            STUB + "type -t git\ngit push origin v0\n",
            encoding="utf-8",
            newline="\n",
        )
        done = subprocess.run(
            [_bash(), "-e", script.name],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "STUB_SUCCEEDS_ON": "1", "STUB_LSREMOTE": "0"},
            cwd=tmp_path,
        )
        assert done.returncode == 0, done.stderr
        assert done.stdout.splitlines()[0] == "function", (
            f"git resolved to something other than the stub: {done.stdout!r}"
        )
        assert (tmp_path / "stub_log.txt").exists(), "the stub recorded nothing"


class TestItRetriesBeforeGivingUp:
    def test_a_first_push_that_is_rejected_is_retried_and_succeeds(
        self, tmp_path: Path
    ) -> None:
        code, out, err, log = _run_tag_step(tmp_path, succeeds_on=2, lsremote=0)
        assert code == 0, f"the step gave up after one rejection: {out}{err}"
        pushes = [line for line in log if line.startswith("PUSH")]
        assert len(pushes) == 2, f"expected exactly two attempts, got {log}"
        # GitHub reads `::warning::` off stdout, so that is where the
        # annotation has to be; a silent retry would hide the flakiness.
        assert "attempt 1 of 3" in out, f"the retry was silent: {out}{err}"

    def test_it_stops_after_three_attempts(self, tmp_path: Path) -> None:
        code, _out, _err, log = _run_tag_step(tmp_path, succeeds_on=99, lsremote=1)
        assert code == 1
        pushes = [line for line in log if line.startswith("PUSH")]
        assert len(pushes) == 3, f"expected three attempts and no more, got {log}"

    def test_the_tag_is_created_once_before_the_pushes(self, tmp_path: Path) -> None:
        _code, _out, _err, log = _run_tag_step(tmp_path, succeeds_on=1, lsremote=0)
        assert log[0].startswith("TAGGED"), f"the tag was created after the push: {log}"
        first_push = next(line for line in log if line.startswith("PUSH"))
        assert log.count(first_push) == 1, f"the same tag was pushed twice: {log}"


class TestAClaimedFailureIsCheckedAgainstTheRemote:
    def test_a_tag_that_is_on_the_remote_ends_the_step_successfully(
        self, tmp_path: Path
    ) -> None:
        """A push can be accepted and still report a failure to the client."""
        code, out, _err, log = _run_tag_step(tmp_path, succeeds_on=99, lsremote=0)
        assert code == 0, f"the remote had the tag, so there was nothing left to do: {log}"
        assert "on the remote" in out


class TestTheRecoveryIsWrittenDown:
    def test_the_failure_says_why_a_rerun_will_not_help(self, tmp_path: Path) -> None:
        code, out, err, _log = _run_tag_step(tmp_path, succeeds_on=99, lsremote=1)
        assert code == 1
        assert "nothing to release" in out, (
            "a reader of this failure will re-run the workflow, which cannot work: "
            f"the message has to say so. Got: {out}{err}"
        )

    def test_the_failure_names_a_command_that_would_work(self, tmp_path: Path) -> None:
        _code, out, err, _log = _run_tag_step(tmp_path, succeeds_on=99, lsremote=1)
        # The command has to be runnable as printed, so it must name the real
        # remote-tracking ref rather than the local branch that may be behind.
        assert "git push origin v9.9.9" in out, out + err
        assert "git tag -a v9.9.9" in out, out + err


class TestTheStepStaysWhereTheReasonIs:
    def test_the_step_that_pushes_the_tag_is_the_step_after_the_bump(self) -> None:
        action = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        names = [s.get("name") for s in action["jobs"]["decide"]["steps"]]
        bump = names.index("Commit the version bump")
        tag = names.index("Tag it")
        assert bump < tag, (
            "the comment explains a failure mode of the order these two run in; "
            "if the order changes the explanation is about nothing"
        )
