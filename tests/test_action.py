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
import sys
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


def step_named(name: str) -> dict:
    """One composite step, found by name.

    By name, not by index: a step inserted above the one a test meant would
    otherwise move every test onto its neighbour and quietly compare the wrong
    script. That is not hypothetical - adding `Set up Python` above the install
    step does exactly that to the index-based version of this helper.
    """
    steps = read_action()["runs"]["steps"]
    for step in steps:
        if step.get("name") == name:
            return step
    names = [step.get("name") for step in steps]
    raise AssertionError(f"no step named {name!r}; the steps are {names}")


def run_step(
    tmp_path: Path, name: str, *, env_extra: dict[str, str], real_cli: bool = False
) -> dict:
    """Run one composite step's `run:` body with a stub citevouch on PATH.

    With ``real_cli`` the stub is replaced by a wrapper around this working
    tree's own CLI. The argv recorder proves the wiring; the real CLI proves
    the wiring produces a command the tool actually accepts, which is a
    different claim and the one that catches a path convention mismatch.
    """
    step = step_named(name)
    if "run" not in step:
        raise AssertionError(f"step {name!r} has no shell body to run: {sorted(step)}")
    script = tmp_path / f"step-{name.replace(' ', '-')}.sh"
    script.write_text(step["run"], encoding="utf-8", newline="\n")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    # A stub that records its arguments and returns a chosen code, so the test
    # can assert what the action forwarded rather than what the tool decided.
    stub = bin_dir / "citevouch"
    if real_cli:
        # Same argv recording, then hand off to this checkout's CLI. The
        # interpreter is spelled with forward slashes because the body runs
        # under git bash on Windows, where a POSIX path is what works.
        stub.write_text(
            "#!/usr/bin/env bash\n"
            'printf "%s\n" "$@" > "$CITEVOUCH_ARGS"\n'
            f'exec "{Path(sys.executable).as_posix()}" -m citevouch "$@"\n',
            encoding="utf-8",
            newline="\n",
        )
    else:
        stub.write_text(
            "#!/usr/bin/env bash\n"
            'printf "%s\n" "$@" > "$CITEVOUCH_ARGS"\n'
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

    # Starting from the real environment, not from a literal: the body runs
    # `python`, and on Windows an interpreter launched with a stripped
    # environment dies in `_Py_HashRandomization_Init` because SYSTEMROOT is
    # gone. That is the failure `tests/test_child_env.py` exists to catch, and
    # it is not worth reintroducing here to keep a dict tidy.
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{_bin_dir_of(_bash())}{os.pathsep}{os.environ['PATH']}",
        "CITEVOUCH_ARGS": str(args_file),
        "CITEVOUCH_PYTHON_ARGS": str(python_args_file),
        "GITHUB_OUTPUT": str(output_file),
        "GITHUB_WORKSPACE": str(tmp_path),
        "RUNNER_TEMP": str(tmp_path / "temp"),
        "HOME": str(tmp_path),
        **({"PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"} if real_cli else {}),
        **(env_extra or {}),
    }
    (tmp_path / "temp").mkdir(exist_ok=True)
    # Placeholders only: a test that brings its own real ledger is testing
    # the path resolution, and an unconditional `{}` here would quietly
    # replace it with a file the CLI refuses.
    if not (tmp_path / "manuscript.md").exists():
        (tmp_path / "manuscript.md").write_text("# t\n", encoding="utf-8")
    if not (tmp_path / "citevouch.lock.json").exists():
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
            "Install citevouch",
            env_extra={"ACTION_REF": "v0.11.0", "ACTION_REPO": "lyear12/citevouch"},
        )
        assert result["returncode"] == 0, result["stderr"]
        installed = " ".join(result["python_args"])
        assert "v0.11.0" in installed, installed
        assert "lyear12/citevouch" in installed, installed

    def test_it_falls_back_to_main_only_when_no_ref_is_given(self, tmp_path: Path):
        result = run_step(
            tmp_path, "Install citevouch", env_extra={"ACTION_REPO": "lyear12/citevouch"}
        )
        assert result["returncode"] == 0, result["stderr"]
        assert "main" in " ".join(result["python_args"])


