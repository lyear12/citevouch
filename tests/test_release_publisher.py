"""One publisher, and a tag is compared by where it points, not by its name.

Two different questions, both about the same word — "the tag exists":

* **Publishing is exclusive.** Three doors lead to `release.yml` (tag push, hand
  dispatch, and `workflow_call` from auto-release). Two runs that both believe
  they own the same version race on one tag, one draft release and one PyPI
  upload. `release.yml` now carries a `publisher` concurrency group for all
  three.

* **A tag's name is not its identity.** The recovery path in `auto-release.yml`
  used to accept `git ls-remote --tags` succeeding as proof that its own push
  landed. Measured against a real bare remote whose `v9.9.9` pointed at a
  different commit: all three push attempts were rejected, `ls-remote` exited 0,
  the step reported `::notice::v9.9.9 is on the remote even though no attempt
  exited zero` and exited **0** — while the version bump this run had just
  pushed to `main` was left with nothing pointing at it. A stranded number is
  exactly what the retry loop exists to prevent, so the same check now peels the
  remote tag (`refs/tags/$tag^{commit}`, which answers for annotated and
  lightweight tags alike) and compares it to this run's commit.

The tag cases run the step body against a real git repository rather than a
stub: the question is about what git says, and a stub would only replay my own
beliefs about that.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
AUTO_RELEASE = REPO / ".github" / "workflows" / "auto-release.yml"
RELEASE = REPO / ".github" / "workflows" / "release.yml"

TAG_STEP = "Tag it"


def _bash() -> str:
    """A bash that really runs, or a failure rather than a skip."""
    found = shutil.which("bash")
    for candidate in [
        found,
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
        "/bin/bash",
        "/usr/bin/bash",
    ]:
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
    pytest.fail("no usable bash: the tag step cannot be exercised at all")


def _step_body(workflow: Path, job: str, name: str) -> str:
    data = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    for step in data["jobs"][job]["steps"]:
        if step.get("name") == name:
            body = step["run"]
            assert isinstance(body, str)
            return body
    raise AssertionError(f"no `{name}` step in {workflow.name}")


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    done = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and done.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed in {cwd}:\n{done.stdout}{done.stderr}"
        )
    return done


class _Repo:
    """A bare origin plus a clone whose HEAD is a version-bump commit."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.origin = root / "origin.git"
        self.work = root / "work"
        _git(root, "init", "-q", "--bare", "--initial-branch=main", str(self.origin))
        _git(root, "init", "-q", "--initial-branch=main", str(self.work))
        for key, value in [
            ("user.email", "release@example.invalid"),
            ("user.name", "citevouch release"),
            ("commit.gpgsign", "false"),
            ("tag.gpgsign", "false"),
        ]:
            _git(self.work, "config", key, value)
        self._write("one\n")
        _git(self.work, "add", "f.txt")
        _git(self.work, "commit", "-qm", "the commit a green Test ran against")
        _git(self.work, "remote", "add", "origin", str(self.origin))
        _git(self.work, "push", "-q", "origin", "HEAD:main")
        self.tested = self._rev("HEAD")

        # The bump commit auto-release makes after the green run.
        self._write("two\n")
        _git(self.work, "commit", "-qam", "Release 9.9.9")
        self.release = self._rev("HEAD")

    def _write(self, text: str) -> None:
        (self.work / "f.txt").write_text(text, encoding="utf-8", newline="\n")

    def _rev(self, rev: str) -> str:
        return _git(self.work, "rev-parse", rev).stdout.strip()

    def tag_here(self, name: str = "v9.9.9") -> None:
        _git(self.work, "tag", "-a", name, "-m", "this release")
        _git(self.work, "push", "-q", "origin", name)

    def tag_elsewhere(self, name: str = "v9.9.9") -> None:
        """A concurrent run already published this number, at the tested commit."""
        _git(self.work, "push", "-q", "origin", f"{self.tested}:refs/tags/{name}")

    def run_step(self) -> subprocess.CompletedProcess[str]:
        body = _step_body(AUTO_RELEASE, "decide", TAG_STEP)
        assert "$${{" not in body
        script = self.work / "tagit.sh"
        # `sleep` is stubbed because the retry loop waits 10 + 20 + 30 seconds
        # between attempts, and a test that takes a minute to prove a refusal is
        # a test somebody deletes.
        script.write_text(
            "set -eu\nsleep() { :; }\n" + body,
            encoding="utf-8",
            newline="\n",
        )
        output = self.root / "github_output"
        output.write_text("", encoding="utf-8")
        summary = self.root / "github_summary"
        summary.write_text("", encoding="utf-8")
        return subprocess.run(
            [_bash(), script.name],
            cwd=self.work,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            env={
                **os.environ,
                "VERSION": "9.9.9",
                "GITHUB_OUTPUT": str(output),
                "GITHUB_STEP_SUMMARY": str(summary),
            },
        )

    def remote_tag_commit(self, name: str = "v9.9.9") -> str:
        return _git(self.origin, "rev-parse", f"refs/tags/{name}^{{commit}}").stdout.strip()

    def local_tag_commit(self, name: str = "v9.9.9") -> str:
        return self._rev(f"refs/tags/{name}^{{commit}}")


