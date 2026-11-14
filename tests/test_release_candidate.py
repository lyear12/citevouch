"""The green run and the released tree must be the same commit, or its child.

`workflow_run` reports the SHA whose Test finished green. The event carries no
promise that `main` still points there. The released v0.24.0 run showed the
shape of the hole: the job checked out `main` by name, so a merge landing while
it was queued would have gone to PyPI under a version number with no Test run of
its own behind it - the oldest failure mode in this project, a check that
answers a question about a different commit than the one being shipped.

Two things are pinned here, and they are different questions:

* the *decision* job must not proceed when `main` has moved past the tested
  SHA (tested by running the step body against a git stub);
* the *release* job must refuse a tree that is not the tested commit or its
  single version-bump child (tested against a real git repository, because the
  question is about ancestry and a stub would answer my own beliefs about it).

Neither test asserts that certain words appear in the YAML. A string assertion
would stay green if the step compared the wrong pair of SHAs.
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

FRESH_STEP = "Refuse to release a commit that main has already moved past"
TREE_STEP = "Record which commit is being released"

# `git ls-remote` is the only thing the freshness step is allowed to ask, so
# that is the whole stub. A bash function shadows the PATH lookup on every
# platform, which an executable file does not (see tests/test_tag_push.py for
# the Windows post-mortem).
GIT_STUB = """
git() {
  case "$1" in
    ls-remote)
      echo "LSREMOTE $*" >> stub_log.txt
      if [ -n "$STUB_HEAD" ]; then
        printf '%s\\trefs/heads/main\\n' "$STUB_HEAD"
      fi
      return "${STUB_REMOTE_RC:-0}"
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
    pytest.fail("no usable bash: the release candidate cannot be exercised at all")


def _step(workflow: Path, job: str, prefix: str) -> str:
    """The step's shell body, with GitHub's expressions left for the caller.

    `${{ inputs.candidate }}` is not shell - bash reads it as a bad
    substitution - so each caller substitutes before running. An unset
    expression evaluates to the empty string on the runner, which is what the
    tag-push path supplies here.
    """
    action = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    for step in action["jobs"][job]["steps"]:
        if str(step.get("name", "")).startswith(prefix):
            return step["run"]
    raise AssertionError(f"no `{prefix}` step in {workflow.name}")


def _run_fresh(tmp_path: Path, *, head: str, tested: str, remote_rc: int = 0):
    body = _step(AUTO_RELEASE, "decide", FRESH_STEP)
    script = tmp_path / "fresh.sh"
    script.write_text(GIT_STUB + body, encoding="utf-8", newline="\n")
    output = tmp_path / "github_output"
    output.write_text("", encoding="utf-8")
    summary = tmp_path / "github_summary"
    summary.write_text("", encoding="utf-8")
    done = subprocess.run(
        [_bash(), "-e", script.name],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env={
            **os.environ,
            "TESTED_SHA": tested,
            "STUB_HEAD": head,
            "STUB_REMOTE_RC": str(remote_rc),
            "GITHUB_OUTPUT": str(output),
            # The runner always sets this; a body that redirects into an empty
            # variable dies on `-e`, and that failure would be an artefact of
            # the harness rather than of the workflow.
            "GITHUB_STEP_SUMMARY": str(summary),
        },
        cwd=tmp_path,
    )
    return done, output.read_text(encoding="utf-8")


class TestTheDecisionIsAboutTheTestedCommit:
    def test_main_still_at_the_tested_sha_is_released(self, tmp_path: Path) -> None:
        done, out = _run_fresh(tmp_path, head="aaaa1111", tested="aaaa1111")
        assert done.returncode == 0, done.stderr
        assert "stale=false" in out
        assert "candidate=aaaa1111" in out, (
            f"the tested SHA was not carried forward to the release job: {out!r}"
        )

    def test_main_moved_past_the_tested_sha_releases_nothing(self, tmp_path: Path) -> None:
        """This is the whole point: a green Test for A must not publish B."""
        done, out = _run_fresh(tmp_path, head="bbbb2222", tested="aaaa1111")
        assert done.returncode == 0, (
            f"a stale candidate failed the run instead of standing down: {done.stdout}{done.stderr}"
        )
        assert "stale=true" in out
        assert "released=true" not in out, (
            f"a stale candidate still announced a release: {out!r}"
        )
        assert "candidate=" not in out, (
            f"a stale candidate still named a commit to release: {out!r}"
        )
        assert "::notice::" in done.stdout, f"the stand-down was silent: {done.stdout}"

    def test_a_remote_that_cannot_be_read_fails_rather_than_guesses(
        self, tmp_path: Path
    ) -> None:
        """Silence is not a matching SHA: an unknown main must stop the release."""
        done, out = _run_fresh(tmp_path, head="", tested="aaaa1111", remote_rc=0)
        assert done.returncode == 1, (
            f"an unreadable remote was treated as a match: {done.stdout}{out!r}"
        )
        assert "stale=false" not in out
        assert "::error::" in done.stdout

    def test_a_remote_that_errors_fails_too(self, tmp_path: Path) -> None:
        done, _out = _run_fresh(tmp_path, head="", tested="aaaa1111", remote_rc=2)
        assert done.returncode == 1


