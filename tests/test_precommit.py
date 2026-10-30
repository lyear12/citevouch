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

import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / ".pre-commit-hooks.yaml"


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
        # The command takes a manuscript and a ledger, not a list of changed
        # files. With filenames appended, `citevouch check a.md b.md` is a usage
        # error - exit 2 - and the author is told the hook is broken.
        for hook in hooks():
            assert hook.get("pass_filenames") is False, hook["id"]


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

    def _run(
        self, root: Path, entry: str, tmp_path: Path, *, extra: str = "manuscript.md"
    ) -> subprocess.CompletedProcess:
        folder = self._bin(tmp_path)
        env = {
            "PATH": f"{folder.as_posix()}:/usr/bin:/bin",
            "PYTHON": __import__("sys").executable,
            "PYTHONPATH": str(ROOT / "src"),
            "PYTHONIOENCODING": "utf-8",
        }
        script = f"cd {root.as_posix()!r} && {entry} {extra}"
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
                    __import__("sys").executable,
                    "-m",
                    "citevouch",
                    "scan",
                    "manuscript.md",
                    "--root",
                    ".",
                ],
                cwd=root,
                capture_output=True,
                env={"PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8", "PATH": ""},
            ).returncode
            == 0
        )
        done = self._run(root, by_id()["citevouch"]["entry"], tmp_path)
        assert done.returncode == 0, done.stdout + done.stderr

    def test_a_drifted_manuscript_fails_the_check_hook(self, tmp_path: Path) -> None:
        root = self._project(tmp_path)
        env = {"PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8", "PATH": ""}
        subprocess.run(
            [__import__("sys").executable, "-m", "citevouch", "scan", "manuscript.md"],
            cwd=root,
            capture_output=True,
            env=env,
        )
        # The source changes under the ledger: this is the case the hook is for.
        (root / "papers" / "a.txt").write_text("Something else entirely.\n", encoding="utf-8")
        done = self._run(root, by_id()["citevouch"]["entry"], tmp_path)
        assert done.returncode == 1, done.stdout + done.stderr
