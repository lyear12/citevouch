"""An action that declares inputs it never forwards is a decoration.

The Marketplace entry is the only place people look for "a check I can add to
CI", so `action.yml` has to be real: every input has to reach the command line,
and the exit code has to survive to the step. A composite action is YAML plus
shell, which means nothing compiles it and no type checker sees it - the only
way to know the inputs are wired is to run the script body against a fake
`citevouch` and read what arrived.

These tests execute the action's shell with a stub on PATH. They do not run
GitHub's runner, so they prove the wiring and nothing about the environment.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ACTION = ROOT / "action.yml"


def _bash() -> str:
    """Find a bash that actually runs.

    On Windows, `bash` on PATH is `C:\\Windows\\System32\\bash.exe`, the WSL
    stub, which answers "no installed distributions" with exit 1 and UTF-16
    output. Git bash is the one that works, and it is not always first.
    """
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
        if probe.returncode == 0 and probe.stdout.strip() == "ok":
            return candidate
    pytest.fail("no working bash on this machine; the action cannot be tested")


def read_action() -> dict:
    """The action file, with the shell steps kept as text."""
    import yaml

    return yaml.safe_load(ACTION.read_text(encoding="utf-8"))


def run_step(tmp_path: Path, step_index: int, *, env_extra: dict[str, str]) -> dict:
    """Run one composite step's `run:` body with a stub citevouch on PATH."""
    action = read_action()
    step = action["runs"]["steps"][step_index]
    script = tmp_path / f"step-{step_index}.sh"
    script.write_text(step["run"], encoding="utf-8", newline="\n")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    # A stub that records its arguments and returns a chosen code, so the test
    # can assert what the action forwarded rather than what the tool decided.
    stub = bin_dir / "citevouch"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        'printf "%s\\n" "$@" > "$CITEVOUCH_ARGS"\n'
        'printf "%s" "${CITEVOUCH_STDOUT:-}"\n'
        'exit "${CITEVOUCH_EXIT:-0}"\n',
        encoding="utf-8",
        newline="\n",
    )
    stub.chmod(0o755)
    python_stub = bin_dir / "python"
    python_stub.write_text(
        '#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "$CITEVOUCH_PYTHON_ARGS"\nexit 0\n',
        encoding="utf-8",
        newline="\n",
    )
    python_stub.chmod(0o755)

    args_file = tmp_path / "args.txt"
    python_args_file = tmp_path / "python-args.txt"
    output_file = tmp_path / "gh-output.txt"
    output_file.write_text("", encoding="utf-8")

    env = {
        "PATH": f"{bin_dir}{os.pathsep}{_bin_dir_of(_bash())}{os.pathsep}{os.environ['PATH']}",
        "CITEVOUCH_ARGS": str(args_file),
        "CITEVOUCH_PYTHON_ARGS": str(python_args_file),
        "GITHUB_OUTPUT": str(output_file),
        "GITHUB_WORKSPACE": str(tmp_path),
        "RUNNER_TEMP": str(tmp_path / "temp"),
        # The paths the action passes are relative to the workspace, and the
        # script starts with `cd "${GITHUB_WORKSPACE}"`, so the ledger and the
        # manuscript have to exist there for a real run. The stub does not look,
        # but `--use-recorded` with a missing ledger is exactly the case the
        # action has to refuse, so the fixtures are created anyway.
        "HOME": str(tmp_path),
        **(env_extra or {}),
    }
    (tmp_path / "temp").mkdir(exist_ok=True)
    (tmp_path / "manuscript.md").write_text("# t\n", encoding="utf-8")
    (tmp_path / "citevouch.lock.json").write_text("{}", encoding="utf-8")

    completed = subprocess.run(
        [_bash(), str(script)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=str(tmp_path),
    )
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        # The stub writes one argument per line, so a path containing a space
        # stays one argument here. Splitting on whitespace instead would turn
        # "my paper/main draft.md" into three and hide the very bug this file
        # exists to catch.
        "args": _lines(args_file),
        "python_args": _lines(python_args_file),
        "outputs": output_file.read_text(encoding="utf-8"),
    }


def _lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def _bin_dir_of(bash: str) -> str:
    """The directory of the shell's own tools, for sed/grep and friends."""
    return str(Path(bash).parent)


class TestTheFileItself:
    def test_it_parses_and_says_what_it_is(self):
        action = read_action()
        assert action["name"] == "citevouch"
        assert action["runs"]["using"] == "composite"
        assert action["description"].strip()

    def test_the_inputs_are_the_ones_the_command_takes(self):
        inputs = read_action()["inputs"]
        assert "manuscript" in inputs
        assert inputs["manuscript"]["required"] is True
        for name in ("root", "ledger", "fail-on", "format"):
            assert name in inputs, f"the action cannot express --{name}"
            assert inputs[name]["default"].strip()

    def test_the_manuscript_input_is_required_rather_than_guessed(self):
        # A default of "manuscript.md" would silently check whichever file
        # happens to have that name; the whole point of the gate is that the
        # document is named.
        assert read_action()["inputs"]["manuscript"].get("required") is True
        assert "default" not in read_action()["inputs"]["manuscript"]

    def test_the_default_fail_on_is_the_cli_default(self):
        assert read_action()["inputs"]["fail-on"]["default"] == "high"