class TestAStaleCandidateCannotPlanARelease:
    """The freshness step's verdict has to bind the steps after it.

    `stale=true` writes `released` nothing at all and exits 0. If the planning
    step still ran it would print `releasing 9.9.9`, set `released=true`, and
    the publish job would fire - the stand-down would be a log line while the
    release went ahead, which is the worst version of this defect: a guard that
    reports the right thing and does not stop anything.

    GitHub evaluates `if:` before the step exists as a shell script, so this can
    only be read off the YAML. That is a weaker check than running the body, and
    it is the only one available for a step-skipping condition.
    """

    @staticmethod
    def _plan_step() -> dict:
        action = yaml.safe_load(AUTO_RELEASE.read_text(encoding="utf-8"))
        for step in action["jobs"]["decide"]["steps"]:
            if str(step.get("name", "")).startswith("Decide the next version"):
                return step
        raise AssertionError("no `Decide the next version` step in auto-release.yml")

    def test_planning_is_skipped_when_the_candidate_is_stale(self) -> None:
        condition = str(self._plan_step().get("if", ""))
        assert "stale" in condition, (
            f"the planning step runs unconditionally (if: {condition!r}), so a "
            "stale candidate would set released=true straight after the "
            "freshness step decided to stand down"
        )
        # `if: always()` or `if: success()` would both run after a stand-down.
        assert "always()" not in condition
        assert "success()" not in condition

    def test_the_freshness_step_actually_produces_that_output(self) -> None:
        action = yaml.safe_load(AUTO_RELEASE.read_text(encoding="utf-8"))
        steps = action["jobs"]["decide"]["steps"]
        fresh = next(s for s in steps if str(s.get("name", "")).startswith(FRESH_STEP))
        assert fresh.get("id") == "fresh", (
            f"the freshness step's id is {fresh.get('id')!r}, so `steps.fresh` "
            "names nothing and the condition below it is always false"
        )
        assert "stale=" in fresh["run"]

    def test_a_stale_candidate_does_not_reach_the_publish_job(self) -> None:
        action = yaml.safe_load(AUTO_RELEASE.read_text(encoding="utf-8"))
        job = action["jobs"]["release"]
        assert job.get("if"), "the publish job has no condition at all"
        assert "released" in str(job["if"]), (
            f"the publish job runs on {job['if']!r}, which does not depend on the decision"
        )


class TestTheCheckoutIsNotWhateverMainSaysNow:
    def test_the_ref_is_the_run_sha_and_not_the_branch(self) -> None:
        """A one-line reviewer's question: which commit does this job build?

        `ref: main` is the defect, and it is invisible unless you read the key.
        This asserts the expression names the run's SHA; the shell tests above
        prove what happens when that SHA and main disagree.
        """
        action = yaml.safe_load(AUTO_RELEASE.read_text(encoding="utf-8"))
        checkout = action["jobs"]["decide"]["steps"][0]
        ref = str(checkout.get("with", {}).get("ref", ""))
        assert "workflow_run.head_sha" in ref, (
            f"the decide job checks out {ref!r}, which is not the tested commit"
        )
        assert ref.strip() != "main"