class TestTheRunStep:
    def test_every_input_reaches_the_command_line(self, tmp_path: Path):
        result = run_step(
            tmp_path,
            "Run the check",
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
        # The ledger is the one input the action resolves before passing it on:
        # the CLI reads a relative --ledger against --root, while the input is
        # documented as repository-relative. Sending it through as typed looks
        # right and finds the wrong file whenever root is not the repository
        # root, so the action makes it absolute against the workspace first.
        #
        # Asserted by shape rather than by `Path.is_absolute`, because git bash
        # reports the workspace as a POSIX path (`/tmp/...` or `/c/...`) and
        # Windows' `Path.is_absolute` does not recognise those.
        ledger = args[args.index("--ledger") + 1]
        tail = "locks/citevouch.lock.json"
        assert ledger.endswith(tail), ledger
        assert ledger != tail, f"passed through as typed instead of resolved: {ledger}"
        assert "--fail-on" in args and "medium" in args
        assert "--format" in args and "markdown" in args
        # The recorded ledger is what a gate watches: a gate that re-derives
        # the ledger on every run would pass by rewriting its own baseline.
        assert "--use-recorded" in args

    def test_a_path_with_a_space_survives(self, tmp_path: Path):
        result = run_step(
            tmp_path,
            "Run the check",
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

    def test_the_ledger_is_found_when_the_root_is_a_subdirectory(self, tmp_path: Path):
        """The case the pass-through could not survive.

        `root: paper` means the manuscript and its sources live in `paper/`,
        while the ledger is documented as repository-relative and usually sits
        at the top, because it is the one file a reviewer reads in the diff.
        The CLI would look for `paper/citevouch.lock.json` and report
        "no ledger at paper/citevouch.lock.json" about a file that is right
        there in the repository.
        """
        result = run_step(
            tmp_path,
            "Run the check",
            env_extra={
                "IN_MANUSCRIPT": "manuscript.md",
                "IN_ROOT": "paper",
                "IN_LEDGER": "citevouch.lock.json",
                "IN_FAIL_ON": "high",
                "IN_FORMAT": "text",
            },
        )
        assert result["returncode"] == 0, result["stderr"]
        args = result["args"]
        ledger = args[args.index("--ledger") + 1]
        # Not `paper/citevouch.lock.json`, and not the bare name either.
        assert ledger.endswith("/citevouch.lock.json"), ledger
        assert not ledger.endswith("/paper/citevouch.lock.json"), ledger
        assert ledger != "citevouch.lock.json", ledger

    def test_a_real_run_finds_the_ledger_of_a_subdirectory_project(self, tmp_path: Path):
        """The end-to-end case: the real CLI, the documented layout.

        `root: paper` with `paper/manuscript.md`, `paper/sources.toml` and a
        ledger at the top of the repository. The argv tests prove the
        action forwards what it resolved; this one proves the CLI accepts
        it, which is the claim that was wrong.
        """
        paper = tmp_path / "paper"
        paper.mkdir()
        (paper / "note.txt").write_text(
            "The corpus contains 154,391 utterances.\n", encoding="utf-8"
        )
        (paper / "sources.toml").write_text('[sources]\np = "note.txt"\n', encoding="utf-8")
        (paper / "manuscript.md").write_text(
            "# Paper\n\n"
            "```claim c1 source=p page=1\n"
            ">> The corpus contains 154,391 utterances.\n"
            "```\n",
            encoding="utf-8",
        )
        env = {"PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"}
        subprocess.run(
            [sys.executable, "-m", "citevouch", "scan", "manuscript.md", "--root", "."],
            cwd=str(paper),
            check=True,
            capture_output=True,
            env={**os.environ, **env},
        )
        (paper / "citevouch.lock.json").replace(tmp_path / "citevouch.lock.json")

        result = run_step(
            tmp_path,
            "Run the check",
            env_extra={
                # Both documented as repository-relative, which is the whole
                # point: the manuscript names its own path, the ledger names
                # its own path, and `root` is only where sources.toml lives.
                "IN_MANUSCRIPT": "paper/manuscript.md",
                "IN_ROOT": "paper",
                "IN_LEDGER": "citevouch.lock.json",
                "IN_FAIL_ON": "high",
                "IN_FORMAT": "text",
            },
            real_cli=True,
        )
        assert result["returncode"] == 0, (
            f"the documented layout failed: {result['stderr']}{result['stdout']}"
        )
        assert "1 verified" in result["stdout"], result["stdout"]

    def test_an_absolute_ledger_is_left_alone(self, tmp_path: Path):
        absolute = str(tmp_path / "elsewhere" / "kept.json")
        result = run_step(
            tmp_path,
            "Run the check",
            env_extra={
                "IN_MANUSCRIPT": "manuscript.md",
                "IN_ROOT": "paper",
                "IN_LEDGER": absolute,
                "IN_FAIL_ON": "high",
                "IN_FORMAT": "text",
            },
        )
        assert result["returncode"] == 0, result["stderr"]
        args = result["args"]
        assert args[args.index("--ledger") + 1] == absolute

    @pytest.mark.parametrize("code", [0, 1])
    def test_a_verdict_is_passed_through_unchanged(self, tmp_path: Path, code: int):
        result = run_step(
            tmp_path,
            "Run the check",
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
            "Run the check",
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
            "Run the check",
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
        run_body = step_named("Run the check")["run"]
        forwarded = set(re.findall(r"IN_([A-Z_]+)", run_body))
        expected = {name.upper().replace("-", "_") for name in declared}
        # `python-version` selects the interpreter, so it is spent by the
        # `Set up Python` step and must not reach the command line. That is a
        # claim about wiring, so it is checked rather than asserted in a
        # comment: the first version of this test simply discarded
        # PYTHON_VERSION here, and the input was in fact inert everywhere -
        # forwarded as an env var no shell body ever read.
        expected.discard("PYTHON_VERSION")
        assert forwarded == expected, f"declared but not forwarded: {expected - forwarded}"

    def test_every_input_is_read_by_some_step(self):
        # The defect this file exists to prevent, in its general form: an input
        # that is declared, wired into an env block, and never read. It reads
        # as a supported option and silently does nothing.
        action = read_action()
        steps = action["runs"]["steps"]
        used = "\n".join(step.get("run", "") for step in steps)
        used += "\n".join(
            f"{key}={value}"
            for step in steps
            for key, value in (step.get("with") or {}).items()
        )
        used += "\n".join(
            f"{key}={value}" for step in steps for key, value in (step.get("env") or {}).items()
        )
        for name in action["inputs"]:
            assert f"inputs.{name}" in used, (
                f"input {name!r} is declared but no step reads inputs.{name!r}; "
                "a caller setting it would see no effect"
            )

    def test_the_python_version_input_chooses_the_interpreter(self):
        # Not "the input is mentioned somewhere" - that passes on the old bug,
        # where it was passed as an unused env var. It has to reach a
        # setup-python step's `with:`, which is the only thing that can honour
        # it.
        setup = [
            step
            for step in read_action()["runs"]["steps"]
            if str(step.get("uses", "")).startswith("actions/setup-python")
        ]
        assert setup, "no setup-python step, so `python-version` cannot do anything"
        assert any(
            (step.get("with") or {}).get("python-version") == "${{ inputs.python-version }}"
            for step in setup
        ), "the setup-python step does not read the python-version input"

    def test_a_shell_step_is_never_handed_an_env_var_it_ignores(self):
        # Environment blocks are cheap to paste and invisible when dead. Every
        # `env:` key on a shell step must be read by that step's own body.
        #
        # The pattern allows a default (`${ACTION_REF:-main}`) and the bare
        # `$KEY` form; requiring the exact `${KEY}` spelling would fail on a
        # perfectly good read, and a guard whose idea of "used" is narrower
        # than the shell's is a guard that reports false alarms until somebody
        # deletes it.
        for step in read_action()["runs"]["steps"]:
            env = step.get("env") or {}
            body = step.get("run") or ""
            for key in env:
                pattern = re.compile(
                    r"\$\{" + re.escape(key) + r"[:}]|\$" + re.escape(key) + r"\b"
                )
                assert pattern.search(body), (
                    f"step {step.get('name')!r} declares env {key} and never reads it; "
                    f"its body is: {body[:200]!r}"
                )