class TestTheTagIsComparedByItsTarget:
    def test_a_fresh_tag_is_pushed(self, tmp_path: Path) -> None:
        repo = _Repo(tmp_path)
        done = repo.run_step()
        assert done.returncode == 0, done.stdout + done.stderr
        assert repo.remote_tag_commit() == repo.release

    def test_a_local_tag_at_this_commit_is_a_rerun_not_a_failure(self, tmp_path: Path) -> None:
        """Re-running a release that got as far as the tag is the repair path."""
        repo = _Repo(tmp_path)
        repo.tag_here()
        done = repo.run_step()
        assert done.returncode == 0, done.stdout + done.stderr
        assert repo.remote_tag_commit() == repo.release

    def test_a_local_tag_at_another_commit_refuses(self, tmp_path: Path) -> None:
        repo = _Repo(tmp_path)
        repo.tag_elsewhere()
        _git(repo.work, "fetch", "-q", "--tags", "origin")
        done = repo.run_step()
        assert done.returncode == 1, (
            f"a tag standing at another commit was accepted: {done.stdout}"
        )
        assert "::error::" in done.stdout
        assert repo.remote_tag_commit() == repo.tested, "the tag was moved"

    def test_the_recovery_path_compares_the_remote_target(self, tmp_path: Path) -> None:
        """The measured defect: the name was on the remote, this run's commit was not.

        Every push attempt is rejected because the remote already carries
        `v9.9.9` — at a *different* commit. Accepting the name would strand the
        bump commit this run pushed to `main`, with nothing pointing at it.
        """
        repo = _Repo(tmp_path)
        repo.tag_elsewhere()
        done = repo.run_step()
        assert done.returncode == 1, (
            "the step accepted a remote tag that points somewhere else, leaving "
            f"its own bump commit unmentioned:\n{done.stdout}"
        )
        assert "::error::" in done.stdout, f"the refusal was silent: {done.stdout}"
        assert repo.remote_tag_commit() == repo.tested, "the other run's tag was moved"

    def test_the_recovery_path_accepts_a_remote_tag_at_this_commit(
        self, tmp_path: Path
    ) -> None:
        """A push can be accepted and still report failure; then the remote agrees.

        Same commit, so the run did its job: the tag exists, it points at this
        release's tree, and re-attempting is pointless.
        """
        repo = _Repo(tmp_path)
        _git(repo.work, "push", "-q", "origin", f"{repo.release}:refs/tags/v9.9.9")
        done = repo.run_step()
        assert done.returncode == 0, (
            "a remote tag at this very commit was treated as somebody else's:\n"
            f"{done.stdout}{done.stderr}"
        )
        assert repo.remote_tag_commit() == repo.release

    def test_an_unreachable_remote_does_not_pass(self, tmp_path: Path) -> None:
        """A remote that cannot be read says nothing about the tag."""
        repo = _Repo(tmp_path)
        # Repoint rather than delete: a bare repository keeps read-only object
        # files on Windows, and cleaning it up here would fail for a reason
        # that has nothing to do with the step.
        _git(repo.work, "remote", "set-url", "origin", str(tmp_path / "gone.git"))
        done = repo.run_step()
        assert done.returncode == 1, f"a vanished remote was reported as success: {done.stdout}"

    def test_a_lightweight_tag_is_peeled_too(self, tmp_path: Path) -> None:
        """`refs/tags/x` is a tag object for annotated and a commit for lightweight."""
        repo = _Repo(tmp_path)
        _git(repo.work, "tag", "v9.9.9", repo.release)  # no -a: a commit ref
        assert repo.local_tag_commit() == repo.release
        done = repo.run_step()
        assert done.returncode == 0, done.stdout + done.stderr


class TestOnePublisherAtATime:
    def test_release_carries_a_concurrency_group(self) -> None:
        data = yaml.safe_load(RELEASE.read_text(encoding="utf-8"))
        concurrency = data.get("concurrency")
        assert concurrency, (
            "release.yml has no concurrency group, so two runs can publish at once"
        )
        assert concurrency.get("group"), f"the group name is empty: {concurrency!r}"
        assert concurrency.get("cancel-in-progress") is False, (
            "a cancelled publisher can stop after the tag and before the release"
        )

    def test_the_publisher_group_is_not_the_caller_group(self) -> None:
        """Sharing one name would deadlock the usual path.

        auto-release holds its group for the whole run, and the release job is a
        reusable workflow it calls. If the called workflow waited on the same
        group, the run that frees it would be the run blocked on it, and no
        release would ever finish. The exclusion has to be on a second name.
        """
        release = yaml.safe_load(RELEASE.read_text(encoding="utf-8"))
        auto = yaml.safe_load(AUTO_RELEASE.read_text(encoding="utf-8"))
        publisher = release["concurrency"]["group"]
        decider = (auto.get("concurrency") or {}).get("group")
        assert decider, "auto-release.yml lost its own concurrency group"
        assert publisher != decider, (
            f"both workflows wait on {publisher!r}; the caller would block its own callee"
        )

    def test_every_door_into_the_workflow_is_covered(self) -> None:
        """Concurrency is workflow-level, so it has to be there, not per job."""
        data = yaml.safe_load(RELEASE.read_text(encoding="utf-8"))
        assert "concurrency" in data, "concurrency belongs at the workflow level"
        for job in data["jobs"].values():
            assert "concurrency" not in job, (
                "a job-level group would leave the other jobs unguarded"
            )

    def test_the_workflow_is_still_reusable(self) -> None:
        """`workflow_call` must survive: the usual door is a reusable call."""
        data = yaml.safe_load(RELEASE.read_text(encoding="utf-8"))
        # PyYAML reads the bare key `on` as the boolean True (YAML 1.1), so the
        # trigger block is under either name depending on the reader.
        triggers = data.get("on", data.get(True))
        assert triggers, f"no trigger block found: {sorted(map(str, data))}"
        assert "workflow_call" in triggers, (
            "auto-release.yml calls this workflow, so workflow_call has to exist"
        )