class TestTheReleasedTreeDescendsFromTheTestedOne:
    """Real repositories, because ancestry is not a thing a stub can answer."""

    @staticmethod
    def _repo(path: Path) -> None:
        def run(*args: str) -> str:
            done = subprocess.run(
                ["git", *args],
                cwd=path,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                env={
                    **os.environ,
                    "GIT_AUTHOR_NAME": "t",
                    "GIT_AUTHOR_EMAIL": "t@example.invalid",
                    "GIT_COMMITTER_NAME": "t",
                    "GIT_COMMITTER_EMAIL": "t@example.invalid",
                    "GIT_CONFIG_GLOBAL": str(path / ".gitconfig"),
                    "GIT_CONFIG_SYSTEM": str(path / ".gitconfig"),
                },
            )
            assert done.returncode == 0, f"git {' '.join(args)}: {done.stderr}"
            return done.stdout.strip()

        path.mkdir(parents=True, exist_ok=True)
        run("init", "-q", "-b", "main")
        run("commit", "-q", "--allow-empty", "-m", "first")

    @staticmethod
    def _commit(path: Path, message: str) -> str:
        done = subprocess.run(
            ["git", "commit", "-q", "--allow-empty", "-m", message],
            cwd=path,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            env={
                **os.environ,
                "GIT_AUTHOR_NAME": "t",
                "GIT_AUTHOR_EMAIL": "t@example.invalid",
                "GIT_COMMITTER_NAME": "t",
                "GIT_COMMITTER_EMAIL": "t@example.invalid",
                "GIT_CONFIG_GLOBAL": str(path / ".gitconfig"),
                "GIT_CONFIG_SYSTEM": str(path / ".gitconfig"),
            },
        )
        assert done.returncode == 0, done.stderr
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=path, capture_output=True, text=True
        )
        return head.stdout.strip()

    def _run_tree(self, repo: Path, candidate: str):
        body = _step(RELEASE, "release", TREE_STEP).replace(
            "${{ inputs.candidate }}", candidate
        )
        script = repo / "tree.sh"
        script.write_text(body, encoding="utf-8", newline="\n")
        output = repo / "github_output"
        output.write_text("", encoding="utf-8")
        done = subprocess.run(
            [_bash(), "-e", script.name],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "GITHUB_OUTPUT": str(output)},
            cwd=repo,
        )
        return done, output.read_text(encoding="utf-8")

    def test_the_bump_commit_after_the_tested_one_is_allowed(self, tmp_path: Path) -> None:
        """The normal path: Test goes green, the bump commit lands, then the tag."""
        repo = tmp_path / "r"
        self._repo(repo)
        tested = self._commit(repo, "the change")
        self._commit(repo, "Release 9.9.9")
        done, out = self._run_tree(repo, tested)
        assert done.returncode == 0, f"{done.stdout}{done.stderr}"
        assert f"source_sha={tested}" in out
        assert "release_sha=" in out

    def test_a_second_commit_after_the_test_is_refused(self, tmp_path: Path) -> None:
        """The race: something else landed between the green run and the tag."""
        repo = tmp_path / "r"
        self._repo(repo)
        tested = self._commit(repo, "the change")
        self._commit(repo, "Release 9.9.9")
        self._commit(repo, "an untested merge")
        done, _out = self._run_tree(repo, tested)
        assert done.returncode == 1, (
            f"a tree with an untested commit in it was released: {done.stdout}"
        )
        assert "never saw" in done.stdout + done.stderr or "::error::" in done.stdout

    def test_a_tested_sha_that_is_not_an_ancestor_is_refused(self, tmp_path: Path) -> None:
        """A green Test on a branch that was never merged proves nothing here."""
        repo = tmp_path / "r"
        self._repo(repo)
        base = self._commit(repo, "base")
        # A commit on a side branch, not on main.
        side = subprocess.run(
            ["git", "checkout", "-q", "-b", "side"],
            cwd=repo,
            capture_output=True,
            text=True,
        )
        assert side.returncode == 0, side.stderr
        unrelated = self._commit(repo, "only on the side branch")
        subprocess.run(
            ["git", "checkout", "-q", "main"], cwd=repo, capture_output=True, text=True
        )
        subprocess.run(
            ["git", "reset", "-q", "--hard", base], cwd=repo, capture_output=True, text=True
        )
        done, _out = self._run_tree(repo, unrelated)
        assert done.returncode == 1, (
            f"a tested SHA that is not an ancestor was accepted: {done.stdout}"
        )

    def test_no_candidate_supplied_is_not_a_failure(self, tmp_path: Path) -> None:
        """A tag push has no candidate, and must keep working."""
        repo = tmp_path / "r"
        self._repo(repo)
        done, _out = self._run_tree(repo, "")
        assert done.returncode == 0, f"{done.stdout}{done.stderr}"


class TestTheCallerPassesTheCandidate:
    def test_auto_release_hands_the_release_job_its_candidate(self) -> None:
        action = yaml.safe_load(AUTO_RELEASE.read_text(encoding="utf-8"))
        job = action["jobs"]["release"]
        passed = job.get("with", {}).get("candidate", "")
        assert "candidate" in str(job.get("with", {})), (
            "the release job is called without a candidate, so the tree guard "
            "would silently take the tag-push path on every automatic release"
        )
        assert str(passed).strip() != "" and "candidate" in str(passed)

    def test_release_declares_the_candidate_input(self) -> None:
        action = yaml.safe_load(RELEASE.read_text(encoding="utf-8"))
        inputs = action[True]["workflow_call"]["inputs"]
        assert "candidate" in inputs
        assert inputs["candidate"].get("required") is False, (
            "a required candidate would break tag pushes and manual dispatch"
        )
