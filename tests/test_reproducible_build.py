"""The release artefacts have to be reproducible, or the digest guard is a wall.

`release.yml` refuses to replace a published asset whose digest differs from
the one the run built (tests/test_release_recovery.py). That guard is only
workable if rebuilding one tree yields one set of bytes - otherwise a resumed
release can never match what was already published, and the honest refusal
turns into a permanent block.

Measured before the fix: two `python -m build` runs two seconds apart produced
different wheel and sdist digests while every extracted member was byte-equal.
The wheel differed because zip members carry a mod time; the sdist additionally
because `tarfile.open(..., "w:gz")` writes the current time into the gzip
header.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
TOOL = REPO / "tools" / "normalise_artifacts.py"
sys.path.insert(0, str(REPO / "tools"))

import normalise_artifacts  # noqa: E402  (path set up above)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _build(outdir: Path) -> list[Path]:
    """Build a wheel and an sdist into `outdir`, twice, and return the files."""
    outdir.mkdir(parents=True, exist_ok=True)
    done = subprocess.run(
        [sys.executable, "-m", "build", "--no-isolation", "--outdir", str(outdir), str(REPO)],
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    if done.returncode != 0:
        pytest.fail(
            f"the build failed, so reproducibility was never measured: {done.stderr[-2000:]}"
        )
    return sorted(p for p in outdir.iterdir() if p.is_file())


class TestOneTreeGivesOneSetOfBytes:
    """The property the release guard depends on."""

    def test_two_builds_of_one_tree_have_the_same_digest(self, tmp_path: Path) -> None:
        first = tmp_path / "first"
        second = tmp_path / "second"
        artefacts_one = _build(first)
        artefacts_two = _build(second)
        assert [p.name for p in artefacts_one] == [p.name for p in artefacts_two], (
            "the two builds produced different file names, so they cannot be compared"
        )

        epoch = normalise_artifacts.resolve_epoch(None)
        for directory in (first, second):
            normalise_artifacts.normalise(directory, epoch)

        digests = {p.name: _digest(p) for p in artefacts_one}
        again = {p.name: _digest(p) for p in artefacts_two}
        assert digests == again, (
            "the same tree built twice gave different bytes, so the release guard "
            f"could never accept a rebuilt artefact: {digests} vs {again}"
        )

    def test_normalising_does_not_change_the_contents(self, tmp_path: Path) -> None:
        """Reproducibility must not be bought by dropping or rewriting payloads."""
        import tarfile
        import zipfile

        built = _build(tmp_path / "dist")
        epoch = normalise_artifacts.resolve_epoch(None)
        before: dict[str, dict[str, str]] = {}
        for path in built:
            if path.suffix == ".whl":
                with zipfile.ZipFile(path) as archive:
                    before[path.name] = {
                        name: hashlib.sha256(archive.read(name)).hexdigest()
                        for name in archive.namelist()
                    }
            elif path.name.endswith(".tar.gz"):
                with tarfile.open(path) as archive:
                    before[path.name] = {
                        member.name: hashlib.sha256(
                            archive.extractfile(member).read()
                        ).hexdigest()
                        for member in archive.getmembers()
                        if member.isfile()
                    }

        normalise_artifacts.normalise(tmp_path / "dist", epoch)

        for path in built:
            if path.suffix == ".whl":
                with zipfile.ZipFile(path) as archive:
                    after = {
                        name: hashlib.sha256(archive.read(name)).hexdigest()
                        for name in archive.namelist()
                    }
            else:
                with tarfile.open(path) as archive:
                    after = {
                        member.name: hashlib.sha256(
                            archive.extractfile(member).read()
                        ).hexdigest()
                        for member in archive.getmembers()
                        if member.isfile()
                    }
            assert after == before[path.name], (
                f"{path.name} changed content while being normalised"
            )


class TestTheClockIsActuallyGone:
    """Two builds a second apart can agree by luck; the header cannot.

    The sdist's gzip header is the one part of the archive that is *not* a
    member, so normalising members alone leaves the current time in it - and a
    test that only compares two builds in the same second cannot see that.
    """

    def test_the_sdist_header_carries_the_epoch_not_the_clock(self, tmp_path: Path) -> None:
        import gzip

        built = _build(tmp_path / "dist")
        sdist = next(p for p in built if p.name.endswith(".tar.gz"))
        epoch = normalise_artifacts.resolve_epoch(None)
        normalise_artifacts.normalise(tmp_path / "dist", epoch)
        with gzip.open(sdist, "rb") as handle:
            handle.read(1)
            # `GzipFile.mtime` is populated from the header on read.
            header_mtime = handle.mtime
        assert header_mtime == epoch, (
            f"the gzip header says {header_mtime}, not the epoch {epoch}: the clock is "
            "still in the archive, so two builds can differ without any member changing"
        )

    def test_a_different_epoch_gives_a_different_sdist(self, tmp_path: Path) -> None:
        """The epoch is the only knob; if it does not reach the bytes, it does nothing."""
        built = _build(tmp_path / "dist")
        sdist = next(p for p in built if p.name.endswith(".tar.gz"))
        normalise_artifacts.normalise(tmp_path / "dist", 1_000_000_000)
        first = _digest(sdist)
        normalise_artifacts.normalise(tmp_path / "dist", 1_000_000_001)
        assert _digest(sdist) != first, (
            "moving the epoch one second changed nothing, so the timestamp is not in the bytes"
        )


class TestTheEpochComesFromSomewhereStable:
    """A normaliser that stamps "now" reproduces nothing.

    These tests stub the clock sources rather than asking the checkout: the
    first version asserted that `resolve_epoch(None)` found a commit time, and
    that is true in a clone and false in an unpacked sdist - where the suite
    also runs, and where it went red on every job of every platform at once.
    A test about the order of two sources has no business depending on a third
    thing (whether this directory has a `.git`) that neither source is.
    """

    def test_the_repository_time_is_used_when_there_is_one(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
        monkeypatch.setattr(normalise_artifacts, "epoch_from_git", lambda: 1_600_000_000)
        assert normalise_artifacts.resolve_epoch(None) == 1_600_000_000

    def test_a_checkout_that_cannot_ask_git_gets_a_fixed_number(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The fallback must be a constant, not the clock.

        Falling back to `time.time()` would reproduce exactly one build, which
        is the defect this whole module exists to remove.
        """
        monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
        monkeypatch.setattr(normalise_artifacts, "epoch_from_git", lambda: None)
        assert normalise_artifacts.resolve_epoch(None) == normalise_artifacts.FALLBACK_EPOCH
        assert normalise_artifacts.FALLBACK_EPOCH == 0, (
            "the sentinel changed; every recorded digest was produced with 0"
        )

    def test_the_environment_wins_over_the_repository(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SOURCE_DATE_EPOCH", "1234567890")
        monkeypatch.setattr(normalise_artifacts, "epoch_from_git", lambda: 1_600_000_000)
        assert normalise_artifacts.resolve_epoch(None) == 1234567890

    def test_an_explicit_epoch_wins_over_everything(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SOURCE_DATE_EPOCH", "1234567890")
        assert normalise_artifacts.resolve_epoch(42) == 42

    def test_a_bad_environment_value_is_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SOURCE_DATE_EPOCH", "not a number")
        monkeypatch.setattr(normalise_artifacts, "epoch_from_git", lambda: 1_600_000_000)
        assert normalise_artifacts.resolve_epoch(None) == 1_600_000_000, (
            "an unparseable SOURCE_DATE_EPOCH was taken over the repository, "
            "which hides the mistake instead of reporting it"
        )


class TestTheReleaseWorkflowUsesIt:
    """A tool nothing calls normalises nothing."""

    def test_the_build_step_normalises_before_publishing(self) -> None:
        import yaml

        workflow = yaml.safe_load(
            (REPO / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        )
        jobs = workflow["jobs"]
        release = jobs["release"]
        names = [step.get("name", "") for step in release["steps"]]
        build = names.index("Build")
        body = release["steps"][build]["run"]
        assert "normalise_artifacts.py" in body, (
            "the build step does not normalise, so the digests it publishes are the clock's"
        )
        # It has to be part of the same step: anything that runs later could
        # read the artefacts first, and the smoke test installs the wheel.
        assert names.index("Build") < names.index(
            "Smoke-test the built wheel in a clean directory"
        ), "normalising after the smoke test would normalise a wheel nobody installs"

    def test_the_tool_is_shipped_in_the_sdist(self, tmp_path: Path) -> None:
        """`tools/` scripts are only useful where the tests can reach them."""
        assert (REPO / "tools" / "normalise_artifacts.py").is_file()
        manifest = (REPO / "MANIFEST.in").read_text(encoding="utf-8")
        assert "tools" in manifest, (
            "the sdist does not carry tools/, so the packaged build instructions "
            "would name a file the sdist does not have"
        )