class TestTheInstallStep:
    def test_it_pins_the_installed_ref_to_the_action_ref(self, tmp_path: Path):
        result = run_step(
            tmp_path,
            0,
            env_extra={"ACTION_REF": "v0.11.0", "ACTION_REPO": "lyear12/citevouch"},
        )
        assert result["returncode"] == 0, result["stderr"]
        installed = " ".join(result["python_args"])
        assert "v0.11.0" in installed, installed
        assert "lyear12/citevouch" in installed, installed

    def test_it_falls_back_to_main_only_when_no_ref_is_given(self, tmp_path: Path):
        result = run_step(tmp_path, 0, env_extra={"ACTION_REPO": "lyear12/citevouch"})
        assert result["returncode"] == 0, result["stderr"]
        assert "main" in " ".join(result["python_args"])


class TestTheRunStep:
    def test_every_input_reaches_the_command_line(self, tmp_path: Path):
        result = run_step(
            tmp_path,
            1,
            env_extra={
                "IN_MANUSCRIPT": "paper/main.md",
                "IN_ROOT": "paper",
                "IN_LEDGER": "locks/citevouch.lock.json",
                "IN_FAIL_ON": "medium",
                "IN_FORMAT": "markdown",
            },
        )
        assert result["returncode"] == 0, result["stderr"]
        args = result["args"]
        assert args[0] == "check"
        assert "paper/main.md" in args
        assert "--root" in args and "paper" in args
        assert "--ledger" in args and "locks/citevouch.lock.json" in args
        assert "--fail-on" in args and "medium" in args
        assert "--format" in args and "markdown" in args
        # The recorded ledger is what a gate watches: a gate that re-derives
        # the ledger on every run would pass by rewriting its own baseline.
        assert "--use-recorded" in args

    def test_a_path_with_a_space_survives(self, tmp_path: Path):
        result = run_step(
            tmp_path,
            1,
            env_extra={
                "IN_MANUSCRIPT": "my paper/main draft.md",
                "IN_ROOT": "my paper",
                "IN_LEDGER": "citevouch.lock.json",
                "IN_FAIL_ON": "high",
                "IN_FORMAT": "text",
            },
        )
        assert result["returncode"] == 0, result["stderr"]
        assert "my paper/main draft.md" in result["args"]
        assert "my paper" in result["args"]

    @pytest.mark.parametrize("code", [0, 1])
    def test_a_verdict_is_passed_through_unchanged(self, tmp_path: Path, code: int):
        result = run_step(
            tmp_path,
            1,
            env_extra={
                "IN_MANUSCRIPT": "manuscript.md",
                "IN_ROOT": ".",
                "IN_LEDGER": "citevouch.lock.json",
                "IN_FAIL_ON": "high",
                "IN_FORMAT": "text",
                "CITEVOUCH_EXIT": str(code),
            },
        )
        assert result["returncode"] == code
        assert f"exit-code={code}" in result["outputs"]

    def test_a_usage_error_is_not_reported_as_a_green_run(self, tmp_path: Path):
        result = run_step(
            tmp_path,
            1,
            env_extra={
                "IN_MANUSCRIPT": "manuscript.md",
                "IN_ROOT": ".",
                "IN_LEDGER": "citevouch.lock.json",
                "IN_FAIL_ON": "high",
                "IN_FORMAT": "text",
                "CITEVOUCH_EXIT": "2",
            },
        )
        # 2 means "could not run"; letting it through as a finding would make a
        # missing ledger look like a clean manuscript.
        assert result["returncode"] == 2
        assert "could not run" in result["stdout"] + result["stderr"]

    def test_sarif_is_written_and_announced(self, tmp_path: Path):
        result = run_step(
            tmp_path,
            1,
            env_extra={
                "IN_MANUSCRIPT": "manuscript.md",
                "IN_ROOT": ".",
                "IN_LEDGER": "citevouch.lock.json",
                "IN_FAIL_ON": "high",
                "IN_FORMAT": "sarif",
                "CITEVOUCH_STDOUT": '{"version": "2.1.0"}',
            },
        )
        assert result["returncode"] == 0, result["stderr"]
        written_line = next(
            line for line in result["outputs"].splitlines() if line.startswith("sarif=")
        )
        # Compared as paths, not as strings: RUNNER_TEMP arrives with the
        # runner's own separators, and the script appends "/citevouch.sarif" to
        # it, so the same file has two spellings on Windows.
        reported = Path(written_line.split("=", 1)[1])
        assert reported == tmp_path / "temp" / "citevouch.sarif"
        assert reported.read_text(encoding="utf-8").strip() == '{"version": "2.1.0"}'


class TestTheRepositoryWiring:
    def test_the_readme_shows_the_action_rather_than_a_pip_install(self):
        for name in ("README.md", "README.zh-CN.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            assert "lyear12/citevouch@" in text
            # The three-line pip form is still documented as the no-action path;
            # what must not happen is the action existing and the docs not
            # mentioning it, which is how a shipped feature stays invisible.
            assert re.search(r"uses:\s*lyear12/citevouch@", text), (
                f"{name} never shows the action"
            )

    def test_the_action_names_no_input_the_command_cannot_honour(self):
        action = read_action()
        declared = set(action["inputs"])
        run_body = action["runs"]["steps"][1]["run"]
        forwarded = set(re.findall(r"IN_([A-Z_]+)", run_body))
        expected = {name.upper().replace("-", "_") for name in declared}
        # `python-version` is consumed by the install step, not the run step.
        expected.discard("PYTHON_VERSION")
        assert forwarded == expected, f"declared but not forwarded: {expected - forwarded}"
