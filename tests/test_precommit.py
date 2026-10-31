"""The hook file is the only interface pre-commit ever sees.

pre-commit finds `.pre-commit-hooks.yaml` at the repository root and runs
`entry` with the files its `files` pattern matched, unless `pass_filenames` is
false. Nothing in this repository executes it, so - like `action.yml` - it is
checked by reading it the way pre-commit would and by running the command it
names against a project that should fail.

The hook that records evidence is deliberately a separate id. A hook that
re-records on every commit would turn "the PDF changed under me" into "the
ledger now agrees", which is the single failure this tool exists to catch.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / ".pre-commit-hooks.yaml"


def _env(**overrides: str) -> dict[str, str]:
    """The environment for a child interpreter, built on top of this one.

    Handing `subprocess` a dict that is not `os.environ` replaces the whole
    environment rather than extending it.  On Windows that takes `SYSTEMROOT`
    away, and CPython dies before it can print a test result:

        Fatal Python error: _Py_HashRandomization_Init: failed to get random
        numbers to initialize Python

    which surfaces as `assert 1 == 0` on whichever test spawned it.  The same
    defect was fixed once in `tests/test_critic_round2.py` and reintroduced
    here, so the shape lives in one place now.
    """
    env = dict(os.environ)
    env.update(overrides)
    return env


def hooks() -> list[dict]:
    return yaml.safe_load(HOOKS.read_text(encoding="utf-8"))


def by_id() -> dict[str, dict]:
    return {hook["id"]: hook for hook in hooks()}


class TestTheFilePreCommitReads:
    def test_it_is_a_list_of_hooks(self) -> None:
        assert isinstance(hooks(), list) and hooks()

    def test_every_hook_has_the_keys_pre_commit_requires(self) -> None:
        for hook in hooks():
            for key in ("id", "name", "entry", "language", "files"):
                assert key in hook, f"{hook.get('id')} has no {key}"

    def test_the_ids_are_unique(self) -> None:
        ids = [hook["id"] for hook in hooks()]
        assert len(ids) == len(set(ids))

    def test_it_installs_itself_the_way_pre_commit_can(self) -> None:
        # `language: python` builds an environment from the repository's own
        # pyproject.toml, which is what makes `entry: citevouch ...` resolve.
        for hook in hooks():
            assert hook["language"] == "python"
            assert hook["entry"].startswith("citevouch ")

    def test_a_hook_does_not_receive_filenames(self) -> None:
        # The command takes exactly one manuscript. `files:` matches every
        # Markdown file in the repository, so handing pre-commit's list
        # over would pass several and `check` would exit 2 on the extras.
        for hook in hooks():
            assert hook.get("pass_filenames") is False, hook["id"]

    def test_the_manuscript_is_named_somewhere(self) -> None:
        """Filenames off means the hook has to supply the path itself.

        This is the half the old file was missing: it said
        `pass_filenames: false` and nothing else, so pre-commit ran a bare
        `citevouch check`, which exits 2 on the missing argument. A hook
        whose command cannot run has no opinion about the manuscript.
        """
        for hook in hooks():
            args = hook.get("args") or []
            assert any(not arg.startswith("-") for arg in args), hook["id"]


class TestWhatItMatches:
    @pytest.mark.parametrize("name", ["manuscript.md", "paper.markdown", "paper.tex"])
    def test_a_manuscript_is_matched(self, name: str) -> None:
        import re

        assert any(re.search(hook["files"], name) for hook in hooks()), name

    def test_a_python_file_is_not_matched(self) -> None:
        import re

        assert not any(re.search(hook["files"], "src/citevouch/cli.py") for hook in hooks())


class TestTheTwoHooksAreDifferent:
    def test_one_checks_and_one_records(self) -> None:
        entries = {hook["entry"] for hook in hooks()}
        assert "citevouch check" in entries
        assert "citevouch scan" in entries

    def test_the_recording_hook_says_it_mutates(self) -> None:
        recording = by_id()["citevouch-record"]
        text = (recording.get("description") or "").lower()
        assert "scan" in recording["entry"]
        assert "writes" in text or "mutat" in text, (
            "a hook that rewrites the ledger has to say so where people look"
        )


class TestTheHookCommandActuallyRuns:
    """Run the entry exactly as pre-commit would, from the project root."""

    def _bash(self) -> str:
        found = shutil.which("bash")
        candidates = [Path(r"C:\Program Files\Git\bin\bash.exe")]
        if found:
            candidates.insert(0, Path(found))
        for candidate in candidates:
            if not candidate.is_file():
                continue
            probe = subprocess.run(
                [str(candidate), "-c", "echo ok"], capture_output=True, text=True, timeout=60
            )
            if probe.returncode == 0 and probe.stdout.strip() == "ok":
                return str(candidate)
        pytest.fail("no working bash on this machine")

    def _project(self, tmp_path: Path) -> Path:
        root = tmp_path / "p"
        (root / "papers").mkdir(parents=True)
        (root / "papers" / "a.txt").write_text(
            "The corpus contains 154,391 utterances in total.\n", encoding="utf-8", newline="\n"
        )
        (root / "sources.toml").write_text(
            '[sources]\na = "papers/a.txt"\n', encoding="utf-8", newline="\n"
        )
        (root / "manuscript.md").write_text(
            textwrap.dedent(
                """\
                ```claim id=c1 source=a page=1
                quote: |
                  The corpus contains 154,391 utterances in total.
                claim: |
                  The corpus is large.
                ```
                """
            ),
            encoding="utf-8",
            newline="\n",
        )
        return root

    def _bin(self, tmp_path: Path) -> Path:
        """A `citevouch` on PATH, which is what `language: python` provides.

        pre-commit builds an environment from `pyproject.toml` and puts its
        console script on PATH, so `entry: citevouch check` resolves to the
        installed command. This machine runs the source tree instead of an
        installed copy, so the wrapper stands in for the entry point only -
        everything after the command name is exactly what the hook passes.
        """
        folder = tmp_path / "bin"
        folder.mkdir()
        wrapper = folder / "citevouch"
        wrapper.write_text(
            '#!/bin/sh\nexec "${PYTHON:-python}" -m citevouch "$@"\n',
            encoding="utf-8",
            newline="\n",
        )
        wrapper.chmod(0o755)
        return folder

    def _run(self, root: Path, hook_id: str, tmp_path: Path) -> subprocess.CompletedProcess:
        folder = self._bin(tmp_path)
        env = _env(
            PATH=f"{folder.as_posix()}:/usr/bin:/bin",
            PYTHON=sys.executable,
            PYTHONPATH=str(ROOT / "src"),
            PYTHONIOENCODING="utf-8",
        )
        # The command is composed from the file, not from a guess. These
        # tests used to append `manuscript.md` themselves, which is how a
        # hook that ran a bare `citevouch check` - exit 2, no claim read -
        # stayed green: the test ran the command it wished the hook ran.
        hook = by_id()[hook_id]
        handed = " ".join(hook.get("args") or ())
        if hook["pass_filenames"]:
            handed = f"{handed} manuscript.md".strip()
        script = f"cd {root.as_posix()!r} && {hook['entry']} {handed}".rstrip()
        # Decoding is explicit: the child writes the manuscript's own quote back
        # in a failure message, and this machine's default code page cannot hold
        # it. A test that dies of an encoding error has proved nothing about the
        # hook.
        return subprocess.run(
            [self._bash(), "-c", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
            env=env,
        )

    def test_a_clean_project_passes_the_check_hook(self, tmp_path: Path) -> None:
        root = self._project(tmp_path)
        assert (
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "citevouch",
                    "scan",
                    "manuscript.md",
                    "--root",
                    ".",
                ],
                cwd=root,
                capture_output=True,
                env=_env(PYTHONPATH=str(ROOT / "src"), PYTHONIOENCODING="utf-8"),
            ).returncode
            == 0
        )
        done = self._run(root, "citevouch", tmp_path)
        assert done.returncode == 0, done.stdout + done.stderr

    def test_a_drifted_manuscript_fails_the_check_hook(self, tmp_path: Path) -> None:
        root = self._project(tmp_path)
        env = _env(PYTHONPATH=str(ROOT / "src"), PYTHONIOENCODING="utf-8")
        subprocess.run(
            [sys.executable, "-m", "citevouch", "scan", "manuscript.md"],
            cwd=root,
            capture_output=True,
            env=env,
        )
        # The source changes under the ledger: this is the case the hook is for.
        (root / "papers" / "a.txt").write_text("Something else entirely.\n", encoding="utf-8")
        done = self._run(root, "citevouch", tmp_path)
        assert done.returncode == 1, done.stdout + done.stderr

    def test_the_hook_command_can_actually_run(self) -> None:
        """A `check` with no argument is an argparse error, not a verdict.

        This is the defect that hid behind these tests: `pass_filenames:
        false` plus `entry: citevouch check` and no `args:` means
        pre-commit runs the command with no manuscript, and `check` exits 2
        without reading a claim. The suite stayed green because the helper
        added `manuscript.md` itself - it tested the command it wished the
        hook ran.
        """
        for hook in hooks():
            named = [arg for arg in hook.get("args") or [] if not arg.startswith("-")]
            assert named, (
                f"{hook['id']} names no manuscript and takes no filenames, so "
                "pre-commit runs it with no argument and it exits 2"
            )
