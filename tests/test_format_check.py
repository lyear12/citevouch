"""The file count the lint job quotes, measured over the tracked files.

`ruff format --check .` walks the working tree, so the number it prints depends
on which machine ran it - a scratch test being written locally makes it 58 where
CI's checkout makes it 57. Three releases in a row quoted a file count that held
only on the machine that wrote it, and each time the gate caught it after the
fact, because the gate measures the claim.

`tools/format_check.sh` measures `git ls-files` instead. Same set on every
clone, so the number in a commit message is one a reader can reproduce. These
tests are about that difference, not about ruff.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "format_check.sh"
EXTS = ("*.py", "*.md", "*.toml")


def _bash() -> str:
    """A bash that runs.  On Windows, `bash` on PATH is the WSL stub."""
    candidates = [
        shutil.which("bash"),
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
        "/bin/bash",
        "/usr/bin/bash",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        probe = subprocess.run(
            [candidate, "-c", "echo ok"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if probe.returncode == 0 and "ok" in probe.stdout:
            return candidate
    pytest.fail("no working bash: these tests cannot be skipped here")


def _run(repo: Path) -> subprocess.CompletedProcess:
    script = SCRIPT.as_posix()
    return subprocess.run(
        [_bash(), "-c", f"cd '{repo.as_posix()}' && sh '{script}'"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _reported(*texts: str) -> str:
    for text in texts:
        for line in text.splitlines():
            if "files already formatted" in line:
                return line.strip()
    return ""


def _tracked(repo: Path) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "--", *EXTS], cwd=repo, capture_output=True, text=True
    ).stdout
    return [line for line in out.split("\n") if line]


def test_the_script_exists_and_is_tracked() -> None:
    """A script the checkout does not carry is a script CI cannot run."""
    assert SCRIPT.is_file()
    out = subprocess.run(
        ["git", "ls-files", "--", "tools/format_check.sh"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert out == "tools/format_check.sh"


def test_it_reports_the_number_of_tracked_files_ruff_accepts() -> None:
    result = _run(ROOT)
    assert result.returncode == 0, result.stderr
    reported = _reported(result.stdout, result.stderr)
    assert reported, (result.stdout, result.stderr)
    # pyproject.toml and demo/sources.toml are handed to ruff but are not
    # Python or Markdown, so ruff declines them and they never reach the count.
    declined = 2
    assert int(reported.split()[0]) == len(_tracked(ROOT)) - declined


def test_an_untracked_file_does_not_change_the_count(tmp_path: Path) -> None:
    """This is the whole point: the local number and CI's number must agree.

    A drafted test nobody has added yet is invisible to `git ls-files` and must
    stay invisible to the count, or the commit message will be wrong on the
    machine that did not have the draft.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]
    (repo / "kept.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "kept.md").write_text("# kept\n", encoding="utf-8")
    subprocess.run([*git, "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run([*git, "add", "."], cwd=repo, check=True)
    subprocess.run([*git, "commit", "-q", "-m", "two files"], cwd=repo, check=True)

    before = _run(repo)
    assert before.returncode == 0, before.stderr
    assert _reported(before.stdout, before.stderr).split()[0] == "2"

    (repo / "draft_uncommitted.py").write_text("y = 2\n", encoding="utf-8")
    after = _run(repo)
    assert after.returncode == 0, after.stderr
    assert _reported(after.stdout, after.stderr).split()[0] == "2"


def test_a_checkout_with_nothing_in_it_is_not_a_clean_checkout(tmp_path: Path) -> None:
    """No files is not "0 files already formatted".

    Reading a clean result out of an empty tree is the same mistake as reading
    zero passing tests out of a suppressed summary line: silence treated as a
    measurement. Two reports in this repository's history came from exactly
    that, so the script has to say it did not run.
    """
    repo = tmp_path / "empty"
    repo.mkdir()
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.com",
            "init",
            "-q",
            "-b",
            "main",
        ],
        cwd=repo,
        check=True,
    )
    result = _run(repo)
    assert result.returncode == 2
    assert "no tracked files" in result.stderr
    assert "files already formatted" not in result.stdout


def test_a_misformatted_tracked_file_fails_with_ones_not_xargs_123(tmp_path: Path) -> None:
    """`xargs` reports a child's exit 1 as 123.

    The gate only reads "zero or not", but the person debugging a red build
    reads the number, and 123 names a tool rather than a problem. The script
    maps it back so the exit code still means "ruff found something".
    """
    repo = tmp_path / "bad"
    repo.mkdir()
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]
    (repo / "bad.py").write_text("x = [1,2,3]" + chr(10), encoding="utf-8")
    subprocess.run([*git, "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run([*git, "add", "."], cwd=repo, check=True)
    subprocess.run([*git, "commit", "-q", "-m", "one file"], cwd=repo, check=True)

    result = _run(repo)
    assert result.returncode == 1, (result.returncode, result.stdout, result.stderr)
