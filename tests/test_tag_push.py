"""The tag push is the one step that cannot be re-run.

`Commit the version bump` pushes to main before `Tag it` runs. So a rejected
tag push leaves the version bumped and the Unreleased section empty, and a
re-run of the workflow decides there is nothing to release - the number is
stranded and nothing in the log says so. That is what happened to v0.19.6:
`! [remote rejected] v0.19.6 -> v0.19.6 (failed)`, no reason given, seconds
after the branch push to the same remote succeeded.

These tests run the step's shell body against a fake `git`, rather than
asserting that certain strings appear in the YAML. A string assertion would
stay green if the retry loop ran the wrong command, and it cannot tell whether
the recovery text survives on the path that needs it.
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
    steps = action["jobs"]["decide"]["steps"]
    for step in steps:
        if step.get("name") == "Tag it":
            return step["run"]
    raise AssertionError("no `Tag it` step in auto-release.yml")


FAKE_GIT = """#!/bin/sh
# A git that does only what the tag step asks of it, and can be told to fail.
# The counters live in files so that each invocation of this script sees what
# the previous one did - that is what makes the retry observable.
case "$1" in
  rev-parse)
    # No tag exists yet.
    exit 1
    ;;
  tag)
    echo "TAGGED $*" >> "$STUB_LOG"
    exit 0
    ;;
  push)
    n=$(cat "$STUB_COUNTER" 2>/dev/null || echo 0)
    n=$((n + 1))
    echo "$n" > "$STUB_COUNTER"
    echo "PUSH $n $*" >> "$STUB_LOG"
    if [ "$n" -ge "$STUB_SUCCEEDS_ON" ]; then
      exit 0
    fi
    echo "! [remote rejected] $4 (failed)" >&2
    exit 1
    ;;
  ls-remote)
    echo "LSREMOTE $*" >> "$STUB_LOG"
    exit "$STUB_LSREMOTE"
    ;;
esac
exit 0
"""


def _run_tag_step(
    tmp_path: Path,
    *,
    succeeds_on: int,
    lsremote: int,
) -> tuple[int, str, str, list[str]]:
    """Run the real shell body of `Tag it` with a stub git on PATH."""
    script = tmp_path / "tag_step.sh"
    script.write_text(_tag_step(), encoding="utf-8", newline="\n")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "git"
    stub.write_text(FAKE_GIT, encoding="utf-8", newline="\n")
    stub.chmod(0o755)

    counter = tmp_path / "counter"
    log = tmp_path / "log.txt"
    env = {
        **os.environ,
        "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
        "VERSION": "9.9.9",
        "STUB_SUCCEEDS_ON": str(succeeds_on),
        "STUB_LSREMOTE": str(lsremote),
        "STUB_COUNTER": str(counter),
        "STUB_LOG": str(log),
    }
    done = subprocess.run(
        [_bash(), str(script)],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=tmp_path,
    )
    lines = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return done.returncode, done.stdout, done.stderr, lines


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
        code, out, _err, _log = _run_tag_step(tmp_path, succeeds_on=99, lsremote=0)
        assert code == 0, "the remote had the tag, so the step had nothing left to do"
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
