"""Tests for the reuse decision (CV-007, build-once half)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "release.yml"
sys.path.insert(0, str(REPO / "tools"))

import release_candidate  # noqa: E402

WHEEL = "citevouch-9.9.9-py3-none-any.whl"
SDIST = "citevouch-9.9.9.tar.gz"


def _artefacts(dist: Path) -> None:
    dist.mkdir(parents=True, exist_ok=True)
    (dist / WHEEL).write_bytes(b"the wheel this run built\n")
    (dist / SDIST).write_bytes(b"the sdist this run built\n")


def _record(
    dist: Path,
    *,
    version: str = "9.9.9",
    tag: str = "v9.9.9",
    candidate: str = "b" * 40,
    source_sha: str = "b" * 40,
    release_sha: str = "c" * 40,
) -> None:
    release_candidate.write(
        dist,
        version=version,
        tag=tag,
        candidate=candidate,
        source_sha=source_sha,
        release_sha=release_sha,
    )


def _run(*argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REPO / "tools" / "release_candidate.py"), *argv],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


class TestWhatTheReleaseSaysItIsIsCheckedFirst:
    """A record lifted from another release passes `check` and is still wrong.

    `check` answers "are these files the ones this record describes". The reuse
    decision has to answer a different question - "does this release page hold
    what this run would have built" - and a page carrying a correctly-signed
    record of a *different* version answers the first question yes.
    """

    def test_a_complete_release_can_be_reused(self, tmp_path: Path) -> None:
        _artefacts(tmp_path)
        _record(tmp_path)
        assert release_candidate.reuse(tmp_path, version="9.9.9", tag="v9.9.9") == []

    def test_another_version_cannot(self, tmp_path: Path) -> None:
        _artefacts(tmp_path)
        _record(tmp_path, version="9.9.9")
        problems = release_candidate.reuse(tmp_path, version="9.9.10", tag="v9.9.9")
        assert len(problems) == 1
        assert "9.9.9" in problems[0] and "9.9.10" in problems[0]

    def test_another_tag_cannot(self, tmp_path: Path) -> None:
        _artefacts(tmp_path)
        _record(tmp_path, tag="v9.9.9")
        problems = release_candidate.reuse(tmp_path, version="9.9.9", tag="v9.9.10")
        assert len(problems) == 1
        assert "v9.9.9" in problems[0] and "v9.9.10" in problems[0]

    def test_another_tested_commit_cannot(self, tmp_path: Path) -> None:
        _artefacts(tmp_path)
        _record(tmp_path, candidate="b" * 40)
        problems = release_candidate.reuse(
            tmp_path, version="9.9.9", tag="v9.9.9", candidate="d" * 40
        )
        assert len(problems) == 1
        assert "b" * 40 in problems[0] and "d" * 40 in problems[0]

    def test_a_tag_push_has_no_candidate_to_compare(self, tmp_path: Path) -> None:
        # A tag pushed by hand has no tested commit, and the record it wrote
        # says so with the release commit. Demanding one here would make every
        # manual release un-reusable, which is the opposite of the point.
        _artefacts(tmp_path)
        _record(tmp_path, candidate="")
        assert release_candidate.reuse(tmp_path, version="9.9.9", tag="v9.9.9") == []

    def test_bytes_that_drifted_still_stop_it(self, tmp_path: Path) -> None:
        _artefacts(tmp_path)
        _record(tmp_path)
        (tmp_path / SDIST).write_bytes(b"other sdist bytes\n")
        problems = release_candidate.reuse(tmp_path, version="9.9.9", tag="v9.9.9")
        assert problems and any(SDIST in problem for problem in problems)

    def test_a_missing_record_is_not_reusable(self, tmp_path: Path) -> None:
        _artefacts(tmp_path)
        with pytest.raises(SystemExit):
            release_candidate.reuse(tmp_path, version="9.9.9", tag="v9.9.9")


class TestTheCommandSaysItToo:
    def test_reusable_prints_the_release(self, tmp_path: Path) -> None:
        _artefacts(tmp_path)
        _record(tmp_path)
        done = _run("reuse", str(tmp_path), "--version", "9.9.9", "--tag", "v9.9.9")
        assert done.returncode == 0, done.stderr
        assert "is what v9.9.9 published" in done.stdout
        assert "2 artefact(s)" in done.stdout

    def test_a_wrong_version_exits_one_with_an_error_annotation(self, tmp_path: Path) -> None:
        _artefacts(tmp_path)
        _record(tmp_path, version="9.9.9")
        done = _run("reuse", str(tmp_path), "--version", "9.9.10", "--tag", "v9.9.9")
        assert done.returncode == 1
        assert "::error::" in done.stdout


def _steps() -> list[dict]:
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return data["jobs"]["release"]["steps"]


def _named(name: str) -> dict:
    for step in _steps():
        if step.get("name") == name:
            return step
    raise AssertionError(f"no {name!r} step in release.yml")


class TestTheWorkflowUsesTheDecision:
    def test_the_reuse_step_comes_before_the_build(self) -> None:
        names = [step.get("name") for step in _steps()]
        assert names.index(
            "Reuse the published artefacts if this release already has them"
        ) < names.index("Build")

    def test_the_build_is_skipped_only_when_the_release_is_reusable(self) -> None:
        assert _named("Build")["if"] == "steps.reuse.outputs.reusable != 'true'"

    def test_the_record_is_not_rewritten_for_reused_bytes(self) -> None:
        # Rewriting it would replace a statement about the run that built these
        # bytes with a statement about a run that built nothing.
        assert _named("Record which commit produced these bytes")["if"] == (
            "steps.reuse.outputs.reusable != 'true'"
        )

    def test_the_reuse_step_asks_about_the_three_identities(self) -> None:
        body = _named("Reuse the published artefacts if this release already has them")["run"]
        assert "release_candidate.py reuse" in body
        for token in ("--version", "--tag", "--candidate"):
            assert token in body, token

    def test_a_first_release_is_not_a_failure(self) -> None:
        body = _named("Reuse the published artefacts if this release already has them")["run"]
        # `gh release download` on a tag with no release exits non-zero. That
        # is the normal first-release path, so the step must continue with
        # reusable=false rather than fail the whole release.
        assert "if ! gh release download" in body
        assert "exit 0" in body
        assert "reusable=false" in body

    def test_the_step_records_its_answer(self) -> None:
        body = _named("Reuse the published artefacts if this release already has them")["run"]
        assert 'echo "reusable=true" >> "$GITHUB_OUTPUT"' in body
        assert 'echo "reusable=false" >> "$GITHUB_OUTPUT"' in body


GH_STUB = """
gh() {
  if [ "$1" = "release" ] && [ "$2" = "download" ]; then
    state=$(cat stub_state 2>/dev/null || echo none)
    if [ "$state" = "none" ]; then
      echo "release not found" >&2
      return 1
    fi
    dir="."
    prev=""
    for arg in "$@"; do
      if [ "$prev" = "--dir" ]; then dir="$arg"; fi
      prev="$arg"
    done
    cp stub_payload/* "$dir"/ 2>/dev/null
    if [ "$state" = "other" ]; then
      printf 'a different build\n' > "$dir/citevouch-9.9.9.tar.gz"
    fi
    return 0
  fi
  return 0
}
"""


def _bash() -> str:
    """A bash that really runs, or a failure rather than a skip.

    `tests/test_release_recovery.py` records why: on Windows, `bash` on PATH is
    often the WSL launcher, and a skip would turn the guard off on a platform
    that cuts releases.
    """
    import shutil

    for candidate in [
        shutil.which("bash"),
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
    pytest.fail("no usable bash: the reuse step cannot be exercised at all")


def _reuse_body() -> str:
    """The step's shell body with GitHub's expressions already evaluated."""
    for step in _steps():
        if str(step.get("name", "")).startswith("Reuse the published"):
            return (
                step["run"]
                .replace("${{ steps.v.outputs.tag }}", "v9.9.9")
                .replace("${{ steps.v.outputs.version }}", "9.9.9")
                .replace("${{ inputs.candidate }}", "")
            )
    raise AssertionError("no reuse step in release.yml")


class TestTheStepBodyItselfDecides:
    """The YAML assertions above say what the step says; these say what it does.

    A step whose text mentions `reusable=true` is not a step that ever writes
    it. These run the real body against a `gh` stub whose download either fails
    (a first release), returns the recorded artefacts, or returns bytes that
    drifted - and they read `$GITHUB_OUTPUT`, which is what the build step
    believes.
    """

    def _run(self, tmp_path: Path, *, state: str, payload: Path | None) -> tuple[int, str]:
        (tmp_path / "tools").mkdir(parents=True)
        import shutil

        shutil.copy2(REPO / "tools" / "release_candidate.py", tmp_path / "tools")
        (tmp_path / "stub_state").write_text(state, encoding="utf-8")
        if payload is not None:
            (tmp_path / "stub_payload").mkdir()
            for item in payload.iterdir():
                shutil.copy2(item, tmp_path / "stub_payload" / item.name)
        script = tmp_path / "reuse.sh"
        script.write_text(GH_STUB + _reuse_body(), encoding="utf-8", newline="\n")
        outputs = tmp_path / "outputs.txt"
        done = subprocess.run(
            [_bash(), "-e", script.name],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "GITHUB_OUTPUT": str(outputs)},
            cwd=tmp_path,
        )
        text = outputs.read_text(encoding="utf-8") if outputs.exists() else ""
        return done.returncode, text

    def _payload(self, tmp_path: Path) -> Path:
        payload = tmp_path / "payload"
        _artefacts(payload)
        _record(payload)
        return payload

    def test_a_first_release_builds_and_does_not_fail(self, tmp_path: Path) -> None:
        code, outputs = self._run(tmp_path / "work", state="none", payload=None)
        # `gh release download` on a tag with no release exits non-zero. If that
        # failed the step, no first release could ever be cut.
        assert code == 0, code
        assert "reusable=false" in outputs

    def test_a_release_that_already_serves_these_bytes_is_reused(self, tmp_path: Path) -> None:
        payload = self._payload(tmp_path)
        code, outputs = self._run(tmp_path / "work2", state="good", payload=payload)
        assert code == 0, code
        assert "reusable=true" in outputs

    def test_bytes_that_drifted_are_rebuilt_rather_than_reused(self, tmp_path: Path) -> None:
        payload = self._payload(tmp_path)
        code, outputs = self._run(tmp_path / "work3", state="other", payload=payload)
        assert code == 0, code
        assert "reusable=false" in outputs
