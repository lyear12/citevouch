"""The seventh review's findings, pinned."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from citevouch import sources

REPO = Path(__file__).resolve().parent.parent


def _run(cmd: list[str], cwd: Path, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False, **kwargs)


def _repo_with_tag(tmp_path: Path) -> Path:
    """A throwaway repository with one commit, so git can be asked real questions."""
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]
    _run(["git", "init", "-q", "-b", "main"], tmp_path)
    (tmp_path / "a.txt").write_text("one\n", encoding="utf-8")
    _run([*git, "add", "."], tmp_path)
    _run([*git, "commit", "-q", "-m", "the first thing"], tmp_path)
    return tmp_path


# --- NEW-1: the hand-release path -----------------------------------------


def test_the_release_notes_script_survives_a_tag_that_does_not_exist(tmp_path: Path):
    """The documented way to release by hand is a workflow_dispatch for a
    version whose tag is not created yet. `git describe` has nothing to
    describe there, and under `set -e` that turned a missing range into a dead
    release - after the build and the smoke test had already run."""
    repo = _repo_with_tag(tmp_path)
    script = REPO / "tools" / "release_notes.sh"
    proc = _run(
        ["bash", "--noprofile", "--norc", "-eo", "pipefail", str(script), "v9.9.9"],
        repo,
    )
    assert proc.returncode == 0, proc.stderr
    assert "the first thing" in proc.stdout


def test_the_release_notes_script_reads_a_real_range(tmp_path: Path):
    repo = _repo_with_tag(tmp_path)
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]
    _run([*git, "tag", "v0.1.0"], repo)
    (repo / "b.txt").write_text("two\n", encoding="utf-8")
    _run([*git, "add", "."], repo)
    _run([*git, "commit", "-q", "-m", "the second thing"], repo)
    _run([*git, "tag", "v0.2.0"], repo)

    script = REPO / "tools" / "release_notes.sh"
    proc = _run(
        ["bash", "--noprofile", "--norc", "-eo", "pipefail", str(script), "v0.2.0"], repo
    )
    assert proc.returncode == 0, proc.stderr
    assert "the second thing" in proc.stdout
    assert "the first thing" not in proc.stdout, "notes described more than this release"


def test_the_workflow_calls_the_script_rather_than_carrying_a_copy():
    workflow = (REPO / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "tools/release_notes.sh" in workflow
    assert "git describe --tags --abbrev=0" not in workflow, (
        "a shell block in the YAML cannot be run by a test; the logic belongs in tools/"
    )


def test_the_script_is_invoked_through_an_interpreter():
    """The index cannot carry the executable bit for this file, and a checkout
    on a Linux runner therefore lands at 644. Calling the path directly works
    on every machine where the mode happens to be right and fails on the one
    machine that matters, which is the runner."""
    workflow = (REPO / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert 'notes=$(bash tools/release_notes.sh "$tag")' in workflow
    assert "notes=$(tools/release_notes.sh" not in workflow, (
        "invoke it as `bash tools/release_notes.sh`; a bare path needs a mode bit"
    )


# --- NEW-2: keys outside the mini-TOML subset -----------------------------


@pytest.fixture()
def no_tomllib(monkeypatch):
    """Make the interpreter look like 3.10 to anything importing tomllib."""
    import builtins

    real = builtins.__import__

    def fake(name, *args, **kwargs):
        if name == "tomllib":
            raise ImportError("simulated 3.10")
        return real(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake)
    monkeypatch.delitem(__import__("sys").modules, "tomllib", raising=False)


def test_a_quoted_key_does_not_take_the_manifest_with_it(no_tomllib):
    text = '[sources]\n"quoted" = "papers/x.pdf"\nother = "papers/y.pdf"\n'
    assert sources._mini_toml(text) == {"sources": {"other": "papers/y.pdf"}}


def test_a_multiline_value_does_not_return_a_path_wearing_its_quotes():
    """Handing back '""papers/x.pdf""' is worse than dropping the key: nothing
    raises, and the file is never found."""
    assert sources._toml_string_or_none('"""papers/x.pdf"""') is None
    assert sources._toml_string_or_none("'''papers/x.pdf'''") is None


def test_the_two_parsers_agree_on_the_manifest_shape(tmp_path: Path):
    """The whole point of the subset is that 3.10 and 3.11 bind the same
    project. Values outside the subset may differ; nothing else may."""
    try:
        import tomllib
    except ImportError:
        pytest.skip("no tomllib on this interpreter to compare against")

    text = '[sources]\none = "papers/1.txt"\ntwo = "papers/2.txt"\n# a comment\n'
    assert sources._mini_toml(text) == tomllib.loads(text)


# --- NEW-3: the cache records the reader that ran -------------------------


def test_the_cache_records_the_extractor_that_actually_produced_the_text(
    tmp_path: Path, monkeypatch
):
    """pypdf can be installed and still fail on a given file; pdftotext then
    does the work. The entry has to say so, or upgrading poppler would leave
    text extracted by the old binary trusted forever. The rename is forced here
    so the assertion is about which reader was recorded, not about whether this
    machine can read the fixture."""
    pdf = tmp_path / "p.pdf"
    pdf.write_bytes(b"%PDF-1.4 placeholder")
    monkeypatch.setattr(
        sources, "_pypdf_pages", lambda _path: (["the page text"], "pypdf-0.0.test")
    )
    _pages, problem = sources.extract_pages(pdf, tmp_path, use_cache=True)
    assert problem is None, problem

    cached = list((tmp_path / ".citevouch" / "cache").glob("*.json"))
    assert cached, "a successful extraction must be cached"
    blob = json.loads(cached[0].read_text(encoding="utf-8"))
    assert blob["extractor"] == "pypdf-0.0.test", (
        "the cache must name the reader that ran, not the one the suffix predicted"
    )


def test_a_cache_entry_naming_an_impossible_reader_is_a_miss(tmp_path: Path):
    path = tmp_path / "a.txt"
    path.write_text("some words\n", encoding="utf-8")
    pages, problem = sources.extract_pages(path, tmp_path)
    assert problem is None and pages
    cached = list((tmp_path / ".citevouch" / "cache").glob("*.json"))
    blob = json.loads(cached[0].read_text(encoding="utf-8"))
    blob["extractor"] = "pypdf-9.9.9"
    cached[0].write_text(json.dumps(blob), encoding="utf-8")

    again, _ = sources.extract_pages(path, tmp_path)
    assert again is not None
    rewritten = json.loads(cached[0].read_text(encoding="utf-8"))
    assert rewritten["extractor"] == "plain", "a stale reader name must re-extract"


# --- NEW-4: the changelog's own tail ----------------------------------------


def _load_next_version():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "next_version", REPO / "tools" / "next_version.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rebuilding_the_links_keeps_what_follows_them():
    """The definitions block sits at the foot of the file today, so anything a
    future release adds below it would be deleted by an automatic release
    commit - silently, and nobody reads those diffs."""
    nv = _load_next_version()
    text = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    tail = "\n## Licensing notes\n\nKeep me: the papers are CC-BY.\n"
    out = nv.update_links(text + tail, "9.9.9")
    assert "Keep me" in out
    assert "[9.9.9]: " not in out  # headings drive the block, not the new version
    assert "9.9.9...HEAD" in out


# --- NEW-5: the nightly's version pick ------------------------------------


def _nightly_version_pipeline() -> str:
    """The shell pipeline nightly.yml uses to pick a version, read from the file.

    Asserting on a copy would only test the copy. This finds the `tag=$(gh
    release list ...)` assignment, joins its continuation lines, and returns
    the pipeline that follows the command.
    """
    workflow = (REPO / ".github" / "workflows" / "nightly.yml").read_text(encoding="utf-8")
    lines = workflow.splitlines()
    for index, line in enumerate(lines):
        if "gh release list" not in line:
            continue
        pieces: list[str] = []
        cursor = index
        while cursor < len(lines):
            piece = lines[cursor].strip()
            pieces.append(piece)
            if piece.endswith(")"):
                break
            cursor += 1
        joined = " ".join(pieces)
        # Shell line continuations are not part of the pipeline the test feeds.
        joined = joined.replace(chr(92) + " ", " ")
        _before, _sep, after = joined.partition("gh release list")
        _head, sep, pipeline = after.partition(" | ")
        assert sep, f"no pipeline after the gh call: {after!r}"
        return pipeline.rstrip().rstrip(")")
    raise AssertionError("could not find the nightly version pick in nightly.yml")


def test_a_prerelease_never_wins_the_nightly():
    """`-k3,3n` reads "0-rc1" as 0, the keys tie, and the whole-line comparison
    then puts "1.0.0-rc1" after "1.0.0" because "-" sorts above nothing. The
    nightly would then test a version nobody installs."""
    pipeline = _nightly_version_pipeline()
    for tags in ("v1.0.0-rc1\nv0.8.0\n", "v0.8.0\nv1.0.0-rc1\n"):
        proc = subprocess.run(
            ["bash", "-c", f"printf '{tags}' | {pipeline}"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.stdout.strip() == "0.8.0", f"{tags!r} -> {proc.stdout!r}"


# --- NEW-6: the dead filter -------------------------------------------------


def test_the_offline_step_has_no_filter_that_matches_nothing():
    """The comment above the step may quote the old expression; the command
    must not contain it. There is no `network` marker, so `-k "not network"`
    selected every test and read like it was excluding something."""
    workflow = (REPO / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")
    commands = [
        line.split("run:", 1)[1].strip()
        for line in workflow.splitlines()
        if line.strip().startswith("run:")
    ]
    assert commands, "no run steps found"
    for command in commands:
        assert '"-k' not in command and "/-k" not in command, command
        assert "-k " not in command, f"a marker filter with no markers: {command}"
    assert "HTTPS_PROXY" in workflow, "the step must still run behind a dead proxy"
